from collections.abc import Generator
from datetime import UTC, datetime
import logging
from typing import Any

import psycopg2
import pytest
from testcontainers.postgres import PostgresContainer

from backend.database import AdColumns, Database

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def postgres_container(
    test_db_name: str, test_db_user: str, test_db_password: str, test_db_port: int
) -> Generator[dict[str, Any], None, None]:
    """Session-scoped fixture that provides a PostgreSQL container."""
    with PostgresContainer(
        "postgres:15",
        dbname=test_db_name,
        username=test_db_user,
        password=test_db_password,
    ) as postgres:
        # Get connection parameters
        db_params = {
            "dbname": postgres.dbname,
            "user": postgres.username,
            "password": postgres.password,
            "host": postgres.get_container_host_ip(),
            "port": postgres.get_exposed_port(test_db_port),
        }

        yield db_params


@pytest.fixture(scope="function")
def database(postgres_container: dict[str, Any]) -> Generator[Database, None, None]:
    """Function-scoped fixture that provides a fresh Database instance for each test."""
    # Clear singleton instance to ensure fresh database for each test
    Database._instance = None

    # Create database instance
    db = Database(**postgres_container)

    # Create ads table
    db.create_ads_table()

    yield db

    # Cleanup: drop the ads table after each test
    try:
        with db.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ads CASCADE;")
            conn.commit()
    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")

    # Reset singleton
    Database._instance = None


@pytest.fixture
def sample_ad_data() -> dict[str, Any]:
    """Fixture providing sample ad data for testing."""
    return {
        AdColumns.DATE_CREATED: datetime(2024, 1, 15, 12, 30, tzinfo=UTC),
        AdColumns.PRICE: 25000.50,
        AdColumns.LOCATION: "Zagreb",
        AdColumns.MAKE: "Volkswagen",
        AdColumns.MODEL: "Golf",
        AdColumns.TYPE: "Hatchback",
        AdColumns.CHASSIS_NUMBER: "WVWZZZ1JZ3W386754",
        AdColumns.MANUFACTURE_YEAR: 2020,
        AdColumns.MODEL_YEAR: 2020,
        AdColumns.MILEAGE: 45000,
        AdColumns.ENGINE: "1.5 TSI",
        AdColumns.POWER: 150,
        AdColumns.DISPLACEMENT: 1498,
        AdColumns.TRANSMISSION: "Manual",
        AdColumns.CONDITION: "Excellent",
        AdColumns.OWNER: "First owner",
        AdColumns.SERVICE_BOOK: True,
        AdColumns.GARAGED: True,
        AdColumns.IN_TRAFFIC_SINCE: 2020,
        AdColumns.FIRST_REGISTRATION_IN_CROATIA: 2020,
        AdColumns.REGISTERED_UNTIL: "2025-12",
        AdColumns.FUEL_CONSUMPTION: "5.8L/100km",
        AdColumns.ECO_CATEGORY: "EURO6",
        AdColumns.NUMBER_OF_GEARS: "6",
        AdColumns.WARRANTY: "2 years",
        AdColumns.AVERAGE_CO2_EMISSION: "132g/km",
        AdColumns.VIDEO_CALL_VIEWING: True,
        AdColumns.GAS: False,
        AdColumns.AUTO_WARRANTY: "Yes",
        AdColumns.NUMBER_OF_DOORS: 5,
        AdColumns.CHASSIS_TYPE: "Sedan",
        AdColumns.NUMBER_OF_SEATS: 5,
        AdColumns.DRIVE_TYPE: "FWD",
        AdColumns.COLOR: "Blue",
        AdColumns.METALIC_COLOR: True,
        AdColumns.SUSPENSION: "Standard",
        AdColumns.TIRE_SIZE: "205/55R16",
        AdColumns.INTERNAL_CODE: "VW-GOLF-001",
    }


@pytest.fixture
def sample_ad_data_minimal() -> dict[str, Any]:
    """Fixture providing minimal ad data for testing."""
    return {
        AdColumns.DATE_CREATED: datetime.now(UTC),
        AdColumns.MAKE: "Toyota",
        AdColumns.MODEL: "Corolla",
    }


