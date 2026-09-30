# Delivery Time Prediction ML

## Short Project Description
An end-to-end Machine Learning engineering project designed to predict food delivery durations (in minutes) based on historical delivery parameters such as delivery distance, weather conditions, traffic intensity, order preparation time, and courier experience.

## Project Objective
The objective of this project is to develop a reliable, production-ready regression model that accurately forecasts food delivery times. The project follows standard industry MLOps practices, progressing from exploratory data analysis and modular feature engineering to model comparison, hyperparameter tuning, model serialization, and serving via a FastAPI backend paired with an interactive frontend interface.

## Current Phase
**Phase 5: Feature Engineering**
- Evaluated raw feature utility and permanently removed non-informative identifier `Order_ID`.
- Engineered domain-grounded distance tiers (`Distance_Category`: Short, Medium, Long).
- Engineered time-related operational indicators (`Is_Peak_Meal_Hour` for dinner rush).
- Formulated preparation efficiency metrics (`Prep_Time_per_Km`).
- Constructed compound physical constraint interactions (`Bike_Long_Distance` yielding +22.4 min penalty, and `Severe_Conditions` yielding +18.0 min penalty).
- Implemented Scikit-Learn custom transformer `DeliveryFeatureEngineer` ensuring zero data leakage.
- Documented findings in `notebooks/04_feature_engineering.ipynb`.

## Project Structure
```text
delivery-time-ml/
│
├── data/                  # Dataset storage (raw and processed data)
│   ├── delivery_data.csv
│   └── Food_Delivery_Times.csv
│
├── notebooks/             # Jupyter notebooks for exploration and prototyping
│   ├── 01_dataset_understanding.ipynb
│   ├── 02_eda.ipynb
│   ├── 03_data_preprocessing.ipynb
│   ├── 04_feature_engineering.ipynb
│   └── model_training.ipynb
│
├── src/                   # Production Python source modules
│   ├── __init__.py
│   ├── preprocess.py      # Preprocessing, custom transformers & serialization
│   ├── train.py           # Model training pipelines (future phase)
│   └── predict.py         # Inference logic (future phase)
│
├── models/                # Serialized model artifacts (.pkl, .joblib)
│   ├── preprocessor.joblib # Fitted/configured preprocessing pipeline
│   └── .gitkeep
│
├── app/                   # Application serving layer (FastAPI / UI)
│   └── __init__.py
│
├── tests/                 # Unit and integration test suites
│   └── __init__.py
│
├── requirements.txt       # Phase-specific project dependencies
├── README.md              # Project overview and documentation
└── .gitignore             # Git exclusion rules for ML artifacts and caches
```

## Future ML Workflow Overview
The development lifecycle progresses sequentially through the following stages:

1. **Problem Definition** - Formulating the delivery time prediction problem as a supervised regression task and defining target evaluation metrics (e.g., MAE, RMSE, R²).
2. **Data Understanding** - Inspecting dataset schemas, field data types, distributions, and initial data sanity checks.
3. **Exploratory Data Analysis (EDA)** - Analyzing correlations, traffic/weather patterns, identifying anomalies, and visualizing key drivers of delivery delay.
4. **Data Preprocessing** - Handling missing values, cleaning anomalous records, and ensuring data integrity.
5. **Feature Engineering** - Encoding categorical variables, scaling numerical features, and engineering domain-relevant features without data leakage.
6. **Train/Test Split** - Establishing rigorous validation strategies (e.g., train/validation/test splits or cross-validation).
7. **Baseline Model** - Building a simple heuristic/linear baseline to benchmark subsequent model iterations.
8. **Model Training** - Training candidate regressors (e.g., Ridge, Random Forest, Gradient Boosting / XGBoost).
9. **Evaluation** - Assessing performance against baseline across evaluation metrics.
10. **Model Comparison** - Comparing predictive power, error distributions, inference latency, and operational trade-offs.
11. **Hyperparameter Tuning** - Optimizing parameters of top-performing candidate models.
12. **Final Model Selection** - Selecting and retraining the final production-ready model.
13. **Model Saving** - Serializing the trained model and preprocessing pipeline artifacts into `models/`.
14. **FastAPI Backend** - Exposing the prediction pipeline via clean REST API endpoints with request validation (Pydantic).
15. **Frontend Interface** - Creating an intuitive UI to submit delivery inputs and view real-time delivery time predictions.
16. **Testing** - Writing unit and integration tests in `tests/` for preprocessing, inference, and API endpoints.
17. **Deployment Preparation** - Containerization / environment readiness for production deployment.
18. **Documentation** - Finalizing project reporting, API documentation, and usage guides.
