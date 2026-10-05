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
    Hotel_ID: Optional[int] = Field(
        default=None,
        description="Hotel Account ID scoping the prediction log (optional).",
        examples=[1],
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
    password: Optional[str] = Field(default=None, max_length=128, description="Optional account password")


class HotelProfileResponse(BaseModel):
    """Schema for hotel profile status response."""

    is_configured: bool
    profile: Optional[Dict[str, Any]] = None


class HotelLoginPayload(BaseModel):
    """Schema for logging into a hotel profile."""

    hotel_name: str = Field(..., min_length=1, max_length=120, description="Hotel or Restaurant Name", examples=["Bella Vista Trattoria"])
    email: str = Field(..., min_length=3, max_length=100, description="Owner / Manager Email", examples=["manager@bellavista.com"])
    password: str = Field(..., min_length=1, max_length=128, description="Account Password", examples=["secret123"])



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

    hotel_id: Optional[int] = Field(default=None, description="Associated Hotel ID.")
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
    email: Optional[str] = Field(default=None, max_length=120, description="Courier email address for automated dispatch notifications.", examples=["tariq.khan@deliveryhub.com"])
    rider_email: Optional[str] = Field(default=None, max_length=120, description="Alias for email.")

    def model_post_init(self, __context: Any) -> None:
        if not self.rider_name and self.name:
            self.rider_name = self.name
        if not self.email and self.rider_email:
            self.email = self.rider_email
        if not self.email and self.rider_name:
            clean_name = self.rider_name.lower().replace(" ", ".")
            self.email = f"{clean_name}@deliveryhub.com"
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


# ==============================================================================
# Automated Dispatch Engine & Cascading Pipeline Schemas
# ==============================================================================

class DispatchCreatePayload(BaseModel):
    """Schema for initiating an automated cascading delivery dispatch."""

    client_name: str = Field(..., min_length=1, max_length=120, description="Customer recipient name.", examples=["Sarah Connor"])
    client_phone: str = Field(..., min_length=5, max_length=30, description="Customer contact phone number.", examples=["+1 (555) 987-6543"])
    client_address: str = Field(..., min_length=3, max_length=250, description="Customer dropoff street address.", examples=["350 5th Ave, Floor 14"])
    tracking_id: Optional[str] = Field(default=None, description="System-generated unique tracking ID.", examples=["TRK-A7B8C9"])
    hotel_id: Optional[int] = Field(default=None, description="Origin hotel ID.")
    dest_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Destination latitude.")
    dest_lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Destination longitude.")
    vehicle_type: Optional[VehicleType] = Field(default=None, description="Vehicle transport type.")
    prep_time_min: Optional[float] = Field(default=None, ge=0.0, le=180.0, description="Order preparation time.")
    traffic_level: Optional[TrafficLevelType] = Field(default=None, description="Current traffic level.")
    items: Optional[List["KitchenItemInput"]] = Field(default=None, description="Food and beverage items ordered for kitchen preparation.")


class DispatchCompletePayload(BaseModel):
    """Schema for completing a delivery and recording performance."""

    actual_duration_min: Optional[float] = Field(default=None, ge=1.0, le=300.0, description="Actual delivery duration in minutes.")
    actual_delivery_minutes: Optional[float] = Field(default=None, ge=1.0, le=300.0, description="Alias for actual delivery duration in minutes.")

    def get_actual_duration(self) -> Optional[float]:
        return self.actual_duration_min if self.actual_duration_min is not None else self.actual_delivery_minutes


# ==============================================================================
# Kitchen Management & Thermal Printing Schemas
# ==============================================================================

class KitchenItemInput(BaseModel):
    """Schema for an individual food or beverage dish ordered for kitchen preparation."""

    item_name: str = Field(..., min_length=1, max_length=150, description="Name of the food or beverage dish.", examples=["Spicy Chicken Burger"])
    quantity: int = Field(default=1, ge=1, le=100, description="Quantity of this item ordered.", examples=[2])
    special_instructions: Optional[str] = Field(default=None, max_length=300, description="Customizations, e.g. spicy level, no onions, extra sauce.", examples=["Extra spicy, no onions"])
    unit_price: Optional[float] = Field(default=0.0, ge=0.0, description="Item unit price (used for delivery bill calculation, excluded from KOT).", examples=[12.50])


class KitchenStatusUpdatePayload(BaseModel):
    """Schema for updating preparation status of a kitchen queue item."""

    item_id: Optional[int] = Field(default=None, description="Database ID of the specific kitchen queue item.")
    tracking_id: Optional[str] = Field(default=None, description="Optional tracking ID to transition all items for an order.")
    status: str = Field(..., description="Target status: Pending, Preparing, Ready, Completed.", examples=["Preparing"])


class KitchenManualOrderPayload(BaseModel):
    """Schema for creating a kitchen queue order directly."""

    hotel_id: Optional[int] = Field(default=None, description="Associated Hotel ID.")
    order_id: Optional[str] = Field(default=None, description="Order identifier.")
    tracking_id: Optional[str] = Field(default=None, description="Unique delivery tracking ID.")
    client_name: Optional[str] = Field(default="Valued Customer", description="Client or guest name.")
    client_phone: Optional[str] = Field(default="N/A", description="Client phone number.")
    client_address: Optional[str] = Field(default="Local Delivery Hub", description="Delivery address.")
    items: List[KitchenItemInput] = Field(..., min_length=1, description="List of food/beverage items to prepare.")


