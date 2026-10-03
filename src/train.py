"""Model training, baseline benchmarking, and evaluation module for Delivery Time Prediction.

This module provides reusable evaluation metrics calculation, baseline heuristics,
and structured results persistence following Scikit-Learn and MLOps standards.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
import joblib
import pandas as pd
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, root_mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor

# Constant definitions
TARGET_COLUMN: str = "Delivery_Time_min"


def calculate_regression_metrics(
    y_true: pd.Series | np.ndarray, 
    y_pred: pd.Series | np.ndarray
) -> Dict[str, float]:
    """Computes standard regression evaluation metrics: MAE, MSE, RMSE, and R2.

    Args:
        y_true: Ground truth target observations.
        y_pred: Predicted target values.

    Returns:
        Dictionary containing rounded 'mae', 'mse', 'rmse', and 'r2' scores.
    """
    mae = float(mean_absolute_error(y_true, y_pred))
    mse = float(mean_squared_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    
    return {
        "mae": round(mae, 4),
        "mse": round(mse, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
    }


def compute_mean_baseline(
    y_train: pd.Series, 
    n_samples: int
) -> Tuple[float, np.ndarray]:
    """Calculates the naive heuristic mean baseline strictly from y_train.

    Data Leakage Guard:
        This function computes the arithmetic mean exclusively from the training
        target vector (y_train). The test set target (y_test) is strictly prohibited
        from entering this calculation.

    Args:
        y_train: Training partition target Series.
        n_samples: Number of prediction samples to generate (e.g., len(y_test)).

    Returns:
        Tuple containing:
            - baseline_mean: The scalar mean delivery time from y_train.
            - y_pred_baseline: Constant prediction array of length n_samples.
    """
    baseline_mean = float(y_train.mean())
    y_pred_baseline = np.full(shape=n_samples, fill_value=baseline_mean, dtype=float)
    return baseline_mean, y_pred_baseline


def save_baseline_results(
    baseline_value: float,
    metrics: Dict[str, float],
    train_count: int,
    test_count: int,
    output_dir: str = os.path.join("..", "models")
) -> Dict[str, str]:
    """Persists baseline metrics to JSON and CSV comparison structures.

    Args:
        baseline_value: The scalar training mean prediction.
        metrics: Dictionary with 'mae', 'rmse', 'r2'.
        train_count: Number of training samples.
        test_count: Number of test samples.
        output_dir: Target directory for model metadata and metrics.

    Returns:
        Dictionary mapping artifact identifiers to saved file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Detailed JSON metadata artifact
    json_path = os.path.join(output_dir, "baseline_metrics.json")
    results_payload: Dict[str, Any] = {
        "model_name": "Baseline (Training Mean)",
        "model_type": "heuristic_baseline",
        "phase": "Phase 7: Baseline Model",
        "created_at": datetime.now().isoformat(),
        "is_ml_model": False,
        "strategy": "mean",
        "baseline_value_minutes": round(baseline_value, 5),
        "sample_counts": {
            "train_samples": train_count,
            "test_samples": test_count,
        },
        "metrics": metrics,
        "notes": (
            "Naive non-parametric benchmark predicting constant training mean. "
            "Zero feature signals used. Establishes the foundational performance floor."
        )
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results_payload, f, indent=2)
        
    # 2. Cumulative model comparison CSV table for Phase 8+ benchmarking
    csv_path = os.path.join(output_dir, "model_comparison.csv")
    comparison_df = pd.DataFrame([{
        "Model": "Baseline (Training Mean)",
        "Type": "Heuristic Baseline",
        "MAE": metrics["mae"],
        "RMSE": metrics["rmse"],
        "R2": metrics["r2"],
        "Notes": f"Constant prediction ({round(baseline_value, 2)} min) from y_train mean"
    }])
    comparison_df.to_csv(csv_path, index=False)
    
    return {
        "json_path": json_path,
        "csv_path": csv_path,
    }


def get_candidate_regressors(random_state: int = 42) -> Dict[str, Any]:
    """Instantiates candidate regression models with simple/default hyperparameters.

    Args:
        random_state: Seed ensuring deterministic tree splitting and bootstrap sampling.

    Returns:
        Dictionary mapping model names to unfitted Scikit-Learn regressor instances.
    """
    return {
        "Linear Regression": LinearRegression(),
        "Decision Tree": DecisionTreeRegressor(random_state=random_state),
        "Random Forest": RandomForestRegressor(random_state=random_state),
    }


