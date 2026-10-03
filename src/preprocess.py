"""Data preprocessing and feature engineering module for Delivery Time Prediction.

This module provides reusable preprocessing pipelines, custom feature transformers,
and serialization utilities following Scikit-Learn standards.
"""

import os
from typing import List, Tuple, Dict, Any, Optional
import pandas as pd
import numpy as np
import joblib

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder
from sklearn.model_selection import train_test_split

# Constant definitions
TARGET_COLUMN: str = "Delivery_Time_min"
ID_COLUMN: str = "Order_ID"

# Base 7-feature definitions (Phase 4)
NUMERICAL_FEATURES: List[str] = [
    "Distance_km",
    "Preparation_Time_min",
    "Courier_Experience_yrs",
]

ORDINAL_FEATURES: List[str] = [
    "Traffic_Level",
]

NOMINAL_FEATURES: List[str] = [
    "Weather",
    "Time_of_Day",
    "Vehicle_Type",
]

TRAFFIC_LEVEL_CATEGORIES: List[str] = [
    "Low",
    "Medium",
    "High",
]

WEATHER_CATEGORIES: List[str] = [
    "Clear",
    "Rainy",
    "Foggy",
    "Snowy",
    "Windy",
]

TIME_OF_DAY_CATEGORIES: List[str] = [
    "Morning",
    "Afternoon",
    "Evening",
    "Night",
]

VEHICLE_TYPE_CATEGORIES: List[str] = [
    "Bike",
    "Scooter",
    "Car",
]

# Raw 7-feature input schema for production inference & API
RAW_FEATURE_NAMES: List[str] = [
    "Distance_km",
    "Weather",
    "Traffic_Level",
    "Time_of_Day",
    "Vehicle_Type",
    "Preparation_Time_min",
    "Courier_Experience_yrs",
]

# Full 12-feature definitions including Phase 5 engineered features
FULL_NUMERICAL_FEATURES: List[str] = [
    "Distance_km",
    "Preparation_Time_min",
    "Courier_Experience_yrs",
    "Prep_Time_per_Km",
]

FULL_ORDINAL_FEATURES: List[str] = [
    "Traffic_Level",
    "Distance_Category",
]

DISTANCE_CATEGORY_CATEGORIES: List[str] = [
    "Short",
    "Medium",
    "Long",
]

BINARY_FEATURES: List[str] = [
    "Is_Peak_Meal_Hour",
    "Bike_Long_Distance",
    "Severe_Conditions",
]


class DeliveryFeatureEngineer(BaseEstimator, TransformerMixin):
    """Custom Scikit-Learn transformer for domain feature engineering.
    
    Transforms raw delivery predictors into high-signal derived features
    using row-level deterministic operations with zero data leakage.
    """
    
    def __init__(self):
        pass
        
    def fit(self, X: pd.DataFrame, y=None):
        """Fit method (no-op as all transformations are deterministic)."""
        return self
        
    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Applies feature engineering transformations.
        
        Args:
            X: Input feature DataFrame.
            
        Returns:
            DataFrame augmented with engineered features.
        """
        X_out = X.copy()
        
        # 1. Distance category binning (Short, Medium, Long)
        X_out["Distance_Category"] = pd.cut(
            X_out["Distance_km"], 
            bins=[0, 5, 12, np.inf], 
            labels=["Short", "Medium", "Long"]
        ).astype(str)
        
        # 2. Peak meal hour indicator (Evening dinner rush)
        X_out["Is_Peak_Meal_Hour"] = (X_out["Time_of_Day"] == "Evening").astype(int)
        
        # 3. Preparation time intensity per km
        X_out["Prep_Time_per_Km"] = (X_out["Preparation_Time_min"] / (X_out["Distance_km"] + 1e-5)).round(2)
        
        # 4. Vehicle x Distance physical constraint interaction (Bicycle > 12 km)
        X_out["Bike_Long_Distance"] = ((X_out["Vehicle_Type"] == "Bike") & (X_out["Distance_km"] > 12.0)).astype(int)
        
        # 5. Compound severe conditions interaction (Adverse weather + High traffic)
        adverse_weather = ["Snowy", "Rainy", "Foggy"]
        X_out["Severe_Conditions"] = (
            X_out["Weather"].isin(adverse_weather) & 
            (X_out["Traffic_Level"] == "High")
        ).astype(int)
        
        return X_out


def separate_features_and_target(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    """Separates input predictors (X) from target variable (y).
    
    Drops the arbitrary transactional identifier (Order_ID) and isolates
    the continuous delivery time target (Delivery_Time_min).
    
    Args:
        df: Raw or loaded delivery DataFrame.
        
    Returns:
        Tuple containing feature DataFrame (X) and target Series (y).
    """
    drop_cols = [TARGET_COLUMN]
    if ID_COLUMN in df.columns:
        drop_cols.append(ID_COLUMN)
        
    X = df.drop(columns=drop_cols)
    y = df[TARGET_COLUMN]
    return X, y


def build_preprocessor(include_engineered: bool = True) -> ColumnTransformer:
    """Builds the unfitted Scikit-Learn ColumnTransformer pipeline.
    
    Args:
        include_engineered: If True, configures transformers for all 12 features
            (including derived features from Phase 5). If False, processes only the
            original 7 base features from Phase 4.
            
    Returns:
        Unfitted ColumnTransformer instance.
    """
    if include_engineered:
        num_cols = FULL_NUMERICAL_FEATURES
        ord_cols = FULL_ORDINAL_FEATURES
        ord_cats = [TRAFFIC_LEVEL_CATEGORIES, DISTANCE_CATEGORY_CATEGORIES]
    else:
        num_cols = NUMERICAL_FEATURES
        ord_cols = ORDINAL_FEATURES
        ord_cats = [TRAFFIC_LEVEL_CATEGORIES]

    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    ord_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OrdinalEncoder(categories=ord_cats)),
    ])

    nom_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    transformers = [
        ("num", num_pipeline, num_cols),
        ("ord", ord_pipeline, ord_cols),
        ("nom", nom_pipeline, NOMINAL_FEATURES),
    ]

    if include_engineered:
        transformers.append(("pass", "passthrough", BINARY_FEATURES))

    preprocessor = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
    )
    return preprocessor


def build_full_preprocessor() -> ColumnTransformer:
    """Convenience alias for build_preprocessor(include_engineered=True)."""
    return build_preprocessor(include_engineered=True)


def save_preprocessor(preprocessor: ColumnTransformer, filepath: str) -> None:
    """Serializes a fitted or configured ColumnTransformer to disk.
    
    Args:
        preprocessor: The ColumnTransformer instance to save.
        filepath: Destination file path for serialization.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    joblib.dump(preprocessor, filepath)


