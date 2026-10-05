"""StorageService abstraction. Keys are opaque, per-user, UUID-based paths; files are NEVER served by URL --
only through authenticated API endpoints that check ownership. Swap LocalStorage for S3Storage via STORAGE_BACKEND."""
from __future__ import annotations
import os, re, shutil
from abc import ABC, abstractmethod
from .config import get_config

_KEY_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")


class StorageService(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes) -> None: ...
    @abstractmethod
    def get(self, key: str) -> bytes: ...
    @abstractmethod
    def delete(self, key: str) -> None: ...
    @abstractmethod
    def delete_prefix(self, prefix: str) -> None: ...
    @abstractmethod
    def exists(self, key: str) -> bool: ...


def _check(key: str) -> str:
    if not _KEY_RE.match(key) or ".." in key.split("/") or key.startswith("/"):
        raise ValueError("Invalid storage key")
    return key


class LocalStorage(StorageService):
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        p = os.path.abspath(os.path.join(self.root, _check(key)))
        if not p.startswith(self.root + os.sep):
            raise ValueError("Path traversal blocked")
        return p

    def put(self, key, data):
        p = self._path(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, p)

    def get(self, key):
        with open(self._path(key), "rb") as f:
            return f.read()

    def delete(self, key):
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def delete_prefix(self, prefix):
        p = self._path(prefix.rstrip("/"))
        shutil.rmtree(p, ignore_errors=True)

    def exists(self, key):
        return os.path.exists(self._path(key))


class S3Storage(StorageService):     # S3 / Cloudflare R2 / MinIO (any S3-compatible API)
    def __init__(self):
        import boto3                  # optional dependency: pip install boto3
        c = get_config()
        self.bucket = c.s3_bucket
        self.s3 = boto3.client("s3", endpoint_url=c.s3_endpoint_url or None, region_name=c.s3_region,
                               aws_access_key_id=c.s3_access_key, aws_secret_access_key=c.s3_secret_key)

    def put(self, key, data):
        self.s3.put_object(Bucket=self.bucket, Key=_check(key), Body=data, ServerSideEncryption="AES256")

    def get(self, key):
        return self.s3.get_object(Bucket=self.bucket, Key=_check(key))["Body"].read()

    def delete(self, key):
        self.s3.delete_object(Bucket=self.bucket, Key=_check(key))

    def delete_prefix(self, prefix):
        pg = self.s3.get_paginator("list_objects_v2")
        for page in pg.paginate(Bucket=self.bucket, Prefix=_check(prefix)):
            objs = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objs:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objs})

    def exists(self, key):
        try:
            self.s3.head_object(Bucket=self.bucket, Key=_check(key))
            return True
        except Exception:  # noqa: BLE001
            return False


_storage: StorageService | None = None


def get_storage() -> StorageService:
    global _storage
    if _storage is None:
        c = get_config()
        _storage = S3Storage() if c.storage_backend == "s3" else LocalStorage(c.storage_dir)
    return _storage


def set_storage(s: StorageService) -> None:
    global _storage
    _storage = s
