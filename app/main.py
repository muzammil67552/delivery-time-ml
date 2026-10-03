"""FastAPI application for Delivery Time Prediction service.

Exposes RESTful endpoints for health status, metadata, and real-time delivery
duration inference using the trained serialized Scikit-Learn pipeline from Phase 15.
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.schemas import (
    DeliveryPredictionRequest,
    DeliveryPredictionResponse,
    HealthResponse,
    RootResponse,
)
from src.predict import load_production_pipeline, predict_delivery_time

# Static files directory for Phase 17 frontend
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager that warms and caches the ML pipeline on startup."""
    try:
        # Pre-load and cache the production pipeline into memory once
        pipeline = load_production_pipeline()
        app.state.pipeline_loaded = pipeline is not None
        app.state.load_error = None
    except Exception as exc:
        app.state.pipeline_loaded = False
        app.state.load_error = str(exc)
    yield


app = FastAPI(
    title="Delivery Time Prediction API",
    description="Production-ready REST API for estimating food delivery times.",
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


@app.get("/", response_model=RootResponse, tags=["General"])
def read_root() -> Dict[str, str]:
    """Root endpoint confirming that the Delivery Time Prediction API is running."""
    return {
        "message": "Delivery Time Prediction API is running",
        "status": "online",
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
def health_check() -> Dict[str, Any]:
    """Health check endpoint verifying API and model pipeline operational status."""
    is_loaded = getattr(app.state, "pipeline_loaded", False)
    if not is_loaded:
        try:
            pipeline = load_production_pipeline()
            is_loaded = pipeline is not None
        except Exception:
            is_loaded = False

    return {
        "status": "healthy" if is_loaded else "degraded",
        "model_loaded": is_loaded,
    }


@app.post(
    "/predict",
    response_model=DeliveryPredictionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Prediction"],
)
def predict(request: DeliveryPredictionRequest) -> Dict[str, float]:
    """Accepts raw delivery features, validates input schema, and returns predicted duration in minutes."""
    try:
        # Convert validated Pydantic model to dictionary
        input_data = request.model_dump()

        # Pass raw input directly to the production prediction pipeline
        predicted_time = predict_delivery_time(input_data)

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


@app.get("/ui", include_in_schema=False)
def serve_ui():
    """Serves the simple frontend interface for interactive manual predictions."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Frontend interface not found.")


@app.get("/style.css", include_in_schema=False)
def serve_css():
    """Directly serves the frontend stylesheet for root-relative requests."""
    css_path = os.path.join(STATIC_DIR, "style.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS file not found.")


@app.get("/script.js", include_in_schema=False)
def serve_js():
    """Directly serves the frontend JavaScript for root-relative requests."""
    js_path = os.path.join(STATIC_DIR, "script.js")
    if os.path.exists(js_path):
        return FileResponse(js_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JavaScript file not found.")