def load_preprocessor(filepath: str) -> ColumnTransformer:
    """Loads a serialized ColumnTransformer from disk.
    
    Args:
        filepath: Path to the serialized joblib file.
        
    Returns:
        Loaded ColumnTransformer instance.
    """
    return joblib.load(filepath)


def split_data(
    X: pd.DataFrame,
    y: pd.Series,
    test_size: float = 0.20,
    random_state: int = 42,
    shuffle: bool = True,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Splits predictors and target into training and testing subsets.
    
    Ensures strict separation of the test set for unbiased generalization evaluation.
    
    Args:
        X: Predictor features DataFrame.
        y: Continuous target Series (Delivery_Time_min).
        test_size: Proportion of the dataset allocated to the test split (default: 0.20).
        random_state: Seed ensuring deterministic, reproducible partitioning (default: 42).
        shuffle: Whether to shuffle data before splitting (default: True).
        
    Returns:
        Tuple of (X_train, X_test, y_train, y_test).
    """
    return train_test_split(
        X, y, test_size=test_size, random_state=random_state, shuffle=shuffle
    )


def save_split_data(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    y_train: pd.Series,
    y_test: pd.Series,
    output_dir: str = "data/processed",
) -> Dict[str, str]:
    """Serializes train/test splits to CSV and saves split metadata.
    
    Saves:
        - train.csv: Combined X_train and y_train for full dataset inspection.
        - test.csv: Combined X_test and y_test for holdout evaluation.
        - X_train.csv, X_test.csv: Feature matrices.
        - y_train.csv, y_test.csv: Target series.
        - split_metadata.json: Partitioning parameters and schema metadata.
        
    Args:
        X_train: Training predictor DataFrame.
        X_test: Testing predictor DataFrame.
        y_train: Training target Series.
        y_test: Testing target Series.
        output_dir: Target directory path for processed splits.
        
    Returns:
        Dictionary mapping artifact names to their saved file paths.
    """
    import json
    from datetime import datetime

    os.makedirs(output_dir, exist_ok=True)

    paths = {
        "X_train": os.path.join(output_dir, "X_train.csv"),
        "X_test": os.path.join(output_dir, "X_test.csv"),
        "y_train": os.path.join(output_dir, "y_train.csv"),
        "y_test": os.path.join(output_dir, "y_test.csv"),
        "train": os.path.join(output_dir, "train.csv"),
        "test": os.path.join(output_dir, "test.csv"),
        "metadata": os.path.join(output_dir, "split_metadata.json"),
    }

    # Save feature matrices and target vectors
    X_train.to_csv(paths["X_train"], index=False)
    X_test.to_csv(paths["X_test"], index=False)
    y_train.to_frame(name=TARGET_COLUMN).to_csv(paths["y_train"], index=False)
    y_test.to_frame(name=TARGET_COLUMN).to_csv(paths["y_test"], index=False)

    # Save unified train and test sets
    train_df = X_train.copy()
    train_df[TARGET_COLUMN] = y_train.values
    train_df.to_csv(paths["train"], index=False)

    test_df = X_test.copy()
    test_df[TARGET_COLUMN] = y_test.values
    test_df.to_csv(paths["test"], index=False)

    # Save split metadata
    metadata = {
        "created_at": datetime.now().isoformat(),
        "random_state": 42,
        "test_size": 0.20,
        "train_rows": len(X_train),
        "test_rows": len(X_test),
        "total_rows": len(X_train) + len(X_test),
        "feature_count": X_train.shape[1],
        "feature_names": list(X_train.columns),
        "target_column": TARGET_COLUMN,
    }
    with open(paths["metadata"], "w") as f:
        json.dump(metadata, f, indent=2)

    return paths


def load_split_data(
    data_dir: str = "data/processed",
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """Loads saved train and test splits from disk.
    
    Args:
        data_dir: Directory containing processed CSV files.
        
    Returns:
        Tuple of (X_train, X_test, y_train, y_test).
    """
    X_train = pd.read_csv(os.path.join(data_dir, "X_train.csv"))
    X_test = pd.read_csv(os.path.join(data_dir, "X_test.csv"))
    y_train = pd.read_csv(os.path.join(data_dir, "y_train.csv"))[TARGET_COLUMN]
    y_test = pd.read_csv(os.path.join(data_dir, "y_test.csv"))[TARGET_COLUMN]
    return X_train, X_test, y_train, y_test


def validate_raw_input(data: Any) -> pd.DataFrame:
    """Validates raw delivery feature inputs for inference and API serving.
    
    Ensures all 7 raw features are present with correct types and realistic ranges.
    
    Args:
        data: Raw delivery record as a dictionary, list of dictionaries, or DataFrame.
        
    Returns:
        Validated pandas DataFrame containing the 7 raw input features with correct dtypes.
        
    Raises:
        ValueError: If required features are missing, categories are invalid,
            or numerical values fall outside physical bounds.
    """
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    elif isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        raise ValueError(f"Unsupported input data type: {type(data)}. Expected dict, list of dicts, or DataFrame.")
        
    # 1. Feature presence verification
    missing_cols = [col for col in RAW_FEATURE_NAMES if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required raw feature columns: {missing_cols}. Expected: {RAW_FEATURE_NAMES}")
        
    # Isolate and order expected features
    df = df[RAW_FEATURE_NAMES].copy()
    
    # 2. Type conversions and range checks
    try:
        df["Distance_km"] = df["Distance_km"].astype(float)
        df["Preparation_Time_min"] = df["Preparation_Time_min"].astype(float)
        df["Courier_Experience_yrs"] = df["Courier_Experience_yrs"].astype(float)
    except (ValueError, TypeError) as e:
        raise ValueError(f"Numerical conversion error: {e}")
        
    if (df["Distance_km"] <= 0).any() or (df["Distance_km"] > 100).any():
        raise ValueError("Distance_km must be strictly positive and <= 100 km.")
        
    if (df["Preparation_Time_min"] < 0).any() or (df["Preparation_Time_min"] > 180).any():
        raise ValueError("Preparation_Time_min must be between 0 and 180 minutes.")
        
    if (df["Courier_Experience_yrs"] < 0).any() or (df["Courier_Experience_yrs"] > 50).any():
        raise ValueError("Courier_Experience_yrs must be between 0 and 50 years.")
        
    # 3. Categorical value validation
    invalid_weather = df[~df["Weather"].isin(WEATHER_CATEGORIES)]["Weather"].unique()
    if len(invalid_weather) > 0:
        raise ValueError(f"Invalid Weather value(s): {list(invalid_weather)}. Expected one of: {WEATHER_CATEGORIES}")
        
    invalid_traffic = df[~df["Traffic_Level"].isin(TRAFFIC_LEVEL_CATEGORIES)]["Traffic_Level"].unique()
    if len(invalid_traffic) > 0:
        raise ValueError(f"Invalid Traffic_Level value(s): {list(invalid_traffic)}. Expected one of: {TRAFFIC_LEVEL_CATEGORIES}")
        
    invalid_tod = df[~df["Time_of_Day"].isin(TIME_OF_DAY_CATEGORIES)]["Time_of_Day"].unique()
    if len(invalid_tod) > 0:
        raise ValueError(f"Invalid Time_of_Day value(s): {list(invalid_tod)}. Expected one of: {TIME_OF_DAY_CATEGORIES}")
        
    invalid_veh = df[~df["Vehicle_Type"].isin(VEHICLE_TYPE_CATEGORIES)]["Vehicle_Type"].unique()
    if len(invalid_veh) > 0:
        raise ValueError(f"Invalid Vehicle_Type value(s): {list(invalid_veh)}. Expected one of: {VEHICLE_TYPE_CATEGORIES}")
        
    return df


def build_production_pipeline(model: Optional[Any] = None) -> Pipeline:
    """Assembles the complete end-to-end production ML pipeline.
    
    Transforms raw delivery predictors through feature engineering,
    column transformations, and regression prediction in one cohesive unit.
    Prevents training-serving skew by embedding all data transformations.
    
    Args:
        model: Optional unfitted regression model instance. If None,
            defaults to LinearRegression (the confirmed Phase 10-13 champion).
            
    Returns:
        Complete Scikit-Learn Pipeline instance.
    """
    if model is None:
        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        
    return Pipeline([
        ("feature_engineering", DeliveryFeatureEngineer()),
        ("preprocessor", build_full_preprocessor()),
        ("regressor", model),
    ])

