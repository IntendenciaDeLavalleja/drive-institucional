import io

from app.extensions import db
from app.models import DriveFile, Folder, StorageSettings, Unit, User

from .conftest import login


def test_superadmin_creates_unit(super_client, app):
    response = super_client.post(
        "/admin/units/",
        data={"name": "Dirección de Turismo", "quota_megabytes": "25"},
        follow_redirects=True,
    )

    assert "Unidad creada" in response.text
    with app.app_context():
        unit = Unit.query.filter_by(name="Dirección de Turismo").one()
        assert unit.quota_bytes == 25 * 1024 * 1024
        assert Folder.query.filter_by(unit_id=unit.id, parent_id=None).one()


def test_global_quota_limits_unit_assignment(super_client, app):
    with app.app_context():
        settings = StorageSettings(id=1, total_quota_bytes=110 * 1024 * 1024)
        db.session.add(settings)
        settings.total_quota_bytes = 110 * 1024 * 1024
        db.session.commit()

    response = super_client.post(
        "/admin/units/",
        data={"name": "Dirección de Turismo", "quota_megabytes": "11"},
        follow_redirects=True,
    )

    assert "supera el espacio total" in response.text
    with app.app_context():
        assert not Unit.query.filter_by(name="Dirección de Turismo").first()


def test_global_quota_cannot_be_lowered_below_assignment(super_client, app):
    with app.app_context():
        db.session.add(StorageSettings(id=1, total_quota_bytes=1024**4))
        db.session.commit()

    response = super_client.post(
        "/admin/units/settings",
        data={"total_quota_megabytes": "99"},
        follow_redirects=True,
    )

    assert "no puede ser menor" in response.text
    with app.app_context():
        assert db.session.get(StorageSettings, 1).total_quota_bytes == 1024**4


def test_admin_cannot_access_another_unit(client, app):
    with app.app_context():
        unit = Unit(name="Dirección de Turismo", quota_bytes=10 * 1024 * 1024)
        db.session.add(unit)
        db.session.flush()
        other = User(username="turismo", email="turismo@lavalleja.uy", role="admin", unit_id=unit.id)
        other.set_password("Contraseña-segura-789")
        db.session.add(other)
        db.session.flush()
        folder = Folder(name=unit.name, unit_id=unit.id, created_by_id=other.id)
        db.session.add(folder)
        db.session.commit()
        folder_id = folder.id

    login(client, app)
    assert client.get(f"/drive/folder/{folder_id}").status_code == 403


def test_unit_quota_blocks_upload(logged_client, app):
    with app.app_context():
        unit = Unit.query.filter_by(name="Dirección de Hacienda").one()
        unit.quota_bytes = 4
        db.session.commit()

    response = logged_client.post(
        "/drive/upload",
        data={"files": (io.BytesIO(b"cinco"), "limite.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    assert "no tiene espacio disponible" in response.text
    with app.app_context():
        assert DriveFile.query.count() == 0
