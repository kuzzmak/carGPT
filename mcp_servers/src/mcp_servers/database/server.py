import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_servers.paths import MCP_SERVERS_DIR

from shared.database import AdColumns, Database
from shared.logging_config import get_logger, setup_logging

# TODO: add resources, prompts? to the server

# Setup MCP-specific logging with base configuration extension
logging_config_path = MCP_SERVERS_DIR / "logging_config.yaml"
setup_logging(logging_config_path)
logger = get_logger("mcp_servers")

mcp = FastMCP(
    "Database Server", port=int(os.environ["ADS_DB_MCP_SERVER_PORT"])
)

try:
    db = Database()
    db.create_ads_table()  # Ensure table exists
    logger.info("Database connection established")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    sys.exit(1)


@mcp.tool()
def get_ad_by_id(ad_id: int) -> dict[str, Any] | None:
    """Get a specific ad by its ID"""
    if db is None:
        return {"error": "Database connection not available"}

    logger.debug(f"get_ad_by_id({ad_id})")
    ad = db.get_ad_by_id(ad_id)

    # Enrich ad with image URLs
    if ad and ad.get("id"):
        image_data = db.get_images_by_ad_id(ad["id"])
        ad["images"] = (
            [img["image_url"] for img in image_data] if image_data else []
        )

    return ad


@mcp.tool()
def get_all_ads(limit: int = 100) -> list[dict[str, Any]]:
    """Get all ads with an optional limit (default: 100)"""
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(f"get_all_ads(limit={limit})")
    return db.get_all_ads(limit)


