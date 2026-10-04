"""Custom Pipeline & Batch Processing engine for Hotel and Merchant datasets.

Enables:
1. Batch ETA predictions on uploaded Excel (.xlsx) / CSV files with downloadable output.
2. Automated custom model retraining on merchant historical delivery data.
3. Automated data validation, profiling, and evaluation comparison.
"""

import io
import os
import uuid
import json
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, cross_val_score

from src.preprocess import (
    RAW_FEATURE_NAMES,
    TARGET_COLUMN,
    WEATHER_CATEGORIES,
    TRAFFIC_LEVEL_CATEGORIES,
    TIME_OF_DAY_CATEGORIES,
    VEHICLE_TYPE_CATEGORIES,
    build_production_pipeline,
)
from src.train import calculate_regression_metrics, compute_mean_baseline, save_production_pipeline
from src.predict import predict_delivery_time, load_production_pipeline

# Directory for custom hotel models
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
CUSTOM_MODEL_PATH = os.path.join(MODELS_DIR, "custom_hotel_pipeline.joblib")
CUSTOM_SPEC_PATH = os.path.join(MODELS_DIR, "custom_hotel_spec.json")

# In-memory store for generated batch export files
_BATCH_RESULTS_STORE: Dict[str, Tuple[str, bytes]] = {}


DEFAULT_FEATURE_VALUES: Dict[str, Any] = {
    "Distance_km": 5.0,
    "Weather": "Clear",
    "Traffic_Level": "Medium",
    "Time_of_Day": "Evening",
    "Vehicle_Type": "Scooter",
    "Preparation_Time_min": 15.0,
    "Courier_Experience_yrs": 3.0,
}


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizes column names by stripping spaces, removing punctuation, and fuzzy-matching synonyms."""
    df = df.copy()
    col_mapping = {}

    alias_map = {
        "Distance_km": [
            "distance_km", "distance", "dist", "distance (km)", "distance(km)",
            "km", "trip_distance", "delivery_distance", "dist_km", "distance in km"
        ],
        "Weather": [
            "weather", "weather_condition", "weather condition", "climate", "conditions",
            "weather_type", "weather_status", "sky"
        ],
        "Traffic_Level": [
            "traffic_level", "traffic level", "trafficlevel", "traffic", "traffic_condition",
            "traffic condition", "congestion", "road_traffic", "traffic_status"
        ],
        "Time_of_Day": [
            "time_of_day", "time of day", "timeofday", "time", "order_time", "order time",
            "timing", "shift", "tod", "day_time", "daytime", "period", "hour_slot"
        ],
        "Vehicle_Type": [
            "vehicle_type", "vehicle type", "vehicletype", "vehicle", "transport",
            "transport_type", "transport type", "fleet", "mode", "delivery_vehicle",
            "delivery_mode", "bike_or_car", "ride_type", "vehicle_mode"
        ],
        "Preparation_Time_min": [
            "preparation_time_min", "preparation_time", "preparation time", "prep_time",
            "prep time", "preptime", "prep_time_min", "kitchen_time", "kitchen time",
            "prep (min)", "prep(min)", "preparation (min)", "prep_duration", "cook_time",
            "cooking_time", "prep_minutes", "food_prep_time"
        ],
        "Courier_Experience_yrs": [
            "courier_experience_yrs", "courier_experience", "courier experience",
            "courierexperience", "experience", "experience_yrs", "experience (years)",
            "experience(yrs)", "experience(years)", "rider_experience", "rider experience",
            "driver_experience", "driver experience", "rider_exp", "courier_exp",
            "years_of_experience", "years_experience", "exp", "courier_years", "driver_exp"
        ],
        "Delivery_Time_min": [
            "delivery_time_min", "delivery_time", "delivery time", "deliverytime",
            "delivery_duration", "delivery duration", "duration", "time_min", "time taken",
            "time_taken", "minutes", "actual_delivery_time", "total_delivery_time",
            "delivery_time(min)", "delivery_time (min)", "trip_time", "eta_min",
            "target", "actual_time", "duration_min"
        ],
    }

    # Flatten alias map
    lookup = {}
    for canon, aliases in alias_map.items():
        for a in aliases:
            lookup[a.lower().replace(" ", "").replace("_", "").replace("-", "")] = canon

    for col in df.columns:
        cleaned_col = str(col).strip()
        simplified = (
            cleaned_col.lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
            .replace("(", "")
            .replace(")", "")
            .replace(".", "")
        )
        if simplified in lookup:
            canon = lookup[simplified]
            if canon not in col_mapping.values():
                col_mapping[col] = canon
            else:
                col_mapping[col] = cleaned_col
        else:
            # Substring heuristic checks if exact match didn't catch it
            if "dist" in simplified and "Distance_km" not in col_mapping.values():
                col_mapping[col] = "Distance_km"
            elif "traffic" in simplified and "Traffic_Level" not in col_mapping.values():
                col_mapping[col] = "Traffic_Level"
            elif "weather" in simplified and "Weather" not in col_mapping.values():
                col_mapping[col] = "Weather"
            elif ("prep" in simplified or "cook" in simplified) and "Preparation_Time_min" not in col_mapping.values():
                col_mapping[col] = "Preparation_Time_min"
            elif ("courier" in simplified or "rider" in simplified or "driver" in simplified or "exp" in simplified) and "Courier_Experience_yrs" not in col_mapping.values():
                col_mapping[col] = "Courier_Experience_yrs"
            elif ("vehic" in simplified or "transport" in simplified or "fleet" in simplified) and "Vehicle_Type" not in col_mapping.values():
                col_mapping[col] = "Vehicle_Type"
            elif ("deliver" in simplified or "duration" in simplified) and "Delivery_Time_min" not in col_mapping.values():
                col_mapping[col] = "Delivery_Time_min"
            else:
                col_mapping[col] = cleaned_col

    df.rename(columns=col_mapping, inplace=True)

    # Strictly deduplicate any columns to guarantee 1D Series access
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

    return df


def auto_impute_missing_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Intelligently detects missing predictor columns and populates them with standard operational defaults."""
    df = df.copy()
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated(keep="first")]

    imputed_cols: List[str] = []

    for col in RAW_FEATURE_NAMES:
        if col not in df.columns:
            df[col] = DEFAULT_FEATURE_VALUES[col]
            imputed_cols.append(col)
        else:
            col_data = df[col]
            if isinstance(col_data, pd.DataFrame):
                col_data = col_data.iloc[:, 0]
                df[col] = col_data
            df[col] = df[col].fillna(DEFAULT_FEATURE_VALUES[col])

    return df, imputed_cols


