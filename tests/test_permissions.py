from app.extensions import db
from app.models import Unit, User


def test_admin_cannot_manage_users(logged_client):
    assert logged_client.get("/admin/users/").status_code == 403
    assert logged_client.get("/admin/units/").status_code == 403
    assert logged_client.get("/drive/audit").status_code == 403


def test_superadmin_creates_admin(super_client, app):
    with app.app_context():
        unit_id = Unit.query.filter_by(name="Dirección de Hacienda").one().id
    response = super_client.post(
        "/admin/users/",
        data={
            "username": "hacienda",
            "email": "hacienda@lavalleja.uy",
            "password": "Temporal-segura-123",
            "role": "admin",
            "unit_id": unit_id,
        },
        follow_redirects=True,
    )
    assert "Usuario creado" in response.text
    with app.app_context():
        assert User.query.filter_by(username="hacienda", role="admin", unit_id=unit_id).one()


def test_superadmin_never_receives_a_unit(super_client, app):
    with app.app_context():
        unit_id = Unit.query.filter_by(name="Dirección de Hacienda").one().id
    response = super_client.post(
        "/admin/users/",
        data={
            "username": "segundo-super",
            "email": "segundo-super@lavalleja.uy",
            "password": "Temporal-segura-123",
            "role": "superadmin",
            "unit_id": unit_id,
        },
        follow_redirects=True,
    )

    assert "Usuario creado" in response.text
    with app.app_context():
        assert User.query.filter_by(username="segundo-super", role="superadmin").one().unit_id is None


def test_last_superadmin_cannot_be_demoted(super_client, app):
    with app.app_context():
        admin = User.query.filter_by(role="admin").one()
        db.session.delete(admin)
        db.session.commit()
        super_id = User.query.filter_by(role="superadmin").one().id
        unit_id = Unit.query.first().id
    response = super_client.post(
        f"/admin/users/{super_id}/update",
        data={"role": "admin", "unit_id": unit_id, "is_active": "on"},
        follow_redirects=True,
    )
    assert "No podés quitarte" in response.text
