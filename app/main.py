"""FastAPI application for Delivery Time Prediction service.

Exposes RESTful endpoints for health status, metadata, real-time delivery
duration inference, batch processing, model retraining, and live interactive
route navigation and hotel intelligence.
"""

import os
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form, Query, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse


from dotenv import load_dotenv

# Load environment configuration from .env
load_dotenv()

from app.schemas import (
    DeliveryPredictionRequest,
    DeliveryPredictionResponse,
    HealthResponse,
    RootResponse,
    HotelProfilePayload,
    HotelProfileResponse,
    RouteCalculationResponse,
    RiderCreatePayload,
    RiderUpdateLocationPayload,
    RiderUpdateStatusPayload,
    RiderListResponse,
)
from src.predict import load_production_pipeline, predict_delivery_time
from src.custom_pipeline import (
    process_batch_predictions,
    get_batch_download,
    execute_custom_retraining,
    get_custom_model_status,
    generate_sample_template,
)
from src.database import (
    init_db,
    get_hotel_profile,
    save_or_update_hotel_profile,
    log_prediction,
    get_recent_predictions,
    get_predictions_count,
    clear_predictions_history,
    create_or_update_rider,
    get_all_riders,
    get_rider_by_id,
    update_rider_location,
    update_rider_status,
    delete_rider,
    get_fleet_stats,
)
from src.routing import (
    calculate_route_navigation,
    CITY_PRESETS,
)

# Static files directory for frontend
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


def ensure_app_ready():
    """Ensures database is initialized and model pipeline is warmed up (critical for serverless platforms like Vercel)."""
    if not getattr(app.state, "pipeline_loaded", False):
        try:
            init_db()
            pipeline = load_production_pipeline()
            app.state.pipeline_loaded = pipeline is not None
            app.state.load_error = None
        except Exception as exc:
            app.state.pipeline_loaded = False
            app.state.load_error = str(exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager that warms and caches the ML pipeline and initializes SQLite."""
    ensure_app_ready()
    yield



app = FastAPI(
    title="Delivery Time Prediction API",
    description="Production-ready REST API for estimating food delivery times with hotel logistics and live routing.",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure Cross-Origin Resource Sharing (CORS) for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static assets directory if available
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get(
    "/",
    tags=["General"],
    summary="Root confirmation endpoint",
)
def read_root(request: Request):
    """Returns a welcome confirmation indicating the prediction API service is running.
    Redirects web browsers with Accept: text/html directly to the interactive UI."""
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header and "application/json" not in accept_header and "*/*" not in accept_header:
        return RedirectResponse(url="/ui")
    return {
        "message": "Delivery Time Prediction API is running",
        "status": "online",
    }



@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Monitoring"],
    summary="Service health and model readiness check",
)
def read_health():
    """Reports operational readiness and confirms the production pipeline is loaded in memory."""
    ensure_app_ready()
    is_loaded = getattr(app.state, "pipeline_loaded", False)
    if not is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model pipeline not ready: {getattr(app.state, 'load_error', 'Not loaded')}",
        )
    return {
        "status": "healthy",
        "model_loaded": True,
    }



@app.post(
    "/predict",
    response_model=DeliveryPredictionResponse,
    tags=["Inference"],
    summary="Generate real-time delivery duration prediction",
)
def predict(request: DeliveryPredictionRequest):
    """Predicts food delivery duration in minutes based on raw delivery inputs."""
    try:
        # Convert validated Pydantic model to dictionary
        input_data = request.model_dump()

        # Pass raw input directly to the production prediction pipeline
        predicted_time = predict_delivery_time(input_data)

        # Log prediction to SQLite database
        try:
            log_prediction(
                order_dict=input_data,
                predicted_time=predicted_time,
                source_type="single",
                destination_address=input_data.get("Destination_Address"),
                dropoff_lat=input_data.get("Dropoff_Lat"),
                dropoff_lng=input_data.get("Dropoff_Lng"),
            )
        except Exception:
            pass

        return {
            "predicted_delivery_time_min": float(predicted_time),
        }

    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )
    except FileNotFoundError as fnf_err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model artifact unavailable: {str(fnf_err)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected prediction error: {str(exc)}",
        )


NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


@app.get("/ui", include_in_schema=False)
def serve_ui():
    """Serves the frontend interface for interactive manual predictions and live map."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html", headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="Frontend interface not found.")


@app.get("/welcome", include_in_schema=False)
def serve_welcome():
    """Serves the Hotel Registration & Onboarding Welcome page."""
    welcome_path = os.path.join(STATIC_DIR, "welcome.html")
    if os.path.exists(welcome_path):
        return FileResponse(welcome_path, media_type="text/html", headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="Welcome onboarding page not found.")