def load_dataframe_from_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Loads a DataFrame from raw bytes supporting both Excel (.xlsx, .xls) and CSV (.csv)."""
    filename_lower = filename.lower()
    try:
        if filename_lower.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename_lower.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            # Fallback attempt CSV then Excel
            try:
                df = pd.read_csv(io.BytesIO(file_bytes))
            except Exception:
                df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as exc:
        raise ValueError(f"Failed to read file '{filename}'. Ensure it is a valid CSV or Excel (.xlsx) spreadsheet: {exc}")

    return normalize_column_names(df)


def generate_sample_template(include_target: bool = False, file_format: str = "xlsx") -> bytes:
    """Generates a clean sample template (Excel or CSV) for merchants to populate."""
    sample_records = [
        {
            "Distance_km": 5.2,
            "Weather": "Clear",
            "Traffic_Level": "Low",
            "Time_of_Day": "Morning",
            "Vehicle_Type": "Bike",
            "Preparation_Time_min": 12.0,
            "Courier_Experience_yrs": 4.0,
        },
        {
            "Distance_km": 11.8,
            "Weather": "Rainy",
            "Traffic_Level": "High",
            "Time_of_Day": "Evening",
            "Vehicle_Type": "Car",
            "Preparation_Time_min": 25.0,
            "Courier_Experience_yrs": 2.5,
        },
        {
            "Distance_km": 7.4,
            "Weather": "Clear",
            "Traffic_Level": "Medium",
            "Time_of_Day": "Afternoon",
            "Vehicle_Type": "Scooter",
            "Preparation_Time_min": 15.0,
            "Courier_Experience_yrs": 5.0,
        },
    ]

    if include_target:
        sample_records = [
            {"Distance_km": 5.2, "Weather": "Clear", "Traffic_Level": "Low", "Time_of_Day": "Morning", "Vehicle_Type": "Bike", "Preparation_Time_min": 12.0, "Courier_Experience_yrs": 4.0, "Delivery_Time_min": 32.0},
            {"Distance_km": 11.8, "Weather": "Rainy", "Traffic_Level": "High", "Time_of_Day": "Evening", "Vehicle_Type": "Car", "Preparation_Time_min": 25.0, "Courier_Experience_yrs": 2.5, "Delivery_Time_min": 68.0},
            {"Distance_km": 7.4, "Weather": "Clear", "Traffic_Level": "Medium", "Time_of_Day": "Afternoon", "Vehicle_Type": "Scooter", "Preparation_Time_min": 15.0, "Courier_Experience_yrs": 5.0, "Delivery_Time_min": 42.0},
            {"Distance_km": 3.1, "Weather": "Clear", "Traffic_Level": "Low", "Time_of_Day": "Night", "Vehicle_Type": "Scooter", "Preparation_Time_min": 10.0, "Courier_Experience_yrs": 3.0, "Delivery_Time_min": 24.0},
            {"Distance_km": 8.9, "Weather": "Foggy", "Traffic_Level": "Medium", "Time_of_Day": "Evening", "Vehicle_Type": "Car", "Preparation_Time_min": 20.0, "Courier_Experience_yrs": 1.5, "Delivery_Time_min": 55.0},
            {"Distance_km": 4.5, "Weather": "Clear", "Traffic_Level": "Low", "Time_of_Day": "Morning", "Vehicle_Type": "Scooter", "Preparation_Time_min": 14.0, "Courier_Experience_yrs": 6.0, "Delivery_Time_min": 29.0},
            {"Distance_km": 14.2, "Weather": "Stormy", "Traffic_Level": "High", "Time_of_Day": "Night", "Vehicle_Type": "Car", "Preparation_Time_min": 30.0, "Courier_Experience_yrs": 4.0, "Delivery_Time_min": 85.0},
            {"Distance_km": 6.0, "Weather": "Rainy", "Traffic_Level": "Medium", "Time_of_Day": "Afternoon", "Vehicle_Type": "Bike", "Preparation_Time_min": 18.0, "Courier_Experience_yrs": 2.0, "Delivery_Time_min": 48.0},
            {"Distance_km": 2.2, "Weather": "Clear", "Traffic_Level": "Low", "Time_of_Day": "Morning", "Vehicle_Type": "Scooter", "Preparation_Time_min": 10.0, "Courier_Experience_yrs": 3.5, "Delivery_Time_min": 19.0},
            {"Distance_km": 9.5, "Weather": "Clear", "Traffic_Level": "High", "Time_of_Day": "Evening", "Vehicle_Type": "Scooter", "Preparation_Time_min": 22.0, "Courier_Experience_yrs": 5.5, "Delivery_Time_min": 54.0},
            {"Distance_km": 12.0, "Weather": "Windy", "Traffic_Level": "Medium", "Time_of_Day": "Night", "Vehicle_Type": "Car", "Preparation_Time_min": 25.0, "Courier_Experience_yrs": 7.0, "Delivery_Time_min": 60.0},
            {"Distance_km": 5.8, "Weather": "Clear", "Traffic_Level": "Low", "Time_of_Day": "Afternoon", "Vehicle_Type": "Scooter", "Preparation_Time_min": 15.0, "Courier_Experience_yrs": 4.5, "Delivery_Time_min": 34.0},
            {"Distance_km": 8.0, "Weather": "Rainy", "Traffic_Level": "High", "Time_of_Day": "Morning", "Vehicle_Type": "Car", "Preparation_Time_min": 20.0, "Courier_Experience_yrs": 3.0, "Delivery_Time_min": 52.0},
            {"Distance_km": 3.8, "Weather": "Clear", "Traffic_Level": "Low", "Time_of_Day": "Night", "Vehicle_Type": "Bike", "Preparation_Time_min": 12.0, "Courier_Experience_yrs": 2.0, "Delivery_Time_min": 28.0},
            {"Distance_km": 10.5, "Weather": "Foggy", "Traffic_Level": "Medium", "Time_of_Day": "Evening", "Vehicle_Type": "Scooter", "Preparation_Time_min": 24.0, "Courier_Experience_yrs": 5.0, "Delivery_Time_min": 58.0},
        ]

    df = pd.DataFrame(sample_records)

    buffer = io.BytesIO()
    if file_format.lower() == "csv":
        df.to_csv(buffer, index=False)
    else:
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="DeliveryOrders", index=False)

    return buffer.getvalue()


def process_batch_predictions(
    file_bytes: bytes,
    filename: str,
    use_custom_model: bool = False,
) -> Tuple[Dict[str, Any], str]:
    """Runs batch predictions on an uploaded dataset and prepares a downloadable file."""
    df = load_dataframe_from_bytes(file_bytes, filename)

    # Automatically impute any missing predictor columns with operational defaults
    df, _ = auto_impute_missing_features(df)

    # Determine model to use
    model_path = CUSTOM_MODEL_PATH if (use_custom_model and os.path.exists(CUSTOM_MODEL_PATH)) else None

    # Compute predictions
    predictions = predict_delivery_time(df, model_path=model_path)

    # Append results
    df["Predicted_Delivery_Time_min"] = predictions

    # Add business delay risk flag
    def categorize_risk(mins: float) -> str:
        if mins <= 35:
            return "Fast / Low Risk"
        elif mins <= 50:
            return "Standard / Medium Risk"
        else:
            return "High Delay Risk"

    df["Delivery_Status_Risk"] = df["Predicted_Delivery_Time_min"].apply(categorize_risk)

    # Summary analytics
    total_orders = int(len(df))
    avg_predicted_min = round(float(df["Predicted_Delivery_Time_min"].mean()), 2)
    min_predicted_min = round(float(df["Predicted_Delivery_Time_min"].min()), 2)
    max_predicted_min = round(float(df["Predicted_Delivery_Time_min"].max()), 2)
    high_risk_count = int((df["Delivery_Status_Risk"] == "High Delay Risk").sum())
    fast_delivery_count = int((df["Delivery_Status_Risk"] == "Fast / Low Risk").sum())

    # Generate output file in same format as upload
    out_buffer = io.BytesIO()
    out_filename = f"predicted_{os.path.splitext(filename)[0]}.xlsx"

    with pd.ExcelWriter(out_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Predictions", index=False)

    out_bytes = out_buffer.getvalue()

    # Store for download
    download_id = str(uuid.uuid4())[:8]
    _BATCH_RESULTS_STORE[download_id] = (out_filename, out_bytes)

    # Convert top 10 preview rows to records
    preview_df = df.head(10).fillna("")
    preview_records = preview_df.to_dict(orient="records")

    summary = {
        "download_id": download_id,
        "filename": out_filename,
        "total_orders": total_orders,
        "avg_delivery_time_min": avg_predicted_min,
        "min_delivery_time_min": min_predicted_min,
        "max_delivery_time_min": max_predicted_min,
        "high_risk_count": high_risk_count,
        "fast_delivery_count": fast_delivery_count,
        "model_used": "Custom Hotel Pipeline" if model_path else "Default Production Pipeline",
        "preview": preview_records,
    }

    return summary, download_id


def get_batch_download(download_id: str) -> Optional[Tuple[str, bytes]]:
    """Retrieves generated batch result file by download ID."""
    return _BATCH_RESULTS_STORE.get(download_id)


def execute_custom_retraining(
    file_bytes: bytes,
    filename: str,
    hotel_name: str = "Merchant / Hotel",
) -> Dict[str, Any]:
    """Automated end-to-end retraining pipeline on merchant historical delivery data."""
    df = load_dataframe_from_bytes(file_bytes, filename)

    # 1. Verification of features and target
    if TARGET_COLUMN not in df.columns:
        raise ValueError(
            f"The uploaded historical training dataset must contain the target column '{TARGET_COLUMN}'. "
            "Please ensure your historical records include delivery times in minutes."
        )

    # 2. Automatically impute any missing predictor columns with operational defaults
    df, imputed_features = auto_impute_missing_features(df)

    # Ensure target column is strictly a 1D Series
    target_data = df[TARGET_COLUMN]
    if isinstance(target_data, pd.DataFrame):
        target_data = target_data.iloc[:, 0]
    df[TARGET_COLUMN] = pd.to_numeric(target_data, errors="coerce")

    # Remove rows where target is missing or non-positive
    df = df.dropna(subset=[TARGET_COLUMN]).copy()
    df = df[df[TARGET_COLUMN] > 0].copy()

    if len(df) < 10:
        raise ValueError(
            f"Insufficient valid training samples ({len(df)} rows). "
            "Please provide at least 10 historical delivery records to train a model."
        )

    # Ensure every predictor column is strictly a 1D Series
    for col in RAW_FEATURE_NAMES:
        if isinstance(df[col], pd.DataFrame):
            df[col] = df[col].iloc[:, 0]

    total_samples = len(df)
    X = df[RAW_FEATURE_NAMES].copy()
    y_raw = df[TARGET_COLUMN]
    if isinstance(y_raw, pd.DataFrame):
        y_raw = y_raw.iloc[:, 0]
    y = pd.Series(y_raw, dtype=float).copy()

    # 2. Train / Test Split (80% Train, 20% Test, minimum 2 test samples)
    test_size = max(2, int(total_samples * 0.20))
    if test_size >= total_samples:
        test_size = 1
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42
    )

    # 3. Naive Baseline Calculation on Training Set
    _, y_pred_baseline = compute_mean_baseline(y_train, len(y_test))
    baseline_metrics = calculate_regression_metrics(y_test, y_pred_baseline)

    # 4. Model Training via production pipeline factory
    pipeline = build_production_pipeline()
    pipeline.fit(X_train, y_train)

    # 5. Holdout Evaluation
    y_pred_test = pipeline.predict(X_test)
    test_metrics = calculate_regression_metrics(y_test, y_pred_test)

    # 6. Cross-Validation
    cv_folds = min(5, max(2, len(X_train) // 3))
    if cv_folds >= 2 and len(X_train) >= cv_folds:
        cv_scores = cross_val_score(
            pipeline, X_train, y_train, cv=cv_folds, scoring="neg_mean_absolute_error"
        )
        cv_mae = round(float(-cv_scores.mean()), 4)
    else:
        cv_mae = round(float(test_metrics["mae"]), 4)

    # 7. Baseline Lift
    if baseline_metrics.get("mae", 0) > 0:
        mae_improvement_pct = round(
            ((baseline_metrics["mae"] - test_metrics["mae"]) / baseline_metrics["mae"]) * 100, 2
        )
    else:
        mae_improvement_pct = 0.0

    # 8. Persist Custom Pipeline Artifact & Metadata
    save_production_pipeline(pipeline, filepath=CUSTOM_MODEL_PATH)

    spec = {
        "hotel_name": hotel_name,
        "source_filename": filename,
        "total_samples": total_samples,
        "train_samples": len(X_train),
        "test_samples": len(X_test),
        "imputed_features": imputed_features,
        "baseline_metrics": baseline_metrics,
        "custom_model_metrics": test_metrics,
        "cv_mae": cv_mae,
        "mae_improvement_pct": mae_improvement_pct,
        "trained_model_path": CUSTOM_MODEL_PATH,
    }

    with open(CUSTOM_SPEC_PATH, "w") as f:
        json.dump(spec, f, indent=2)

    success_msg = f"Successfully trained and saved custom model for '{hotel_name}'!"
    if imputed_features:
        success_msg += f" (Auto-imputed optional columns with operational defaults: {', '.join(imputed_features)})"

    return {
        "status": "success",
        "message": success_msg,
        "imputed_features": imputed_features,
        "metrics": {
            "total_samples": total_samples,
            "train_samples": len(X_train),
            "test_samples": len(X_test),
            "baseline_mae": baseline_metrics["mae"],
            "model_mae": test_metrics["mae"],
            "model_rmse": test_metrics["rmse"],
            "model_r2": test_metrics["r2"],
            "cv_mae": cv_mae,
            "mae_improvement_vs_baseline_pct": f"{mae_improvement_pct}%",
        },
        "model_path": CUSTOM_MODEL_PATH,
    }


def get_custom_model_status() -> Dict[str, Any]:
    """Returns active availability info of the custom hotel model."""
    custom_exists = os.path.exists(CUSTOM_MODEL_PATH)
    spec_data = {}
    if custom_exists and os.path.exists(CUSTOM_SPEC_PATH):
        try:
            with open(CUSTOM_SPEC_PATH, "r") as f:
                spec_data = json.load(f)
        except Exception:
            pass

    return {
        "custom_model_available": custom_exists,
        "custom_model_path": CUSTOM_MODEL_PATH if custom_exists else None,
        "spec": spec_data,
    }
