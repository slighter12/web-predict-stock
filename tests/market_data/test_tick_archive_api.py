import pytest
from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/api/v1/data/tick-archive-dispatches"),
        ("get", "/api/v1/data/tick-archive-dispatches"),
        ("post", "/api/v1/data/tick-archive-imports"),
        ("get", "/api/v1/data/tick-archives"),
        ("post", "/api/v1/data/tick-replays"),
        ("get", "/api/v1/data/tick-replays"),
        ("get", "/api/v1/data/tick-ops/kpis"),
        ("get", "/api/v1/data/tick-gates/p2"),
    ],
)
def test_tick_archive_routes_are_not_public(method: str, path: str):
    request = getattr(client, method)
    kwargs = {"json": {}} if method == "post" else {}

    response = request(path, **kwargs)

    assert response.status_code == 404
