def test_unknown_route_renders_custom_not_found_page(client):
    response = client.get("/ruta-que-no-existe")

    assert response.status_code == 404
    assert "La página que buscás no existe." in response.text
    assert "Error 404" in response.text


def test_json_unknown_route_returns_error_payload(client):
    response = client.get("/api/ruta-que-no-existe")

    assert response.status_code == 404
    assert response.json["code"] == 404
