import io
from datetime import timedelta

from app.extensions import db
from app.models import DriveFile, Folder, StorageSettings, Unit, User, utcnow

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


def test_expired_file_cleanup_removes_object_and_record(logged_client, app):
    logged_client.post(
        "/drive/upload",
        data={"files": (io.BytesIO(b"archivo vencido"), "vencido.txt")},
        content_type="multipart/form-data",
    )
    with app.app_context():
        item = DriveFile.query.one()
        item.created_at = utcnow() - timedelta(days=16)
        db.session.commit()
        object_key = item.object_key

    result = app.test_cli_runner().invoke(args=["prune-expired-files"])

    assert result.exit_code == 0
    assert "1 eliminado(s)" in result.output
    with app.app_context():
        db.session.expire_all()
        assert DriveFile.query.one().deleted_at is not None
        assert object_key not in app.extensions["fake_storage"].objects


def test_expiration_panel_marks_soon_to_expire_files(super_client, app):
    with app.app_context():
        unit = Unit.query.filter_by(name="Dirección de Hacienda").one()
        folder = Folder.query.filter_by(unit_id=unit.id, parent_id=None).one()
        admin = User.query.filter_by(role="admin").one()
        item = DriveFile(
            folder_id=folder.id,
            unit_id=unit.id,
            display_name="proximo.txt",
            object_key="files/proximo.txt",
            content_type="text/plain",
            size_bytes=1,
            uploaded_by_id=admin.id,
            created_at=utcnow() - timedelta(days=14),
        )
        db.session.add(item)
        db.session.commit()

    response = super_client.get("/drive/expiration")

    assert response.status_code == 200
    assert "proximo.txt" in response.text
    assert "expiry-red" in response.text
