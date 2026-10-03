# Delivery Time Prediction — Machine Learning Project

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.4%2B-F7931E.svg)](https://scikit-learn.org/)
[![Pytest](https://img.shields.io/badge/pytest-8.0%2B-brightgreen.svg)](https://pytest.org/)

---

## Project Overview

The **Delivery Time Prediction** project is an end-to-end Machine Learning engineering solution designed to accurately forecast food order delivery durations in minutes. Utilizing historical delivery logs, the system maps customer distance, weather conditions, traffic congestion levels, time of day, transport mode, food preparation time, and courier tenure into precise delivery arrival estimates.

The project encompasses the entire real-world ML lifecycle: exploratory data analysis, leak-free preprocessing, feature engineering, baseline benchmarking, multi-model evaluation, cross-validation, hyperparameter tuning, model serialization, a FastAPI REST service, a lightweight responsive frontend UI, and a suite of unit and integration tests.

---

## Problem Statement

In on-demand food delivery platforms, inaccurate estimated times of arrival (ETAs) lead to customer dissatisfaction, suboptimal dispatching, and courier downtime. Traditional static estimation heuristics (e.g. constant speeds or fixed buffers) fail to account for weather anomalies, dynamic traffic jams, or kitchen bottlenecks.

This project formulates delivery duration prediction as a **supervised regression** task, learning non-linear relationships across multimodal environmental and operational features to deliver consistent, low-error ETA estimates in real time.

---

## Machine Learning Approach

The engineering process followed strict anti-leakage principles across 20 structured phases:

1. **Supervised Learning**: Addressed as continuous target regression (`Delivery_Time_min`).
2. **Data Preprocessing**: Implemented leak-free median imputation for numerical features and most-frequent imputation for categorical variables.
3. **Feature Engineering**: Extracted domain-relevant features inside a custom Scikit-Learn transformer (`DeliveryFeatureEngineer`):
   - `Prep_Time_per_Km`: Ratio of kitchen prep time to delivery distance.
   - `Distance_Category`: Discretized distance buckets (`Short`, `Medium`, `Long`).
   - `Is_Peak_Meal_Hour`: Binary indicator for lunch and dinner delivery rushes.
   - `Bike_Long_Distance`: Interaction indicator for long journeys on pedal bicycles.
   - `Severe_Conditions`: Compound risk flag combining adverse weather (`Rainy`, `Snowy`) with `High` traffic.
4. **Train/Test Split**: Enforced an 80/20 train/test partition using fixed seeds (`random_state=42`), isolating test evaluation.
5. **Cross-Validation**: 5-fold cross-validation performed strictly on `(X_train, y_train)` to ensure model stability across subsets.
6. **Hyperparameter Tuning**: `GridSearchCV` utilized on non-linear tree algorithms to evaluate depth and split constraints.
7. **Model Evaluation & Comparison**: Quantitative benchmarking against a naive heuristic mean baseline across MAE, MSE, RMSE, and $R^2$.
8. **Final Production Pipeline**: Unified feature engineering, column transformation, and model estimator into a single serialized Scikit-Learn `Pipeline`.
9. **Prediction API & Serving**: Production-ready FastAPI backend exposing REST endpoints and serving a vanilla web UI.

---

## Dataset & Feature Schema

The dataset (`data/delivery_data.csv`) contains 1,000 delivery orders with the following schema:

| Feature | Type | Description | Valid Domain / Range |
| :--- | :--- | :--- | :--- |
| `Order_ID` | Identifier | Unique tracking number | Excluded from modeling |
| `Distance_km` | Numerical | Restaurant-to-customer distance | Positive float (0, 100] |
| `Weather` | Nominal | Prevailing atmospheric conditions | `Clear`, `Rainy`, `Foggy`, `Snowy`, `Windy` |
| `Traffic_Level` | Ordinal | Real-time road congestion level | `Low`, `Medium`, `High` |
| `Time_of_Day` | Nominal | Dispatch time window | `Morning`, `Afternoon`, `Evening`, `Night` |
| `Vehicle_Type` | Nominal | Courier transport mode | `Bike`, `Scooter`, `Car` |
| `Preparation_Time_min` | Numerical | Kitchen meal preparation duration | Float [0, 180] minutes |
| `Courier_Experience_yrs`| Numerical | Courier professional tenure | Float [0, 50] years |
| **`Delivery_Time_min`** | **Target** | **Total trip duration in minutes** | **Continuous target variable** |

---

## Tech Stack

- **Core Runtime**: Python 3.11+
- **Data Manipulation**: Pandas, NumPy
- **Machine Learning**: Scikit-Learn (Pipelines, Transformers, Metrics, Model Selection)
- **Model Persistence**: Joblib
- **Exploration & Visualization**: Jupyter, Matplotlib, Seaborn
- **Backend Web API**: FastAPI, Uvicorn, Pydantic v2
- **Frontend User Interface**: HTML5, Vanilla CSS3, JavaScript (Fetch API)
- **Automated Testing**: Pytest, HTTPX, FastAPI TestClient
- **Configuration**: Python-dotenv

---

## Project Structure

```text
delivery-time-ml/
├── data/
│   ├── delivery_data.csv          # Raw delivery records (1,000 samples)
│   ├── Food_Delivery_Times.csv    # Source raw dataset
│   └── processed/                 # Partitioned and validated splits
│       ├── train.csv              # Full training records (800 rows)
│       ├── test.csv               # Unseen test records (200 rows)
│       ├── X_train.csv            # Training feature matrix
│       ├── X_test.csv             # Test feature matrix
│       ├── y_train.csv            # Training target vector
│       ├── y_test.csv             # Test target vector
│       └── split_metadata.json    # Partition schema documentation
│
├── notebooks/                     # Sequential development & experiment records
│   ├── 01_dataset_understanding.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_data_preprocessing.ipynb
│   ├── 04_feature_engineering.ipynb
│   ├── 05_train_test_split.ipynb
│   ├── 06_baseline_model.ipynb
│   ├── 07_model_training.ipynb
│   ├── 08_model_evaluation.ipynb
│   ├── 09_model_comparison.ipynb
│   ├── 10_cross_validation.ipynb
│   ├── 11_hyperparameter_tuning.ipynb
│   └── 12_final_model_analysis.ipynb
│
├── src/                           # Production source modules
│   ├── __init__.py
│   ├── preprocess.py              # Schema validation, transformers & pipeline factory
│   ├── train.py                   # Metrics calculation, training & serialization
│   └── predict.py                 # Standalone prediction engine & singleton loader
│
├── models/                        # Serialized artifacts & registry
│   ├── delivery_time_pipeline.joblib # Final end-to-end production ML pipeline
│   ├── preprocessor.joblib           # Preprocessing pipeline artifact
│   ├── final_model_spec.json         # Approved production model specification
│   ├── baseline_metrics.json         # Heuristic baseline metrics metadata
│   ├── model_comparison.csv          # Central model benchmarking leaderboard
│   └── selected_candidate.json       # Candidate selection audit trail
│
├── app/                           # FastAPI serving layer
│   ├── __init__.py
│   ├── main.py                    # REST application, endpoints & lifespan loader
│   ├── schemas.py                 # Pydantic input/output validation models
│   └── static/                    # Simple web frontend
│       ├── index.html             # Responsive user interface layout
│       ├── style.css              # Custom modern styling
│       └── script.js              # Client controller & async API connection
│
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures & TestClient configuration
│   ├── test_model.py              # Pipeline loading & inference logic tests
│   └── test_api.py                # REST API, schema validation & frontend tests
│
├── .env.example                   # Environment configuration template
├── requirements.txt               # Pinned project dependencies
├── README.md                      # Project documentation
└── .gitignore                     # Git exclusion rules
```

---

## Machine Learning Workflow

```text
Dataset (1,000 samples)
        ↓
Exploratory Data Analysis (EDA)
        ↓
Missing Value Imputation & Encodings
        ↓
Feature Engineering (DeliveryFeatureEngineer)
        ↓
Train / Test Split (80% Train / 20% Test)
        ↓
Naive Heuristic Baseline (y_train Mean = 57.05 min)
        ↓
Candidate Model Training (OLS, Decision Tree, Random Forest)
        ↓
5-Fold Cross-Validation & Metric Evaluation
        ↓
Hyperparameter Optimization (GridSearchCV)
        ↓
Model Comparison & Overfitting Audit
        ↓
Final Pipeline Packaging & Serialization (.joblib)
        ↓
FastAPI Prediction Service (/predict)
        ↓
Interactive Frontend Interface (/ui)
```

---

## Model Benchmark & Evaluation

All models were evaluated on the exact same holdout test set (200 unseen deliveries). The heuristic baseline predicted the static training mean ($57.05$ minutes).

### Evaluation Metrics Defined:
- **MAE (Mean Absolute Error)**: Average absolute magnitude of errors in minutes (primary operational metric).
- **RMSE (Root Mean Squared Error)**: Penalizes larger prediction outliers more heavily.
- **$R^2$ (Coefficient of Determination)**: Proportion of variance explained by the model features ($1.0$ is perfect; $0.0$ is equivalent to predicting the mean).

### Benchmark Comparison Table:

| Model | Model Type | Test MAE (min) | Test RMSE (min) | Test $R^2$ | Status |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Heuristic Baseline** | Non-parametric Mean | 17.5014 | 21.2324 | -0.0058 | Benchmark Floor |
| **Decision Tree** | Recursive Binary Split | 9.0300 | 12.9623 | 0.6251 | High Variance |
| **Random Forest** | Bagging Ensemble (100 trees)| 6.9794 | 9.7563 | 0.7876 | Strong Competitor |
| **Linear Regression** | Ordinary Least Squares | **6.1724** | **9.0711** | **0.8164** | **Selected Champion** |

### Final Model Performance:
- **Selected Model**: Linear Regression fitted on engineered and standardized features.
- **Holdout Test MAE**: **6.17 minutes** (an absolute error reduction of **64.73%** over baseline).
- **Holdout Test RMSE**: **9.07 minutes** (a **57.28%** improvement over baseline).
- **Holdout Test $R^2$**: **0.8164** (explains over 81.6% of delivery variance).
- **Generalization Audit**: Train MAE ($6.63$ min) vs Test MAE ($6.17$ min) confirms zero overfitting.

---

## How to Run the Project

### 1. Environment Setup

Clone or navigate to the repository directory:
```powershell
cd e:\my-project\delivery-time-ml
```

Activate the virtual environment:
```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

If dependencies need to be installed or updated:
```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```

### 2. Start the FastAPI Prediction Server

#### Development Mode (with hot-reload):
```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

#### Production Mode (recommended for production serving):
```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## API Documentation & Endpoints

When the server is active, interactive OpenAPI documentation is accessible at:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

### Endpoints:

#### 1. Root Check
- **`GET /`**
- **Response**:
  ```json
  {
    "message": "Delivery Time Prediction API is running",
    "status": "online"
  }
  ```

#### 2. Health & Model Status
- **`GET /health`**
- **Response**:
  ```json
  {
    "status": "healthy",
    "model_loaded": true
  }
  ```

#### 3. Real-Time Prediction
- **`POST /predict`**
- **Content-Type**: `application/json`
- **Request Body Format**:
  ```json
  {
    "Distance_km": 8.5,
    "Weather": "Clear",
    "Traffic_Level": "Medium",
    "Time_of_Day": "Evening",
    "Vehicle_Type": "Scooter",
    "Preparation_Time_min": 15.0,
    "Courier_Experience_yrs": 3.0
  }
  ```
- **Response Format**:
  ```json
  {
    "predicted_delivery_time_min": 49.93
  }
  ```

---

## How to Use the Frontend UI

1. Start the API server using Uvicorn.
2. In your web browser, navigate to:
   ```text
   http://127.0.0.1:8000/ui
   ```
   *(Alternatively, navigate to `http://127.0.0.1:8000/static/index.html` or double-click `app/static/index.html` directly).*
3. Adjust the delivery features:
   - Distance (km)
   - Weather condition
   - Traffic intensity
   - Dispatch time of day
   - Vehicle type
   - Kitchen preparation time
   - Courier tenure
4. Click **"Predict Delivery Time"**.
5. The application asynchronously posts the payload to `/predict` and displays the estimated arrival time in minutes.

---

## Automated Testing

The project includes unit and integration tests covering pipeline persistence, inference logic, FastAPI endpoints, input boundaries, and the frontend client contract.

### To execute the test suite manually:

```powershell
.\.venv\Scripts\python -m pytest -v
```

Or run individual test modules:
```powershell
# Model and inference tests
.\.venv\Scripts\python -m pytest tests/test_model.py -v

# FastAPI and frontend integration tests
.\.venv\Scripts\python -m pytest tests/test_api.py -v
```

---

## Deployment Guidance

The application is structured to be deployment-ready across modern cloud hosting platforms (e.g. Render, Railway, AWS App Runner, Google Cloud Run, Hugging Face Spaces, or Docker):

1. **Self-Contained Pipeline**: The serialized model artifact (`models/delivery_time_pipeline.joblib`) embeds all custom transformers and encoders, eliminating training-serving skew.
2. **Path Agnostic**: All file path resolutions use `os.path.abspath` relative to module roots; no Windows-specific or hardcoded working directories exist.
3. **Container-Friendly**: Can be packaged with a minimal Python 3.11 Dockerfile executing:
   ```dockerfile
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```
4. **Environment Variables**: Copy `.env.example` to `.env` to override `HOST`, `PORT`, or custom `MODEL_PATH` locations without code modifications.

---

## Learning Outcomes

- **End-to-End MLOps Lifecycle**: Transitioning from raw exploratory data to a production-ready inference service.
- **Leak-Free ML Pipeline**: Designing custom Scikit-Learn transformers (`BaseEstimator`, `TransformerMixin`) that encapsulate feature engineering and preprocessing into a single artifact.
- **Rigorous Model Evaluation**: Overcoming confirmation bias through cross-validation, baseline benchmarking, and residual analysis.
- **Production REST API**: Designing type-safe, validated web interfaces using FastAPI and Pydantic v2.
- **Frontend Integration**: Implementing clean client-server communication using vanilla web standards with CORS support.
- **Testing & Deployment**: Developing test fixtures with Pytest TestClient and preparing applications for containerized production hosting.
