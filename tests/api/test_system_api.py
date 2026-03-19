from fastapi.testclient import TestClient

from backend.app import app

client = TestClient(app)


def test_system_health_endpoint():
    response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "quant-platform-api",
        "version": "1.0.0",
    }
