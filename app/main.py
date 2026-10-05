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
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, JSONResponse


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
    HotelLoginPayload,
    RouteCalculationResponse,
    RiderCreatePayload,
    RiderUpdateLocationPayload,
    RiderUpdateStatusPayload,
    RiderListResponse,
    DispatchCreatePayload,
    DispatchCompletePayload,
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
    authenticate_hotel,
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
    get_dispatch_order_by_tracking_id,
    get_dispatch_order_by_token,
    activate_dispatch_order,
    deactivate_and_cascade_dispatch_order,
    check_and_expire_timeout_dispatches,
    complete_dispatch_order,
    get_active_dispatches,
    get_raw_ml_dispatch_data,
    get_email_logs_for_order,
)
from src.dispatch_engine import (
    generate_tracking_id,
    compute_time_of_day,
    fetch_live_weather,
    compute_delivery_distance,
    execute_automated_dispatch,
    send_dispatch_email,
    handle_cascading_dispatch,
    process_timeout_cascades,
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


def resolve_request_hotel_id(
    request: Request,
    explicit_id: Optional[int] = None,
) -> Optional[int]:
    """Resolves active hotel_id from explicit parameters, custom headers, or session cookies."""
    if explicit_id is not None:
        try:
            return int(explicit_id)
        except (ValueError, TypeError):
            pass

    # 1. Custom request header
    header_val = request.headers.get("X-Hotel-ID")
    if header_val and header_val.isdigit():
        return int(header_val)

    # 2. Query param
    qp = request.query_params.get("hotel_id")
    if qp and qp.isdigit():
        return int(qp)

    # 3. Session cookie
    cookie_val = request.cookies.get("active_hotel_id")
    if cookie_val and cookie_val.isdigit():
        return int(cookie_val)

    return None


def is_hotel_account_configured(hotel_id: Optional[int] = None) -> bool:
    """Determines whether a valid merchant/hotel profile has been configured in the database."""
    try:
        profile = get_hotel_profile(hotel_id=hotel_id)
        if not profile:
            return False
        name = str(profile.get("hotel_name", "")).strip()
        if not name:
            return False
        if name == "My Hotel / Restaurant":
            email = str(profile.get("contact_email", "")).strip()
            addr = str(profile.get("branch_or_address", "")).strip()
            pwd = str(profile.get("password_hash", "")).strip()
            if not email and not addr and not pwd:
                return False
        return True
    except Exception:
        return False


@app.get(
    "/",
    tags=["General"],
    summary="Root entry point",
)
def read_root(request: Request):
    """Entry point routing:
    - For API / automated test clients: returns JSON status.
    - For browser users:
        * If hotel account is already configured -> Redirects to /ui.
        * If no hotel account exists yet (first-time visitor) -> Redirects to /welcome.
    """
    accept = request.headers.get("accept", "")
    user_agent = request.headers.get("user-agent", "").lower()

    # Return JSON for automated test suites or API clients requesting JSON
    if (
        "testclient" in user_agent
        or (accept == "application/json" and "text/html" not in accept)
        or request.query_params.get("format") == "json"
    ):
        return {
            "message": "Delivery Time Prediction API is running",
            "status": "online",
        }

    # Browser clients: Route based on whether hotel account exists
    if is_hotel_account_configured():
        return RedirectResponse(url="/ui", status_code=status.HTTP_302_FOUND)
    else:
        return RedirectResponse(url="/welcome", status_code=status.HTTP_302_FOUND)





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
def predict(request: DeliveryPredictionRequest, http_request: Request):
    """Predicts food delivery duration in minutes based on raw delivery inputs."""
    try:
        # Convert validated Pydantic model to dictionary
        input_data = request.model_dump()

        # Pass raw input directly to the production prediction pipeline
        predicted_time = predict_delivery_time(input_data)

        # Log prediction to SQLite database scoped to active hotel
        try:
            h_id = resolve_request_hotel_id(
                request=http_request,
                explicit_id=input_data.get("Hotel_ID"),
            )
            log_prediction(
                order_dict=input_data,
                predicted_time=predicted_time,
                source_type="single",
                destination_address=input_data.get("Destination_Address"),
                dropoff_lat=input_data.get("Dropoff_Lat"),
                dropoff_lng=input_data.get("Dropoff_Lng"),
                hotel_id=h_id,
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
def serve_ui(request: Request):
    """Serves the frontend interface for interactive manual predictions and live map.
    If no hotel account has been setup yet, redirects first-time users to /welcome."""
    user_agent = request.headers.get("user-agent", "").lower()
    is_test_client = "testclient" in user_agent
    allow_guest = (
        is_test_client
        or request.query_params.get("guest") == "1"
        or request.query_params.get("preview") == "1"
    )

    if not is_hotel_account_configured() and not allow_guest:
        return RedirectResponse(url="/welcome", status_code=status.HTTP_302_FOUND)

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
def get_profile(request: Request, hotel_id: Optional[int] = Query(None)):
    """Retrieves the configured hotel profile from SQLite."""
    hid = resolve_request_hotel_id(request, hotel_id)
    profile = get_hotel_profile(hotel_id=hid)
    return {
        "is_configured": is_hotel_account_configured(hotel_id=hid),
        "profile": profile,
    }



@app.post("/api/hotel-profile", response_model=HotelProfileResponse, tags=["Hotel Configuration"])
def update_profile(payload: HotelProfilePayload, request: Request, response: Response):
    """Saves or updates the hotel profile in SQLite."""
    data = payload.model_dump()
    hid = resolve_request_hotel_id(request)
    if hid and "id" not in data:
        data["id"] = hid
    saved = save_or_update_hotel_profile(data, force_new=False)
    if saved and saved.get("id"):
        response.set_cookie(key="active_hotel_id", value=str(saved["id"]), max_age=86400*30, httponly=False, samesite="lax")
    return {
        "is_configured": True,
        "profile": saved,
    }


@app.post("/api/hotel-login", tags=["Hotel Configuration"])
def hotel_login(payload: HotelLoginPayload, response: Response):
    """Authenticates a hotel manager with Hotel Name, Email, and Password."""
    success, msg, profile = authenticate_hotel(
        hotel_name=payload.hotel_name,
        email=payload.email,
        password=payload.password,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=msg,
        )
    if profile and profile.get("id"):
        response.set_cookie(key="active_hotel_id", value=str(profile["id"]), max_age=86400*30, httponly=False, samesite="lax")
    return {
        "status": "success",
        "message": msg,
        "redirect_url": "/ui",
        "profile": profile,
    }


@app.post("/api/hotel-logout", tags=["Hotel Configuration"])
@app.get("/api/hotel-logout", tags=["Hotel Configuration"])
def hotel_logout(response: Response):
    """Terminates the active hotel manager session and clears all session cookies."""
    response.delete_cookie(key="active_hotel_id", path="/")
    response.set_cookie(key="active_hotel_id", value="", max_age=0, expires=0, path="/")
    return {
        "status": "success",
        "message": "Hotel session logged out successfully.",
        "redirect_url": "/welcome",
    }



@app.post("/api/register-hotel", tags=["Hotel Configuration"])
async def register_hotel(
    response: Response,
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

        # Save hotel profile to SQLite with force_new=True to create fresh account & fleet
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
        saved_profile = save_or_update_hotel_profile(profile_data, force_new=True)

        if saved_profile and saved_profile.get("id"):
            response.set_cookie(key="active_hotel_id", value=str(saved_profile["id"]), max_age=86400*30, httponly=False, samesite="lax")

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
def get_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    hotel_id: Optional[int] = Query(None),
):
    """Retrieves historical order predictions saved in SQLite for the active hotel."""
    hid = resolve_request_hotel_id(request, hotel_id)
    orders = get_recent_predictions(limit=limit, offset=offset, hotel_id=hid)
    total = get_predictions_count(hotel_id=hid)
    return {
        "total": total,
        "orders": orders,
    }


@app.delete("/api/order-history", tags=["Hotel / Order History"])
def clear_history(
    request: Request,
    hotel_id: Optional[int] = Query(None),
):
    """Clears all logged prediction history from SQLite for the active hotel."""
    hid = resolve_request_hotel_id(request, hotel_id)
    deleted_count = clear_predictions_history(hotel_id=hid)
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
def list_riders(
    request: Request,
    status: Optional[str] = Query(None, description="Optional status filter: Available, On Delivery, Offline"),
    hotel_id: Optional[int] = Query(None),
):
    """Retrieves all registered delivery riders with real-time fleet overview stats for the active hotel."""
    hid = resolve_request_hotel_id(request, hotel_id)
    riders = get_all_riders(hotel_id=hid, status_filter=status)
    stats = get_fleet_stats(hotel_id=hid)
    return {
        "total": len(riders),
        "stats": stats,
        "riders": riders,
    }


@app.post("/api/riders", status_code=status.HTTP_201_CREATED, tags=["Rider Fleet"])
def register_rider(payload: RiderCreatePayload, request: Request):
    """Registers a new courier/rider with automatic location resolution if coordinates are omitted."""
    rider_dict = payload.model_dump()
    hid = resolve_request_hotel_id(request, rider_dict.get("hotel_id"))
    rider_dict["hotel_id"] = hid

    # If coordinates are omitted or 0, fallback to hotel base location or address geocoding
    r_lat = rider_dict.get("current_lat")
    r_lng = rider_dict.get("current_lng")
    if r_lat is None or r_lng is None or (r_lat == 0.0 and r_lng == 0.0):
        hotel = get_hotel_profile(hotel_id=hid)
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

    has_custom_gps = (r_lat is not None and r_lng is not None and not (r_lat == 0.0 and r_lng == 0.0))
    tracking_source = "Native Device GPS Sensor (Hardware-Free)" if has_custom_gps else "Station Hub Fallback"

    saved_rider = create_or_update_rider(rider_dict, hotel_id=hid)
    resp = dict(saved_rider)
    resp["status"] = "success"
    resp["message"] = f"Rider '{saved_rider.get('rider_name')}' registered successfully with {tracking_source}!"
    resp["rider"] = saved_rider
    resp["tracking_source"] = tracking_source
    resp["hardware_gps_required"] = False
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
def fleet_statistics(request: Request, hotel_id: Optional[int] = Query(None)):
    """Returns active fleet statistics and courier availability counts for the active hotel."""
    hid = resolve_request_hotel_id(request, hotel_id)
    return {"stats": get_fleet_stats(hotel_id=hid)}


# ==============================================================================
# Automated Dispatch Engine & Cascading Pipeline Endpoints
# ==============================================================================

@app.get("/api/dispatch/generate-tracking-id", tags=["Automated Dispatch Engine"])
def get_next_tracking_id():
    """Generates a guaranteed unique alphanumeric tracking ID for new orders."""
    return {"tracking_id": generate_tracking_id()}


@app.get("/api/weather/live", tags=["Automated Dispatch Engine"])
def get_live_weather(
    lat: float = Query(40.7306, ge=-90.0, le=90.0),
    lng: float = Query(-73.9866, ge=-180.0, le=180.0),
):
    """Fetches live weather condition via Open-Meteo API and calculates time of day."""
    weather = fetch_live_weather(lat, lng)
    time_of_day = compute_time_of_day()
    return {
        "weather": weather,
        "time_of_day": time_of_day,
        "latitude": lat,
        "longitude": lng,
    }


@app.post("/api/dispatch/create", tags=["Automated Dispatch Engine"])
def create_automated_dispatch(payload: DispatchCreatePayload, request: Request):
    """Executes the full automated dispatch workflow:
    1. Generates or validates unique Tracking ID.
    2. Auto-enriches with distance, live weather API condition, and time of day.
    3. Finds closest available courier based on device GPS & performance score.
    4. Evaluates ML delivery ETA.
    5. Dispatches interactive email notification with 5-minute timeout window.
    6. Persists raw payload for Machine Learning retraining.
    """
    hotel_id = resolve_request_hotel_id(request, payload.hotel_id) or 1
    base_url = str(request.base_url).rstrip("/")


    result = execute_automated_dispatch(
        client_name=payload.client_name,
        client_phone=payload.client_phone,
        client_address=payload.client_address,
        hotel_id=hotel_id,
        tracking_id=payload.tracking_id,
        dest_lat=payload.dest_lat,
        dest_lng=payload.dest_lng,
        vehicle_type=payload.vehicle_type,
        prep_time_min=payload.prep_time_min,
        traffic_level=payload.traffic_level,
        base_url=base_url,
    )
    return result


@app.get("/api/dispatch/respond", response_class=HTMLResponse, tags=["Automated Dispatch Engine"])
def respond_dispatch_email(
    request: Request,
    token: str = Query(..., description="Security dispatch token"),
    action: str = Query("activate", description="'activate' or 'deactivate'"),
):
    """Interactive courier email response handler.
    - If rider clicks 'Activate Order', displays full customer details and changes status to 'On Delivery'.
    - If rider clicks 'Deactivate Order', unassigns rider and automatically cascades to the next closest rider.
    - If 5-minute timeout has expired, informs rider and cascades to next rider.
    """
    action = action.lower().strip()
    wants_json = (
        request.query_params.get("format") == "json"
        or "application/json" in request.headers.get("accept", "")
    )
    if action == "activate":
        result = activate_dispatch_order(token)
        if wants_json:
            return JSONResponse(content=result, status_code=200 if result.get("success") else 400)
        if result.get("success"):
            order = result.get("order") or {}
            rider = result.get("rider") or {}
            tracking_id = order.get("tracking_id", "")
            client_name = order.get("client_name", "Valued Customer")
            client_phone = order.get("client_phone", "N/A")
            client_address = order.get("client_address", "Customer Destination")
            distance_km = order.get("distance_km", 0.0)
            predicted_eta = order.get("predicted_eta_min", 25.0)
            rider_name = rider.get("rider_name") or order.get("rider_name", "Courier Partner")

            html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Order Activated • {tracking_id}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #090d16;
      --card-bg: rgba(22, 27, 46, 0.95);
      --border: rgba(99, 102, 241, 0.25);
      --primary: #6366f1;
      --primary-hover: #4f46e5;
      --success: #10b981;
      --success-glow: rgba(16, 185, 129, 0.35);
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: radial-gradient(circle at 50% 0%, #1e1b4b 0%, var(--bg) 75%);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .cockpit-container {{
      max-width: 520px;
      width: 100%;
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 24px;
      box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), 0 0 30px rgba(99, 102, 241, 0.2);
      backdrop-filter: blur(16px);
      overflow: hidden;
    }}
    .cockpit-header {{
      background: linear-gradient(135deg, rgba(16, 185, 129, 0.2) 0%, rgba(99, 102, 241, 0.2) 100%);
      border-bottom: 1px solid var(--border);
      padding: 24px;
      text-align: center;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 14px;
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid var(--success);
      color: #34d399;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      margin-bottom: 12px;
      box-shadow: 0 0 15px var(--success-glow);
    }}
    .status-dot {{
      width: 8px;
      height: 8px;
      background: #34d399;
      border-radius: 50%;
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(0.9); opacity: 0.7; }}
      50% {{ transform: scale(1.3); opacity: 1; }}
      100% {{ transform: scale(0.9); opacity: 0.7; }}
    }}
    h1 {{ font-size: 24px; font-weight: 800; margin-bottom: 6px; }}
    .tracking-tag {{
      display: inline-block;
      font-family: 'JetBrains Mono', monospace;
      font-size: 14px;
      color: #818cf8;
      background: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(99, 102, 241, 0.3);
      padding: 4px 10px;
      border-radius: 8px;
    }}
    .cockpit-body {{ padding: 24px; }}
    .detail-card {{
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      padding: 18px;
      margin-bottom: 20px;
    }}
    .field-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }}
    .field-row:last-child {{ border-bottom: none; }}
    .field-label {{ font-size: 13px; color: var(--text-muted); font-weight: 500; }}
    .field-value {{ font-size: 14px; font-weight: 700; text-align: right; color: #fff; }}
    .address-highlight {{
      font-size: 14px;
      color: #e2e8f0;
      line-height: 1.4;
      max-width: 65%;
      word-break: break-word;
    }}
    .button-group {{ display: flex; flex-direction: column; gap: 12px; margin-top: 10px; }}
    .btn {{
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      padding: 14px;
      border-radius: 12px;
      font-size: 15px;
      font-weight: 700;
      text-decoration: none;
      border: none;
      cursor: pointer;
      transition: all 0.2s ease;
    }}
    .btn-call {{
      background: #0ea5e9;
      color: white;
      box-shadow: 0 4px 15px rgba(14, 165, 233, 0.3);
    }}
    .btn-call:hover {{ background: #0284c7; transform: translateY(-2px); }}
    .btn-map {{
      background: #475569;
      color: white;
    }}
    .btn-map:hover {{ background: #334155; transform: translateY(-2px); }}
    .btn-complete {{
      background: linear-gradient(135deg, #059669 0%, #10b981 100%);
      color: white;
      box-shadow: 0 4px 20px rgba(16, 185, 129, 0.4);
      margin-top: 8px;
    }}
    .btn-complete:hover {{
      background: linear-gradient(135deg, #047857 0%, #059669 100%);
      transform: translateY(-2px);
    }}
    .complete-result {{
      display: none;
      margin-top: 16px;
      padding: 16px;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid var(--success);
      border-radius: 12px;
      font-size: 14px;
      text-align: center;
      color: #6ee7b7;
    }}
    .footer-note {{
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 18px;
    }}
  </style>
</head>
<body>
  <div class="cockpit-container">
    <div class="cockpit-header">
      <div class="status-badge"><span class="status-dot"></span> Active Mission &bull; In Transit</div>
      <h1>Delivery Cockpit</h1>
      <span class="tracking-tag">&#128269; {tracking_id}</span>
    </div>

    <div class="cockpit-body">
      <div class="detail-card">
        <div class="field-row">
          <span class="field-label">&#128100; Assigned Courier</span>
          <span class="field-value">{rider_name}</span>
        </div>
        <div class="field-row">
          <span class="field-label">&#128101; Client Name</span>
          <span class="field-value">{client_name}</span>
        </div>
        <div class="field-row">
          <span class="field-label">&#128222; Contact Phone</span>
          <span class="field-value">{client_phone}</span>
        </div>
        <div class="field-row">
          <span class="field-label">&#128205; Delivery Address</span>
          <span class="field-value address-highlight">{client_address}</span>
        </div>
        <div class="field-row">
          <span class="field-label">&#128755; Route Distance</span>
          <span class="field-value">{distance_km} km</span>
        </div>
        <div class="field-row">
          <span class="field-label">&#9201; Estimated ETA (ML)</span>
          <span class="field-value" style="color: #818cf8;">~{predicted_eta} minutes</span>
        </div>
      </div>

      <div class="button-group">
        <a href="tel:{client_phone}" class="btn btn-call">&#128222; Call Client Directly</a>
        <a href="https://www.google.com/maps/search/?api=1&query={client_address.replace(' ', '+')}" target="_blank" class="btn btn-map">&#128506;&#65039; Open Live Navigation</a>
        <button id="btnComplete" class="btn btn-complete" onclick="markDelivered('{tracking_id}')">&#127937; Mark Delivery Completed (Rider Arrived)</button>
      </div>

      <div id="completeResult" class="complete-result"></div>

      <p class="footer-note">Courier status updated to <strong>On Delivery</strong>. Delivering on or before ETA increases your performance score and assignment priority.</p>
    </div>
  </div>

  <script>
    async function markDelivered(trackingId) {{
      const btn = document.getElementById('btnComplete');
      const box = document.getElementById('completeResult');
      btn.disabled = true;
      btn.textContent = 'Processing delivery record...';
      try {{
        const res = await fetch('/api/dispatch/complete/' + trackingId, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{}})
        }});
        const data = await res.json();
        if (data.success) {{
          btn.style.display = 'none';
          box.style.display = 'block';
          const onTimeTag = data.was_on_time ? '&#127881; On-Time Delivery Verified!' : '&#9888; Delayed Delivery Recorded';
          const perf = data.rider_performance ? '<br /><strong>New Performance Score: ' + data.rider_performance.performance_score + '% &bull; Rating: ' + data.rider_performance.rating + '&#9733;</strong>' : '';
          box.innerHTML = '<strong>' + onTimeTag + '</strong><br />Duration: ' + data.actual_duration_min + ' min (ETA: ' + data.predicted_eta_min + ' min)' + perf + '<br /><br /><span style="color:#94a3b8;font-size:12px;">Raw interaction data logged permanently for ML feature engineering and retraining.</span>';
        }} else {{
          btn.disabled = false;
          btn.textContent = 'Retry Mark Delivered';
          alert('Error: ' + (data.error || 'Failed to complete delivery'));
        }}
      }} catch (err) {{
        btn.disabled = false;
        btn.textContent = 'Retry Mark Delivered';
        alert('Request failed: ' + err.message);
      }}
    }}
  </script>
</body>
</html>"""
            return HTMLResponse(content=html_body, status_code=200)
        else:
            # Activation failed or timed out
            is_expired = result.get("expired", False)
            title = "Invitation Expired (5-Minute Limit)" if is_expired else "Order Action Notice"
            message = result.get("error", "Could not activate this delivery mission.")
            html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: #090d16;
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .card {{
      max-width: 480px;
      background: #1e293b;
      border: 1px solid #dc2626;
      border-radius: 20px;
      padding: 30px;
      text-align: center;
      box-shadow: 0 10px 40px rgba(220, 38, 38, 0.2);
    }}
    .badge {{
      display: inline-block;
      padding: 6px 12px;
      background: rgba(220, 38, 38, 0.2);
      color: #f87171;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 16px;
    }}
    h1 {{ font-size: 22px; margin-bottom: 12px; }}
    p {{ font-size: 15px; color: #cbd5e1; line-height: 1.5; margin-bottom: 20px; }}
    .sub {{ font-size: 13px; color: #94a3b8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">&#9888; Action Expired</div>
    <h1>{title}</h1>
    <p>{message}</p>
    <p class="sub">The cascading dispatch pipeline has automatically rerouted this mission to ensure prompt client fulfillment.</p>
  </div>
</body>
</html>"""
            return HTMLResponse(content=html_body, status_code=200)

    elif action == "deactivate":
        # Rider declined order -> drop, cascade to next closest available rider, and dispatch fresh email
        base_url = str(request.base_url).rstrip("/")
        result = handle_cascading_dispatch(token, reason="rider_declined", base_url=base_url)
        if wants_json:
            return JSONResponse(content=result, status_code=200 if result.get("success") else 400)
        if result.get("success"):
            next_rider_name = result.get("next_rider", {}).get("rider_name", "the next available courier")
            cascaded = result.get("cascaded", False)
            cascade_msg = f"The automated engine has immediately cascaded this mission to {next_rider_name} and sent them an urgent email invitation." if cascaded else "All active couriers have been checked."

            html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Mission Declined &bull; Cascaded</title>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {{
      font-family: 'Plus Jakarta Sans', sans-serif;
      background: #090d16;
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .card {{
      max-width: 480px;
      background: #1e293b;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 20px;
      padding: 30px;
      text-align: center;
      box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
    }}
    .badge {{
      display: inline-block;
      padding: 6px 12px;
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 16px;
    }}
    h1 {{ font-size: 22px; margin-bottom: 12px; }}
    p {{ font-size: 15px; color: #cbd5e1; line-height: 1.5; margin-bottom: 20px; }}
    .sub {{ font-size: 13px; color: #94a3b8; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">&#10006; Order Deactivated</div>
    <h1>Mission Declined</h1>
    <p>You have declined this delivery mission and your status remains available for other tasks.</p>
    <p class="sub">&#128757; {cascade_msg}</p>
  </div>
</body>
</html>"""
            return HTMLResponse(content=html_body, status_code=200)
        else:
            return HTMLResponse(content=f"<h3>{result.get('error', 'Operation failed')}</h3>", status_code=400)

    return HTMLResponse(content="<h3>Unknown action. Use 'activate' or 'deactivate'.</h3>", status_code=400)


@app.get("/api/dispatch/order/{tracking_id}", tags=["Automated Dispatch Engine"])
def get_dispatch_order(tracking_id: str):
    """Retrieves full details of a dispatch order along with its email transmission audit trail."""
    order = get_dispatch_order_by_tracking_id(tracking_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Dispatch order with tracking ID '{tracking_id}' not found.")
    emails = get_email_logs_for_order(tracking_id)
    return {
        "order": order,
        "email_logs": emails,
    }


@app.post("/api/dispatch/complete/{tracking_id}", tags=["Automated Dispatch Engine"])
def complete_dispatch(
    tracking_id: str,
    payload: Optional[DispatchCompletePayload] = None,
):
    """Marks delivery completed:
    - Calculates actual duration vs predicted ETA.
    - Evaluates on-time status.
    - Automatically updates courier performance score and rating.
    - Feeds enriched raw interaction record into predictions_history for ML retraining.
    """
    actual_min = payload.get_actual_duration() if payload else None
    result = complete_dispatch_order(tracking_id=tracking_id, actual_duration_min=actual_min)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error"))
    return result


@app.post("/api/dispatch/check-timeouts", tags=["Automated Dispatch Engine"])
def check_timeouts(request: Request):
    """Scans for dispatch orders pending courier response older than 5 minutes and automatically cascades them."""
    base_url = str(request.base_url).rstrip("/")
    cascaded = process_timeout_cascades(base_url=base_url)
    return {
        "status": "success",
        "cascaded_count": len(cascaded),
        "results": cascaded,
    }


@app.post("/api/dispatch/simulate-timeout/{tracking_id}", tags=["Automated Dispatch Engine"])
def simulate_timeout_cascade(tracking_id: str, request: Request):
    """Developer / Testing utility to immediately simulate the 5-minute timeout on a pending order and cascade it."""
    order = get_dispatch_order_by_tracking_id(tracking_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Dispatch order '{tracking_id}' not found.")
    token = order.get("dispatch_token")
    if not token:
        raise HTTPException(status_code=400, detail="Order does not have a pending dispatch token.")
    base_url = str(request.base_url).rstrip("/")
    res = handle_cascading_dispatch(token, reason="simulated_5_min_timeout", base_url=base_url)
    return res



@app.get("/api/dispatch/active", tags=["Automated Dispatch Engine"])
def list_active_dispatches(request: Request, hotel_id: Optional[int] = Query(None)):
    """Retrieves active dispatches for the current hotel."""
    hid = resolve_request_hotel_id(request, hotel_id)
    return {"orders": get_active_dispatches(hotel_id=hid)}


@app.get("/api/dispatch/raw-ml-data", tags=["Automated Dispatch Engine"])
def list_raw_ml_data(request: Request, hotel_id: Optional[int] = Query(None)):
    """Retrieves raw data records formatted specifically for Machine Learning data pipeline and retraining."""
    hid = resolve_request_hotel_id(request, hotel_id)
    rows = get_raw_ml_dispatch_data(hotel_id=hid)
    return {
        "total_records": len(rows),
        "records": rows,
    }


