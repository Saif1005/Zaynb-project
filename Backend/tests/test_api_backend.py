"""Tests API backend production (app/main.py)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analyze_rejects_invalid_s3():
    r = client.post(
        "/api/v1/analyze",
        json={
            "patient_id": "PATIENT001",
            "s3_uri_r1": "not-a-uri",
            "s3_uri_r2": "s3://bucket/patients/P1/input/R2.fastq.gz",
        },
    )
    assert r.status_code == 422


def test_analyze_rejects_identical_fastq():
    uri = "s3://genomic-cancer-pipeline-input-dev-857281493967/patients/P1/input/R1.fastq.gz"
    r = client.post(
        "/api/v1/analyze",
        json={
            "patient_id": "PATIENT001",
            "s3_uri_r1": uri,
            "s3_uri_r2": uri,
        },
    )
    assert r.status_code == 422


def test_analyze_accepts_valid_payload():
    r = client.post(
        "/api/v1/analyze",
        json={
            "patient_id": "PATIENT001",
            "s3_uri_r1": "s3://genomic-cancer-pipeline-input-dev-857281493967/patients/PATIENT001/input/R1.fastq.gz",
            "s3_uri_r2": "s3://genomic-cancer-pipeline-input-dev-857281493967/patients/PATIENT001/input/R2.fastq.gz",
        },
    )
    assert r.status_code == 202
    data = r.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    assert data["patient_id"] == "PATIENT001"

    status_r = client.get(f"/api/v1/jobs/{data['job_id']}")
    assert status_r.status_code == 200
    assert status_r.json()["job_id"] == data["job_id"]


def test_job_not_found():
    r = client.get("/api/v1/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
