from app.storage import StorageError, storage


def test_health_checks_database_and_storage(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_health_is_unavailable_when_storage_fails(client, monkeypatch):
    def unavailable():
        raise StorageError("MinIO no está disponible")

    monkeypatch.setattr(storage, "healthcheck", unavailable)
    response = client.get("/health")

    assert response.status_code == 503
    assert response.json == {"status": "unavailable"}