class TestDatabase:
    """Test class for Database functionality."""

    def test_database_singleton_behavior(self, postgres_container):
        """Test that Database follows singleton pattern."""
        # Clear singleton to start fresh
        Database._instance = None

        db1 = Database(**postgres_container)
        db2 = Database(**postgres_container)

        assert db1 is db2
        assert isinstance(db1, Database)

    def test_database_connection(self, database):
        """Test that database connection works properly."""
        with database.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            version = cursor.fetchone()
            assert version is not None
            assert "PostgreSQL" in version[0]

    def test_create_ads_table(self, database):
        """Test ads table creation."""
        result = database.create_ads_table()
        assert result is True

        # Verify table exists
        with database.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'ads'
                );
            """
            )
            exists = cursor.fetchone()[0]
            assert exists is True

    def test_insert_ad_full_data(self, database, sample_ad_data):
        """Test inserting an ad with full data."""
        ad_id = database.insert_ad(sample_ad_data)

        assert ad_id is not None
        assert isinstance(ad_id, int)
        assert ad_id > 0

    def test_insert_ad_minimal_data(self, database, sample_ad_data_minimal):
        """Test inserting an ad with minimal data."""
        ad_id = database.insert_ad(sample_ad_data_minimal)

        assert ad_id is not None
        assert isinstance(ad_id, int)
        assert ad_id > 0

    def test_insert_ad_empty_data(self, database):
        """Test inserting ad with empty data."""
        ad_id = database.insert_ad({})
        assert ad_id is None

    def test_insert_ad_invalid_columns(self, database):
        """Test inserting ad with invalid columns."""
        invalid_data = {"invalid_column": "some_value", "another_invalid": 123}
        ad_id = database.insert_ad(invalid_data)
        assert ad_id is None

    def test_insert_ad_mixed_valid_invalid_columns(
        self, database, sample_ad_data_minimal
    ):
        """Test inserting ad with mix of valid and invalid columns."""
        mixed_data = sample_ad_data_minimal.copy()
        mixed_data["invalid_column"] = "should_be_ignored"
        mixed_data["another_invalid"] = 999

        ad_id = database.insert_ad(mixed_data)
        assert ad_id is not None

        # Verify only valid data was inserted
        ad = database.get_ad_by_id(ad_id)
        assert ad is not None
        assert "invalid_column" not in ad
        assert "another_invalid" not in ad
        assert ad[AdColumns.MAKE] == sample_ad_data_minimal[AdColumns.MAKE]

    def test_get_ad_by_id(self, database, sample_ad_data):
        """Test retrieving an ad by ID."""
        # Insert ad first
        ad_id = database.insert_ad(sample_ad_data)
        assert ad_id is not None

        # Retrieve ad
        ad = database.get_ad_by_id(ad_id)

        assert ad is not None
        assert ad[AdColumns.ID] == ad_id
        assert ad[AdColumns.MAKE] == sample_ad_data[AdColumns.MAKE]
        assert ad[AdColumns.MODEL] == sample_ad_data[AdColumns.MODEL]
        assert ad[AdColumns.PRICE] == sample_ad_data[AdColumns.PRICE]
        assert ad[AdColumns.INSERTION_TIME] is not None

    def test_get_ad_by_nonexistent_id(self, database):
        """Test retrieving ad with non-existent ID."""
        ad = database.get_ad_by_id(99999)
        assert ad is None

    def test_get_all_ads_empty(self, database):
        """Test getting all ads when database is empty."""
        ads = database.get_all_ads()
        assert ads == []

    def test_get_all_ads_with_limit(self, database, sample_ad_data):
        """Test getting all ads with limit."""
        # Insert multiple ads
        ad_ids = []
        for i in range(5):
            ad_data = sample_ad_data.copy()
            ad_data[AdColumns.MAKE] = f"Make{i}"
            ad_id = database.insert_ad(ad_data)
            ad_ids.append(ad_id)

        # Test with limit
        ads = database.get_all_ads(limit=3)
        assert len(ads) == 3

        # Should be ordered by insertion_time DESC (most recent first)
        assert ads[0][AdColumns.MAKE] == "Make4"  # Last inserted

    def test_get_ads_by_criteria(self, database, sample_ad_data):
        """Test getting ads by search criteria."""
        # Insert test ads
        ad1_data = sample_ad_data.copy()
        ad1_data[AdColumns.MAKE] = "BMW"
        ad1_data[AdColumns.MODEL] = "X5"
        ad1_id = database.insert_ad(ad1_data)

        ad2_data = sample_ad_data.copy()
        ad2_data[AdColumns.MAKE] = "BMW"
        ad2_data[AdColumns.MODEL] = "X3"
        database.insert_ad(ad2_data)

        ad3_data = sample_ad_data.copy()
        ad3_data[AdColumns.MAKE] = "Audi"
        ad3_data[AdColumns.MODEL] = "A4"
        database.insert_ad(ad3_data)

        # Search by make
        bmw_ads = database.get_ads_by_criteria({AdColumns.MAKE: "BMW"})
        assert len(bmw_ads) == 2

        # Search by make and model
        x5_ads = database.get_ads_by_criteria(
            {AdColumns.MAKE: "BMW", AdColumns.MODEL: "X5"}
        )
        assert len(x5_ads) == 1
        assert x5_ads[0][AdColumns.ID] == ad1_id

        # Search with non-existent criteria
        non_existent = database.get_ads_by_criteria({AdColumns.MAKE: "NonExistentMake"})
        assert len(non_existent) == 0

    def test_get_ads_by_criteria_empty_criteria(self, database, sample_ad_data):
        """Test getting ads with empty criteria."""
        database.insert_ad(sample_ad_data)

        ads = database.get_ads_by_criteria({})
        assert len(ads) == 1

    def test_update_ad(self, database, sample_ad_data):
        """Test updating an existing ad."""
        # Insert ad
        ad_id = database.insert_ad(sample_ad_data)
        assert ad_id is not None

        # Update ad
        update_data = {
            AdColumns.PRICE: 30000.00,
            AdColumns.MILEAGE: 50000,
            AdColumns.LOCATION: "Split",
        }
        result = database.update_ad(ad_id, update_data)
        assert result is True

        # Verify update
        updated_ad = database.get_ad_by_id(ad_id)
        assert updated_ad[AdColumns.PRICE] == 30000.00
        assert updated_ad[AdColumns.MILEAGE] == 50000
        assert updated_ad[AdColumns.LOCATION] == "Split"
        # Original data should remain unchanged
        assert updated_ad[AdColumns.MAKE] == sample_ad_data[AdColumns.MAKE]

    def test_update_nonexistent_ad(self, database):
        """Test updating non-existent ad."""
        result = database.update_ad(99999, {AdColumns.PRICE: 15000})
        assert result is False

    def test_update_ad_empty_data(self, database, sample_ad_data):
        """Test updating ad with empty data."""
        ad_id = database.insert_ad(sample_ad_data)
        result = database.update_ad(ad_id, {})
        assert result is False

    def test_update_ad_protected_fields(self, database, sample_ad_data):
        """Test updating protected fields (id, insertion_time)."""
        ad_id = database.insert_ad(sample_ad_data)

        # Try to update protected fields - should be ignored
        update_data = {
            AdColumns.ID: 99999,
            AdColumns.INSERTION_TIME: datetime.now(UTC),
            AdColumns.PRICE: 40000,  # This should work
        }
        result = database.update_ad(ad_id, update_data)
        assert result is True

        # Verify protected fields weren't changed but price was
        updated_ad = database.get_ad_by_id(ad_id)
        assert updated_ad[AdColumns.ID] == ad_id  # ID unchanged
        assert updated_ad[AdColumns.PRICE] == 40000  # Price changed

    def test_delete_ad(self, database, sample_ad_data):
        """Test deleting an ad."""
        # Insert ad
        ad_id = database.insert_ad(sample_ad_data)
        assert ad_id is not None

        # Verify ad exists
        ad = database.get_ad_by_id(ad_id)
        assert ad is not None

        # Delete ad
        result = database.delete_ad(ad_id)
        assert result is True

        # Verify ad is deleted
        deleted_ad = database.get_ad_by_id(ad_id)
        assert deleted_ad is None

    def test_delete_nonexistent_ad(self, database):
        """Test deleting non-existent ad."""
        result = database.delete_ad(99999)
        assert result is False

    def test_get_ads_count(self, database, sample_ad_data):
        """Test getting total ads count."""
        # Initially should be 0
        count = database.get_ads_count()
        assert count == 0

        # Insert ads
        for i in range(3):
            ad_data = sample_ad_data.copy()
            ad_data[AdColumns.MAKE] = f"Make{i}"
            database.insert_ad(ad_data)

        # Count should be 3
        count = database.get_ads_count()
        assert count == 3

        # Delete one ad
        ads = database.get_all_ads()
        database.delete_ad(ads[0][AdColumns.ID])

        # Count should be 2
        count = database.get_ads_count()
        assert count == 2

    def test_search_ads_by_text_default_fields(self, database, sample_ad_data):
        """Test text search in default fields."""
        # Insert test ads
        ad1_data = sample_ad_data.copy()
        ad1_data[AdColumns.MAKE] = "BMW"
        ad1_data[AdColumns.MODEL] = "X5"
        ad1_data[AdColumns.LOCATION] = "Zagreb"
        database.insert_ad(ad1_data)

        ad2_data = sample_ad_data.copy()
        ad2_data[AdColumns.MAKE] = "Audi"
        ad2_data[AdColumns.MODEL] = "BMW"  # BMW in model field
        ad2_data[AdColumns.LOCATION] = "Split"
        database.insert_ad(ad2_data)

        ad3_data = sample_ad_data.copy()
        ad3_data[AdColumns.MAKE] = "Ford"
        ad3_data[AdColumns.MODEL] = "Focus"
        ad3_data[AdColumns.LOCATION] = "BMW Street"  # BMW in location
        database.insert_ad(ad3_data)

        # Search for "BMW" - should find all 3 ads
        results = database.search_ads_by_text("BMW")
        assert len(results) == 3

        # Search for "Zagreb" - should find 1 ad
        results = database.search_ads_by_text("Zagreb")
        assert len(results) == 1
        assert results[0][AdColumns.LOCATION] == "Zagreb"

    def test_search_ads_by_text_custom_fields(self, database, sample_ad_data):
        """Test text search in custom fields."""
        # Insert test ad
        ad_data = sample_ad_data.copy()
        ad_data[AdColumns.ENGINE] = "2.0 TDI"
        ad_data[AdColumns.TRANSMISSION] = "Automatic"
        database.insert_ad(ad_data)

        # Search in engine field
        results = database.search_ads_by_text("TDI", fields=[AdColumns.ENGINE])
        assert len(results) == 1

        # Search in transmission field
        results = database.search_ads_by_text("Auto", fields=[AdColumns.TRANSMISSION])
        assert len(results) == 1

        # Search in non-matching field
        results = database.search_ads_by_text("TDI", fields=[AdColumns.TRANSMISSION])
        assert len(results) == 0

    def test_search_ads_by_text_case_insensitive(self, database, sample_ad_data):
        """Test that text search is case insensitive."""
        ad_data = sample_ad_data.copy()
        ad_data[AdColumns.MAKE] = "BMW"
        database.insert_ad(ad_data)

        # Test different cases
        for search_term in ["BMW", "bmw", "Bmw", "bMw"]:
            results = database.search_ads_by_text(search_term)
            assert len(results) == 1
            assert results[0][AdColumns.MAKE] == "BMW"

    def test_search_ads_by_text_with_limit(self, database, sample_ad_data):
        """Test text search with limit."""
        # Insert multiple ads with same make
        for i in range(5):
            ad_data = sample_ad_data.copy()
            ad_data[AdColumns.MAKE] = "TestMake"
            ad_data[AdColumns.MODEL] = f"Model{i}"
            database.insert_ad(ad_data)

        # Search with limit
        results = database.search_ads_by_text("TestMake", limit=3)
        assert len(results) == 3

    def test_search_ads_by_text_no_results(self, database, sample_ad_data):
        """Test text search with no matching results."""
        database.insert_ad(sample_ad_data)

        results = database.search_ads_by_text("NonExistentBrand")
        assert len(results) == 0


class TestDatabaseErrorHandling:
    """Test error handling in Database class."""

    def test_database_connection_error(self):
        """Test database connection error handling."""
        # Clear singleton
        Database._instance = None

        # Try to connect with invalid parameters
        invalid_params = {
            "host": "nonexistent_host",
            "port": "9999",
            "dbname": "invalid_db",
            "user": "invalid_user",
            "password": "invalid_pass",
        }

        with pytest.raises(psycopg2.Error):
            Database(**invalid_params)

    def test_operations_with_connection_errors(self, postgres_container):
        """Test database operations when connection fails."""
        # Create database with valid connection
        db = Database(**postgres_container)
        db.create_ads_table()

        # Modify connection params to cause errors
        original_params = db._connection_params.copy()
        db._connection_params["host"] = "nonexistent_host"

        # Test various operations should handle errors gracefully
        assert db.insert_ad({"make": "Test"}) is None
        assert db.get_ad_by_id(1) is None
        assert db.get_all_ads() == []
        assert db.get_ads_by_criteria({"make": "Test"}) == []
        assert db.update_ad(1, {"make": "Updated"}) is False
        assert db.delete_ad(1) is False
        assert db.get_ads_count() == 0
        assert db.search_ads_by_text("test") == []

        # Restore connection params
        db._connection_params = original_params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
