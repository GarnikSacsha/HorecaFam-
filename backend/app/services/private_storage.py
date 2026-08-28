import asyncio
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class UploadTarget:
    url: str
    fields: dict[str, str]


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    mime_type: str
    size_bytes: int
    sha256: str


class PrivateStorage(Protocol):
    async def prepare_upload(
        self,
        *,
        object_key: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> UploadTarget: ...

    async def inspect_object(self, *, object_key: str) -> ObjectMetadata | None: ...

    async def create_download_url(self, *, object_key: str, expires_seconds: int) -> str: ...


class Boto3PrivateStorage:
    def __init__(self, *, client: Any, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def prepare_upload(
        self,
        *,
        object_key: str,
        mime_type: str,
        size_bytes: int,
        sha256: str,
        expires_seconds: int,
    ) -> UploadTarget:
        response = await asyncio.to_thread(
            self._client.generate_presigned_post,
            Bucket=self._bucket,
            Key=object_key,
            Fields={"Content-Type": mime_type, "x-amz-meta-sha256": sha256},
            Conditions=[
                {"Content-Type": mime_type},
                {"x-amz-meta-sha256": sha256},
                ["content-length-range", size_bytes, size_bytes],
            ],
            ExpiresIn=expires_seconds,
        )
        return UploadTarget(
            url=cast(str, response["url"]),
            fields=cast(dict[str, str], response["fields"]),
        )

    async def inspect_object(self, *, object_key: str) -> ObjectMetadata | None:
        try:
            response = await asyncio.to_thread(
                self._client.head_object,
                Bucket=self._bucket,
                Key=object_key,
            )
        except self._client.exceptions.ClientError as exc:
            error_code = str(exc.response.get("Error", {}).get("Code", ""))
            if error_code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        metadata = cast(dict[str, str], response.get("Metadata", {}))
        return ObjectMetadata(
            mime_type=cast(str, response.get("ContentType", "")),
            size_bytes=cast(int, response.get("ContentLength", 0)),
            sha256=metadata.get("sha256", ""),
        )

    async def create_download_url(self, *, object_key: str, expires_seconds: int) -> str:
        return cast(
            str,
            await asyncio.to_thread(
                self._client.generate_presigned_url,
                "get_object",
                Params={"Bucket": self._bucket, "Key": object_key},
                ExpiresIn=expires_seconds,
            ),
        )


def build_private_storage(settings: Settings) -> Boto3PrivateStorage:
    settings.validate_private_storage()
    if (
        settings.storage_bucket is None
        or settings.storage_endpoint_url is None
        or settings.storage_access_key_id is None
        or settings.storage_secret_access_key is None
    ):
        raise RuntimeError("Private storage configuration invariant is broken")
    boto3 = import_module("boto3")
    client = boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        region_name=settings.storage_region,
        aws_access_key_id=settings.storage_access_key_id.get_secret_value(),
        aws_secret_access_key=settings.storage_secret_access_key.get_secret_value(),
    )
    return Boto3PrivateStorage(client=client, bucket=settings.storage_bucket)
