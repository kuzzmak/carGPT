from typing import Any

from mcp.server.fastmcp import FastMCP

from backend.database import AdColumns
from backend.database.database import Database
from backend.paths import BACKEND_DIR

from shared.src.shared.logging_config import get_logger, setup_logging

# Setup MCP-specific logging with base configuration extension
logging_config_path = (
    BACKEND_DIR
    / "src"
    / "backend"
    / "mcp_servers"
    / "database"
    / "logging_config_mcp.yaml"
)
setup_logging(logging_config_path)
logger = get_logger("mcp_database_server")

# Create server
mcp = FastMCP("Database Server")

# Initialize database connection
try:
    db = Database()
    db.create_ads_table()  # Ensure table exists
    logger.info("Database connection established")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    db = None


@mcp.tool()
def get_ad_by_id(ad_id: int) -> dict[str, Any] | None:
    """Get a specific ad by its ID"""
    if db is None:
        return {"error": "Database connection not available"}

    logger.debug(f"get_ad_by_id({ad_id})")
    return db.get_ad_by_id(ad_id)


@mcp.tool()
def get_all_ads(limit: int = 100) -> list[dict[str, Any]]:
    """Get all ads with an optional limit (default: 100)"""
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(f"get_all_ads(limit={limit})")
    return db.get_all_ads(limit)


@mcp.tool()
def search_ads_by_criteria(
    make: str | None = None,
    model: str | None = None,
    location: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search ads by specific criteria like make, model, location, and price range"""
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(
        f"search_ads_by_criteria(make={make}, model={model}, location={location}, min_price={min_price}, max_price={max_price}, limit={limit})"
    )

    criteria = {}
    if make:
        criteria["make"] = make
    if model:
        criteria["model"] = model
    if location:
        criteria["location"] = location

    # For price range, we need to use a custom query since get_ads_by_criteria doesn't support ranges
    if min_price is not None or max_price is not None:
        # Build a more complex search for price ranges
        return search_ads_with_price_range(
            criteria, min_price, max_price, limit
        )

    return db.get_ads_by_criteria(criteria, limit)


@mcp.tool()
def search_ads_by_text(
    search_term: str, fields: list[str] | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Search ads by text across multiple fields (default: make, model, location, type)"""
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(
        f"search_ads_by_text(search_term='{search_term}', fields={fields}, limit={limit})"
    )
    return db.search_ads_by_text(search_term, fields, limit)


@mcp.tool()
def get_ads_count() -> int:
    """Get the total number of ads in the database"""
    if db is None:
        return 0

    logger.debug("get_ads_count()")
    return db.get_ads_count()


def search_ads_with_price_range(
    base_criteria: dict[str, Any],
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Helper function to search ads with price range filtering"""
    if db is None:
        return [{"error": "Database connection not available"}]

    try:
        # Build range criteria for price
        range_criteria = {}
        if min_price is not None or max_price is not None:
            price_range = {}
            if min_price is not None:
                price_range["min"] = min_price
            if max_price is not None:
                price_range["max"] = max_price
            range_criteria[AdColumns.PRICE] = price_range

        # Use the new search_ads_with_range method
        return db.search_ads_with_range(
            criteria=base_criteria, range_criteria=range_criteria, limit=limit
        )

    except Exception as e:
        logger.error(f"Error in price range search: {e}")
        return [{"error": f"Search failed: {str(e)}"}]


@mcp.tool()
def search_ads_with_range(
    criteria: dict[str, Any] | None = None,
    range_criteria: dict[str, dict[str, Any]] | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Advanced search with support for range filtering on numerical columns.

    Args:
        criteria: Dictionary of exact match criteria
        range_criteria: Dictionary of range criteria in format:
            {
                'column_name': {'min': min_value, 'max': max_value}
            }
            Supported columns: price, manufacture_year, model_year, mileage, power,
            displacement, in_traffic_since, first_registration_in_croatia,
            number_of_doors, number_of_seats
        limit: Maximum number of results to return

    Example:
        range_criteria = {
            'price': {'min': 10000, 'max': 50000},
            'mileage': {'max': 100000},
            'manufacture_year': {'min': 2015}
        }
    """
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(
        f"search_ads_with_range(criteria={criteria}, range_criteria={range_criteria}, limit={limit})"
    )

    return db.search_ads_with_range(
        criteria=criteria, range_criteria=range_criteria, limit=limit
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
