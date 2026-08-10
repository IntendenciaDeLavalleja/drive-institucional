from app.config import public_base_url


def test_public_links_prefer_flask_run_host(monkeypatch):
    monkeypatch.setenv("FLASK_RUN_HOST", "https://mapi.drive.lavalleja.uy/")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://ignored.example")

    assert public_base_url() == "https://mapi.drive.lavalleja.uy"


def test_open_graph_image_uses_public_logo_and_configured_origin(client):
    response = client.get("/admin/login")

    assert 'https://drive.test/public/Logo.webp?v=20260810-logo-public-v2' in response.text
    assert 'og:image:width" content="1024' in response.text


def test_brand_assets_are_served_only_from_public_directory(client):
    assert client.get("/public/Logo.webp").status_code == 200
    assert client.get("/public/favicon.ico").status_code == 200
    assert client.get("/static/logo.webp").status_code == 404
    assert client.get("/static/favicon.ico").status_code == 404
