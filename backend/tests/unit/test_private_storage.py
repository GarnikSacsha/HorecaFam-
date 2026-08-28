from typing import Any

import pytest

from app.core.config import Settings
from app.services.private_storage import Boto3PrivateStorage, build_private_storage


class FakeS3Client:
    def __init__(self) -> None:
        self.upload_kwargs: dict[str, Any] | None = None
        self.download_kwargs: dict[str, Any] | None = None

    def generate_presigned_post(self, **kwargs: Any) -> dict[str, object]:
        self.upload_kwargs = kwargs
        return {"url": "https://storage.test/upload", "fields": {"key": kwargs["Key"]}}

    def generate_presigned_url(self, operation: str, **kwargs: Any) -> str:
        self.download_kwargs = {"operation": operation, **kwargs}
        return "https://storage.test/read"


@pytest.mark.asyncio
async def test_boto3_adapter_only_generates_private_presigned_requests() -> None:
    client = FakeS3Client()
    storage = Boto3PrivateStorage(client=client, bucket="private-training")

    upload = await storage.prepare_upload(
        object_key="training/org/location/opaque",
        mime_type="image/webp",
        size_bytes=1024,
        sha256="a" * 64,
        expires_seconds=900,
    )
    download = await storage.create_download_url(
        object_key="training/org/location/opaque",
        expires_seconds=300,
    )

    assert upload.url == "https://storage.test/upload"
    assert client.upload_kwargs is not None
    assert client.upload_kwargs["ExpiresIn"] == 900
    assert client.upload_kwargs["Conditions"][-1] == ["content-length-range", 1024, 1024]
    assert download == "https://storage.test/read"
    assert client.download_kwargs is not None
    assert client.download_kwargs["ExpiresIn"] == 300


def test_storage_factory_requires_complete_configuration() -> None:
    incomplete = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://localhost/horeca_test",
    )
    with pytest.raises(ValueError, match="incomplete"):
        build_private_storage(incomplete)

    complete = Settings(
        app_env="test",
        database_url="postgresql+asyncpg://localhost/horeca_test",
        storage_bucket="private-training",
        storage_endpoint_url="https://storage.test",
        storage_access_key_id="test-access-key",
        storage_secret_access_key="test-secret-key",
    )
    storage = build_private_storage(complete)

    assert isinstance(storage, Boto3PrivateStorage)
