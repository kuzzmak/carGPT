"""
FastAPI server for CarGPT backend.

This FastAPI application provides REST API endpoints for accessing car ads data
stored in PostgreSQL database through the Database class.

Endpoints:
- GET /ads - Get all ads (with optional limit)
- GET /ads/{ad_id} - Get a specific ad by ID
- POST /ads/search - Search ads by criteria
- POST /ads/search/text - Search ads by text
- GET /health - Health check endpoint
- GET /stats - Get database statistics
"""

from datetime import datetime
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.database import Database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CarGPT Backend API",
    description="REST API for car ads data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize database connection
try:
    db = Database()
    logger.info("Database connection initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise


# Pydantic models for request/response
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
    mileage_max: int | None = None
    location: str | None = None
    engine: str | None = None
    transmission: str | None = None
    condition: str | None = None


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


# API Endpoints


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        db.get_ads_count()
        database_connected = True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        database_connected = False

    return HealthResponse(
        status="healthy" if database_connected else "unhealthy",
        timestamp=datetime.now(),
        database_connected=database_connected,
    )


@app.get("/ads", response_model=list[AdResponse])
async def get_ads(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of ads to return",
    ),
):
    """Get all ads with optional limit."""
    try:
        return db.get_all_ads(limit=limit)
    except Exception as e:
        logger.error(f"Error fetching ads: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.get("/ads/{ad_id}", response_model=AdResponse)
async def get_ad_by_id(ad_id: int):
    """Get a specific ad by ID."""
    try:
        ad = db.get_ad_by_id(ad_id)
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")
        return ad
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ad {ad_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.post("/ads/search", response_model=list[AdResponse])
async def search_ads(
    criteria: SearchCriteria,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    ),
):
    """Search ads by criteria."""
    try:
        # Convert the search criteria to a dictionary, filtering out None values
        search_dict = {}

        if criteria.make:
            search_dict["make"] = criteria.make
        if criteria.model:
            search_dict["model"] = criteria.model
        if criteria.location:
            search_dict["location"] = criteria.location
        if criteria.engine:
            search_dict["engine"] = criteria.engine
        if criteria.transmission:
            search_dict["transmission"] = criteria.transmission
        if criteria.condition:
            search_dict["condition"] = criteria.condition

        # For range queries, we'll need to modify the database method or handle them differently
        # For now, let's use exact matches for the basic implementation
        return db.get_ads_by_criteria(search_dict, limit=limit)
    except Exception as e:
        logger.error(f"Error searching ads: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.post("/ads/search/text", response_model=list[AdResponse])
async def search_ads_by_text(
    search_request: TextSearchRequest,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    ),
):
    """Search ads by text in specified fields."""
    try:
        return db.search_ads_by_text(
            search_term=search_request.search_term,
            fields=search_request.fields,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error searching ads by text: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.get("/stats", response_model=StatsResponse)
async def get_database_stats():
    """Get database statistics."""
    try:
        total_ads = db.get_ads_count()

        # Get unique makes and models count (this would require additional database methods)
        # For now, we'll return basic stats
        return StatsResponse(
            total_ads=total_ads,
            unique_makes=0,  # Placeholder - would need additional DB method
            unique_models=0,  # Placeholder - would need additional DB method
            avg_price=None,  # Placeholder - would need additional DB method
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
