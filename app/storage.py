import hashlib
import os
import uuid
from dataclasses import dataclass

from minio import Minio
from minio.error import S3Error


class StorageError(RuntimeError):
    pass


class HashingReader:
    def __init__(self, stream):
        self.stream = stream
        self.sha256 = hashlib.sha256()

    def read(self, size=-1):
        chunk = self.stream.read(size)
        if chunk:
            self.sha256.update(chunk)
        return chunk


@dataclass
class StoredObject:
    object_key: str
    size_bytes: int
    etag: str | None
    sha256: str


class MinioStorage:
    def __init__(self):
        self.client = None
        self.bucket = None

    def init_app(self, app):
        self.client = None
        self.bucket = app.config["MINIO_BUCKET"]
        required = ("MINIO_ENDPOINT", "MINIO_ACCESS_KEY", "MINIO_SECRET_KEY")
        if not all(app.config.get(key) for key in required):
            if app.testing:
                return
            raise RuntimeError("Configuración de MinIO incompleta")
        self.client = Minio(
            app.config["MINIO_ENDPOINT"],
            access_key=app.config["MINIO_ACCESS_KEY"],
            secret_key=app.config["MINIO_SECRET_KEY"],
            secure=app.config["MINIO_SECURE"],
        )
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
        # Intencionalmente no se aplica ninguna política pública.

    def _require_client(self):
        if not self.client:
            raise StorageError("MinIO no está disponible")

    def upload(self, file_storage) -> StoredObject:
        self._require_client()
        stream = file_storage.stream
        current = stream.tell()
        stream.seek(0, os.SEEK_END)
        length = stream.tell()
        stream.seek(current)
        ext = os.path.splitext(file_storage.filename or "")[1].lower()[:20]
        key = f"files/{uuid.uuid4().hex}{ext}"
        reader = HashingReader(stream)
        try:
            result = self.client.put_object(
                self.bucket,
                key,
                reader,
                length,
                content_type=file_storage.mimetype or "application/octet-stream",
                part_size=64 * 1024 * 1024,
            )
            return StoredObject(key, length, getattr(result, "etag", None), reader.sha256.hexdigest())
        except S3Error as exc:
            raise StorageError("No se pudo guardar el archivo") from exc

    def open(self, object_key, offset=0, length=0):
        self._require_client()
        try:
            return self.client.get_object(self.bucket, object_key, offset=offset, length=length)
        except S3Error as exc:
            raise StorageError("No se pudo leer el archivo") from exc

    def delete(self, object_key):
        self._require_client()
        try:
            self.client.remove_object(self.bucket, object_key)
        except S3Error as exc:
            raise StorageError("No se pudo eliminar el archivo") from exc

    def stat(self, object_key):
        self._require_client()
        try:
            return self.client.stat_object(self.bucket, object_key)
        except S3Error as exc:
            raise StorageError("No se pudo consultar el archivo") from exc

    def healthcheck(self):
        self._require_client()
        try:
            if not self.client.bucket_exists(self.bucket):
                raise StorageError("El bucket de MinIO no existe")
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("MinIO no está disponible") from exc


storage = MinioStorage()
