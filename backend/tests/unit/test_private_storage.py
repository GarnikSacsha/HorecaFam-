import json
import os
from base64 import b64decode
from datetime import UTC, datetime
from importlib import import_module
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

from app.core.config import Settings
from app.services.private_storage import Boto3PrivateStorage, build_private_storage


@pytest.fixture(autouse=True)
def isolated_storage_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(os.environ):
        if name.startswith(("AWS_", "STORAGE_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("AWS_CONFIG_FILE", os.devnull)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", os.devnull)
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setattr(import_module("boto3"), "DEFAULT_SESSION", None)

    def reject_network(*args: Any, **kwargs: Any) -> None:
        pytest.fail("Storage unit tests must not send provider requests")

    monkeypatch.setattr(import_module("botocore.endpoint").Endpoint, "make_request", reject_network)


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
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://localhost/horeca_test",
    )
    with pytest.raises(ValueError, match="incomplete"):
        build_private_storage(incomplete)

    complete = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://localhost/horeca_test",
        storage_bucket="private-training",
        storage_endpoint_url="https://storage.test",
        storage_access_key_id="test-access-key",
        storage_secret_access_key="test-secret-key",
    )
    storage = build_private_storage(complete)

    assert isinstance(storage, Boto3PrivateStorage)


@pytest.mark.parametrize("style", [None, "auto", "path", "virtual"])
async def test_factory_presigns_expected_addressing_style(style: str | None) -> None:
    options: dict[str, Any] = {}
    if style is not None:
        options["storage_addressing_style"] = style
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://localhost/horeca_test",
        storage_bucket="private-training",
        storage_endpoint_url="https://storage.test",
        storage_region="auto",
        storage_access_key_id="test-access-key",
        storage_secret_access_key="test-secret-key",
        **options,
    )
    storage = build_private_storage(settings)
    started = datetime.now(UTC)
    upload = await storage.prepare_upload(
        object_key="training/image.webp",
        mime_type="image/webp",
        size_bytes=1024,
        sha256="a" * 64,
        expires_seconds=900,
    )
    download = await storage.create_download_url(
        object_key="training/image.webp", expires_seconds=300
    )
    finished = datetime.now(UTC)
    virtual = style == "virtual"
    hostname = "private-training.storage.test" if virtual else "storage.test"
    prefix = "" if virtual else "/private-training"
    upload_parts = urlsplit(upload.url)
    download_parts = urlsplit(download)
    assert upload_parts.scheme == download_parts.scheme == "https"
    assert upload_parts.hostname == download_parts.hostname == hostname
    assert upload_parts.path.rstrip("/") == prefix
    assert download_parts.path == f"{prefix}/training/image.webp"
    policy = json.loads(b64decode(upload.fields["policy"]))
    assert {"Content-Type": "image/webp"} in policy["conditions"]
    assert {"x-amz-meta-sha256": "a" * 64} in policy["conditions"]
    assert ["content-length-range", 1024, 1024] in policy["conditions"]
    assert {"key": "training/image.webp"} in policy["conditions"]
    assert {"bucket": "private-training"} in policy["conditions"]
    expiration = datetime.fromisoformat(policy["expiration"])
    assert 899 <= (expiration - started).total_seconds() <= 901
    query = parse_qs(download_parts.query)
    if "X-Amz-Expires" in query:
        assert query["X-Amz-Expires"] == ["300"]
        assert "X-Amz-Signature" in query
    else:
        assert "Signature" in query
        expires_at = int(query["Expires"][0])
        assert started.timestamp() + 299 <= expires_at <= finished.timestamp() + 301