def train_and_evaluate_model(
    model_name: str,
    model: Any,
    preprocessor: ColumnTransformer,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Tuple[Pipeline, np.ndarray, Dict[str, float]]:
    """Trains a model via an integrated Scikit-Learn Pipeline and evaluates on holdout test set.

    Anti-Leakage Architecture:
        The regressor and preprocessor are wrapped in a single Scikit-Learn Pipeline.
        The entire pipeline is fitted exclusively on (X_train, y_train). The test set
        is solely used to generate out-of-sample predictions via pipeline.predict(X_test).

    Args:
        model_name: Descriptive name of the candidate model.
        model: Unfitted Scikit-Learn regressor instance.
        preprocessor: Unfitted ColumnTransformer instance.
        X_train: Training predictor matrix.
        y_train: Training target vector.
        X_test: Testing predictor matrix.
        y_test: Testing target vector.

    Returns:
        Tuple containing:
            - fitted_pipeline: The fitted Scikit-Learn Pipeline object.
            - y_pred: Array of out-of-sample test predictions.
            - metrics: Dictionary with 'mae', 'rmse', and 'r2'.
    """
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", model),
    ])
    
    # Fit strictly on training data
    pipeline.fit(X_train, y_train)
    
    # Predict on test data
    y_pred = pipeline.predict(X_test)
    
    # Calculate performance metrics
    metrics = calculate_regression_metrics(y_test, y_pred)
    
    return pipeline, y_pred, metrics


def update_model_comparison(
    new_rows: List[Dict[str, Any]],
    comparison_path: str = os.path.join("..", "models", "model_comparison.csv")
) -> pd.DataFrame:
    """Updates the centralized model comparison CSV registry with newly evaluated models.

    Args:
        new_rows: List of dictionaries matching the comparison schema (Model, Type, MAE, RMSE, R2, Notes).
        comparison_path: Filepath to the CSV registry.

    Returns:
        Updated DataFrame containing all baseline and trained models.
    """
    if os.path.exists(comparison_path):
        existing_df = pd.read_csv(comparison_path)
    else:
        existing_df = pd.DataFrame(columns=["Model", "Type", "MAE", "RMSE", "R2", "Notes"])
        
    new_df = pd.DataFrame(new_rows)
    
    # Concatenate and deduplicate by 'Model' keeping the latest record
    combined_df = pd.concat([existing_df, new_df], ignore_index=True)
    combined_df = combined_df.drop_duplicates(subset=["Model"], keep="last").reset_index(drop=True)
    
    # Ensure target directory exists and save
    os.makedirs(os.path.dirname(comparison_path), exist_ok=True)
    combined_df.to_csv(comparison_path, index=False)
    
    return combined_df


def train_production_pipeline(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    model: Optional[Any] = None,
) -> Pipeline:
    """Trains the complete production ML pipeline on training data.
    
    The pipeline automatically encapsulates:
      1. Feature Engineering (DeliveryFeatureEngineer)
      2. Missing value imputation, scaling, and categorical encoding (ColumnTransformer)
      3. Regression Estimator (LinearRegression by default)
      
    Args:
        X_train: Predictor DataFrame (either raw 7 features or full 12 features).
        y_train: Training target Series (Delivery_Time_min).
        model: Optional unfitted regression estimator. Defaults to LinearRegression.
        
    Returns:
        Fitted Scikit-Learn Pipeline ready for production prediction.
    """
    from src.preprocess import build_production_pipeline, RAW_FEATURE_NAMES
    
    # Ensure pipeline trains on the clean raw feature subset if present
    if all(feat in X_train.columns for feat in RAW_FEATURE_NAMES):
        X_fit = X_train[RAW_FEATURE_NAMES]
    else:
        X_fit = X_train
        
    pipeline = build_production_pipeline(model=model)
    pipeline.fit(X_fit, y_train)
    return pipeline


def save_production_pipeline(
    pipeline: Pipeline,
    filepath: str = os.path.join("models", "delivery_time_pipeline.joblib"),
) -> str:
    """Serializes the complete trained production pipeline to disk.
    
    Args:
        pipeline: Fitted production Pipeline instance.
        filepath: Destination file path for serialization.
        
    Returns:
        Normalized path to the saved artifact.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    joblib.dump(pipeline, filepath)
    return filepath