@mcp.tool()
def search_ads(
    make: str | None = None,
    model: str | None = None,
    location: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    search_term: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Search ads with support for exact matches, price range, and text search.

    This is the primary search function that combines exact criteria, price range filtering,
    and text search capabilities. Use this for most search operations.

    Args:
        make: Exact make to search for (e.g., 'BMW', 'Mercedes', 'Audi')
        model: Exact model to search for (e.g., 'X5', 'C-Class', 'A4')
        location: Exact location to search for (e.g., 'Zagreb', 'Split', 'Rijeka')
        min_price: Minimum price in the range (inclusive)
        max_price: Maximum price in the range (inclusive)
        search_term: Text to search for across make, model, location, and type fields (case-insensitive)
        limit: Maximum number of results to return (default: 100)

    Returns:
        List of ad dictionaries matching the criteria, ordered by insertion_time DESC (newest first)

    Examples:
        # 1. Search for BMW cars only
        search_ads(make="BMW")

        # 2. Search for BMW cars with price between 10,000 and 50,000
        search_ads(make="BMW", min_price=10000, max_price=50000)

        # 3. Search for cars in Zagreb with max price 30,000
        search_ads(location="Zagreb", max_price=30000)

        # 4. Search for BMW X5 specifically
        search_ads(make="BMW", model="X5")

        # 5. Search for cars above 25,000 in price
        search_ads(min_price=25000)

        # 6. Search for cars below 20,000 in price
        search_ads(max_price=20000)

        # 7. Text search for "Sport" in any text field
        search_ads(search_term="Sport")

        # 8. Combine exact match with text search: BMW cars with "Automatic" mentioned
        search_ads(make="BMW", search_term="Automatic")

        # 9. Complex search: BMW cars in Zagreb, price 20k-40k, with "SUV" mentioned
        search_ads(make="BMW", location="Zagreb", min_price=20000, max_price=40000, search_term="SUV")

        # 10. Get first 10 results only
        search_ads(make="Mercedes", limit=10)

        # 11. Search for all ads (no criteria)
        search_ads()

    Common Use Cases:
        - Find cars by brand: search_ads(make="BMW")
        - Find cars in price range: search_ads(min_price=15000, max_price=35000)
        - Find local cars: search_ads(location="Zagreb")
        - Find specific models: search_ads(make="Volkswagen", model="Golf")
        - Search with keywords: search_ads(search_term="automatic transmission")
        - Combined searches: search_ads(make="Audi", location="Split", max_price=30000)
    """
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(
        f"search_ads(make={make}, model={model}, location={location}, min_price={min_price}, max_price={max_price}, search_term={search_term}, limit={limit})"
    )

    # Build exact criteria
    exact_criteria = {}
    if make:
        exact_criteria["make"] = make
    if model:
        exact_criteria["model"] = model
    if location:
        exact_criteria["location"] = location

    # Build range criteria for price
    range_criteria = {}
    if min_price is not None or max_price is not None:
        price_range = {}
        if min_price is not None:
            price_range["min"] = min_price
        if max_price is not None:
            price_range["max"] = max_price
        range_criteria[AdColumns.PRICE] = price_range

    # Build text search criteria
    text_search = None
    if search_term:
        # Note: Using Any type to work around the incorrect type annotation in database.py
        text_search = {"term": search_term}  # type: ignore

    logger.debug("Executing search with criteria:")
    logger.debug(f"  Exact: {exact_criteria}")
    logger.debug(f"  Range: {range_criteria}")
    logger.debug(f"  Text: {text_search}")
    logger.debug(f"  Limit: {limit}")

    ads = db.search_ads(
        exact_criteria=exact_criteria if exact_criteria else None,
        range_criteria=range_criteria if range_criteria else None,
        text_search=text_search,
        limit=limit,
    )

    # Enrich ads with image URLs
    for ad in ads:
        ad_id = ad.get("id")
        if ad_id:
            image_data = db.get_images_by_ad_id(ad_id)
            ad["images"] = (
                [img["image_url"] for img in image_data] if image_data else []
            )

    logger.debug("Found ads:")
    for ad in ads:
        logger.debug(ad)

    return ads


@mcp.tool()
def search_ads_by_text(
    search_term: str, fields: list[str] | None = None, limit: int = 100
) -> list[dict[str, Any]]:
    """Search ads by text across multiple fields (default: make, model, location, type).

    This tool provides focused text search capabilities across specific fields.
    Use this when you need to search for specific terms in particular fields.

    Args:
        search_term: The text to search for (case-insensitive, partial matches supported)
        fields: List of field names to search in. If None, searches in: make, model, location, type.
                Available fields: make, model, location, type, engine, transmission, condition,
                owner, fuel_consumption, eco_category, warranty, chassis_type, drive_type,
                color, suspension, tire_size, internal_code
        limit: Maximum number of results to return (default: 100)

    Returns:
        List of ad dictionaries where the search term was found, ordered by insertion_time DESC

    Examples:
        # 1. Search for "BMW" in default fields (make, model, location, type)
        search_ads_by_text("BMW")

        # 2. Search for "automatic" in transmission field only
        search_ads_by_text("automatic", fields=["transmission"])

        # 3. Search for "diesel" in engine field
        search_ads_by_text("diesel", fields=["engine"])

        # 4. Search across multiple specific fields
        search_ads_by_text("sport", fields=["model", "type"])

        # 5. Search for color
        search_ads_by_text("blue", fields=["color"])

        # 6. Search for fuel efficiency
        search_ads_by_text("5.5", fields=["fuel_consumption"])

        # 7. Search for specific conditions
        search_ads_by_text("excellent", fields=["condition"])

        # 8. Search in location with partial matches
        search_ads_by_text("Zagreb")  # Will find "Zagreb", "Zagreb Center", etc.

        # 9. Case-insensitive search
        search_ads_by_text("bmw")  # Will find "BMW", "Bmw", "bmw"

        # 10. Search with limit
        search_ads_by_text("volkswagen", limit=20)

    Common Use Cases:
        - Brand search: search_ads_by_text("Mercedes")
        - Transmission type: search_ads_by_text("manual", fields=["transmission"])
        - Engine search: search_ads_by_text("TDI", fields=["engine"])
        - Location search: search_ads_by_text("Split")
        - Car type: search_ads_by_text("SUV", fields=["type"])
        - Condition: search_ads_by_text("excellent", fields=["condition"])
    """
    if db is None:
        return [{"error": "Database connection not available"}]

    logger.debug(
        f"search_ads_by_text(search_term='{search_term}', fields={fields}, limit={limit})"
    )
    ads = db.search_ads_by_text(search_term, fields, limit)

    # Enrich ads with image URLs
    for ad in ads:
        ad_id = ad.get("id")
        if ad_id:
            image_data = db.get_images_by_ad_id(ad_id)
            ad["images"] = (
                [img["image_url"] for img in image_data] if image_data else []
            )

    return ads


@mcp.tool()
def get_ads_count() -> int:
    """Get the total number of ads in the database"""
    if db is None:
        return 0

    logger.debug("get_ads_count()")
    return db.get_ads_count()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
