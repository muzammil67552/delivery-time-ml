"""Pydantic schemas for the Delivery Time Prediction API."""

from typing import Literal
from pydantic import BaseModel, Field


WeatherType = Literal["Clear", "Rainy", "Foggy", "Snowy", "Windy"]
TrafficLevelType = Literal["Low", "Medium", "High"]
TimeOfDayType = Literal["Morning", "Afternoon", "Evening", "Night"]
VehicleType = Literal["Bike", "Scooter", "Car"]


class DeliveryPredictionRequest(BaseModel):
    """Schema for validating incoming delivery prediction requests."""

    Distance_km: float = Field(
        ...,
        gt=0,
        le=100,
        description="Distance from restaurant to destination in kilometers (0, 100].",
        examples=[8.5],
    )
    Weather: WeatherType = Field(
        ...,
        description="Prevailing weather condition.",
        examples=["Clear"],
    )
    Traffic_Level: TrafficLevelType = Field(
        ...,
        description="Current traffic congestion level.",
        examples=["Medium"],
    )
    Time_of_Day: TimeOfDayType = Field(
        ...,
        description="Dispatch time of day window.",
        examples=["Evening"],
    )
    Vehicle_Type: VehicleType = Field(
        ...,
        description="Mode of delivery transport.",
        examples=["Scooter"],
    )
    Preparation_Time_min: float = Field(
        ...,
        ge=0,
        le=180,
        description="Kitchen food preparation time in minutes [0, 180].",
        examples=[15.0],
    )
    Courier_Experience_yrs: float = Field(
        ...,
        ge=0,
        le=50,
        description="Courier experience in years [0, 50].",
        examples=[3.0],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "Distance_km": 8.5,
                "Weather": "Clear",
                "Traffic_Level": "Medium",
                "Time_of_Day": "Evening",
                "Vehicle_Type": "Scooter",
                "Preparation_Time_min": 15.0,
                "Courier_Experience_yrs": 3.0,
            }
        }
    }


class DeliveryPredictionResponse(BaseModel):
    """Schema for prediction output response."""

    predicted_delivery_time_min: float = Field(
        ...,
        description="Predicted total delivery duration in minutes.",
        examples=[49.93],
    )


class HealthResponse(BaseModel):
    """Schema for API health status check."""

    status: str = Field(..., examples=["healthy"])
    model_loaded: bool = Field(..., examples=[True])


class RootResponse(BaseModel):
    """Schema for root endpoint response."""

    message: str = Field(..., examples=["Delivery Time Prediction API is running"])
    status: str = Field(..., examples=["online"])
