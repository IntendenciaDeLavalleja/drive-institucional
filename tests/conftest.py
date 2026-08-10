import io
from types import SimpleNamespace

import pytest

from app import create_app
from app.extensions import db
from app.models import Folder, Unit, User
from app.storage import StoredObject, storage


class ObjectResponse(io.BytesIO):
    def release_conn(self):
        pass


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.counter = 0

    def upload(self, file_storage):
        self.counter += 1
        data = file_storage.stream.read()
        key = f"files/test-{self.counter}"
        self.objects[key] = data
        import hashlib

        return StoredObject(key, len(data), f"etag-{self.counter}", hashlib.sha256(data).hexdigest())

    def delete(self, key):
        self.objects.pop(key)

    def stat(self, key):
        return SimpleNamespace(size=len(self.objects[key]))

    def healthcheck(self):
        return None

    def open(self, key, offset=0, length=0):
        data = self.objects[key][offset : offset + length if length else None]
        return ObjectResponse(data)


@pytest.fixture()
def app(monkeypatch):
    app = create_app(
        "testing",
        {
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "PUBLIC_BASE_URL": "https://drive.test",
            "TRUSTED_PROXY_COUNT": 0,
        },
    )
    fake = FakeStorage()
    monkeypatch.setattr(storage, "upload", fake.upload)
    monkeypatch.setattr(storage, "delete", fake.delete)
    monkeypatch.setattr(storage, "stat", fake.stat)
    monkeypatch.setattr(storage, "open", fake.open)
    app.extensions["fake_storage"] = fake
    with app.app_context():
        db.create_all()
        unit = Unit(name="Dirección de Hacienda", quota_bytes=100 * 1024 * 1024)
        db.session.add(unit)
        db.session.flush()
        admin = User(username="admin", email="admin@lavalleja.uy", role="admin", unit_id=unit.id, is_active=True)
        admin.set_password("Contraseña-segura-123")
        superadmin = User(
            username="super", email="super@lavalleja.uy", role="superadmin", is_active=True
        )
        superadmin.set_password("Contraseña-segura-456")
        db.session.add_all([admin, superadmin])
        db.session.flush()
        db.session.add(Folder(name=unit.name, unit_id=unit.id, created_by_id=admin.id))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, app, email="admin@lavalleja.uy", password="Contraseña-segura-123"):
    response = client.post("/admin/login", data={"email": email, "password": password})
    assert response.status_code == 302
    code = app.extensions["outbox"][-1]["code"]
    return client.post("/admin/2fa", data={"code": code}, follow_redirects=True)


@pytest.fixture()
def logged_client(client, app):
    response = login(client, app)
    assert response.status_code == 200
    return client


@pytest.fixture()
def super_client(client, app):
    response = login(client, app, "super@lavalleja.uy", "Contraseña-segura-456")
    assert response.status_code == 200
    return client
