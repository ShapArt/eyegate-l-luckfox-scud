import pytest


@pytest.mark.parametrize(
    "path", ["/", "/kiosk", "/monitor", "/enroll", "/sim", "/layout"]
)
def test_spa_routes_serve_index(client, path):
    resp = client.get(path)
    assert resp.status_code == 200
    body = resp.text.lower()
    assert '<div id="root">' in body
