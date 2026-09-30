# Delivery Time Prediction ML

## Short Project Description
An end-to-end Machine Learning engineering project designed to predict food delivery durations (in minutes) based on historical delivery parameters such as delivery distance, weather conditions, traffic intensity, order preparation time, and courier experience.

## Project Objective
The objective of this project is to develop a reliable, production-ready regression model that accurately forecasts food delivery times. The project follows standard industry MLOps practices, progressing from exploratory data analysis and modular feature engineering to model comparison, hyperparameter tuning, model serialization, and serving via a FastAPI backend paired with an interactive frontend interface.

## Current Phase
**Phase 3: Exploratory Data Analysis (EDA)**
- Univariate distribution analysis (histograms and KDE curves) for numerical features.
- Categorical frequency analysis (count plots) across ambient and operational factors.
- Bivariate scatter and regression analysis against target `Delivery_Time_min`.
- Multivariate correlation heatmap identifying strong drivers and verifying absence of multicollinearity.
- Outlier detection and validation via IQR method.
- Documented findings in `notebooks/02_eda.ipynb`.

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
│   └── model_training.ipynb
│
├── src/                   # Production Python source modules
│   ├── __init__.py
│   ├── preprocess.py      # Data cleaning and feature engineering (future phase)
│   ├── train.py           # Model training pipelines (future phase)
│   └── predict.py         # Inference logic (future phase)
│
├── models/                # Serialized model artifacts (.pkl, .joblib)
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
