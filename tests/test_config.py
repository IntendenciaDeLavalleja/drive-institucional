from app.config import public_base_url


def test_public_links_prefer_flask_run_host(monkeypatch):
    monkeypatch.setenv("FLASK_RUN_HOST", "https://mapi.drive.lavalleja.uy/")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://ignored.example")

    assert public_base_url() == "https://mapi.drive.lavalleja.uy"
