from hashlib import sha256
from io import BytesIO
from typing import Any

import pytest

from app.services.private_storage import Boto3PrivateStorage


class SnapshotClient:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.objects: dict[str, bytes] = {}
        self.body: BytesIO | None = None

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        self.body = BytesIO(self.data)
        return {
            "Body": self.body,
            "ContentType": "image/png",
            "ContentLength": len(self.data),
            "Metadata": {"sha256": sha256(b"original").hexdigest()},
        }

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.data = b"replaced-source"
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}


@pytest.mark.parametrize("data,valid", [(b"original", True), (b"tampered", False)])
async def test_finalization_hashes_bytes_and_publishes_same_snapshot(
    data: bytes, valid: bool
) -> None:
    client = SnapshotClient(data)
    storage = Boto3PrivateStorage(client=client, bucket="test-only")
    result = await storage.finalize_upload(
        source_key="upload",
        target_key="final",
        mime_type="image/png",
        size_bytes=8,
        sha256=sha256(b"original").hexdigest(),
    )
    assert result is valid
    assert client.objects == ({"final": b"original"} if valid else {})
    assert client.body is not None and client.body.closed
