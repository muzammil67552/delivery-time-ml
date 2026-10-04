"""API and Integration tests for FastAPI delivery prediction service.

Verifies:
3. FastAPI '/' root endpoint
4. FastAPI '/health' status endpoint
5. FastAPI '/predict' endpoint
6. Valid prediction request
7. Invalid/missing input handling
8. Frontend assets and Frontend -> API prediction flow
"""

import io
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


def test_09_download_templates(client: TestClient):
    """Test 9: Verify sample template download endpoints return valid spreadsheet data."""
    # Test CSV template
    csv_resp = client.get("/api/sample-template?template_type=prediction&format=csv")
    assert csv_resp.status_code == 200
    assert "Distance_km" in csv_resp.text

    # Test Excel template
    xlsx_resp = client.get("/api/sample-template?template_type=prediction&format=xlsx")
    assert xlsx_resp.status_code == 200
    assert len(xlsx_resp.content) > 100


def test_10_batch_prediction_endpoint(client: TestClient):
    """Test 10: Verify batch prediction endpoint processes uploaded CSV files and provides downloads."""
    csv_content = (
        "Distance_km,Weather,Traffic_Level,Time_of_Day,Vehicle_Type,Preparation_Time_min,Courier_Experience_yrs\n"
        "8.5,Clear,Medium,Evening,Scooter,15.0,3.0\n"
        "12.0,Rainy,High,Night,Car,20.0,5.0\n"
    )
    files = {"file": ("test_orders.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    response = client.post("/api/batch-predict", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["total_orders"] == 2
    assert "download_id" in data
    assert len(data["preview"]) == 2

    # Test downloading the generated batch result
    dl_resp = client.get(f"/api/download-batch/{data['download_id']}")
    assert dl_resp.status_code == 200
    assert len(dl_resp.content) > 0


def test_11_model_status_endpoint(client: TestClient):
    """Test 11: Verify model status endpoint reports availability information."""
    response = client.get("/api/model-status")
    assert response.status_code == 200
    data = response.json()
    assert "custom_model_available" in data


def test_12_hotel_profile_flow(client: TestClient):
    """Test 12: Verify hotel profile creation, persistence in SQLite, and retrieval."""
    # Read initial status
    initial_resp = client.get("/api/hotel-profile")
    assert initial_resp.status_code == 200
    initial_data = initial_resp.json()
    assert "is_configured" in initial_data

    # Save hotel profile
    payload = {
        "hotel_name": "The Grand Royal Palace",
        "branch_or_address": "742 Evergreen Terrace, Sector 5",
        "contact_email": "concierge@grandroyal.com",
        "contact_phone": "+1-800-555-0199",
        "default_prep_time_min": 18.0,
        "default_vehicle_type": "Scooter",
    }
    save_resp = client.post("/api/hotel-profile", json=payload)
    assert save_resp.status_code == 200
    save_data = save_resp.json()
    assert save_data["is_configured"] is True
    assert save_data["profile"]["hotel_name"] == "The Grand Royal Palace"
    assert save_data["profile"]["default_prep_time_min"] == 18.0

    # Verify retrieval
    get_resp = client.get("/api/hotel-profile")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["profile"]["hotel_name"] == "The Grand Royal Palace"


def test_13_order_history_logging(client: TestClient, valid_delivery_payload):
    """Test 13: Verify predictions are automatically logged into SQLite order history."""
    # Execute a prediction
    pred_resp = client.post("/predict", json=valid_delivery_payload)
    assert pred_resp.status_code == 200

    # Retrieve history
    history_resp = client.get("/api/order-history?limit=10")
    assert history_resp.status_code == 200
    history_data = history_resp.json()
    assert history_data["total"] >= 1
    assert len(history_data["orders"]) >= 1

    latest_order = history_data["orders"][0]
    assert latest_order["distance_km"] == valid_delivery_payload["Distance_km"]
    assert "predicted_time_min" in latest_order
    assert latest_order["source_type"] == "single"


def test_14_city_presets_endpoint(client: TestClient):
    """Test 14: Verify GET '/api/city-presets' returns available cities and landmarks."""
    response = client.get("/api/city-presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert "New York" in data["presets"]
    assert "landmarks" in data["presets"]["New York"]
    assert len(data["presets"]["New York"]["landmarks"]) > 0


def test_15_calculate_route_endpoint(client: TestClient):
    """Test 15: Verify GET '/api/calculate-route' computes road distance and polyline waypoints."""
    # From Hotel in Manhattan to Times Square
    params = {
        "origin_lat": 40.7306,
        "origin_lng": -73.9866,
        "dest_lat": 40.7580,
        "dest_lng": -73.9855,
    }
    response = client.get("/api/calculate-route", params=params)
    assert response.status_code == 200
    data = response.json()
    assert "distance_km" in data
    assert data["distance_km"] > 0
    assert "route_coords" in data
    assert len(data["route_coords"]) >= 2
    assert "duration_min" in data
    assert "source" in data


def test_16_predict_with_destination_address_and_coords(client: TestClient, valid_delivery_payload):
    """Test 16: Verify POST '/predict' handles destination address and GPS dropoff coordinates."""
    payload = valid_delivery_payload.copy()
    payload["Destination_Address"] = "Empire State Commercial Hub, 350 5th Ave"
    payload["Dropoff_Lat"] = 40.7484
    payload["Dropoff_Lng"] = -73.9857

    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "predicted_delivery_time_min" in data

    # Verify that destination address was logged in SQLite
    history_resp = client.get("/api/order-history?limit=1")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert history["orders"][0]["destination_address"] == "Empire State Commercial Hub, 350 5th Ave"


def test_17_riders_crud_and_fleet_stats(client: TestClient):
    """Test 17: Verify rider registration, GPS location update, status toggle, and fleet stats."""
    # 1. Fetch initial riders list
    list_resp = client.get("/api/riders")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert "riders" in list_data
    assert "total" in list_data

    # 2. Register a new courier
    new_rider_payload = {
        "name": "Alex Mercer",
        "phone": "+1-555-0199",
        "vehicle_type": "Scooter",
        "courier_exp_yrs": 4.5,
        "rating": 4.9,
        "status": "Available",
        "current_address": "Central District Hub, Lane 4",
        "current_lat": 40.7320,
        "current_lng": -73.9870
    }
    create_resp = client.post("/api/riders", json=new_rider_payload)
    assert create_resp.status_code in (200, 201)
    rider_info = create_resp.json()
    assert "id" in rider_info
    rider_id = rider_info["id"]
    assert rider_info.get("rider_name") == "Alex Mercer" or rider_info.get("name") == "Alex Mercer"
    assert rider_info["vehicle_type"] == "Scooter"
    assert rider_info["courier_exp_yrs"] == 4.5

    # 3. Fetch single rider by ID
    get_rider_resp = client.get(f"/api/riders/{rider_id}")
    assert get_rider_resp.status_code == 200
    assert get_rider_resp.json()["id"] == rider_id

    # 4. Update GPS location
    loc_payload = {
        "lat": 40.7410,
        "lng": -73.9890,
        "address": "Updated Dispatch Station 7"
    }
    loc_resp = client.put(f"/api/riders/{rider_id}/location", json=loc_payload)
    assert loc_resp.status_code == 200
    assert loc_resp.json()["current_lat"] == 40.7410

    # 5. Update Status
    status_resp = client.patch(f"/api/riders/{rider_id}/status", json={"status": "On Delivery"})
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "On Delivery"

    # 6. Check Fleet Stats
    stats_resp = client.get("/api/fleet/stats")
    assert stats_resp.status_code == 200
    stats_data = stats_resp.json()
    stats = stats_data.get("stats", stats_data)
    assert "total_riders" in stats
    assert stats["total_riders"] >= 1
    assert "available_riders" in stats



    # 7. Delete the created rider
    del_resp = client.delete(f"/api/riders/{rider_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True




