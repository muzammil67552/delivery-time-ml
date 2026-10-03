"""API and Integration tests for FastAPI delivery prediction service.

Verifies:
3. FastAPI '/' root endpoint
4. FastAPI '/health' status endpoint
5. FastAPI '/predict' endpoint
6. Valid prediction request
7. Invalid/missing input handling
8. Frontend assets and Frontend -> API prediction flow
"""

import pytest
from fastapi.testclient import TestClient


def test_03_root_endpoint(client: TestClient):
    """Test 3: Verify GET '/' returns 200 OK and confirmation message."""
    response = client.get("/")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "message" in data, "Response JSON missing 'message' key."
    assert "Delivery Time Prediction API is running" in data["message"]
    assert data.get("status") == "online"


def test_04_health_endpoint(client: TestClient):
    """Test 4: Verify GET '/health' returns 200 OK with model status."""
    response = client.get("/health")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert data.get("status") == "healthy", f"Expected status 'healthy', got {data.get('status')}"
    assert data.get("model_loaded") is True, f"Expected model_loaded True, got {data.get('model_loaded')}"


def test_05_06_predict_valid_request(client: TestClient, valid_delivery_payload):
    """Test 5 & 6: Verify POST '/predict' accepts valid payload and returns predicted minutes."""
    response = client.post("/predict", json=valid_delivery_payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "predicted_delivery_time_min" in data, "Response missing 'predicted_delivery_time_min' key."
    predicted_time = data["predicted_delivery_time_min"]
    assert isinstance(predicted_time, (int, float)), f"Expected float, got {type(predicted_time)}."
    assert predicted_time > 0, f"Expected positive delivery time, got {predicted_time}."


def test_06_predict_boundary_request(client: TestClient, edge_case_delivery_payload):
    """Test 6b: Verify POST '/predict' handles valid edge-case boundary values."""
    response = client.post("/predict", json=edge_case_delivery_payload)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()
    assert "predicted_delivery_time_min" in data
    assert data["predicted_delivery_time_min"] > 0


def test_07_predict_missing_required_field(client: TestClient, valid_delivery_payload):
    """Test 7a: Verify POST '/predict' returns 422 when required fields are missing."""
    invalid_payload = valid_delivery_payload.copy()
    del invalid_payload["Distance_km"]  # Remove mandatory feature
    
    response = client.post("/predict", json=invalid_payload)
    assert response.status_code == 422, f"Expected 422 Unprocessable Entity, got {response.status_code}."
    data = response.json()
    assert "detail" in data


def test_07_predict_negative_distance(client: TestClient, valid_delivery_payload):
    """Test 7b: Verify POST '/predict' returns 422 when distance is negative (violates gt=0)."""
    invalid_payload = valid_delivery_payload.copy()
    invalid_payload["Distance_km"] = -3.5
    
    response = client.post("/predict", json=invalid_payload)
    assert response.status_code == 422, f"Expected 422, got {response.status_code}."


def test_07_predict_invalid_category(client: TestClient, valid_delivery_payload):
    """Test 7c: Verify POST '/predict' returns 422 when categorical feature is invalid."""
    invalid_payload = valid_delivery_payload.copy()
    invalid_payload["Weather"] = "Sunny"  # Valid options are Clear, Rainy, Foggy, Snowy, Windy
    
    response = client.post("/predict", json=invalid_payload)
    assert response.status_code == 422, f"Expected 422, got {response.status_code}."


def test_07_predict_out_of_bounds_numerical(client: TestClient, valid_delivery_payload):
    """Test 7d: Verify POST '/predict' returns 422 when numerical feature exceeds valid limits."""
    invalid_payload = valid_delivery_payload.copy()
    invalid_payload["Preparation_Time_min"] = 300  # Max is 180 min
    
    response = client.post("/predict", json=invalid_payload)
    assert response.status_code == 422, f"Expected 422, got {response.status_code}."


def test_08_frontend_assets_served(client: TestClient):
    """Test 8a: Verify static frontend files and UI endpoint are accessible."""
    # Test GET /ui
    ui_resp = client.get("/ui")
    assert ui_resp.status_code == 200, f"Expected 200 for /ui, got {ui_resp.status_code}."
    assert "text/html" in ui_resp.headers.get("content-type", "")
    assert "Delivery Time Predictor" in ui_resp.text

    # Test GET /static/index.html
    html_resp = client.get("/static/index.html")
    assert html_resp.status_code == 200, f"Expected 200 for /static/index.html, got {html_resp.status_code}."
    assert "prediction-form" in html_resp.text

    # Test GET /static/style.css & GET /style.css
    css_resp = client.get("/static/style.css")
    assert css_resp.status_code == 200, f"Expected 200 for /static/style.css, got {css_resp.status_code}."
    css_direct_resp = client.get("/style.css")
    assert css_direct_resp.status_code == 200, f"Expected 200 for /style.css, got {css_direct_resp.status_code}."

    # Test GET /static/script.js & GET /script.js
    js_resp = client.get("/static/script.js")
    assert js_resp.status_code == 200, f"Expected 200 for /static/script.js, got {js_resp.status_code}."
    js_direct_resp = client.get("/script.js")
    assert js_direct_resp.status_code == 200, f"Expected 200 for /script.js, got {js_direct_resp.status_code}."


def test_08_frontend_to_api_flow(client: TestClient):
    """Test 8b: Verify end-to-end frontend payload contract against the /predict API."""
    # Matches the exact structure assembled by frontend script.js
    frontend_payload = {
        "Distance_km": 12.0,
        "Weather": "Rainy",
        "Traffic_Level": "High",
        "Time_of_Day": "Night",
        "Vehicle_Type": "Car",
        "Preparation_Time_min": 25.0,
        "Courier_Experience_yrs": 5.0,
    }

    response = client.post("/predict", json=frontend_payload)
    assert response.status_code == 200
    data = response.json()
    assert "predicted_delivery_time_min" in data
    assert data["predicted_delivery_time_min"] > 0
