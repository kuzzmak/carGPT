from datetime import datetime

from pydantic import BaseModel, Field


class AdResponse(BaseModel):
    """Response model for ad data."""

    id: int
    insertion_time: datetime | None
    date_created: datetime
    price: float | None
    location: str | None
    make: str | None
    model: str | None
    type: str | None
    chassis_number: str | None
    manufacture_year: int | None
    model_year: int | None
    mileage: int | None
    engine: str | None
    power: int | None
    displacement: int | None
    transmission: str | None
    condition: str | None
    owner: str | None
    service_book: bool | None
    garaged: bool | None
    in_traffic_since: int | None
    first_registration_in_croatia: int | None
    registered_until: str | None
    fuel_consumption: str | None
    eco_category: str | None
    number_of_gears: str | None
    warranty: str | None
    average_co2_emission: str | None
    video_call_viewing: bool | None
    gas: bool | None
    auto_warranty: str | None
    number_of_doors: int | None
    chassis_type: str | None
    number_of_seats: int | None
    drive_type: str | None
    color: str | None
    metalic_color: bool | None
    suspension: str | None
    tire_size: str | None

    class Config:
        from_attributes = True


class SearchCriteria(BaseModel):
    """Model for search criteria."""

    make: str | None = None
    model: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    manufacture_year_min: int | None = None
    manufacture_year_max: int | None = None
    mileage_min: int | None = None
    mileage_max: int | None = None
    power_min: int | None = None
    power_max: int | None = None
    location: str | None = None
    engine: str | None = None
    transmission: str | None = None
    condition: str | None = None
    text_search: str | None = None
    text_search_fields: list[str] | None = None


class TextSearchRequest(BaseModel):
    """Model for text search request."""

    search_term: str = Field(..., description="Text to search for")
    fields: list[str] | None = Field(
        default=None, description="Fields to search in"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: datetime
    database_connected: bool


class StatsResponse(BaseModel):
    """Database statistics response."""

    total_ads: int
    unique_makes: int
    unique_models: int
    avg_price: float | None


class ChatMessage(BaseModel):
    """Model for chat message."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class ChatRequest(BaseModel):
    """Model for chat request."""

    session_id: str = Field(..., description="Session ID for the chat")
    message: str = Field(..., description="User message")


class ChatResponse(BaseModel):
    """Model for chat response."""

    response: str = Field(..., description="Assistant response")
    timestamp: datetime = Field(default_factory=datetime.now)
