from app.extensions import db
from app.models import AuditLog, TwoFactorCode, User

from .conftest import login


def test_login_requires_second_factor(client, app):
    response = client.post(
        "/admin/login", data={"email": "admin@lavalleja.uy", "password": "Contraseña-segura-123"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin/2fa")
    with client.session_transaction() as session:
        assert session["pending_2fa_user_id"]


def test_valid_2fa_logs_user_in(client, app):
    response = login(client, app)
    assert "Dirección de Hacienda" in response.text
    with app.app_context():
        assert AuditLog.query.filter_by(action="LOGIN").count() == 1
        challenge = TwoFactorCode.query.order_by(TwoFactorCode.id.desc()).first()
        assert challenge.consumed_at is not None


def test_code_cannot_be_reused(client, app):
    client.post("/admin/login", data={"email": "admin@lavalleja.uy", "password": "Contraseña-segura-123"})
    code = app.extensions["outbox"][-1]["code"]
    assert client.post("/admin/2fa", data={"code": code}).status_code == 302
    client.post("/admin/logout")
    with app.app_context():
        challenge = TwoFactorCode.query.order_by(TwoFactorCode.id.desc()).first()
        assert challenge.verify(code) is False


def test_bad_password_does_not_reveal_user(client):
    response = client.post("/admin/login", data={"email": "admin@lavalleja.uy", "password": "bad"})
    assert "Correo o contraseña incorrectos" in response.text


def test_user_can_optionally_update_own_profile(logged_client, app):
    response = logged_client.post(
        "/admin/profile",
        data={"username": "admin-actualizado", "email": "", "password": "Nueva-clave-segura-123"},
        follow_redirects=True,
    )

    assert "Perfil actualizado" in response.text
    with app.app_context():
        user = User.query.filter_by(email="admin@lavalleja.uy").one()
        assert user.username == "admin-actualizado"
        assert user.check_password("Nueva-clave-segura-123")
        assert AuditLog.query.filter_by(action="PROFILE_UPDATE").count() == 1


def test_profile_form_uses_isolated_spacious_layout(logged_client):
    response = logged_client.get("/admin/profile")

    assert 'class="file-panel profile-form" data-profile-version="spacious"' in response.text
