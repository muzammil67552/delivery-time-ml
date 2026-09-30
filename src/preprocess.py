"""Data preprocessing module for Delivery Time Prediction.

This module provides reusable preprocessing pipelines, feature transformers,
and serialization utilities following Scikit-Learn standards.
"""

import os
from typing import List, Tuple
import pandas as pd
import joblib

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
