"""Unit and integration tests for Model Loading and Prediction logic.

Verifies:
1. Model loading via `load_production_pipeline`
2. Prediction function via `predict_delivery_time`
3. Pipeline input validation error handling
"""

import os
import pytest
from sklearn.pipeline import Pipeline

from src.predict import load_production_pipeline, predict_delivery_time


def test_01_model_loading():
    """Test 1: Verify the saved production pipeline loads correctly and has required steps."""
    pipeline = load_production_pipeline()
    assert pipeline is not None, "Pipeline failed to load."
    assert isinstance(pipeline, Pipeline), "Loaded object must be a Scikit-Learn Pipeline."
    
    # Check expected steps from Phase 15 pipeline
    step_names = [name for name, _ in pipeline.steps]
    assert "feature_engineering" in step_names, "Missing 'feature_engineering' step in pipeline."
    assert "preprocessor" in step_names, "Missing 'preprocessor' step in pipeline."
    assert "regressor" in step_names, "Missing 'regressor' step in pipeline."


def test_01_model_loading_missing_file():
    """Test 1b: Verify FileNotFoundError is raised when attempting to load a non-existent model."""
    fake_path = os.path.join("models", "non_existent_model.joblib")
    with pytest.raises(FileNotFoundError):
        load_production_pipeline(filepath=fake_path)


def test_02_predict_single_instance(valid_delivery_payload):
    """Test 2: Verify prediction function returns a single float for a single dict input."""
    prediction = predict_delivery_time(valid_delivery_payload)
    assert isinstance(prediction, float), f"Expected float, got {type(prediction)}."
    assert prediction > 0, f"Predicted delivery time should be positive, got {prediction}."
    assert round(prediction, 2) == prediction, "Prediction should be rounded to 2 decimal places."


def test_02_predict_batch_instances(valid_delivery_payload, edge_case_delivery_payload):
    """Test 2b: Verify prediction function returns a list of floats for batch inputs."""
    batch_input = [valid_delivery_payload, edge_case_delivery_payload]
    predictions = predict_delivery_time(batch_input)
    assert isinstance(predictions, list), f"Expected list, got {type(predictions)}."
    assert len(predictions) == 2, f"Expected 2 predictions, got {len(predictions)}."
    for p in predictions:
        assert isinstance(p, float), f"Expected float in batch, got {type(p)}."
        assert p > 0, f"Predicted delivery time must be positive, got {p}."


def test_02_predict_invalid_numerical_input(valid_delivery_payload):
    """Test 2c: Verify prediction function raises ValueError when numerical inputs are out of bounds."""
    invalid_data = valid_delivery_payload.copy()
    invalid_data["Distance_km"] = -5.0  # Invalid negative distance
    with pytest.raises(ValueError) as exc_info:
        predict_delivery_time(invalid_data)
    assert "Distance_km must be strictly positive" in str(exc_info.value)


def test_02_predict_invalid_categorical_input(valid_delivery_payload):
    """Test 2d: Verify prediction function raises ValueError when categorical values are unrecognized."""
    invalid_data = valid_delivery_payload.copy()
    invalid_data["Weather"] = "Tornado"  # Unrecognized category
    with pytest.raises(ValueError) as exc_info:
        predict_delivery_time(invalid_data)
    assert "Invalid Weather value" in str(exc_info.value)
