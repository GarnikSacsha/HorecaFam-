from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import Asset, AuditEvent
from app.services.private_storage import ObjectMetadata, UploadTarget
from app.services.training_assets import (
    archive_unlinked_asset,
    complete_asset_upload,
    get_admin_asset_access,
    prepare_asset_upload,
)
from tests.factories.identity import make_location, make_organization, make_user


@dataclass
class FakePrivateStorage:
    metadata: ObjectMetadata | None = None

    async def finalize_upload(
        self, *, source_key: str, target_key: str, mime_type: str, size_bytes: int, sha256: str
    ) -> bool:
        return self.metadata == ObjectMetadata(
            mime_type=mime_type, size_bytes=size_bytes, sha256=sha256
        )

    def __post_init__(self) -> None:
        self.prepared_keys: list[str] = []
        self.accessed_keys: list[str] = []

    async def prepare_upload(
        self,
        *,
        object_key: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> UploadTarget:
        self.prepared_keys.append(object_key)
        return UploadTarget(
            url="https://storage.test/upload",
            fields={"key": object_key, "Content-Type": mime_type},
        )

    async def inspect_object(self, *, object_key: str) -> ObjectMetadata | None:
        return self.metadata

    async def create_download_url(self, *, object_key: str, expires_seconds: int) -> str:
        self.accessed_keys.append(object_key)
        return f"https://storage.test/read/{object_key}?ttl={expires_seconds}"


async def identity_root(db: AsyncSession) -> tuple[UUID, UUID, UUID]:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db.add_all([organization, location, user])
    await db.commit()
    return organization.id, location.id, user.id


@pytest.mark.integration
async def test_upload_intent_is_private_bounded_and_idempotent(
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)
    storage = FakePrivateStorage()
    now = datetime.now(UTC)

    first = await prepare_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="asset-intent-1",
        file_name=" Борщ.webp ",
        mime_type="image/webp",
        size_bytes=1024,
        sha256="a" * 64,
        now=now,
    )
    replay = await prepare_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="asset-intent-1",
        file_name=" Борщ.webp ",
        mime_type="image/webp",
        size_bytes=1024,
        sha256="a" * 64,
        now=now,
    )

    assert first.asset.id == replay.asset.id
    assert first.asset.object_key == replay.asset.object_key
    assert "Борщ" not in first.asset.object_key
    assert first.upload_url.startswith("https://storage.test/")
    assert first.expires_at > now


@pytest.mark.integration
async def test_complete_verifies_object_and_produces_short_lived_access(
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)
    storage = FakePrivateStorage()
    now = datetime.now(UTC)
    intent = await prepare_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="asset-intent-2",
        file_name="dish.png",
        mime_type="image/png",
        size_bytes=2048,
        sha256="b" * 64,
        now=now,
    )
    storage.metadata = ObjectMetadata(
        mime_type="image/png",
        size_bytes=2048,
        sha256="b" * 64,
    )

    completed = await complete_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        asset_id=intent.asset.id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="asset-complete-2",
        sha256="b" * 64,
        now=now,
    )
    access = await get_admin_asset_access(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        asset_id=completed.id,
    )

    assert completed.status == "ready"
    assert completed.ready_at == now
    assert access.endswith("ttl=300")


@pytest.mark.integration
@pytest.mark.parametrize(
    ("mime_type", "size_bytes", "sha256"),
    [
        ("image/svg+xml", 100, "c" * 64),
        ("image/png", 5 * 1024 * 1024 + 1, "c" * 64),
        ("image/png", 100, "short"),
    ],
)
async def test_upload_intent_rejects_unapproved_files(
    db_session: AsyncSession,
    mime_type: str,
    size_bytes: int,
    sha256: str,
) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)

    with pytest.raises(APIError) as invalid:
        await prepare_asset_upload(
            db_session,
            storage=FakePrivateStorage(),
            organization_id=organization_id,
            location_id=location_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            idempotency_key="invalid-upload",
            file_name="unsafe.file",
            mime_type=mime_type,
            size_bytes=size_bytes,
            sha256=sha256,
            now=datetime.now(UTC),
        )

    assert invalid.value.code == "ASSET_UPLOAD_INVALID"


