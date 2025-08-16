from contextlib import contextmanager
import logging
import os
from typing import Any

import psycopg2

from backend.database import AdColumns

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADS_TABLE_NAME = "ads"


class Database:
    _instance = None
    _default_params = {
        "dbname": os.getenv("CARGPT_DB_NAME", "ads_db"),
        "user": os.getenv("CARGPT_DB_USER", "adsuser"),
        "password": os.getenv("CARGPT_DB_PASSWORD", "pass"),
        "host": os.getenv("CARGPT_DB_HOST", "localhost"),
        "port": os.getenv("CARGPT_DB_PORT", "5432"),
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, **connection_params):
        if self._initialized:
            return

        # Set connection parameters (start with defaults, then override with provided params)
        self._connection_params = self._default_params.copy()
        if connection_params:
            self._connection_params.update(connection_params)

        self._initialized = True

        # Test the connection on initialization
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                logger.info("Database connection established successfully")
        except psycopg2.Error as e:
            logger.error(f"Failed to establish database connection: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self._connection_params)
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def create_ads_table(self) -> bool:
        """Create the ads table if it doesn't exist."""
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {ADS_TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            insertion_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_created TIMESTAMP NOT NULL,
            price NUMERIC(10, 2),
            location VARCHAR(100),
            make VARCHAR(30),
            model VARCHAR(50),
            type VARCHAR(100),
            chassis_number VARCHAR(17),
            manufacture_year INT,
            model_year INT,
            mileage INT,
            engine VARCHAR(20),
            power INT,
            displacement INT,
            transmission VARCHAR(30),
            condition VARCHAR(20),
            owner VARCHAR(20),
            service_book BOOLEAN,
            garaged BOOLEAN,
            in_traffic_since INT,
            first_registration_in_croatia INT,
            registered_until VARCHAR(20),
            fuel_consumption VARCHAR(20),
            eco_category VARCHAR(20),
            number_of_gears VARCHAR(20),
            warranty VARCHAR(20),
            average_co2_emission VARCHAR(20),
            video_call_viewing BOOLEAN,
            gas BOOLEAN,
            auto_warranty VARCHAR(20),
            number_of_doors INT,
            chassis_type VARCHAR(20),
            number_of_seats INT,
            drive_type VARCHAR(20),
            color VARCHAR(20),
            metalic_color BOOLEAN,
            suspension VARCHAR(20),
            tire_size VARCHAR(20),
            internal_code VARCHAR(50)
        );
        """

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                logger.info(
                    f"Table '{ADS_TABLE_NAME}' created successfully or already exists!"
                )
                return True
        except psycopg2.Error as e:
            logger.error(f"Error creating table: {e}")
            return False

    def insert_ad(self, ad_data: dict[str, Any]) -> int | None:
        """Insert a new ad into the database.

        Args:
            ad_data: Dictionary containing ad information

        Returns:
            The ID of the inserted ad, or None if insertion failed
        """
        # Get insertable columns from the enum
        allowed_columns = AdColumns.get_insertable_columns()

        # Filter ad_data to only include allowed columns
        filtered_data = {
            k: v for k, v in ad_data.items() if k in allowed_columns
        }

        if not filtered_data:
            logger.error("No valid data provided for insertion")
            return None

        # Build the query dynamically
        columns = list(filtered_data.keys())
        values = list(filtered_data.values())
        placeholders = ", ".join(["%s"] * len(values))
        columns_str = ", ".join(columns)

        insert_query = f"""
        INSERT INTO {ADS_TABLE_NAME} ({columns_str})
        VALUES ({placeholders})
        RETURNING id;
        """

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(insert_query, values)
                ad_id = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"Ad inserted successfully with ID: {ad_id}")
                return ad_id
        except psycopg2.Error as e:
            logger.error(f"Error inserting ad: {e}")
            return None

    def get_ad_by_id(self, ad_id: int) -> dict[str, Any] | None:
        """Retrieve an ad by its ID.

        Args:
            ad_id: The ID of the ad to retrieve

        Returns:
            Dictionary containing ad data, or None if not found
        """
        query = "SELECT * FROM ads WHERE id = %s;"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (ad_id,))
                result = cursor.fetchone()

                if result:
                    # Get column names
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, result, strict=True))
                return None
        except psycopg2.Error as e:
            logger.error(f"Error retrieving ad: {e}")
            return None

    def get_ads_by_criteria(
        self, criteria: dict[str, Any], limit: int = 100
    ) -> list[dict[str, Any]]:
        """Retrieve ads based on search criteria.

        Args:
            criteria: Dictionary of search criteria
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing ad data
        """
        if not criteria:
            return self.get_all_ads(limit)

        # Build WHERE clause dynamically
        conditions = []
        values = []

        for key, value in criteria.items():
            if value is not None:
                conditions.append(f"{key} = %s")
                values.append(value)

        if not conditions:
            return self.get_all_ads(limit)

        where_clause = " AND ".join(conditions)
        query = (
            f"SELECT * FROM {ADS_TABLE_NAME} WHERE {where_clause} LIMIT %s;"
        )
        values.append(limit)

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                results = cursor.fetchall()

                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True))
                        for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error retrieving ads: {e}")
            return []

    def get_all_ads(self, limit: int = 100) -> list[dict[str, Any]]:
        """Retrieve all ads with a limit.

        Args:
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing ad data
        """
        query = f"SELECT * FROM {ADS_TABLE_NAME} ORDER BY insertion_time DESC LIMIT %s;"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (limit,))
                results = cursor.fetchall()

                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True))
                        for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error retrieving ads: {e}")
            return []

    def update_ad(self, ad_id: int, update_data: dict[str, Any]) -> bool:
        """Update an existing ad.

        Args:
            ad_id: The ID of the ad to update
            update_data: Dictionary containing fields to update

        Returns:
            True if update was successful, False otherwise
        """
        if not update_data:
            logger.error("No update data provided")
            return False

        # Build SET clause dynamically
        set_clauses = []
        values = []

        for key, value in update_data.items():
            if key not in [
                AdColumns.ID,
                AdColumns.INSERTION_TIME,
            ]:  # Don't allow updating these fields
                set_clauses.append(f"{key} = %s")
                values.append(value)

        if not set_clauses:
            logger.error("No valid fields to update")
            return False

        values.append(ad_id)  # Add ad_id for WHERE clause
        set_clause = ", ".join(set_clauses)
        query = f"UPDATE {ADS_TABLE_NAME} SET {set_clause} WHERE id = %s;"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                rows_affected = cursor.rowcount
                conn.commit()

                if rows_affected > 0:
                    logger.info(f"Ad {ad_id} updated successfully")
                    return True

                logger.warning(f"No ad found with ID {ad_id}")
                return False

        except psycopg2.Error as e:
            logger.error(f"Error updating ad: {e}")
            return False

    def delete_ad(self, ad_id: int) -> bool:
        """Delete an ad by its ID.

        Args:
            ad_id: The ID of the ad to delete

        Returns:
            True if deletion was successful, False otherwise
        """
        query = f"DELETE FROM {ADS_TABLE_NAME} WHERE id = %s;"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (ad_id,))
                rows_affected = cursor.rowcount
                conn.commit()

                if rows_affected > 0:
                    logger.info(f"Ad {ad_id} deleted successfully")
                    return True

                logger.warning(f"No ad found with ID {ad_id}")
                return False

        except psycopg2.Error as e:
            logger.error(f"Error deleting ad: {e}")
            return False

    def get_ads_count(self) -> int:
        """Get the total number of ads in the database.

        Returns:
            Total number of ads
        """
        query = f"SELECT COUNT(*) FROM {ADS_TABLE_NAME};"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchone()[0]
        except psycopg2.Error as e:
            logger.error(f"Error getting ads count: {e}")
            return 0

    def search_ads_by_text(
        self,
        search_term: str,
        fields: list[str] | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Search ads by text in specified fields.

        Args:
            search_term: The text to search for
            fields: List of fields to search in (default: make, model, location)
            limit: Maximum number of results to return

        Returns:
            List of dictionaries containing matching ad data
        """
        if fields is None:
            fields = [
                AdColumns.MAKE,
                AdColumns.MODEL,
                AdColumns.LOCATION,
                AdColumns.TYPE,
            ]

        # Build search conditions
        conditions = []
        values = []
        search_pattern = f"%{search_term}%"

        for field in fields:
            conditions.append(f"LOWER({field}) LIKE LOWER(%s)")
            values.append(search_pattern)

        where_clause = " OR ".join(conditions)
        query = f"SELECT * FROM {ADS_TABLE_NAME} WHERE {where_clause} ORDER BY insertion_time DESC LIMIT %s;"
        values.append(limit)

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                results = cursor.fetchall()

                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True))
                        for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error searching ads: {e}")
            return []

    @property
    def instance(self) -> "Database":
        if self._instance is None:
            raise RuntimeError("Database instance not initialized")
        return self._instance
