from app.api.routes.health import health


def test_health_endpoint_payload() -> None:
    response = health()

    assert response.model_dump() == {"status": "ok", "service": "budget-app-api"}