@pytest.mark.integration
@pytest.mark.parametrize("reason", ["expired", "checksum", "missing", "mime", "metadata_checksum"])
async def test_failed_asset_completion_is_durable_and_cannot_issue_access(
    db_session: AsyncSession, reason: str
) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)
    storage = FakePrivateStorage()
    now = datetime.now(UTC)
    intent = await prepare_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="failed-intent",
        file_name="dish.png",
        mime_type="image/png",
        size_bytes=100,
        sha256="a" * 64,
        now=now,
    )
    asset_id = intent.asset.id
    if reason != "missing":
        storage.metadata = ObjectMetadata(
            mime_type="image/jpeg" if reason == "mime" else "image/png",
            size_bytes=100,
            sha256=("b" if reason == "metadata_checksum" else "a") * 64,
        )
    audit_before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
    with pytest.raises(APIError) as denied:
        await complete_asset_upload(
            db_session,
            storage=storage,
            organization_id=organization_id,
            location_id=location_id,
            asset_id=asset_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            idempotency_key="failed-complete",
            sha256=("b" if reason == "checksum" else "a") * 64,
            now=now + timedelta(minutes=15) if reason == "expired" else now,
        )
    assert denied.value.code == (
        "ASSET_UPLOAD_EXPIRED" if reason == "expired" else "ASSET_UPLOAD_INVALID"
    )
    persisted = await db_session.get_one(Asset, asset_id)
    assert persisted.status == "failed" and persisted.ready_at is None
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await get_admin_asset_access(
            db_session,
            storage=storage,
            organization_id=organization_id,
            location_id=location_id,
            asset_id=asset_id,
        )
    assert storage.accessed_keys == []
    with pytest.raises(APIError, match="ASSET_NOT_READY"):
        await complete_asset_upload(
            db_session,
            storage=storage,
            organization_id=organization_id,
            location_id=location_id,
            asset_id=asset_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            idempotency_key="failed-complete-retry",
            sha256="a" * 64,
            now=now,
        )
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_before


@pytest.mark.integration
async def test_archive_unlinked_asset_is_idempotent_and_tenant_scoped(
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)
    storage = FakePrivateStorage()
    now = datetime.now(UTC)
    intent = await prepare_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="archive-intent",
        file_name="dish.png",
        mime_type="image/png",
        size_bytes=100,
        sha256="a" * 64,
        now=now,
    )
    asset_id = intent.asset.id
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await archive_unlinked_asset(
            db_session,
            organization_id=uuid4(),
            location_id=location_id,
            asset_id=asset_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            now=now,
        )
    assert (await db_session.get_one(Asset, asset_id)).status == "pending_upload"
    for _ in range(2):
        archived = await archive_unlinked_asset(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            asset_id=asset_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            now=now,
        )
        assert archived.status == "archived" and archived.archived_at == now
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == "training_asset_archived",
                AuditEvent.target_id == asset_id,
            )
        )
        == 1
    )


@pytest.mark.integration
async def test_complete_rejects_mismatched_private_object(db_session: AsyncSession) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)
    storage = FakePrivateStorage()
    now = datetime.now(UTC)
    intent = await prepare_asset_upload(
        db_session,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        idempotency_key="asset-intent-3",
        file_name="dish.jpg",
        mime_type="image/jpeg",
        size_bytes=512,
        sha256="d" * 64,
        now=now,
    )
    storage.metadata = ObjectMetadata(
        mime_type="image/jpeg",
        size_bytes=513,
        sha256="d" * 64,
    )

    with pytest.raises(APIError) as invalid:
        await complete_asset_upload(
            db_session,
            storage=storage,
            organization_id=organization_id,
            location_id=location_id,
            asset_id=intent.asset.id,
            actor_user_id=user_id,
            request_id=uuid4(),
            idempotency_key="asset-complete-3",
            sha256="d" * 64,
            now=now,
        )

    assert invalid.value.code == "ASSET_UPLOAD_INVALID"
