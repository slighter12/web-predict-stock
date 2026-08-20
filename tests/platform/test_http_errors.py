import json

from backend.platform.http.errors import build_error_response


def test_build_error_response_keeps_server_request_id_authoritative():
    response = build_error_response(
        status_code=429,
        request_id="req_server",
        code="CALIBRATION_BUSY",
        message="retry later",
        headers={"x-request-id": "req_caller", "Retry-After": "1"},
    )

    assert response.headers["x-request-id"] == "req_server"
    assert response.headers["retry-after"] == "1"
    assert json.loads(response.body)["meta"]["request_id"] == "req_server"
