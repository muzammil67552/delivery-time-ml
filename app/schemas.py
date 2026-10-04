"""Pydantic schemas for the Delivery Time Prediction API."""

from typing import Literal, Optional, List, Dict, Any
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
    Destination_Address: Optional[str] = Field(
        default=None,
        description="Customer delivery street address or landmark (optional).",
        examples=["Empire State Commercial Hub, 350 5th Ave"],
    )
    Dropoff_Lat: Optional[float] = Field(
        default=None,
        description="Customer delivery destination latitude (optional).",
        examples=[40.7484],
    )
    Dropoff_Lng: Optional[float] = Field(
        default=None,
        description="Customer delivery destination longitude (optional).",
        examples=[-73.9857],
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
                "Destination_Address": "Empire State Commercial Hub, 350 5th Ave",
                "Dropoff_Lat": 40.7484,
                "Dropoff_Lng": -73.9857,
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


class HotelProfilePayload(BaseModel):
    """Schema for creating or updating hotel profile in SQLite."""

    hotel_name: str = Field(..., min_length=2, max_length=120, examples=["The Grand Palace Hotel"])
    branch_or_address: str = Field(default="", max_length=200, examples=["Downtown Hub, Main Avenue 4"])
    contact_email: str = Field(default="", max_length=100, examples=["logistics@grandpalace.com"])
    contact_phone: str = Field(default="", max_length=30, examples=["+1 (555) 234-5678"])
    default_prep_time_min: float = Field(default=15.0, ge=0, le=180, examples=[15.0])
    default_vehicle_type: VehicleType = Field(default="Scooter", examples=["Scooter"])
    latitude: Optional[float] = Field(default=40.7306, ge=-90.0, le=90.0, examples=[40.7306])
    longitude: Optional[float] = Field(default=-73.9866, ge=-180.0, le=180.0, examples=[-73.9866])
    city_preset: Optional[str] = Field(default="New York", max_length=60, examples=["New York"])


class HotelProfileResponse(BaseModel):
    """Schema for hotel profile status response."""

    is_configured: bool
    profile: Optional[Dict[str, Any]] = None


class RouteCalculationResponse(BaseModel):
    """Schema for calculated navigation route and road distance."""

    distance_km: float = Field(..., description="Estimated or live road distance in kilometers.")
    duration_min: float = Field(..., description="Estimated travel duration in minutes.")
    route_coords: List[List[float]] = Field(..., description="Ordered list of [latitude, longitude] polyline waypoints.")
    source: str = Field(..., description="Route calculation engine source.")


# ==============================================================================
# Rider & Courier Fleet Schemas
# ==============================================================================

class RiderCreatePayload(BaseModel):
    """Schema for registering a new delivery rider in the fleet."""

    rider_name: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Full name of the courier.", examples=["Tariq Khan"])
    name: Optional[str] = Field(default=None, min_length=2, max_length=100, description="Alias for rider name.")
    phone: str = Field(..., min_length=5, max_length=30, description="Contact phone or mobile number.", examples=["+92 300 1234567"])
    vehicle_type: VehicleType = Field(default="Scooter", description="Primary transport vehicle mode.", examples=["Scooter"])
    courier_exp_yrs: float = Field(default=2.0, ge=0.0, le=50.0, description="Courier delivery experience in years.", examples=[3.5])
    rating: Optional[float] = Field(default=4.8, ge=1.0, le=5.0, description="Customer service rating [1.0, 5.0].", examples=[4.9])
    status: Optional[str] = Field(default="Available", description="Operational availability status.", examples=["Available"])
    current_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Current GPS latitude.", examples=[24.8385])
    current_lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Current GPS longitude.", examples=[67.0810])
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Alias for latitude.")
    lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Alias for longitude.")
    current_address: Optional[str] = Field(default="", max_length=200, description="Current landmark or street location.", examples=["Defence View, Karachi"])
    address: Optional[str] = Field(default=None, max_length=200, description="Alias for address.")

    def model_post_init(self, __context: Any) -> None:
        if not self.rider_name and self.name:
            self.rider_name = self.name
        if self.current_lat is None and self.lat is not None:
            self.current_lat = self.lat
        if self.current_lng is None and self.lng is not None:
            self.current_lng = self.lng
        if not self.current_address and self.address:
            self.current_address = self.address
        if not self.rider_name:
            self.rider_name = "Courier Rider"


class RiderUpdateLocationPayload(BaseModel):
    """Schema for updating a rider's live GPS coordinates."""

    current_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Live latitude coordinate.")
    current_lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Live longitude coordinate.")
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Alias for latitude.")
    lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Alias for longitude.")
    current_address: Optional[str] = Field(default=None, max_length=200, description="Optional street or landmark address.")
    address: Optional[str] = Field(default=None, max_length=200, description="Alias for address.")

    def get_lat(self) -> float:
        return self.current_lat if self.current_lat is not None else (self.lat or 0.0)

    def get_lng(self) -> float:
        return self.current_lng if self.current_lng is not None else (self.lng or 0.0)

    def get_address(self) -> Optional[str]:
        return self.current_address or self.address



class RiderUpdateStatusPayload(BaseModel):
    """Schema for toggling rider operational status."""

    status: str = Field(..., description="Target status: Available, On Delivery, Busy, Offline.", examples=["Available"])


class RiderListResponse(BaseModel):
    """Schema for list of fleet riders with summary metrics."""

    total: int
    stats: Dict[str, Any]
    riders: List[Dict[str, Any]]

