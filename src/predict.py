"""Inference and prediction module for Delivery Time Prediction.

This module provides production-ready prediction capabilities for real-time
inference and API serving. It accepts raw delivery parameters, applies input
validation, passes the data through the serialized end-to-end ML pipeline
(feature engineering -> imputation -> scaling -> encoding -> regression),
and returns estimated delivery durations in minutes.

Design Principles:
- Anti-Leakage / Zero-Skew: Uses the exact serialized Pipeline fitted during training.
- Decoupled: Independent of training notebooks and scripts.
- Type-Safe: Robust validation of raw inputs with informative error messages.
- Production-Optimized: In-memory pipeline caching for sub-millisecond latency.
"""

import os
from typing import Dict, Any, Union, List, Optional
import pandas as pd
import numpy as np
import joblib
from sklearn.pipeline import Pipeline

from src.preprocess import validate_raw_input, RAW_FEATURE_NAMES

# Default artifact path (supports optional environment override for deployment)
DEFAULT_MODEL_PATH: str = os.getenv(
    "MODEL_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "models",
        "delivery_time_pipeline.joblib",
    ),
)


# Global in-memory cache for singleton loading
_CACHED_PIPELINE: Optional[Pipeline] = None
_CACHED_PATH: Optional[str] = None


def load_production_pipeline(filepath: Optional[str] = None) -> Pipeline:
    """Loads and caches the serialized production pipeline from disk.
    
    Caches the loaded pipeline in memory to eliminate redundant disk I/O on
    subsequent prediction requests (critical for low-latency web API endpoints).
    
    Args:
        filepath: Optional path to the serialized joblib file. Defaults to
            'models/delivery_time_pipeline.joblib'.
            
    Returns:
        Loaded Scikit-Learn Pipeline instance.
        
    Raises:
        FileNotFoundError: If the specified model artifact does not exist.
    """
    global _CACHED_PIPELINE, _CACHED_PATH
    
    target_path = filepath if filepath is not None else DEFAULT_MODEL_PATH
    target_path = os.path.abspath(target_path)
    
    if _CACHED_PIPELINE is not None and _CACHED_PATH == target_path:
        return _CACHED_PIPELINE
        
    if not os.path.exists(target_path):
        raise FileNotFoundError(
            f"Production pipeline artifact not found at: '{target_path}'. "
            "Please ensure Phase 15 model serialization has been executed."
        )
        
    pipeline = joblib.load(target_path)
    _CACHED_PIPELINE = pipeline
    _CACHED_PATH = target_path
    return pipeline


def predict_delivery_time(
    input_data: Union[Dict[str, Any], List[Dict[str, Any]], pd.DataFrame],
    model_path: Optional[str] = None,
) -> Union[float, List[float]]:
    """Generates delivery time predictions from raw order parameters.
    
    Expected Raw Input Features:
        - Distance_km (float): Distance from restaurant to customer in kilometers (>0).
        - Weather (str): Weather conditions ('Clear', 'Rainy', 'Foggy', 'Snowy', 'Windy').
        - Traffic_Level (str): Real-time traffic congestion ('Low', 'Medium', 'High').
        - Time_of_Day (str): Time of delivery dispatch ('Morning', 'Afternoon', 'Evening', 'Night').
        - Vehicle_Type (str): Delivery mode ('Bike', 'Scooter', 'Car').
        - Preparation_Time_min (float): Kitchen food preparation time in minutes (>=0).
        - Courier_Experience_yrs (float): Courier tenure in years (>=0).
        
    Example Usage:
        >>> order = {
        ...     "Distance_km": 8.5,
        ...     "Weather": "Clear",
        ...     "Traffic_Level": "Medium",
        ...     "Time_of_Day": "Evening",
        ...     "Vehicle_Type": "Scooter",
        ...     "Preparation_Time_min": 15.0,
        ...     "Courier_Experience_yrs": 3.0
        ... }
        >>> predict_delivery_time(order)
        49.93
        
    Args:
        input_data: Single dictionary, list of dictionaries, or pandas DataFrame
            containing raw delivery attributes.
        model_path: Optional custom path to a serialized pipeline artifact.
        
    Returns:
        Predicted delivery duration in minutes:
            - float (rounded to 2 decimals) if single dict input.
            - List[float] (rounded to 2 decimals) if batch list/DataFrame input.
            
    Raises:
        ValueError: If inputs fail schema validation or contain out-of-range values.
        FileNotFoundError: If the model pipeline artifact cannot be located.
    """
    # 1. Input validation & DataFrame normalization
    validated_df = validate_raw_input(input_data)
    
    # 2. Pipeline retrieval
    pipeline = load_production_pipeline(filepath=model_path)
    
    # 3. Prediction generation
    raw_predictions = pipeline.predict(validated_df)
    
    # 4. Format output
    if isinstance(input_data, dict):
        return round(float(raw_predictions[0]), 2)
    else:
        return [round(float(p), 2) for p in raw_predictions]
