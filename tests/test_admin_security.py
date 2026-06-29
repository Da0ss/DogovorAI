"""
Tests for admin-only endpoints.
"""

from config.settings import settings


def test_metrics_requires_auth(client):
    response = client.get("/api/metrics/summary")
    assert response.status_code == 401


def test_metrics_rejects_non_admin(client):
    settings.admin_emails = "admin@example.com"
    response = client.get(
        "/api/metrics/summary",
        headers={"Authorization": "Bearer test-token-user@example.com"},
    )
    assert response.status_code == 403


def test_metrics_allows_configured_admin(client):
    settings.admin_emails = "admin@example.com"
    response = client.get(
        "/api/metrics/summary",
        headers={"Authorization": "Bearer test-token-admin@example.com"},
    )
    assert response.status_code == 200
    assert "total_users" in response.json()


def test_users_endpoint_requires_admin(client):
    settings.admin_emails = "admin@example.com"
    response = client.get(
        "/api/auth/users",
        headers={"Authorization": "Bearer test-token-user@example.com"},
    )
    assert response.status_code == 403
