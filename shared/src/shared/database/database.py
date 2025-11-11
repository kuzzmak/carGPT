import os
import re
from contextlib import contextmanager
from typing import Any

import psycopg2

from shared.database import AdColumns
from shared.database.utils import (
    ADS_TABLE_COLUMNS_SQL,
    IMAGES_TABLE_COLUMNS_SQL,
)
from shared.logging_config import get_logger

# Set up logging
logger = get_logger("database")

# Backward-compatibility constant; not used internally
ADS_TABLE_NAME = "ads"
IMAGES_TABLE_NAME = "ad_images"


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

    def __init__(
        self, default_table_name: str | None = None, **connection_params
    ):
        if self._initialized:
            return

        # Set connection parameters (start with defaults, then override with provided params)
        self._connection_params = self._default_params.copy()
        if connection_params:
            self._connection_params.update(connection_params)

        # Default table name used when a method call does not provide one explicitly
        self._default_table_name = default_table_name or os.getenv(
            "CARGPT_DEFAULT_TABLE", ADS_TABLE_NAME
        )

        self._initialized = True

        # Test the connection on initialization
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                logger.info("Database connection established successfully")
        except psycopg2.Error as e:
            logger.error(f"Failed to establish database connection: {e}")
            raise

    # ----------------------
    # Connection Management
    # ----------------------
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = None
        try:
            conn = psycopg2.connect(**self._connection_params)  # type: ignore[arg-type]
            yield conn
        except psycopg2.Error as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    # ----------------------
    # Helpers
    # ----------------------
    def _ensure_table_name(self, table_name: str | None) -> str:
        name = table_name or self._default_table_name
        if not name:
            raise ValueError("Table name must be provided or set as default.")
        if not self._validate_identifier(name):
            raise ValueError(f"Invalid table name: {name}")
        return name

    @staticmethod
    def _validate_identifier(identifier: str) -> bool:
        """Basic validation to avoid SQL injection via identifiers (table/column names)."""
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier))

    @staticmethod
    def _validate_order_by(order_by: str) -> bool:
        # Supports patterns like: col, col2 DESC, col3 ASC, col4
        return bool(
            re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?(\s*,\s*[A-Za-z_][A-Za-z0-9_]*(\s+(ASC|DESC))?)*",
                order_by.strip(),
            )
        )

    # ----------------------
    # Generic Table Utilities
    # ----------------------
    def install_extension(self, extension_name: str) -> bool:
        """Install a PostgreSQL extension if it doesn't already exist."""
        if not self._validate_identifier(extension_name):
            raise ValueError(f"Invalid extension name: {extension_name}")

        install_extension_query = (
            f"CREATE EXTENSION IF NOT EXISTS {extension_name};"
        )

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(install_extension_query)
                conn.commit()
                logger.info(
                    f"Extension '{extension_name}' installed successfully or already exists!"
                )
                return True
        except psycopg2.Error as e:
            logger.error(f"Error installing extension '{extension_name}': {e}")
            return False

    def create_table(
        self, table_name: str, columns_definition_sql: str
    ) -> bool:
        """Create a table with the provided column definition if it doesn't exist."""
        table = self._ensure_table_name(table_name)
        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {table} (
            {columns_definition_sql}
        );
        """
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(create_table_query)
                conn.commit()
                logger.info(
                    f"Table '{table}' created successfully or already exists!"
                )
                return True
        except psycopg2.Error as e:
            logger.error(f"Error creating table '{table}': {e}")
            return False

    # ----------------------
    # Generic CRUD Operations
    # ----------------------
    def insert(
        self,
        record: dict[str, Any],
        table_name: str | None = None,
        allowed_columns: list[str] | None = None,
        returning: str = "id",
    ) -> Any | None:
        """Insert a new record into the specified table.

        Args:
            record: Dictionary containing the data to insert
            table_name: Target table (defaults to instance's default)
            allowed_columns: Optional whitelist of columns to include
            returning: Column to return (defaults to 'id')
        Returns:
            The value of the returning column, or None if insertion failed
        """
        table = self._ensure_table_name(table_name)

        if allowed_columns is not None:
            record = {
                k: v for k, v in record.items() if k in set(allowed_columns)
            }
        if not record:
            logger.error("No valid data provided for insertion")
            return None

        # Validate column identifiers
        for col in record.keys():
            if not self._validate_identifier(col):
                raise ValueError(f"Invalid column name: {col}")
        if returning and not self._validate_identifier(returning):
            raise ValueError(f"Invalid returning column: {returning}")

        columns = list(record.keys())
        values = list(record.values())
        placeholders = ", ".join(["%s"] * len(values))
        columns_str = ", ".join(columns)

        insert_query = f"""
        INSERT INTO {table} ({columns_str})
        VALUES ({placeholders})
        RETURNING {returning};
        """

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(insert_query, values)
                ret_val = cursor.fetchone()[0]
                conn.commit()
                logger.info(
                    f"Insert into '{table}' succeeded. Returning {returning}={ret_val}"
                )
                return ret_val
        except psycopg2.Error as e:
            logger.error(f"Error inserting into '{table}': {e}")
            return None

    def upsert(
        self,
        record: dict[str, Any],
        table_name: str | None = None,
        conflict_columns: list[str] | None = None,
        returning: str = "id",
    ) -> Any | None:
        """Insert record or do nothing if conflict occurs on specified columns."""
        table = self._ensure_table_name(table_name)

        if not conflict_columns:
            raise ValueError("conflict_columns must be specified for upsert")

        # Validate identifiers
        for col in record.keys():
            if not self._validate_identifier(col):
                raise ValueError(f"Invalid column name: {col}")
        for col in conflict_columns:
            if not self._validate_identifier(col):
                raise ValueError(f"Invalid conflict column: {col}")
        if returning and not self._validate_identifier(returning):
            raise ValueError(f"Invalid returning column: {returning}")

        columns = list(record.keys())
        values = list(record.values())
        placeholders = ", ".join(["%s"] * len(values))
        columns_str = ", ".join(columns)
        conflict_clause = ", ".join(conflict_columns)

        query = f"""
            INSERT INTO {table} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT ({conflict_clause}) DO NOTHING
            RETURNING {returning};
        """

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                result = cursor.fetchone()
                conn.commit()
                return result[0] if result else None
        except psycopg2.Error as e:
            logger.error(f"Error upserting into '{table}': {e}")
            return None

    def get_by_id(
        self, record_id: int, table_name: str | None = None
    ) -> dict[str, Any] | None:
        table = self._ensure_table_name(table_name)
        query = f"SELECT * FROM {table} WHERE id = %s;"
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (record_id,))
                result = cursor.fetchone()
                if result:
                    columns = [desc[0] for desc in cursor.description]
                    return dict(zip(columns, result, strict=True))
                return None
        except psycopg2.Error as e:
            logger.error(f"Error retrieving from '{table}': {e}")
            return None

    def get_by_criteria(
        self,
        criteria: dict[str, Any],
        table_name: str | None = None,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        table = self._ensure_table_name(table_name)
        if not criteria:
            return self.get_all(
                table_name=table, limit=limit, order_by=order_by
            )

        conditions: list[str] = []
        values: list[Any] = []

        for key, value in criteria.items():
            if value is not None:
                if not self._validate_identifier(key):
                    raise ValueError(f"Invalid column name: {key}")
                conditions.append(f"{key} = %s")
                values.append(value)

        if not conditions:
            return self.get_all(
                table_name=table, limit=limit, order_by=order_by
            )

        where_clause = " AND ".join(conditions)

        if order_by is not None:
            if not self._validate_order_by(order_by):
                raise ValueError(f"Invalid ORDER BY clause: {order_by}")
            query = f"SELECT * FROM {table} WHERE {where_clause} ORDER BY {order_by} LIMIT %s;"
        else:
            query = f"SELECT * FROM {table} WHERE {where_clause} LIMIT %s;"

        values.append(limit)
        logger.debug(f"Executing query: {query} with values {values}")

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                results = cursor.fetchall()
                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True)) for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error retrieving from '{table}': {e}")
            return []

    def get_all(
        self,
        table_name: str | None = None,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        table = self._ensure_table_name(table_name)
        if order_by is not None:
            if not self._validate_order_by(order_by):
                raise ValueError(f"Invalid ORDER BY clause: {order_by}")
            query = f"SELECT * FROM {table} ORDER BY {order_by} LIMIT %s;"
        else:
            query = f"SELECT * FROM {table} LIMIT %s;"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (limit,))
                results = cursor.fetchall()
                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True)) for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error retrieving from '{table}': {e}")
            return []

    def update_by_id(
        self,
        record_id: int,
        update_data: dict[str, Any],
        table_name: str | None = None,
        disallowed_columns: list[str] | None = None,
    ) -> bool:
        if not update_data:
            logger.error("No update data provided")
            return False

        table = self._ensure_table_name(table_name)
        disallowed = set(
            disallowed_columns or ["id", "insertion_time"]
        )  # don't update these by default

        set_clauses: list[str] = []
        values: list[Any] = []

        for key, value in update_data.items():
            if key in disallowed:
                continue
            if not self._validate_identifier(key):
                raise ValueError(f"Invalid column name: {key}")
            set_clauses.append(f"{key} = %s")
            values.append(value)

        if not set_clauses:
            logger.error("No valid fields to update")
            return False

        values.append(record_id)
        set_clause = ", ".join(set_clauses)
        query = f"UPDATE {table} SET {set_clause} WHERE id = %s;"

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                rows_affected = cursor.rowcount
                conn.commit()
                if rows_affected > 0:
                    logger.info(
                        f"Record {record_id} in '{table}' updated successfully"
                    )
                    return True
                logger.warning(
                    f"No record found with ID {record_id} in '{table}'"
                )

                return False
        except psycopg2.Error as e:
            logger.error(f"Error updating '{table}': {e}")
            return False

    def delete_by_id(
        self, record_id: int, table_name: str | None = None
    ) -> bool:
        table = self._ensure_table_name(table_name)
        query = f"DELETE FROM {table} WHERE id = %s;"
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (record_id,))
                rows_affected = cursor.rowcount
                conn.commit()
                if rows_affected > 0:
                    logger.info(
                        f"Record {record_id} deleted from '{table}' successfully"
                    )
                    return True
                logger.warning(
                    f"No record found with ID {record_id} in '{table}'"
                )
                return False
        except psycopg2.Error as e:
            logger.error(f"Error deleting from '{table}': {e}")
            return False

    def get_count(self, table_name: str | None = None) -> int:
        table = self._ensure_table_name(table_name)
        query = f"SELECT COUNT(*) FROM {table};"
        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query)
                return cursor.fetchone()[0]
        except psycopg2.Error as e:
            logger.error(f"Error getting count from '{table}': {e}")
            return 0

    # ----------------------
    # Generic Search Operations
    # ----------------------
    def search_text(
        self,
        search_term: str,
        fields: list[str],
        table_name: str | None = None,
        limit: int = 100,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        table = self._ensure_table_name(table_name)
        if not fields:
            logger.error("No fields provided for text search")
            return []

        # Validate identifiers
        for field in fields:
            if not self._validate_identifier(field):
                raise ValueError(
                    f"Invalid column name in text search: {field}"
                )

        conditions = []
        values: list[Any] = []
        search_pattern = f"%{search_term}%"

        for field in fields:
            conditions.append(f"LOWER({field}) LIKE LOWER(%s)")
            values.append(search_pattern)

        where_clause = " OR ".join(conditions)

        if order_by is not None:
            if not self._validate_order_by(order_by):
                raise ValueError(f"Invalid ORDER BY clause: {order_by}")
            query = f"SELECT * FROM {table} WHERE {where_clause} ORDER BY {order_by} LIMIT %s;"
        else:
            query = f"SELECT * FROM {table} WHERE {where_clause} LIMIT %s;"

        values.append(limit)

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                results = cursor.fetchall()
                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True)) for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error searching in '{table}': {e}")
            return []

    def search_with_range(
        self,
        criteria: dict[str, Any] | None = None,
        range_criteria: dict[str, dict[str, Any]] | None = None,
        table_name: str | None = None,
        limit: int = 100,
        order_by: str | None = None,
        numerical_columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        table = self._ensure_table_name(table_name)
        numerical_set = set(numerical_columns or [])

        conditions: list[str] = []
        values: list[Any] = []

        # Exact matches
        if criteria:
            for key, value in criteria.items():
                if value is not None:
                    if not self._validate_identifier(key):
                        raise ValueError(f"Invalid column name: {key}")
                    conditions.append(f"{key} = %s")
                    values.append(value)

        # Ranges
        if range_criteria:
            for column, range_params in range_criteria.items():
                if numerical_set and column not in numerical_set:
                    logger.warning(
                        f"Column '{column}' not in allowed numerical columns. Skipping."
                    )
                    continue
                if not self._validate_identifier(column):
                    raise ValueError(f"Invalid column name: {column}")

                min_value = range_params.get("min")
                max_value = range_params.get("max")
                if min_value is not None:
                    conditions.append(f"{column} >= %s")
                    values.append(min_value)
                if max_value is not None:
                    conditions.append(f"{column} <= %s")
                    values.append(max_value)

        # Build query
        if conditions:
            where_clause = " AND ".join(conditions)
            base_query = f"SELECT * FROM {table} WHERE {where_clause}"
        else:
            base_query = f"SELECT * FROM {table}"

        if order_by is not None:
            if not self._validate_order_by(order_by):
                raise ValueError(f"Invalid ORDER BY clause: {order_by}")
            query = f"{base_query} ORDER BY {order_by} LIMIT %s;"
        else:
            query = f"{base_query} LIMIT %s;"

        values.append(limit)

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                results = cursor.fetchall()
                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True)) for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error searching with range in '{table}': {e}")
            return []

    def search(
        self,
        exact_criteria: dict[str, Any] | None = None,
        range_criteria: dict[str, dict[str, Any]] | None = None,
        text_search: dict[str, Any] | None = None,
        table_name: str | None = None,
        limit: int = 100,
        order_by: str | None = None,
        numerical_columns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        table = self._ensure_table_name(table_name)
        numerical_set = set(numerical_columns or [])

        conditions: list[str] = []
        values: list[Any] = []

        # Exact
        if exact_criteria:
            for key, value in exact_criteria.items():
                if value is not None:
                    if not self._validate_identifier(key):
                        raise ValueError(f"Invalid column name: {key}")
                    conditions.append(f"{key} = %s")
                    values.append(value)

        # Range
        if range_criteria:
            for column, range_params in range_criteria.items():
                if numerical_set and column not in numerical_set:
                    logger.warning(
                        f"Column '{column}' not in allowed numerical columns. Skipping."
                    )
                    continue
                if not self._validate_identifier(column):
                    raise ValueError(f"Invalid column name: {column}")

                min_value = range_params.get("min")
                max_value = range_params.get("max")
                if min_value is not None:
                    conditions.append(f"{column} >= %s")
                    values.append(min_value)
                if max_value is not None:
                    conditions.append(f"{column} <= %s")
                    values.append(max_value)

        # Text search
        if text_search:
            search_term = text_search.get("term")
            search_fields = text_search.get("fields", [])
            if search_term and search_fields:
                text_conditions = []
                search_pattern = f"%{search_term}%"
                # Normalize to strings
                search_fields = [
                    getattr(f, "value", str(f)) for f in search_fields
                ]
                for field in search_fields:
                    if not self._validate_identifier(field):
                        raise ValueError(
                            f"Invalid column name in text search: {field}"
                        )
                    text_conditions.append(f"LOWER({field}) LIKE LOWER(%s)")
                    values.append(search_pattern)
                if text_conditions:
                    conditions.append(f"({' OR '.join(text_conditions)})")

        # Build final query
        if conditions:
            where_clause = " AND ".join(conditions)
            base_query = f"SELECT * FROM {table} WHERE {where_clause}"
        else:
            base_query = f"SELECT * FROM {table}"

        if order_by is not None:
            if not self._validate_order_by(order_by):
                raise ValueError(f"Invalid ORDER BY clause: {order_by}")
            query = f"{base_query} ORDER BY {order_by} LIMIT %s;"
        else:
            query = f"{base_query} LIMIT %s;"

        values.append(limit)
        logger.debug(f"Executing query: {query} with values {values}")

        try:
            with self.get_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, values)
                results = cursor.fetchall()
                if results:
                    columns = [desc[0] for desc in cursor.description]
                    return [
                        dict(zip(columns, row, strict=True)) for row in results
                    ]
                return []
        except psycopg2.Error as e:
            logger.error(f"Error searching in '{table}': {e}")
            return []

    # ----------------------
    # Backward-compatible ads-specific wrappers
    # ----------------------
    def create_ads_table(self) -> bool:
        """Create the 'ads' table with predefined schema (backward compatibility)."""
        table = self._ensure_table_name(ADS_TABLE_NAME)
        return self.create_table(table, ADS_TABLE_COLUMNS_SQL)

    def create_images_table(self) -> bool:
        """Create the 'ad_images' table with predefined schema."""
        table = self._ensure_table_name(IMAGES_TABLE_NAME)
        return self.create_table(table, IMAGES_TABLE_COLUMNS_SQL)

    def insert_ad(
        self, ad_data: dict[str, Any]
    ) -> int | None:
        allowed_columns = AdColumns.get_insertable_columns()
        ret = self.insert(
            ad_data,
            table_name=ADS_TABLE_NAME,
            allowed_columns=allowed_columns,
            returning="id",
        )
        return int(ret) if ret is not None else None

    def insert_image_url(
        self, ad_id: int, image_url: str, image_order: int = 0
    ) -> int | None:
        image_data = {
            "ad_id": ad_id,
            "image_url": image_url,
            "image_order": image_order,
        }
        ret = self.insert(
            image_data,
            table_name=IMAGES_TABLE_NAME,
            allowed_columns=["ad_id", "image_url", "image_order"],
            returning="id",
        )
        return int(ret) if ret is not None else None

    def get_ad_by_id(
        self, ad_id: int, table_name: str | None = None
    ) -> dict[str, Any] | None:
        return self.get_by_id(ad_id, table_name=table_name)

    def get_ads_by_criteria(
        self,
        criteria: dict[str, Any],
        limit: int = 100,
        table_name: str | None = None,
        order_by: str | None = None,
    ) -> list[dict[str, Any]]:
        return self.get_by_criteria(
            criteria, table_name=table_name, limit=limit, order_by=order_by
        )

    def get_all_ads(
        self, limit: int = 100, table_name: str | None = None
    ) -> list[dict[str, Any]]:
        # Preserve previous default ordering if column exists; caller may override as needed
        try:
            return self.get_all(
                table_name=table_name,
                limit=limit,
                order_by="insertion_time DESC",
            )
        except ValueError:
            return self.get_all(table_name=table_name, limit=limit)

    def update_ad(
        self,
        ad_id: int,
        update_data: dict[str, Any],
        table_name: str | None = None,
    ) -> bool:
        # Prevent updating id and insertion_time by default
        return self.update_by_id(ad_id, update_data, table_name=table_name)

    def delete_ad(self, ad_id: int, table_name: str | None = None) -> bool:
        return self.delete_by_id(ad_id, table_name=table_name)

    def get_ads_count(self, table_name: str | None = None) -> int:
        return self.get_count(table_name=table_name)

    def search_ads_by_text(
        self,
        search_term: str,
        fields: list[str] | None = None,
        limit: int = 100,
        table_name: str | None = None,
    ) -> list[dict[str, Any]]:
        if fields is None:
            # Default to common ad text fields when not specified
            try:
                default_fields = [
                    AdColumns.MAKE,
                    AdColumns.MODEL,
                    AdColumns.LOCATION,
                    AdColumns.TYPE,
                ]
                fields = [getattr(f, "value", str(f)) for f in default_fields]
            except Exception:
                logger.warning(
                    "Text search fields not provided; defaulting to empty list"
                )
                fields = []
        # Preserve previous default ordering if possible
        try:
            return self.search_text(
                search_term,
                fields=fields,
                table_name=table_name,
                limit=limit,
                order_by="insertion_time DESC",
            )
        except ValueError:
            return self.search_text(
                search_term,
                fields=fields,
                table_name=table_name,
                limit=limit,
            )

    def search_ads_with_range(
        self,
        criteria: dict[str, Any] | None = None,
        range_criteria: dict[str, dict[str, Any]] | None = None,
        limit: int = 100,
        table_name: str | None = None,
    ) -> list[dict[str, Any]]:
        numerical_columns: list[str] | None = None
        try:
            cols = AdColumns.get_numerical_columns()
            numerical_columns = (
                [getattr(c, "value", str(c)) for c in cols] if cols else None
            )
        except Exception:
            numerical_columns = None
        try:
            return self.search_with_range(
                criteria=criteria,
                range_criteria=range_criteria,
                table_name=table_name,
                limit=limit,
                order_by="insertion_time DESC",
                numerical_columns=numerical_columns,
            )
        except ValueError:
            return self.search_with_range(
                criteria=criteria,
                range_criteria=range_criteria,
                table_name=table_name,
                limit=limit,
                numerical_columns=numerical_columns,
            )

    def search_ads(
        self,
        exact_criteria: dict[str, Any] | None = None,
        range_criteria: dict[str, dict[str, Any]] | None = None,
        text_search: dict[str, Any] | None = None,
        limit: int = 100,
        table_name: str | None = None,
    ) -> list[dict[str, Any]]:
        numerical_columns: list[str] | None = None
        try:
            cols = AdColumns.get_numerical_columns()
            numerical_columns = (
                [getattr(c, "value", str(c)) for c in cols] if cols else None
            )
        except Exception:
            numerical_columns = None

        # Ensure default text fields if not provided (backward-compatible behavior)
        if (
            text_search
            and text_search.get("term")
            and not text_search.get("fields")
        ):
            try:
                default_fields = [
                    AdColumns.MAKE,
                    AdColumns.MODEL,
                    AdColumns.LOCATION,
                    AdColumns.TYPE,
                ]
                text_search = {
                    "term": text_search.get("term"),
                    "fields": [
                        getattr(f, "value", str(f)) for f in default_fields
                    ],
                }
            except Exception:
                pass

        try:
            return self.search(
                exact_criteria=exact_criteria,
                range_criteria=range_criteria,
                text_search=text_search,
                table_name=table_name,
                limit=limit,
                order_by="insertion_time DESC",
                numerical_columns=numerical_columns,
            )
        except ValueError:
            return self.search(
                exact_criteria=exact_criteria,
                range_criteria=range_criteria,
                text_search=text_search,
                table_name=table_name,
                limit=limit,
                numerical_columns=numerical_columns,
            )

    @property
    def instance(self) -> "Database":
        if self._instance is None:
            raise RuntimeError("Database instance not initialized")
        return self._instance
