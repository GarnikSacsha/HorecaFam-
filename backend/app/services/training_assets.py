from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import Asset, AuditEvent, Location
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.private_storage import PrivateStorage

UPLOAD_EXPIRES_SECONDS = 15 * 60
ACCESS_EXPIRES_SECONDS = 5 * 60
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(frozen=True, slots=True)
class AssetUploadIntent:
    asset: Asset
    upload_url: str
    upload_fields: dict[str, str]
    expires_at: datetime


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _resource_not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _upload_invalid() -> APIError:
    return _error(422, "ASSET_UPLOAD_INVALID", "Файл не відповідає вимогам зображень.")


def _upload_expired() -> APIError:
    return _error(409, "ASSET_UPLOAD_EXPIRED", "Час завантаження файлу минув.")


def _asset_not_ready() -> APIError:
    return _error(409, "ASSET_NOT_READY", "Зображення ще не готове.")


def _validate_upload(
    *,
    file_name: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
) -> str:
    normalized_name = PurePosixPath(file_name.strip().replace("\\", "/")).name
    if (
        not normalized_name
        or len(normalized_name) > 255
        or mime_type not in ALLOWED_IMAGE_TYPES
        or not 1 <= size_bytes <= MAX_IMAGE_BYTES
        or len(sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in sha256)
    ):
        raise _upload_invalid()
    return normalized_name


def _audit(
    db: AsyncSession,
    *,
    asset: Asset,
    actor_user_id: UUID,
    request_id: UUID,
    action: str,
) -> None:
    db.add(
        AuditEvent(
            organization_id=asset.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action=action,
            target_type="asset",
            target_id=asset.id,
            old_values=None,
            new_values={"location_id": str(asset.location_id), "status": asset.status},
            request_id=request_id,
            outcome="success",
        )
    )


async def _upload_target(
    storage: PrivateStorage,
    *,
    asset: Asset,
    now: datetime,
) -> AssetUploadIntent:
    target = await storage.prepare_upload(
        object_key=asset.object_key,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        sha256=asset.sha256,
        expires_seconds=UPLOAD_EXPIRES_SECONDS,
    )
    return AssetUploadIntent(
        asset=asset,
        upload_url=target.url,
        upload_fields=target.fields,
        expires_at=now + timedelta(seconds=UPLOAD_EXPIRES_SECONDS),
    )


async def prepare_asset_upload(
    db: AsyncSession,
    *,
    storage: PrivateStorage,
    organization_id: UUID,
    location_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    idempotency_key: str,
    file_name: str,
    mime_type: str,
    size_bytes: int,
    sha256: str,
    now: datetime,
) -> AssetUploadIntent:
    normalized_name = _validate_upload(
        file_name=file_name,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256=sha256,
    )
    normalized_sha = sha256.lower()
    fingerprint = request_fingerprint(
        {
            "location_id": str(location_id),
            "file_name": normalized_name,
            "mime_type": mime_type,
            "size_bytes": size_bytes,
            "sha256": normalized_sha,
        }
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_asset_upload_prepare",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        if replay is not None:
            asset = await db.scalar(
                select(Asset).where(
                    Asset.id == replay.resource_id,
                    Asset.organization_id == organization_id,
                    Asset.location_id == location_id,
                )
            )
            if asset is None:
                raise RuntimeError("Idempotent Asset resource is unavailable")
            await db.commit()
            return await _upload_target(storage, asset=asset, now=now)

        location_exists = await db.scalar(
            select(Location.id).where(
                Location.id == location_id,
                Location.organization_id == organization_id,
            )
        )
        if location_exists is None:
            raise _resource_not_found()
        asset = Asset(
            id=uuid4(),
            organization_id=organization_id,
            location_id=location_id,
            status="pending_upload",
            object_key=f"training/{organization_id}/{location_id}/{uuid4().hex}",
            original_filename=normalized_name,
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=normalized_sha,
            created_by_user_id=actor_user_id,
            upload_expires_at=now + timedelta(seconds=UPLOAD_EXPIRES_SECONDS),
        )
        db.add(asset)
        await db.flush()
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_asset_upload_prepare",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="asset",
            resource_id=asset.id,
            response_status=201,
            now=now,
        )
        _audit(
            db,
            asset=asset,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_asset_upload_prepared",
        )
        intent = await _upload_target(storage, asset=asset, now=now)
        await db.commit()
        return intent
    except Exception:
        await db.rollback()
        raise


async def complete_asset_upload(
    db: AsyncSession,
    *,
    storage: PrivateStorage,
    organization_id: UUID,
    location_id: UUID,
    asset_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    idempotency_key: str,
    sha256: str,
    now: datetime,
) -> Asset:
    fingerprint = request_fingerprint({"asset_id": str(asset_id), "sha256": sha256.lower()})
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_asset_upload_complete",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        asset = await db.scalar(
            select(Asset)
            .where(
                Asset.id == asset_id,
                Asset.organization_id == organization_id,
                Asset.location_id == location_id,
            )
            .with_for_update()
        )
        if asset is None:
            raise _resource_not_found()
        if replay is not None and asset.status == "ready":
            await db.commit()
            return asset
        if asset.status != "pending_upload":
            raise _asset_not_ready()
        if asset.upload_expires_at <= now:
            asset.status = "failed"
            await db.commit()
            raise _upload_expired()
        if sha256.lower() != asset.sha256:
            asset.status = "failed"
            await db.commit()
            raise _upload_invalid()
        metadata = await storage.inspect_object(object_key=asset.object_key)
        if metadata is None or (
            metadata.mime_type != asset.mime_type
            or metadata.size_bytes != asset.size_bytes
            or metadata.sha256.lower() != asset.sha256
        ):
            asset.status = "failed"
            await db.commit()
            raise _upload_invalid()
        asset.status = "ready"
        asset.ready_at = now
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_asset_upload_complete",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="asset",
            resource_id=asset.id,
            response_status=200,
            now=now,
        )
        _audit(
            db,
            asset=asset,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_asset_upload_completed",
        )
        await db.commit()
        return asset
    except Exception:
        await db.rollback()
        raise


async def get_admin_asset_access(
    db: AsyncSession,
    *,
    storage: PrivateStorage,
    organization_id: UUID,
    location_id: UUID,
    asset_id: UUID,
) -> str:
    asset = await db.scalar(
        select(Asset).where(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
            Asset.location_id == location_id,
            Asset.status == "ready",
        )
    )
    if asset is None:
        raise _resource_not_found()
    return await storage.create_download_url(
        object_key=asset.object_key,
        expires_seconds=ACCESS_EXPIRES_SECONDS,
    )
