from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.private_storage import ObjectMetadata, UploadTarget
from app.services.training_assets import (
    complete_asset_upload,
    get_admin_asset_access,
    prepare_asset_upload,
)
from tests.factories.identity import make_location, make_organization, make_user


@dataclass
class FakePrivateStorage:
    metadata: ObjectMetadata | None = None

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
