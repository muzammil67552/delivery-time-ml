"""Shared pytest fixtures for Delivery Time Prediction tests."""

from typing import Dict, Any
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    """Provides a FastAPI TestClient session with lifespan startup/shutdown events."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_delivery_payload() -> Dict[str, Any]:
    """Provides a realistic, valid delivery prediction payload for testing."""
    return {
        "Distance_km": 8.5,
        "Weather": "Clear",
        "Traffic_Level": "Medium",
        "Time_of_Day": "Evening",
        "Vehicle_Type": "Scooter",
        "Preparation_Time_min": 15.0,
        "Courier_Experience_yrs": 3.0,
    }


@pytest.fixture
def edge_case_delivery_payload() -> Dict[str, Any]:
    """Provides boundary-value valid inputs (e.g. minimal distance, 0 prep time)."""
    return {
        "Distance_km": 0.5,
        "Weather": "Rainy",
        "Traffic_Level": "High",
        "Time_of_Day": "Night",
        "Vehicle_Type": "Bike",
        "Preparation_Time_min": 0.0,
        "Courier_Experience_yrs": 0.0,
    }
