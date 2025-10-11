import logging
import uuid
from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any

import psycopg2
import pytest
from testcontainers.postgres import PostgresContainer

from shared.database import AdColumns, Database
from shared.database.utils import (
    ADS_TABLE_COLUMNS_SQL,
    CONVERSATIONS_TABLE_COLUMNS_SQL,
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def postgres_container(
    test_db_name: str,
    test_db_user: str,
    test_db_password: str,
    test_db_port: int,
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
def database(
    postgres_container: dict[str, Any],
) -> Generator[Database, None, None]:
    """Function-scoped fixture that provides a fresh Database instance for each test."""
    # Clear singleton instance to ensure fresh database for each test
    Database._instance = None

    # Create database instance
    db = Database(**postgres_container)

    db.install_extension("citext")

    # Create tables
    db.create_table("ads", ADS_TABLE_COLUMNS_SQL)
    db.create_table("conversations", CONVERSATIONS_TABLE_COLUMNS_SQL)

    yield db

    # Cleanup: drop the ads table after each test
    try:
        with db.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS ads CASCADE;")
            cursor.execute("DROP TABLE IF EXISTS conversations CASCADE;")
            conn.commit()
    except Exception as e:
        logger.error(f"Error cleaning up database: {e}")

    # Reset singleton
    Database._instance = None


@pytest.fixture
def sample_ad_data() -> dict[str, Any]:
    """Fixture providing sample ad data for testing."""
    return {
        AdColumns.URL: "http://example.com/ad/123",
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

    def test_upsert_new_conversation(self, database):
        """Test upserting a new conversation record (should insert)."""
        # Prepare conversation data
        session_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        conversation_data = {
            "session_id": session_id,
            "user_id": user_id,
        }

        # Upsert new conversation
        conversation_id = database.upsert(
            conversation_data,
            table_name="conversations",
            conflict_columns=["session_id"],
            returning="id",
        )

        assert conversation_id is not None
        assert isinstance(conversation_id, int)
        assert conversation_id > 0

        # Verify record was inserted
        with database.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM conversations WHERE id = %s;",
                (conversation_id,),
            )
            result = cursor.fetchone()
            assert result is not None
            columns = [desc[0] for desc in cursor.description]
            conversation = dict(zip(columns, result))
            assert conversation["session_id"] == session_id
            assert conversation["user_id"] == user_id

    def test_upsert_existing_conversation(self, database):
        """Test upserting an existing conversation record (should do nothing)."""
        session_id = str(uuid.uuid4())
        user_id_1 = str(uuid.uuid4())
        user_id_2 = str(uuid.uuid4())

        # First upsert
        conversation_id_1 = database.upsert(
            {"session_id": session_id, "user_id": user_id_1},
            table_name="conversations",
            conflict_columns=["session_id"],
            returning="id",
        )
        assert conversation_id_1 is not None

        # Second upsert with same session_id but different user_id (should do nothing)
        conversation_id_2 = database.upsert(
            {"session_id": session_id, "user_id": user_id_2},
            table_name="conversations",
            conflict_columns=["session_id"],
            returning="id",
        )

        # Should return None because no new record was inserted
        assert conversation_id_2 is None

        # Verify only one record exists and it has the original user_id
        with database.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM conversations WHERE session_id = %s;",
                (session_id,),
            )
            count = cursor.fetchone()[0]
            assert count == 1

            cursor.execute(
                "SELECT user_id FROM conversations WHERE session_id = %s;",
                (session_id,),
            )
            stored_user_id = cursor.fetchone()[0]
            assert (
                stored_user_id == user_id_1
            )  # Should still be the original user_id

    def test_upsert_conversation_use_case(self, database):
        """Test upsert for the conversation tracking use case."""
        session_id = str(uuid.uuid4())
        user_id_1 = str(uuid.uuid4())
        user_id_2 = str(uuid.uuid4())

        # First upsert - should insert new conversation
        result_1 = database.upsert(
            {"session_id": session_id, "user_id": user_id_1},
            table_name="conversations",
            conflict_columns=["session_id"],
            returning="id",
        )
        assert result_1 is not None

        # Second upsert with same session_id - should do nothing
        result_2 = database.upsert(
            {"session_id": session_id, "user_id": user_id_2},
            table_name="conversations",
            conflict_columns=["session_id"],
            returning="id",
        )
        assert result_2 is None

        # Verify original record is unchanged
        with database.get_connection() as conn, conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_id FROM conversations WHERE session_id = %s;",
                (session_id,),
            )
            stored_user_id = cursor.fetchone()[0]
            assert stored_user_id == user_id_1  # Should still be original user

    def test_upsert_without_conflict_columns(self, database):
        """Test that upsert raises ValueError when conflict_columns is not provided."""
        with pytest.raises(
            ValueError, match="conflict_columns must be specified"
        ):
            database.upsert({"session_id": "test"}, table_name="conversations")

    def test_upsert_with_empty_conflict_columns(self, database):
        """Test that upsert raises ValueError when conflict_columns is empty."""
        with pytest.raises(
            ValueError, match="conflict_columns must be specified"
        ):
            database.upsert(
                {"session_id": "test"},
                table_name="conversations",
                conflict_columns=[],
            )

    def test_upsert_with_invalid_column_names(self, database):
        """Test that upsert validates column names properly."""
        # Test invalid record column
        with pytest.raises(ValueError, match="Invalid column name"):
            database.upsert(
                {"invalid'; DROP TABLE conversations; --": "malicious"},
                table_name="conversations",
                conflict_columns=["session_id"],
            )

        # Test invalid conflict column
        with pytest.raises(ValueError, match="Invalid conflict column"):
            database.upsert(
                {"session_id": "valid-uuid"},
                table_name="conversations",
                conflict_columns=["invalid'; DROP TABLE conversations; --"],
            )

        # Test invalid returning column
        with pytest.raises(ValueError, match="Invalid returning column"):
            database.upsert(
                {"session_id": "valid-uuid"},
                table_name="conversations",
                conflict_columns=["session_id"],
                returning="invalid'; DROP TABLE conversations; --",
            )

    def test_upsert_with_nonexistent_table(self, database):
        """Test upsert behavior with non-existent table."""
        result = database.upsert(
            {"session_id": "test"},
            table_name="nonexistent_table",
            conflict_columns=["session_id"],
        )
        # Should return None due to error
        assert result is None

    def test_upsert_with_nonexistent_conflict_column(self, database):
        """Test upsert behavior with non-existent conflict column."""
        result = database.upsert(
            {"session_id": "valid-uuid"},
            table_name="conversations",
            conflict_columns=["nonexistent_column"],
        )
        # Should return None due to error
        assert result is None

    def test_upsert_returning_different_column(self, database):
        """Test upsert with different returning column."""
        session_id = str(uuid.uuid4())

        result = database.upsert(
            {"session_id": session_id, "user_id": str(uuid.uuid4())},
            table_name="conversations",
            conflict_columns=["session_id"],
            returning="session_id",
        )

        assert result is not None
        assert result == session_id

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
        non_existent = database.get_ads_by_criteria(
            {AdColumns.MAKE: "NonExistentMake"}
        )
        assert len(non_existent) == 0

    def test_get_ads_by_criteria_empty_criteria(
        self, database, sample_ad_data
    ):
        """Test getting ads with empty criteria."""
        database.insert_ad(sample_ad_data)

        ads = database.get_ads_by_criteria({})
        assert len(ads) == 1

    def test_get_ads_by_criteria_with_order_by(self, database, sample_ad_data):
        """Test getting ads by criteria with order_by parameter."""
        # Insert test ads with different prices and makes
        ad1_data = sample_ad_data.copy()
        ad1_data[AdColumns.MAKE] = "BMW"
        ad1_data[AdColumns.PRICE] = 25000.00
        ad1_data[AdColumns.MODEL] = "X5"
        database.insert_ad(ad1_data)

        ad2_data = sample_ad_data.copy()
        ad2_data[AdColumns.MAKE] = "BMW"
        ad2_data[AdColumns.PRICE] = 30000.00
        ad2_data[AdColumns.MODEL] = "X3"
        database.insert_ad(ad2_data)

        ad3_data = sample_ad_data.copy()
        ad3_data[AdColumns.MAKE] = "BMW"
        ad3_data[AdColumns.PRICE] = 20000.00
        ad3_data[AdColumns.MODEL] = "X1"
        database.insert_ad(ad3_data)

        # Test ordering by price ASC
        bmw_ads_price_asc = database.get_ads_by_criteria(
            {AdColumns.MAKE: "BMW"}, order_by="price ASC"
        )
        assert len(bmw_ads_price_asc) == 3
        assert bmw_ads_price_asc[0][AdColumns.PRICE] == 20000.00  # X1
        assert bmw_ads_price_asc[1][AdColumns.PRICE] == 25000.00  # X5
        assert bmw_ads_price_asc[2][AdColumns.PRICE] == 30000.00  # X3

        # Test ordering by price DESC
        bmw_ads_price_desc = database.get_ads_by_criteria(
            {AdColumns.MAKE: "BMW"}, order_by="price DESC"
        )
        assert len(bmw_ads_price_desc) == 3
        assert bmw_ads_price_desc[0][AdColumns.PRICE] == 30000.00  # X3
        assert bmw_ads_price_desc[1][AdColumns.PRICE] == 25000.00  # X5
        assert bmw_ads_price_desc[2][AdColumns.PRICE] == 20000.00  # X1

        # Test ordering by model (alphabetical)
        bmw_ads_model_asc = database.get_ads_by_criteria(
            {AdColumns.MAKE: "BMW"}, order_by="model ASC"
        )
        assert len(bmw_ads_model_asc) == 3
        assert bmw_ads_model_asc[0][AdColumns.MODEL] == "X1"
        assert bmw_ads_model_asc[1][AdColumns.MODEL] == "X3"
        assert bmw_ads_model_asc[2][AdColumns.MODEL] == "X5"

    def test_get_ads_by_criteria_with_invalid_order_by(
        self, database, sample_ad_data
    ):
        """Test getting ads by criteria with invalid order_by parameter."""
        database.insert_ad(sample_ad_data)

        # Test with non-existent column name (database error, returns empty list)
        # This doesn't raise ValueError because column name format is valid
        result = database.get_ads_by_criteria(
            {AdColumns.MAKE: "BMW"}, order_by="invalid_column"
        )
        assert result == []  # Returns empty list due to database error

        # Test with SQL injection attempt (should raise ValueError due to invalid format)
        with pytest.raises(ValueError, match="Invalid ORDER BY clause"):
            database.get_ads_by_criteria(
                {AdColumns.MAKE: "BMW"}, order_by="price; DROP TABLE ads;"
            )

        # Test with malformed ORDER BY clause (should raise ValueError)
        with pytest.raises(ValueError, match="Invalid ORDER BY clause"):
            database.get_ads_by_criteria(
                {AdColumns.MAKE: "BMW"}, order_by="price INVALID_DIRECTION"
            )

    def test_get_ads_by_criteria_empty_criteria_with_order_by(
        self, database, sample_ad_data
    ):
        """Test getting ads with empty criteria but with order_by parameter."""
        # Insert multiple ads
        ad1_data = sample_ad_data.copy()
        ad1_data[AdColumns.PRICE] = 25000.00
        database.insert_ad(ad1_data)

        ad2_data = sample_ad_data.copy()
        ad2_data[AdColumns.PRICE] = 15000.00
        database.insert_ad(ad2_data)

        # Empty criteria should delegate to get_all with order_by
        ads = database.get_ads_by_criteria({}, order_by="price ASC")
        assert len(ads) == 2
        assert ads[0][AdColumns.PRICE] == 15000.00
        assert ads[1][AdColumns.PRICE] == 25000.00

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
        results = database.search_ads_by_text(
            "Auto", fields=[AdColumns.TRANSMISSION]
        )
        assert len(results) == 1

        # Search in non-matching field
        results = database.search_ads_by_text(
            "TDI", fields=[AdColumns.TRANSMISSION]
        )
        assert len(results) == 0

    def test_search_ads_by_text_case_insensitive(
        self, database, sample_ad_data
    ):
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

    def test_search_ads_with_range_price_only(self, database):
        """Test range search with price range only."""
        # Insert test data with different prices
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X5",
                AdColumns.PRICE: 15000.00,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Mercedes",
                AdColumns.MODEL: "C-Class",
                AdColumns.PRICE: 25000.00,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Audi",
                AdColumns.MODEL: "A4",
                AdColumns.PRICE: 35000.00,
            },
        ]

        ad_ids = []
        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None
            ad_ids.append(ad_id)

        # Test price range searches
        # Find ads between 20k and 30k
        results = database.search_ads_with_range(
            range_criteria={AdColumns.PRICE: {"min": 20000, "max": 30000}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Mercedes"
        assert results[0]["price"] == 25000.00

        # Find ads above 30k
        results = database.search_ads_with_range(
            range_criteria={AdColumns.PRICE: {"min": 30000}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Audi"

        # Find ads below 20k
        results = database.search_ads_with_range(
            range_criteria={AdColumns.PRICE: {"max": 20000}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "BMW"

    def test_search_ads_with_range_multiple_criteria(self, database):
        """Test range search with multiple numerical criteria."""
        # Insert test data with different numerical values
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Honda",
                AdColumns.MODEL: "Civic",
                AdColumns.PRICE: 15000.00,
                AdColumns.MILEAGE: 50000,
                AdColumns.MANUFACTURE_YEAR: 2015,
                AdColumns.POWER: 120,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Toyota",
                AdColumns.MODEL: "Camry",
                AdColumns.PRICE: 20000.00,
                AdColumns.MILEAGE: 75000,
                AdColumns.MANUFACTURE_YEAR: 2018,
                AdColumns.POWER: 150,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Ford",
                AdColumns.MODEL: "Focus",
                AdColumns.PRICE: 25000.00,
                AdColumns.MILEAGE: 30000,
                AdColumns.MANUFACTURE_YEAR: 2020,
                AdColumns.POWER: 180,
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test multiple range criteria
        results = database.search_ads_with_range(
            range_criteria={
                AdColumns.PRICE: {"min": 18000, "max": 23000},
                AdColumns.MILEAGE: {"max": 80000},
                AdColumns.MANUFACTURE_YEAR: {"min": 2017},
            }
        )
        assert len(results) == 1
        assert results[0]["make"] == "Toyota"

        # Test with power range
        results = database.search_ads_with_range(
            range_criteria={AdColumns.POWER: {"min": 140, "max": 160}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Toyota"

    def test_search_ads_with_range_and_exact_criteria(self, database):
        """Test range search combined with exact match criteria."""
        # Insert test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Volkswagen",
                AdColumns.MODEL: "Golf",
                AdColumns.LOCATION: "Zagreb",
                AdColumns.PRICE: 18000.00,
                AdColumns.MILEAGE: 60000,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Volkswagen",
                AdColumns.MODEL: "Passat",
                AdColumns.LOCATION: "Split",
                AdColumns.PRICE: 22000.00,
                AdColumns.MILEAGE: 45000,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Skoda",
                AdColumns.MODEL: "Octavia",
                AdColumns.LOCATION: "Zagreb",
                AdColumns.PRICE: 16000.00,
                AdColumns.MILEAGE: 70000,
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test exact criteria + range criteria
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "Volkswagen"},
            range_criteria={AdColumns.PRICE: {"min": 20000}},
        )
        assert len(results) == 1
        assert results[0]["model"] == "Passat"

        # Test location + mileage range
        results = database.search_ads(
            exact_criteria={AdColumns.LOCATION: "Zagreb"},
            range_criteria={AdColumns.MILEAGE: {"max": 65000}},
        )
        assert len(results) == 1
        assert results[0]["make"] == "Volkswagen"
        assert results[0]["model"] == "Golf"

    def test_search_ads_with_range_no_results(self, database):
        """Test range search with no matching results."""
        # Insert test data
        test_ad = {
            AdColumns.DATE_CREATED: datetime.now(UTC),
            AdColumns.MAKE: "Test",
            AdColumns.MODEL: "Car",
            AdColumns.PRICE: 15000.00,
            AdColumns.MILEAGE: 50000,
        }

        ad_id = database.insert_ad(test_ad)
        assert ad_id is not None

        # Test range that should return no results
        results = database.search_ads_with_range(
            range_criteria={AdColumns.PRICE: {"min": 50000}}
        )
        assert len(results) == 0

        # Test impossible range
        results = database.search_ads_with_range(
            range_criteria={AdColumns.MILEAGE: {"min": 100000, "max": 90000}}
        )
        assert len(results) == 0

    def test_search_ads_with_range_empty_criteria(self, database):
        """Test range search with empty criteria (should return all ads)."""
        # Insert test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car1",
                AdColumns.MODEL: "Model1",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car2",
                AdColumns.MODEL: "Model2",
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test with empty criteria
        results = database.search_ads_with_range(limit=10)
        assert len(results) == 2

        # Test with None criteria
        results = database.search_ads_with_range(
            criteria=None, range_criteria=None
        )
        assert len(results) == 2

    def test_search_ads_with_range_limit(self, database):
        """Test range search with limit parameter."""
        # Insert multiple test ads
        for i in range(5):
            test_ad = {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: f"Car{i}",
                AdColumns.MODEL: f"Model{i}",
                AdColumns.PRICE: 10000.00 + (i * 1000),
            }
            ad_id = database.insert_ad(test_ad)
            assert ad_id is not None

        # Test with limit
        results = database.search_ads_with_range(
            range_criteria={AdColumns.PRICE: {"min": 10000}}, limit=3
        )
        assert len(results) == 3

    def test_search_ads_with_range_invalid_column(self, database):
        """Test range search with invalid numerical column."""
        # Insert test data
        test_ad = {
            AdColumns.DATE_CREATED: datetime.now(UTC),
            AdColumns.MAKE: "Test",
            AdColumns.MODEL: "Car",
        }

        ad_id = database.insert_ad(test_ad)
        assert ad_id is not None

        # Test with non-numerical column (should be ignored with warning)
        results = database.search_ads_with_range(
            range_criteria={"make": {"min": "A", "max": "Z"}}
        )
        # Should return the ad since invalid range criteria is ignored
        assert len(results) == 1

    def test_search_ads_with_range_year_ranges(self, database):
        """Test range search specifically for year-related columns."""
        # Insert test data with different years
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Old",
                AdColumns.MODEL: "Car",
                AdColumns.MANUFACTURE_YEAR: 2010,
                AdColumns.MODEL_YEAR: 2010,
                AdColumns.IN_TRAFFIC_SINCE: 2011,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "New",
                AdColumns.MODEL: "Car",
                AdColumns.MANUFACTURE_YEAR: 2020,
                AdColumns.MODEL_YEAR: 2020,
                AdColumns.IN_TRAFFIC_SINCE: 2020,
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test manufacture year range
        results = database.search_ads_with_range(
            range_criteria={AdColumns.MANUFACTURE_YEAR: {"min": 2015}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "New"

        # Test model year range
        results = database.search_ads_with_range(
            range_criteria={AdColumns.MODEL_YEAR: {"max": 2015}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Old"

    def test_search_ads_with_range_doors_and_seats(self, database):
        """Test range search for doors and seats columns."""
        # Insert test data with different door/seat configurations
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Small",
                AdColumns.MODEL: "Car",
                AdColumns.NUMBER_OF_DOORS: 3,
                AdColumns.NUMBER_OF_SEATS: 4,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Family",
                AdColumns.MODEL: "Car",
                AdColumns.NUMBER_OF_DOORS: 5,
                AdColumns.NUMBER_OF_SEATS: 7,
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test doors range
        results = database.search_ads_with_range(
            range_criteria={AdColumns.NUMBER_OF_DOORS: {"min": 5}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Family"

        # Test seats range
        results = database.search_ads_with_range(
            range_criteria={AdColumns.NUMBER_OF_SEATS: {"max": 5}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Small"

    def test_search_ads_exact_criteria_only(self, database):
        """Test search_ads with only exact criteria."""
        # Insert test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X5",
                AdColumns.LOCATION: "Zagreb",
                AdColumns.PRICE: 25000.00,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X3",
                AdColumns.LOCATION: "Split",
                AdColumns.PRICE: 35000.00,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Audi",
                AdColumns.MODEL: "A4",
                AdColumns.LOCATION: "Zagreb",
                AdColumns.PRICE: 30000.00,
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test exact criteria search
        results = database.search_ads(exact_criteria={AdColumns.MAKE: "BMW"})
        assert len(results) == 2
        for result in results:
            assert result["make"] == "BMW"

        # Test multiple exact criteria
        results = database.search_ads(
            exact_criteria={
                AdColumns.MAKE: "BMW",
                AdColumns.LOCATION: "Zagreb",
            }
        )
        assert len(results) == 1
        assert results[0]["model"] == "X5"

    def test_search_ads_range_criteria_only(self, database):
        """Test search_ads with only range criteria."""
        # Insert test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car1",
                AdColumns.MODEL: "Model1",
                AdColumns.PRICE: 15000.00,
                AdColumns.MILEAGE: 50000,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car2",
                AdColumns.MODEL: "Model2",
                AdColumns.PRICE: 25000.00,
                AdColumns.MILEAGE: 30000,
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car3",
                AdColumns.MODEL: "Model3",
                AdColumns.PRICE: 35000.00,
                AdColumns.MILEAGE: 70000,
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test price range only
        results = database.search_ads(
            range_criteria={AdColumns.PRICE: {"min": 20000, "max": 30000}}
        )
        assert len(results) == 1
        assert results[0]["make"] == "Car2"

        # Test multiple range criteria
        results = database.search_ads(
            range_criteria={
                AdColumns.PRICE: {"min": 10000},
                AdColumns.MILEAGE: {"max": 60000},
            }
        )
        assert len(results) == 2
        # Should include Car1 (50k mileage) and Car2 (30k mileage), but not Car3 (70k mileage)

    def test_search_ads_text_search_only(self, database):
        """Test search_ads with only text search."""
        # Insert test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X5",
                AdColumns.LOCATION: "Zagreb",
                AdColumns.TYPE: "SUV",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Mercedes",
                AdColumns.MODEL: "BMW",  # BMW in model field
                AdColumns.LOCATION: "Split",
                AdColumns.TYPE: "Sedan",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Audi",
                AdColumns.MODEL: "A4",
                AdColumns.LOCATION: "BMW Street",  # BMW in location
                AdColumns.TYPE: "Sedan",
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test default text search
        results = database.search_ads(text_search={"term": "BMW"})
        assert len(results) == 3

        # Test custom fields text search
        results = database.search_ads(
            text_search={"term": "SUV", "fields": [AdColumns.TYPE]}
        )
        assert len(results) == 1
        assert results[0]["make"] == "BMW"

        # Test case insensitive
        results = database.search_ads(text_search={"term": "bmw"})
        assert len(results) == 3

    def test_search_ads_combined_criteria(self, database):
        """Test search_ads with BMW cars between 10000 and 50000 price range."""
        # Insert test data - the main use case from the request
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X5",
                AdColumns.PRICE: 35000.00,
                AdColumns.MILEAGE: 45000,
                AdColumns.LOCATION: "Zagreb",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "320i",
                AdColumns.PRICE: 15000.00,
                AdColumns.MILEAGE: 80000,
                AdColumns.LOCATION: "Split",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "M3",
                AdColumns.PRICE: 60000.00,  # Outside price range
                AdColumns.MILEAGE: 25000,
                AdColumns.LOCATION: "Rijeka",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Mercedes",
                AdColumns.MODEL: "C-Class",
                AdColumns.PRICE: 25000.00,  # In price range but not BMW
                AdColumns.MILEAGE: 50000,
                AdColumns.LOCATION: "Osijek",
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test the main use case: BMW cars with price between 10000 and 50000
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "BMW"},
            range_criteria={AdColumns.PRICE: {"min": 10000, "max": 50000}},
        )
        assert len(results) == 2
        for result in results:
            assert result["make"] == "BMW"
            assert 10000 <= result["price"] <= 50000

        # Verify the specific models found
        models = [result["model"] for result in results]
        assert "X5" in models
        assert "320i" in models
        assert "M3" not in models  # Too expensive

    def test_search_ads_all_criteria_types(self, database):
        """Test search_ads with exact, range, and text criteria combined."""
        # Insert comprehensive test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X5 Sport",
                AdColumns.PRICE: 35000.00,
                AdColumns.MILEAGE: 45000,
                AdColumns.LOCATION: "Zagreb",
                AdColumns.TYPE: "SUV",
                AdColumns.TRANSMISSION: "Automatic",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "320i Comfort",
                AdColumns.PRICE: 25000.00,
                AdColumns.MILEAGE: 60000,
                AdColumns.LOCATION: "Split",
                AdColumns.TYPE: "Sedan",
                AdColumns.TRANSMISSION: "Manual",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X3 Base",
                AdColumns.PRICE: 30000.00,
                AdColumns.MILEAGE: 55000,
                AdColumns.LOCATION: "Rijeka",
                AdColumns.TYPE: "SUV",
                AdColumns.TRANSMISSION: "Automatic",
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test all three criteria types together
        results = database.search_ads(
            exact_criteria={
                AdColumns.MAKE: "BMW",
                AdColumns.TRANSMISSION: "Automatic",
            },
            range_criteria={
                AdColumns.PRICE: {"min": 30000, "max": 40000},
                AdColumns.MILEAGE: {"max": 50000},
            },
            text_search={"term": "Sport", "fields": [AdColumns.MODEL]},
        )
        assert len(results) == 1
        assert results[0]["model"] == "X5 Sport"

        # Test different combination
        results = database.search_ads(
            exact_criteria={AdColumns.TYPE: "SUV"},
            range_criteria={AdColumns.PRICE: {"max": 32000}},
        )
        assert len(results) == 1
        assert results[0]["model"] == "X3 Base"

    def test_search_ads_no_criteria(self, database):
        """Test search_ads with no criteria (should return all ads)."""
        # Insert test data
        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car1",
                AdColumns.MODEL: "Model1",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "Car2",
                AdColumns.MODEL: "Model2",
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None

        # Test with no criteria
        results = database.search_ads()
        assert len(results) == 2

        # Test with all None criteria
        results = database.search_ads(
            exact_criteria=None, range_criteria=None, text_search=None
        )
        assert len(results) == 2

    def test_search_ads_no_results(self, database):
        """Test search_ads with criteria that match no ads."""
        # Insert test data
        test_ad = {
            AdColumns.DATE_CREATED: datetime.now(UTC),
            AdColumns.MAKE: "BMW",
            AdColumns.MODEL: "X5",
            AdColumns.PRICE: 25000.00,
        }

        ad_id = database.insert_ad(test_ad)
        assert ad_id is not None

        # Test exact criteria with no match
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "NonExistent"}
        )
        assert len(results) == 0

        # Test range criteria with no match
        results = database.search_ads(
            range_criteria={AdColumns.PRICE: {"min": 50000}}
        )
        assert len(results) == 0

        # Test text search with no match
        results = database.search_ads(text_search={"term": "NonExistentTerm"})
        assert len(results) == 0

        # Test impossible combination
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "BMW"},
            range_criteria={AdColumns.PRICE: {"min": 50000}},  # BMW costs 25k
        )
        assert len(results) == 0

    def test_search_ads_with_limit(self, database):
        """Test search_ads with limit parameter."""
        # Insert multiple BMW ads
        for i in range(5):
            test_ad = {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: f"Model{i}",
                AdColumns.PRICE: 20000.00 + (i * 1000),
            }
            ad_id = database.insert_ad(test_ad)
            assert ad_id is not None

        # Test with limit
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "BMW"}, limit=3
        )
        assert len(results) == 3

        # Test range search with limit
        results = database.search_ads(
            range_criteria={AdColumns.PRICE: {"min": 20000}}, limit=2
        )
        assert len(results) == 2

    def test_search_ads_invalid_range_column(self, database):
        """Test search_ads with invalid range column."""
        # Insert test data
        test_ad = {
            AdColumns.DATE_CREATED: datetime.now(UTC),
            AdColumns.MAKE: "BMW",
            AdColumns.MODEL: "X5",
        }

        ad_id = database.insert_ad(test_ad)
        assert ad_id is not None

        # Test with invalid range column (should be ignored)
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "BMW"},
            range_criteria={"invalid_column": {"min": 100}},
        )
        assert len(results) == 1  # Should find the BMW despite invalid range

    def test_search_ads_empty_text_search(self, database):
        """Test search_ads with empty text search term."""
        # Insert test data
        test_ad = {
            AdColumns.DATE_CREATED: datetime.now(UTC),
            AdColumns.MAKE: "BMW",
            AdColumns.MODEL: "X5",
        }

        ad_id = database.insert_ad(test_ad)
        assert ad_id is not None

        # Test with empty search term
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "BMW"},
            text_search={"term": ""},
        )
        assert len(results) == 1  # Should ignore empty text search

        # Test with None search term
        results = database.search_ads(
            exact_criteria={AdColumns.MAKE: "BMW"},
            text_search={"term": None},
        )
        assert len(results) == 1  # Should ignore None text search

    def test_search_ads_ordering(self, database):
        """Test that search_ads returns results ordered by insertion_time DESC."""
        # Insert test data with delays to ensure different insertion times
        import time

        test_ads = [
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "First",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "Second",
            },
            {
                AdColumns.DATE_CREATED: datetime.now(UTC),
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "Third",
            },
        ]

        for ad in test_ads:
            ad_id = database.insert_ad(ad)
            assert ad_id is not None
            time.sleep(0.01)  # Small delay to ensure different insertion times

        # Test ordering
        results = database.search_ads(exact_criteria={AdColumns.MAKE: "BMW"})
        assert len(results) == 3
        # Should be ordered by insertion_time DESC (most recent first)
        assert results[0]["model"] == "Third"
        assert results[1]["model"] == "Second"
        assert results[2]["model"] == "First"

    def test_get_by_criteria_generic_with_order_by(
        self, database, sample_ad_data
    ):
        """Test the generic get_by_criteria method with order_by parameter."""
        # Use the ads-specific insert method since the generic method
        # needs to handle required fields like date_created

        # Insert test records using the insert_ad method
        record1 = sample_ad_data.copy()
        record1.update(
            {
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X5",
                AdColumns.PRICE: 25000.00,
                AdColumns.MILEAGE: 50000,
            }
        )
        record2 = sample_ad_data.copy()
        record2.update(
            {
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X3",
                AdColumns.PRICE: 30000.00,
                AdColumns.MILEAGE: 40000,
            }
        )
        record3 = sample_ad_data.copy()
        record3.update(
            {
                AdColumns.MAKE: "BMW",
                AdColumns.MODEL: "X1",
                AdColumns.PRICE: 20000.00,
                AdColumns.MILEAGE: 60000,
            }
        )

        # Insert using ads-specific method
        id1 = database.insert_ad(record1)
        id2 = database.insert_ad(record2)
        id3 = database.insert_ad(record3)

        assert all([id1, id2, id3])

        # Test generic get_by_criteria with order_by
        results_price_asc = database.get_by_criteria(
            {"make": "BMW"}, order_by="price ASC"
        )
        assert len(results_price_asc) == 3
        assert results_price_asc[0]["price"] == 20000.00  # X1
        assert results_price_asc[1]["price"] == 25000.00  # X5
        assert results_price_asc[2]["price"] == 30000.00  # X3

        # Test ordering by mileage DESC
        results_mileage_desc = database.get_by_criteria(
            {"make": "BMW"}, order_by="mileage DESC"
        )
        assert len(results_mileage_desc) == 3
        assert results_mileage_desc[0]["mileage"] == 60000  # X1
        assert results_mileage_desc[1]["mileage"] == 50000  # X5
        assert results_mileage_desc[2]["mileage"] == 40000  # X3

        # Test multi-column ordering
        results_multi = database.get_by_criteria(
            {"make": "BMW"}, order_by="price ASC, model DESC"
        )
        assert len(results_multi) == 3
        # Should be ordered by price first, then by model descending
        assert results_multi[0]["price"] == 20000.00  # X1 (lowest price)

    def test_get_by_criteria_generic_invalid_order_by(self, database):
        """Test the generic get_by_criteria method with invalid order_by parameter."""
        # Test with non-existent column name (database error, returns empty list)
        result = database.get_by_criteria(
            {"make": "BMW"}, order_by="invalid_column"
        )
        assert result == []  # Returns empty list due to database error

        # Test with SQL injection attempt (should raise ValueError due to invalid format)
        with pytest.raises(ValueError, match="Invalid ORDER BY clause"):
            database.get_by_criteria(
                {"make": "BMW"}, order_by="price; DROP TABLE ads;"
            )

        # Test with malformed order by (should raise ValueError due to invalid format)
        with pytest.raises(ValueError, match="Invalid ORDER BY clause"):
            database.get_by_criteria(
                {"make": "BMW"}, order_by="price INVALID_DIRECTION"
            )


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
        assert (
            db.search_ads_with_range(range_criteria={"price": {"min": 10000}})
            == []
        )

        # Restore connection params
        db._connection_params = original_params


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
