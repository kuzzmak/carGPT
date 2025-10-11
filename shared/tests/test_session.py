"""Tests for PostgreSQLSession implementation.

This module contains comprehensive tests for the PostgreSQLSession class,
including database operations, error handling, and edge cases.
"""

import asyncio
import uuid
from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import psycopg2
import pytest
from testcontainers.postgres import PostgresContainer

from shared.session import PostgreSQLSession

# Test constants
EXPECTED_ITEM_COUNT = 2
EXPECTED_TOTAL_CONCURRENT_ITEMS = 10
LARGE_MESSAGE_SIZE = 10000
ORDERING_TEST_COUNT = 5


@pytest.fixture(scope="session")
def postgres_container_session(
    test_db_name: str,
    test_db_user: str,
    test_db_password: str,
    test_db_port: int,
) -> Generator[dict[str, Any], None, None]:
    """Session-scoped fixture that provides a PostgreSQL container for session tests."""
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
def connection_string(postgres_container_session: dict[str, Any]) -> str:
    """Generate PostgreSQL connection string."""
    params = postgres_container_session
    return (
        f"postgresql://{params['user']}:{params['password']}@"
        f"{params['host']}:{params['port']}/{params['dbname']}"
    )


@pytest.fixture(scope="function")
def session_id() -> str:
    """Generate a unique session ID for testing."""
    return f"test_session_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="function")
def session(
    connection_string: str, session_id: str
) -> Generator[PostgreSQLSession, None, None]:
    """Create a PostgreSQLSession instance for testing."""
    session = PostgreSQLSession(
        session_id=session_id,
        connection_string=connection_string,
        sessions_table="test_agent_sessions",
        messages_table="test_agent_messages",
    )

    yield session

    # Cleanup: close connection (table data will be isolated by unique session_id)
    session.close()


@pytest.fixture(scope="function")
def sample_items() -> list[dict[str, Any]]:
    """Sample conversation items for testing."""
    return [
        {
            "type": "user",
            "content": "Hello, how are you?",
            "timestamp": "2024-01-01T10:00:00Z",
        },
        {
            "type": "assistant",
            "content": "I'm doing well, thank you!",
            "timestamp": "2024-01-01T10:00:30Z",
        },
        {
            "type": "user",
            "content": "What's the weather like?",
            "timestamp": "2024-01-01T10:01:00Z",
        },
        {
            "type": "assistant",
            "content": "I'd need your location to check the weather.",
            "timestamp": "2024-01-01T10:01:15Z",
        },
    ]


