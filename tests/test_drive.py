import io

from app.extensions import db
from app.models import AuditLog, DriveFile, Folder


def test_folder_lifecycle(logged_client, app):
    response = logged_client.post("/drive/folders", data={"name": "Hacienda"}, follow_redirects=True)
    assert "Carpeta creada" in response.text
    with app.app_context():
        folder = Folder.query.filter_by(name="Hacienda").one()
        folder_id = folder.id
    response = logged_client.post(
        f"/drive/folders/{folder_id}/rename", data={"name": "Hacienda y Finanzas"}, follow_redirects=True
    )
    assert "Carpeta renombrada" in response.text
    with app.app_context():
        assert db.session.get(Folder, folder_id).name == "Hacienda y Finanzas"


def test_upload_download_range_and_delete(logged_client, app):
    payload = b"%PDF-1.7\ncontenido institucional"
    response = logged_client.post(
        "/drive/upload",
        data={"files": (io.BytesIO(payload), "rendicion.pdf")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert "1 archivo(s) subido(s)" in response.text
    with app.app_context():
        item = DriveFile.query.one()
        file_id = item.id
        assert item.sha256
        assert AuditLog.query.filter_by(action="FILE_UPLOAD").count() == 1
    response = logged_client.get(f"/drive/files/{file_id}/download", headers={"Range": "bytes=0-7"})
    assert response.status_code == 206
    assert response.data == payload[:8]
    assert response.headers["Content-Range"].startswith("bytes 0-7/")
    response = logged_client.post(f"/drive/files/{file_id}/delete", follow_redirects=True)
    assert "Archivo eliminado" in response.text
    with app.app_context():
        assert db.session.get(DriveFile, file_id).deleted_at is not None


def test_folder_delete_removes_nested_objects(logged_client, app):
    logged_client.post("/drive/folders", data={"name": "Padre"})
    with app.app_context():
        parent_id = Folder.query.filter_by(name="Padre").one().id
    logged_client.post("/drive/folders", data={"name": "Hija", "parent_id": parent_id})
    with app.app_context():
        child_id = Folder.query.filter_by(name="Hija").one().id
    logged_client.post(
        "/drive/upload",
        data={"folder_id": child_id, "files": (io.BytesIO(b"datos"), "a.txt")},
        content_type="multipart/form-data",
    )
    response = logged_client.post(f"/drive/folders/{parent_id}/delete", follow_redirects=True)
    assert "Carpeta y contenido eliminados" in response.text
    with app.app_context():
        assert DriveFile.query.one().deleted_at is not None
        assert all(folder.deleted_at for folder in Folder.query.filter(Folder.parent_id.is_not(None)).all())
