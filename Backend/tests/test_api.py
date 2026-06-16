"""Tests for API."""

import pytest
from fastapi.testclient import TestClient
from src.api.routes import app

client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_upload_endpoint_missing_files():
    """Test upload endpoint without files."""
    response = client.post("/api/v1/pipeline/upload", data={"patient_id": "TEST001"})
    # Should fail without files
    assert response.status_code in [400, 422]


if __name__ == "__main__":
    pytest.main([__file__])