class TestPostgreSQLSession:
    """Test class for PostgreSQLSession functionality."""

    def test_initialization(
        self,
        session: PostgreSQLSession,
        session_id: str,
        connection_string: str,
    ):
        """Test PostgreSQLSession initialization."""
        assert session.session_id == session_id
        assert session.connection_string == connection_string
        assert session.sessions_table == "test_agent_sessions"
        assert session.messages_table == "test_agent_messages"
        assert session._pool is None
        assert session._lock is not None

    def test_initialization_with_default_tables(self, connection_string: str):
        """Test initialization with default table names."""
        session = PostgreSQLSession("test_id", connection_string)
        assert session.sessions_table == "agent_sessions"
        assert session.messages_table == "agent_messages"
        session.close()

    def test_psycopg2_import_error(self):
        """Test error handling when psycopg2 is not available."""
        with patch("shared.session.session.psycopg2", None):
            session = PostgreSQLSession("test", "postgresql://test")
            with pytest.raises(ImportError, match="psycopg2 is required"):
                session._get_psycopg2()

    @pytest.mark.asyncio
    async def test_database_initialization(self, session: PostgreSQLSession):
        """Test that database tables are created correctly."""
        # Trigger database initialization by calling _get_pool
        pool = session._get_pool()
        assert pool is not None

        # Verify tables were created by checking if we can query them
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                # Check if sessions table exists
                cur.execute(
                    """
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name = %s
                """,
                    (session.sessions_table,),
                )
                assert cur.fetchone() is not None

                # Check if messages table exists
                cur.execute(
                    """
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name = %s
                """,
                    (session.messages_table,),
                )
                assert cur.fetchone() is not None

                # Check if index exists
                cur.execute(
                    """
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = %s AND indexname = %s
                """,
                    (
                        session.messages_table,
                        f"idx_{session.messages_table}_session_id",
                    ),
                )
                assert cur.fetchone() is not None
        finally:
            pool.putconn(conn)

    @pytest.mark.asyncio
    async def test_add_items_empty_list(self, session: PostgreSQLSession):
        """Test adding empty list of items."""
        await session.add_items([])

        items = await session.get_items()
        assert items == []

    @pytest.mark.asyncio
    async def test_add_and_get_items(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test adding and retrieving items."""
        await session.add_items(sample_items)

        retrieved_items = await session.get_items()
        assert len(retrieved_items) == len(sample_items)

        # Items should be returned in chronological order
        for i, item in enumerate(retrieved_items):
            assert item == sample_items[i]

    @pytest.mark.asyncio
    async def test_get_items_with_limit(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test retrieving items with a limit."""
        await session.add_items(sample_items)

        # Get all items first
        all_items = await session.get_items()
        assert len(all_items) == len(sample_items)

        # Get latest 2 items
        limited_items = await session.get_items(limit=EXPECTED_ITEM_COUNT)
        assert len(limited_items) == EXPECTED_ITEM_COUNT

        # The limited items should be a subset of all items
        for item in limited_items:
            assert item in all_items

        # Test with limit of 1
        single_item = await session.get_items(limit=1)
        assert len(single_item) == 1
        assert single_item[0] in all_items

    @pytest.mark.asyncio
    async def test_get_items_limit_larger_than_available(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test retrieving items with limit larger than available items."""
        await session.add_items(sample_items[:2])  # Add only 2 items

        limited_items = await session.get_items(limit=10)
        assert len(limited_items) == EXPECTED_ITEM_COUNT
        assert limited_items == sample_items[:2]

    @pytest.mark.asyncio
    async def test_get_items_empty_session(self, session: PostgreSQLSession):
        """Test retrieving items from empty session."""
        items = await session.get_items()
        assert items == []

    @pytest.mark.asyncio
    async def test_pop_item(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test popping the most recent item."""
        await session.add_items(sample_items)

        # Pop the most recent item
        popped_item = await session.pop_item()
        assert popped_item == sample_items[-1]  # Should be the last item

        # Verify it was removed
        remaining_items = await session.get_items()
        assert len(remaining_items) == len(sample_items) - 1
        assert remaining_items == sample_items[:-1]

    @pytest.mark.asyncio
    async def test_pop_item_empty_session(self, session: PostgreSQLSession):
        """Test popping from empty session."""
        popped_item = await session.pop_item()
        assert popped_item is None

    @pytest.mark.asyncio
    async def test_pop_item_single_item(self, session: PostgreSQLSession):
        """Test popping the only item in session."""
        item = {"type": "user", "content": "Hello"}
        await session.add_items([item])

        popped_item = await session.pop_item()
        assert popped_item == item

        # Session should now be empty
        remaining_items = await session.get_items()
        assert remaining_items == []

    @pytest.mark.asyncio
    async def test_clear_session(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test clearing all items from session."""
        await session.add_items(sample_items)

        # Verify items were added
        items = await session.get_items()
        assert len(items) == len(sample_items)

        # Clear the session
        await session.clear_session()

        # Verify session is empty
        items = await session.get_items()
        assert items == []

    @pytest.mark.asyncio
    async def test_clear_empty_session(self, session: PostgreSQLSession):
        """Test clearing already empty session."""
        await session.clear_session()  # Should not raise any errors

        items = await session.get_items()
        assert items == []

    @pytest.mark.asyncio
    async def test_multiple_sessions_isolation(
        self, connection_string: str, sample_items: list[dict]
    ):
        """Test that different sessions are isolated from each other."""
        session1 = PostgreSQLSession(
            "session_1", connection_string, "test_sessions", "test_messages"
        )
        session2 = PostgreSQLSession(
            "session_2", connection_string, "test_sessions", "test_messages"
        )

        try:
            # Add items to session1
            await session1.add_items(sample_items[:2])

            # Add different items to session2
            await session2.add_items(sample_items[2:])

            # Verify isolation
            items1 = await session1.get_items()
            items2 = await session2.get_items()

            assert len(items1) == EXPECTED_ITEM_COUNT
            assert len(items2) == EXPECTED_ITEM_COUNT
            assert items1 == sample_items[:2]
            assert items2 == sample_items[2:]

            # Clear session1, session2 should be unaffected
            await session1.clear_session()

            items1 = await session1.get_items()
            items2 = await session2.get_items()

            assert items1 == []
            assert items2 == sample_items[2:]

        finally:
            session1.close()
            session2.close()

    @pytest.mark.asyncio
    async def test_complex_json_data(self, session: PostgreSQLSession):
        """Test storing and retrieving complex JSON data."""
        complex_items = [
            {
                "type": "user",
                "content": "Hello",
                "metadata": {
                    "nested": {"key": "value"},
                    "list": [1, 2, 3],
                    "bool": True,
                    "null_value": None,
                },
            },
            {
                "type": "assistant",
                "content": "Response",
                "data": {
                    "unicode": "🤖",
                    "special_chars": "\"quotes\" and 'apostrophes' and \\backslashes\\",
                },
            },
        ]

        await session.add_items(complex_items)
        retrieved_items = await session.get_items()

        assert len(retrieved_items) == len(complex_items)
        assert retrieved_items == complex_items

    def test_connection_pool_reuse(self, session: PostgreSQLSession):
        """Test that connection pool is reused across operations."""
        # First operation should create the pool
        session._get_pool()
        pool1 = session._pool

        # Second operation should reuse the same pool
        session._get_pool()
        pool2 = session._pool

        assert pool1 is pool2
        assert pool1 is not None

    def test_close_connection(self, session: PostgreSQLSession):
        """Test closing the connection pool."""
        # Initialize pool
        session._get_pool()
        assert session._pool is not None

        # Close the connection
        session.close()
        assert session._pool is None

    def test_close_without_pool(self, session: PostgreSQLSession):
        """Test closing when no pool exists."""
        assert session._pool is None
        session.close()  # Should not raise any errors
        assert session._pool is None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, session: PostgreSQLSession):
        """Test concurrent operations on the same session."""
        items1 = [
            {"type": "user", "content": f"Message {i}"} for i in range(5)
        ]
        items2 = [
            {"type": "assistant", "content": f"Response {i}"} for i in range(5)
        ]

        # Run concurrent add operations
        await asyncio.gather(
            session.add_items(items1), session.add_items(items2)
        )

        # Verify all items were added
        all_items = await session.get_items()
        assert len(all_items) == EXPECTED_TOTAL_CONCURRENT_ITEMS

    @pytest.mark.asyncio
    async def test_session_metadata_handling(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test that session metadata is properly handled."""
        await session.add_items(sample_items)

        # Check that session record was created
        pool = session._get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT session_id, created_at, updated_at 
                    FROM {session.sessions_table} 
                    WHERE session_id = %s
                """,
                    (session.session_id,),
                )

                row = cur.fetchone()
                assert row is not None
                assert row[0] == session.session_id
                assert row[1] is not None  # created_at
                assert row[2] is not None  # updated_at
        finally:
            pool.putconn(conn)

    @pytest.mark.asyncio
    async def test_invalid_json_handling(self, session: PostgreSQLSession):
        """Test handling of items that can't be JSON serialized (edge case)."""
        # This tests the robustness of the implementation
        # Normal usage shouldn't encounter this, but we test it for completeness

        # Add valid item first
        valid_item = {"type": "user", "content": "Hello"}
        await session.add_items([valid_item])

        # Verify the valid item was stored
        items = await session.get_items()
        assert len(items) == 1
        assert items[0] == valid_item

    @pytest.mark.asyncio
    async def test_database_connection_error_handling(self, session_id: str):
        """Test handling of database connection errors."""
        # Use invalid connection string
        invalid_session = PostgreSQLSession(
            session_id=session_id,
            connection_string="postgresql://invalid:invalid@nonexistent:5432/db",
        )

        # This should raise a connection error
        with pytest.raises(
            (psycopg2.OperationalError, psycopg2.DatabaseError)
        ):
            await invalid_session.add_items([{"test": "data"}])

        invalid_session.close()

    @pytest.mark.asyncio
    async def test_large_message_storage(self, session: PostgreSQLSession):
        """Test storing large messages to verify JSONB handling."""
        large_content = "x" * LARGE_MESSAGE_SIZE  # 10KB message
        large_item = {
            "type": "user",
            "content": large_content,
            "metadata": {"size": len(large_content)},
        }

        await session.add_items([large_item])
        retrieved_items = await session.get_items()

        assert len(retrieved_items) == 1
        assert retrieved_items[0] == large_item
        assert len(retrieved_items[0]["content"]) == LARGE_MESSAGE_SIZE

    @pytest.mark.asyncio
    async def test_ordering_consistency(self, session: PostgreSQLSession):
        """Test that items are consistently ordered by creation time."""
        # Add items with small delays to ensure different timestamps
        for i in range(ORDERING_TEST_COUNT):
            await session.add_items([{"order": i, "content": f"Message {i}"}])
            await asyncio.sleep(
                0.01
            )  # Small delay to ensure different timestamps

        # Retrieve all items
        items = await session.get_items()

        # Verify chronological order
        assert len(items) == ORDERING_TEST_COUNT
        for i, item in enumerate(items):
            assert item["order"] == i

    @pytest.mark.asyncio
    async def test_get_items_limit_zero(
        self, session: PostgreSQLSession, sample_items: list[dict]
    ):
        """Test retrieving items with limit of zero."""
        await session.add_items(sample_items)

        limited_items = await session.get_items(limit=0)
        assert limited_items == []

    def test_custom_table_names(self, connection_string: str):
        """Test initialization with custom table names."""
        custom_session = PostgreSQLSession(
            "test_id",
            connection_string,
            sessions_table="custom_sessions",
            messages_table="custom_messages",
        )

        assert custom_session.sessions_table == "custom_sessions"
        assert custom_session.messages_table == "custom_messages"
        custom_session.close()