@app.get("/style.css", include_in_schema=False)
def serve_css():
    """Directly serves the frontend stylesheet for root-relative requests."""
    css_path = os.path.join(STATIC_DIR, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css", headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="CSS file not found.")


@app.get("/script.js", include_in_schema=False)
def serve_js():
    """Directly serves the frontend JavaScript for root-relative requests."""
    js_path = os.path.join(STATIC_DIR, "script.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript", headers=NO_CACHE_HEADERS)
    raise HTTPException(status_code=404, detail="JavaScript file not found.")


# ==============================================================================
# Hotel & Merchant Mode Endpoints (Batch Prediction & Custom Retraining)
# ==============================================================================

@app.post("/api/batch-predict", tags=["Hotel / Batch Mode"])
async def batch_predict(
    file: UploadFile = File(..., description="Uploaded Excel (.xlsx) or CSV (.csv) containing order records"),
    use_custom_model: bool = Form(False, description="Whether to use the custom hotel trained model if available"),
):
    """Processes an uploaded spreadsheet of orders, appends predicted delivery durations, and prepares downloadable file."""
    try:
        file_bytes = await file.read()
        summary, download_id = process_batch_predictions(
            file_bytes=file_bytes,
            filename=file.filename or "upload.xlsx",
            use_custom_model=use_custom_model,
        )
        return {
            "status": "success",
            "download_id": download_id,
            "summary": summary,
            **summary,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Batch processing error: {str(exc)}")


@app.get("/api/download-batch/{download_id}", tags=["Hotel / Batch Mode"])
def download_batch_result(download_id: str):
    """Downloads the processed Excel/CSV file containing delivery time predictions."""
    download_info = get_batch_download(download_id)
    if not download_info:
        raise HTTPException(status_code=404, detail="Requested batch result expired or not found.")

    filename, file_bytes = download_info
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if filename.endswith(".xlsx")
        else "text/csv"
    )

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/retrain-hotel-model", tags=["Hotel / Custom Training"])
async def retrain_hotel_model(
    file: UploadFile = File(..., description="Uploaded Excel (.xlsx) or CSV (.csv) with historical order records and target"),
    hotel_name: str = Form("My Hotel", description="Name of the hotel or merchant"),
):
    """Executes automated end-to-end retraining on hotel historical delivery records."""
    try:
        file_bytes = await file.read()
        metrics = execute_custom_retraining(
            file_bytes=file_bytes,
            filename=file.filename or "training_data.xlsx",
            hotel_name=hotel_name,
        )
        return {
            "status": "success",
            "message": f"Successfully retrained custom model for '{hotel_name}'!",
            "metrics": metrics,
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retraining error: {str(exc)}")


@app.get("/api/sample-template", tags=["Hotel / Helpers"])
def download_sample_template(
    type: Optional[str] = Query(None, description="Template type: 'batch' or 'training'"),
    template_type: Optional[str] = Query(None, description="Alternative alias for template type"),
    format: str = Query("xlsx", pattern="^(xlsx|csv)$", description="File format: 'xlsx' or 'csv'"),
):
    """Generates and downloads sample Excel or CSV template files."""
    chosen_type = type or template_type or "batch"
    include_target = (chosen_type.lower() == "training")
    file_bytes = generate_sample_template(include_target=include_target, file_format=format)

    clean_name = "training" if include_target else "batch"
    if format.lower() == "csv":
        media_type = "text/csv"
        filename = f"delivery_{clean_name}_template.csv"
    else:
        filename = f"delivery_{clean_name}_template.xlsx"
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/model-status", tags=["Hotel / Custom Training"])
def check_custom_model():
    """Checks the status, metadata, and evaluation metrics of the custom hotel model."""
    return get_custom_model_status()


# ==============================================================================
# Hotel Profile & Order History Endpoints (SQLite Persistence)
# ==============================================================================

@app.get("/api/hotel-profile", response_model=HotelProfileResponse, tags=["Hotel Configuration"])
def get_profile():
    """Retrieves the configured hotel profile from SQLite."""
    profile = get_hotel_profile()
    return {
        "is_configured": profile is not None,
        "profile": profile,
    }


@app.post("/api/hotel-profile", response_model=HotelProfileResponse, tags=["Hotel Configuration"])
def update_profile(payload: HotelProfilePayload):
    """Saves or updates the hotel profile in SQLite."""
    saved = save_or_update_hotel_profile(payload.model_dump())
    return {
        "is_configured": True,
        "profile": saved,
    }


@app.post("/api/register-hotel", tags=["Hotel Configuration"])
async def register_hotel(
    hotel_name: str = Form(..., description="Hotel / Restaurant Name"),
    email: str = Form(..., description="Owner Contact Email"),
    password: str = Form(..., description="Account Password"),
    address: str = Form("", description="Hotel Street Address"),
    city_preset: str = Form("New York", description="City location preset"),
    latitude: float = Form(40.7306, description="Hotel latitude"),
    longitude: float = Form(-73.9866, description="Hotel longitude"),
    default_prep_time_min: float = Form(15.0, description="Default kitchen prep time in minutes"),
    default_vehicle_type: str = Form("Scooter", description="Default delivery vehicle type"),
    dataset: Optional[UploadFile] = File(None, description="Optional Excel/CSV delivery history for ML retraining"),
):
    """Registers a hotel / restaurant account and optionally trains a custom ML model on uploaded delivery history."""
    try:
        hotel_name_clean = hotel_name.strip()
        if not hotel_name_clean:
            raise HTTPException(status_code=400, detail="Hotel / Restaurant name cannot be blank.")
        if not email.strip() or "@" not in email:
            raise HTTPException(status_code=400, detail="A valid contact email is required.")
        if not password or len(password) < 4:
            raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")

        retrained = False
        training_metrics = None
        has_custom = False
        model_mae = None
        training_samples = 0
        trained_at_iso = ""

        # If a dataset file was provided and has content
        if dataset and dataset.filename:
            file_bytes = await dataset.read()
            if len(file_bytes) > 0:
                retrain_res = execute_custom_retraining(
                    file_bytes=file_bytes,
                    filename=dataset.filename,
                    hotel_name=hotel_name_clean,
                )
                retrained = True
                training_metrics = retrain_res.get("metrics", {})
                has_custom = True
                model_mae = training_metrics.get("model_mae")
                training_samples = training_metrics.get("total_samples", 0)
                trained_at_iso = datetime.now().isoformat()

        # Ensure geographic coordinates accurately match the hotel address and country
        from src.geocoding import resolve_hotel_coordinates
        final_lat, final_lng, loc_desc = resolve_hotel_coordinates(
            address=address.strip(),
            country=city_preset.strip(),
            provided_lat=latitude,
            provided_lng=longitude,
        )

        # Save hotel profile to SQLite
        profile_data = {
            "hotel_name": hotel_name_clean,
            "branch_or_address": address.strip(),
            "contact_email": email.strip(),
            "password": password,
            "default_prep_time_min": default_prep_time_min,
            "default_vehicle_type": default_vehicle_type,
            "latitude": final_lat,
            "longitude": final_lng,
            "city_preset": city_preset.strip(),
            "has_custom_model": has_custom,
            "model_mae": model_mae,
            "training_samples": training_samples,
            "trained_at": trained_at_iso,
        }
        saved_profile = save_or_update_hotel_profile(profile_data)

        return {
            "status": "success",
            "message": f"Hotel '{hotel_name_clean}' registered successfully!",
            "retrained": retrained,
            "metrics": training_metrics,
            "profile": saved_profile,
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Hotel registration error: {str(exc)}")


@app.get("/api/order-history", tags=["Hotel / Order History"])
def get_history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    """Retrieves historical order predictions saved in SQLite."""
    orders = get_recent_predictions(limit=limit, offset=offset)
    total = get_predictions_count()
    return {
        "total": total,
        "orders": orders,
    }


@app.delete("/api/order-history", tags=["Hotel / Order History"])
def clear_history():
    """Clears all logged prediction history from SQLite."""
    deleted_count = clear_predictions_history()
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "message": "Order prediction history cleared.",
    }


# ==============================================================================
# Navigation, Geocoding & Route Calculation Endpoints (Option 1 & 3)
# ==============================================================================

@app.get("/api/city-presets", tags=["Navigation & Routing"])
def get_city_presets():
    """Returns available city presets and their delivery destination landmarks."""
    return {"presets": CITY_PRESETS}


@app.get("/api/calculate-route", response_model=RouteCalculationResponse, tags=["Navigation & Routing"])
def calculate_route(
    origin_lat: float = Query(..., ge=-90.0, le=90.0, description="Hotel origin latitude"),
    origin_lng: float = Query(..., ge=-180.0, le=180.0, description="Hotel origin longitude"),
    dest_lat: float = Query(..., ge=-90.0, le=90.0, description="Customer dropoff latitude"),
    dest_lng: float = Query(..., ge=-180.0, le=180.0, description="Customer dropoff longitude"),
):
    """Calculates road network distance, driving duration, and route polyline."""
    nav_data = calculate_route_navigation(
        origin_lat=origin_lat,
        origin_lng=origin_lng,
        dest_lat=dest_lat,
        dest_lng=dest_lng,
    )
    return nav_data


# ==============================================================================
# Rider Fleet & Courier Management Endpoints
# ==============================================================================

@app.get("/api/riders", response_model=RiderListResponse, tags=["Rider Fleet"])
def list_riders(status: Optional[str] = Query(None, description="Optional status filter: Available, On Delivery, Offline")):
    """Retrieves all registered delivery riders with real-time fleet overview stats."""
    riders = get_all_riders(status_filter=status)
    stats = get_fleet_stats()
    return {
        "total": len(riders),
        "stats": stats,
        "riders": riders,
    }


@app.post("/api/riders", status_code=status.HTTP_201_CREATED, tags=["Rider Fleet"])
def register_rider(payload: RiderCreatePayload):
    """Registers a new courier/rider with automatic location resolution if coordinates are omitted."""
    rider_dict = payload.model_dump()

    # If coordinates are omitted or 0, fallback to hotel base location or address geocoding
    r_lat = rider_dict.get("current_lat")
    r_lng = rider_dict.get("current_lng")
    if r_lat is None or r_lng is None or (r_lat == 0.0 and r_lng == 0.0):
        hotel = get_hotel_profile()
        if hotel and hotel.get("latitude") and hotel.get("longitude"):
            import random
            offset_lat = (random.random() - 0.5) * 0.015
            offset_lng = (random.random() - 0.5) * 0.015
            rider_dict["current_lat"] = round(float(hotel["latitude"]) + offset_lat, 6)
            rider_dict["current_lng"] = round(float(hotel["longitude"]) + offset_lng, 6)
            if not rider_dict.get("current_address"):
                rider_dict["current_address"] = f"Station near {hotel.get('branch_or_address') or hotel.get('hotel_name')}"
        else:
            rider_dict["current_lat"] = 24.838519
            rider_dict["current_lng"] = 67.081033
            if not rider_dict.get("current_address"):
                rider_dict["current_address"] = "Central Dispatch Hub"

    saved_rider = create_or_update_rider(rider_dict)
    resp = dict(saved_rider)
    resp["status"] = "success"
    resp["message"] = f"Rider '{saved_rider.get('rider_name')}' registered successfully!"
    resp["rider"] = saved_rider
    return resp


@app.get("/api/riders/{rider_id}", tags=["Rider Fleet"])
def get_rider(rider_id: int):
    """Retrieves a specific rider's profile and live status."""
    rider = get_rider_by_id(rider_id)
    if not rider:
        raise HTTPException(status_code=404, detail=f"Rider with ID {rider_id} not found.")
    resp = dict(rider)
    resp["rider"] = rider
    return resp


@app.put("/api/riders/{rider_id}/location", tags=["Rider Fleet"])
def update_location(rider_id: int, payload: RiderUpdateLocationPayload):
    """Updates a rider's live GPS coordinates, typically sent from courier mobile/GPS device."""
    lat_val = payload.get_lat()
    lng_val = payload.get_lng()
    addr_val = payload.get_address()
    updated = update_rider_location(
        rider_id=rider_id,
        lat=lat_val,
        lng=lng_val,
        address=addr_val,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"Rider with ID {rider_id} not found.")
    resp = dict(updated)
    resp["status"] = "success"
    resp["message"] = f"Location updated for {updated.get('rider_name')}."
    resp["rider"] = updated
    return resp



@app.patch("/api/riders/{rider_id}/status", tags=["Rider Fleet"])
def update_status(rider_id: int, payload: RiderUpdateStatusPayload):
    """Updates a rider's operational status (e.g. Available, On Delivery, Busy, Offline)."""
    updated = update_rider_status(rider_id=rider_id, status_val=payload.status)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Rider with ID {rider_id} not found.")
    resp = dict(updated)
    resp["operation_status"] = "success"
    resp["message"] = f"Status changed to '{payload.status}' for {updated.get('rider_name')}."
    resp["rider"] = updated
    return resp


@app.delete("/api/riders/{rider_id}", tags=["Rider Fleet"])
def remove_rider(rider_id: int):
    """Deletes a rider from the fleet registry."""
    success = delete_rider(rider_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Rider with ID {rider_id} not found.")
    return {"status": "success", "success": True, "message": f"Rider {rider_id} removed."}



@app.get("/api/fleet/stats", tags=["Rider Fleet"])
def fleet_statistics():
    """Returns active fleet statistics and courier availability counts."""
    return {"stats": get_fleet_stats()}

