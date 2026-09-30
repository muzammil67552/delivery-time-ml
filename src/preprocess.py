"""Data preprocessing and feature engineering module for Delivery Time Prediction.

This module provides reusable preprocessing pipelines, custom feature transformers,
and serialization utilities following Scikit-Learn standards.
"""

import os
from typing import List, Tuple
import pandas as pd
import numpy as np
import joblib

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler, OneHotEncoder, OrdinalEncoder

# Constant definitions
TARGET_COLUMN: str = "Delivery_Time_min"
ID_COLUMN: str = "Order_ID"

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


def build_preprocessor() -> ColumnTransformer:
    """Builds the unfitted Scikit-Learn ColumnTransformer pipeline.
    
    Assembles three modular sub-pipelines:
    1. Numerical pipeline: Median imputation + StandardScaler.
    2. Ordinal pipeline: Most-frequent imputation + OrdinalEncoder (Low < Medium < High).
    3. Nominal pipeline: Most-frequent imputation + OneHotEncoder (unknowns ignored).
    
    Returns:
        Unfitted ColumnTransformer instance.
    """
    num_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])

    ord_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OrdinalEncoder(categories=[TRAFFIC_LEVEL_CATEGORIES])),
    ])

    nom_pipeline = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("encoder", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
    ])

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", num_pipeline, NUMERICAL_FEATURES),
            ("ord", ord_pipeline, ORDINAL_FEATURES),
            ("nom", nom_pipeline, NOMINAL_FEATURES),
        ],
        remainder="drop",
    )
    return preprocessor


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
