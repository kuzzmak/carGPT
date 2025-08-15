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

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database.database import Database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="CarGPT Backend API",
    description="REST API for car ads data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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
    insertion_time: Optional[datetime]
    date_created: datetime
    price: Optional[float]
    location: Optional[str]
    make: Optional[str]
    model: Optional[str]
    type: Optional[str]
    chassis_number: Optional[str]
    manufacture_year: Optional[int]
    model_year: Optional[int]
    mileage: Optional[int]
    engine: Optional[str]
    power: Optional[int]
    displacement: Optional[int]
    transmission: Optional[str]
    condition: Optional[str]
    owner: Optional[str]
    service_book: Optional[bool]
    garaged: Optional[bool]
    in_traffic_since: Optional[int]
    first_registration_in_croatia: Optional[int]
    registered_until: Optional[str]
    fuel_consumption: Optional[str]
    eco_category: Optional[str]
    number_of_gears: Optional[str]
    warranty: Optional[str]
    average_co2_emission: Optional[str]
    video_call_viewing: Optional[bool]
    gas: Optional[bool]
    auto_warranty: Optional[str]
    number_of_doors: Optional[int]
    chassis_type: Optional[str]
    number_of_seats: Optional[int]
    drive_type: Optional[str]
    color: Optional[str]
    metalic_color: Optional[bool]
    suspension: Optional[str]
    tire_size: Optional[str]

    class Config:
        from_attributes = True


class SearchCriteria(BaseModel):
    """Model for search criteria."""
    make: Optional[str] = None
    model: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    manufacture_year_min: Optional[int] = None
    manufacture_year_max: Optional[int] = None
    mileage_max: Optional[int] = None
    location: Optional[str] = None
    engine: Optional[str] = None
    transmission: Optional[str] = None
    condition: Optional[str] = None


class TextSearchRequest(BaseModel):
    """Model for text search request."""
    search_term: str = Field(..., description="Text to search for")
    fields: Optional[List[str]] = Field(default=None, description="Fields to search in")


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
    avg_price: Optional[float]


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
        database_connected=database_connected
    )


@app.get("/ads", response_model=List[AdResponse])
async def get_ads(limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of ads to return")):
    """Get all ads with optional limit."""
    try:
        ads = db.get_all_ads(limit=limit)
        return ads
    except Exception as e:
        logger.error(f"Error fetching ads: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/ads/search", response_model=List[AdResponse])
async def search_ads(
    criteria: SearchCriteria,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of results to return")
):
    """Search ads by criteria."""
    try:
        # Convert the search criteria to a dictionary, filtering out None values
        search_dict = {}
        
        if criteria.make:
            search_dict['make'] = criteria.make
        if criteria.model:
            search_dict['model'] = criteria.model
        if criteria.location:
            search_dict['location'] = criteria.location
        if criteria.engine:
            search_dict['engine'] = criteria.engine
        if criteria.transmission:
            search_dict['transmission'] = criteria.transmission
        if criteria.condition:
            search_dict['condition'] = criteria.condition
        
        # For range queries, we'll need to modify the database method or handle them differently
        # For now, let's use exact matches for the basic implementation
        ads = db.get_ads_by_criteria(search_dict, limit=limit)
        return ads
    except Exception as e:
        logger.error(f"Error searching ads: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/ads/search/text", response_model=List[AdResponse])
async def search_ads_by_text(
    search_request: TextSearchRequest,
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of results to return")
):
    """Search ads by text in specified fields."""
    try:
        ads = db.search_ads_by_text(
            search_term=search_request.search_term,
            fields=search_request.fields,
            limit=limit
        )
        return ads
    except Exception as e:
        logger.error(f"Error searching ads by text: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
            avg_price=None  # Placeholder - would need additional DB method
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
