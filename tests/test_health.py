"""
Tests for Health Check Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


class TestHealthEndpoints:
    """Health check endpoint tests"""

    def test_root_endpoint(self):
        """
        Test root endpoint serves landing page
        """
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 200

    def test_health_check_endpoint(self):
        """
        Test basic health check endpoint
        """
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "🟢 OK"
        assert data["service"] == "DogovorAI"

    def test_health_status_endpoint(self):
        """
        Test health status endpoint with database info
        """
        response = client.get("/api/health/")
        assert response.status_code in [200, 503]  # 503 if DB not configured
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert data["service"] == "DogovorAI"

    def test_liveness_probe(self):
        """
        Test Kubernetes liveness probe endpoint
        """
        response = client.get("/api/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "DogovorAI"

    def test_readiness_probe(self):
        """
        Test Kubernetes readiness probe endpoint
        """
        response = client.get("/api/health/ready")
        # May return 503 if database not configured
        assert response.status_code in [200, 503]

    def test_analytics_config_endpoint(self):
        """
        Test public analytics tracking configuration endpoint
        """
        response = client.get("/api/config/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "posthog_api_key" in data
        assert "posthog_host" in data
        assert "ga_measurement_id" in data
        assert "gtm_id" in data


class TestAPIDocumentation:
    """API documentation tests"""

    def test_swagger_docs_available(self):
        """
        Test that Swagger UI documentation is available
        """
        response = client.get("/docs")
        assert response.status_code == 200

    def test_openapi_schema_available(self):
        """
        Test that OpenAPI schema is available
        """
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "DogovorAI"
