from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.services.private_storage import ObjectMetadata
from app.services.training_assets import complete_asset_upload, prepare_asset_upload
from tests.integration.test_training_assets import FakePrivateStorage, identity_root


class SnapshotStorage(FakePrivateStorage):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.objects: dict[str, bytes] = {}

    async def finalize_upload(
        self, *, source_key: str, target_key: str, mime_type: str, size_bytes: int, sha256: str
    ) -> bool:
        self.objects[target_key] = self.objects[source_key]
        return True


async def test_completed_asset_never_reuses_upload_capability(db_session: AsyncSession) -> None:
    organization_id, location_id, user_id = await identity_root(db_session)
    storage = SnapshotStorage()
    now = datetime.now(UTC)
    scope: dict[str, Any] = dict(
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        now=now,
    )
    upload: dict[str, Any] = dict(
        idempotency_key="immutable-upload",
        file_name="dish.png",
        mime_type="image/png",
        size_bytes=8,
        sha256=sha256(b"original").hexdigest(),
    )
    intent = await prepare_asset_upload(db_session, **scope, **upload)
    source_key = intent.asset.object_key
    storage.objects[source_key] = b"original"
    checksum = sha256(b"original").hexdigest()
    storage.metadata = ObjectMetadata(mime_type="image/png", size_bytes=8, sha256=checksum)
    asset = await complete_asset_upload(
        db_session,
        **scope,
        asset_id=intent.asset.id,
        idempotency_key="immutable-complete",
        sha256=checksum,
    )
    assert asset.object_key != source_key
    assert asset.object_key not in storage.prepared_keys
    storage.objects[source_key] = b"tampered"
    assert storage.objects[asset.object_key] == b"original"
    with pytest.raises(APIError, match="ASSET_NOT_READY"):
        await prepare_asset_upload(db_session, **scope, **upload)
