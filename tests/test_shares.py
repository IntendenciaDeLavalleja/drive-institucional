import io
import re
from datetime import timedelta
from urllib.parse import urlparse

from app.extensions import db
from app.models import DriveFile, ShareAccessLog, ShareLink


def create_file(client):
    client.post(
        "/drive/upload",
        data={"files": (io.BytesIO(b"archivo compartido"), "informe.pdf")},
        content_type="multipart/form-data",
    )
    from app.models import DriveFile

    return DriveFile.query.one().id


def extract_url(text):
    match = re.search(r'value="(https://drive\.test/s/[^"]+)"', text)
    assert match
    return match.group(1)


def test_password_protected_share(logged_client, app):
    with app.app_context():
        file_id = create_file(logged_client)
    response = logged_client.post(
        f"/drive/files/{file_id}/share",
        data={"days": "7", "max_downloads": "2", "password": "clave-segura", "label": "Tribunal"},
    )
    public_url = extract_url(response.text)
    path = urlparse(public_url).path
    public_client = app.test_client()
    assert "protegido con contraseña" in public_client.get(path).text
    assert public_client.post(path, data={"password": "mala"}).status_code == 401
    assert public_client.post(path, data={"password": "clave-segura"}).status_code == 200
    first = public_client.get(path + "/download")
    assert first.data == b"archivo compartido"
    with app.app_context():
        link = ShareLink.query.one()
        assert link.download_count == 1
        assert ShareAccessLog.query.filter_by(event="DOWNLOAD", outcome="SUCCESS").count() == 1


def test_download_limit_and_revocation(logged_client, app):
    with app.app_context():
        file_id = create_file(logged_client)
    response = logged_client.post(
        f"/drive/files/{file_id}/share", data={"days": "1", "max_downloads": "1"}
    )
    path = urlparse(extract_url(response.text)).path
    public_client = app.test_client()
    assert public_client.get(path + "/download").status_code == 200
    # La misma sesión puede completar/reintentar la transferencia; una sesión
    # nueva ya no puede consumir un segundo cupo.
    assert public_client.get(path + "/download").status_code == 200
    assert app.test_client().get(path + "/download").status_code == 410
    with app.app_context():
        link_id = ShareLink.query.one().id
    logged_client.post(f"/drive/shares/{link_id}/revoke")
    assert public_client.get(path).status_code == 410


def test_plain_token_is_not_stored(logged_client, app):
    with app.app_context():
        file_id = create_file(logged_client)
    response = logged_client.post(f"/drive/files/{file_id}/share", data={"days": "7"})
    token = urlparse(extract_url(response.text)).path.rsplit("/", 1)[-1]
    with app.app_context():
        link = ShareLink.query.one()
        assert token != link.token_hash
        assert len(link.token_hash) == 64


def test_share_expiration_cannot_exceed_file_retention(logged_client, app):
    with app.app_context():
        file_id = create_file(logged_client)
    logged_client.post(f"/drive/files/{file_id}/share", data={"days": "365"})

    with app.app_context():
        item = db.session.get(DriveFile, file_id)
        link = ShareLink.query.one()
        assert link.expires_at == item.created_at + timedelta(days=app.config["FILE_RETENTION_DAYS"])
