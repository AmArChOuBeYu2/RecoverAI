"""
Environment and dependency verification test suite for RecoverAI.
Verifies that all required packages can be imported and initialized without errors.
"""

import pytest
import fastapi
import pydantic
import sqlalchemy
import openai
import razorpay
import httpx
from fastapi.testclient import TestClient

from backend.main import app

def test_imports():
    """Verify all required dependencies import successfully."""
    assert fastapi.__version__ is not None
    assert pydantic.__version__ is not None
    assert sqlalchemy.__version__ is not None
    assert openai.__version__ is not None
    assert razorpay.__file__ is not None
    assert httpx.__version__ is not None

def test_google_genai_import():
    """Verify google-genai SDK imports cleanly."""
    import google.genai as genai
    assert genai is not None

def test_fastapi_app_health():
    """Verify FastAPI application health endpoint."""
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "RecoverAI"
    assert "OBSERVED" in data["evidence_categories"]
    assert "VERIFIED" in data["evidence_categories"]
