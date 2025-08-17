"""PostgreSQL Session implementation for conversation history storage.

This module provides a PostgreSQL-specific session storage implementation
that integrates with the existing agents.memory.session framework.
"""

import asyncio
import json
import threading
from typing import TYPE_CHECKING, Any

try:
    import psycopg2
    import psycopg2.extras
    import psycopg2.pool
except ImportError:
    psycopg2 = None

from agents.memory.session import SessionABC

if TYPE_CHECKING and psycopg2 is not None:
    pass

# Use Any for now since the exact type structure is not available
TResponseInputItem = Any


class PostgreSQLSession(SessionABC):
    """PostgreSQL-based implementation of session storage.

    This implementation stores conversation history in a PostgreSQL database.
    Requires psycopg2 for PostgreSQL operations.
    """

    def __init__(
        self,
        session_id: str,
        connection_string: str,
        sessions_table: str = "agent_sessions",
        messages_table: str = "agent_messages",
    ):
        """Initialize the PostgreSQL session.

        Args:
            session_id: Unique identifier for the conversation session
            connection_string: PostgreSQL connection string (e.g.,
                'postgresql://user:password@localhost:5432/dbname')
            sessions_table: Name of the table to store session metadata. Defaults to
                'agent_sessions'
            messages_table: Name of the table to store message data. Defaults to 'agent_messages'
        """
        self.session_id = session_id
        self.connection_string = connection_string
        self.sessions_table = sessions_table
        self.messages_table = messages_table
        self._pool = None
        self._lock = threading.Lock()

    def _get_psycopg2(self):
        """Get psycopg2 module with proper error handling."""
        if psycopg2 is None:
            raise ImportError(
                "psycopg2 is required for PostgreSQLSession. "
                "Install it with: pip install psycopg2-binary"
            )
        return psycopg2

    def _get_pool(self):
        """Get or create the connection pool."""
        if self._pool is None:
            with self._lock:
                if self._pool is None:
                    psycopg2_module = self._get_psycopg2()
                    self._pool = psycopg2_module.pool.ThreadedConnectionPool(
                        minconn=1, maxconn=10, dsn=self.connection_string
                    )
                    self._init_db()
        return self._pool

    def _init_db(self) -> None:
        """Initialize the database schema."""
        pool = self._get_pool()
        conn = None
        try:
            conn = pool.getconn()
            with conn.cursor() as cur:
                # Create sessions table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.sessions_table} (
                        session_id TEXT PRIMARY KEY,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create messages table
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.messages_table} (
                        id SERIAL PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        message_data JSONB NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES {self.sessions_table} (session_id)
                            ON DELETE CASCADE
                    )
                """)

                # Create index for performance
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.messages_table}_session_id
                    ON {self.messages_table} (session_id, created_at)
                """)

                conn.commit()
        finally:
            if conn:
                pool.putconn(conn)

    async def get_items(
        self, limit: int | None = None
    ) -> list[TResponseInputItem]:
        """Retrieve the conversation history for this session.

        Args:
            limit: Maximum number of items to retrieve. If None, retrieves all items.
                   When specified, returns the latest N items in chronological order.

        Returns:
            List of input items representing the conversation history
        """

        def _get_items_sync():
            pool = self._get_pool()
            conn = None
            try:
                conn = pool.getconn()
                psycopg2_module = self._get_psycopg2()
                with conn.cursor(
                    cursor_factory=psycopg2_module.extras.RealDictCursor
                ) as cur:
                    if limit is None:
                        # Fetch all items in chronological order
                        cur.execute(
                            f"""
                            SELECT message_data FROM {self.messages_table}
                            WHERE session_id = %s
                            ORDER BY created_at ASC
                        """,
                            (self.session_id,),
                        )
                    else:
                        # Fetch the latest N items, then reverse for chronological order
                        cur.execute(
                            f"""
                            SELECT message_data FROM (
                                SELECT message_data, created_at FROM {self.messages_table}
                                WHERE session_id = %s
                                ORDER BY created_at DESC
                                LIMIT %s
                            ) AS latest_messages
                            ORDER BY created_at ASC
                        """,
                            (self.session_id, limit),
                        )

                    rows = cur.fetchall()

                    items = []
                    for row in rows:
                        try:
                            # PostgreSQL JSONB is already parsed
                            item = row["message_data"]
                            items.append(item)
                        except (KeyError, TypeError):
                            # Skip invalid entries
                            continue

                    return items
            finally:
                if conn:
                    pool.putconn(conn)

        return await asyncio.to_thread(_get_items_sync)

    async def add_items(self, items: list[TResponseInputItem]) -> None:
        """Add new items to the conversation history.

        Args:
            items: List of input items to add to the history
        """
        if not items:
            return

        def _add_items_sync():
            pool = self._get_pool()
            conn = None
            try:
                conn = pool.getconn()
                with conn.cursor() as cur:
                    # Ensure session exists
                    cur.execute(
                        f"""
                        INSERT INTO {self.sessions_table} (session_id) 
                        VALUES (%s) 
                        ON CONFLICT (session_id) DO NOTHING
                    """,
                        (self.session_id,),
                    )

                    # Add items
                    message_data = [
                        (self.session_id, json.dumps(item)) for item in items
                    ]
                    cur.executemany(
                        f"""
                        INSERT INTO {self.messages_table} (session_id, message_data) 
                        VALUES (%s, %s::jsonb)
                    """,
                        message_data,
                    )

                    # Update session timestamp
                    cur.execute(
                        f"""
                        UPDATE {self.sessions_table}
                        SET updated_at = CURRENT_TIMESTAMP
                        WHERE session_id = %s
                    """,
                        (self.session_id,),
                    )

                    conn.commit()
            finally:
                if conn:
                    pool.putconn(conn)

        await asyncio.to_thread(_add_items_sync)

    async def pop_item(self) -> TResponseInputItem | None:
        """Remove and return the most recent item from the session.

        Returns:
            The most recent item if it exists, None if the session is empty
        """

        def _pop_item_sync():
            pool = self._get_pool()
            conn = None
            try:
                conn = pool.getconn()
                psycopg2_module = self._get_psycopg2()
                with conn.cursor(
                    cursor_factory=psycopg2_module.extras.RealDictCursor
                ) as cur:
                    # Find the most recent item
                    cur.execute(
                        f"""
                        SELECT id, message_data FROM {self.messages_table}
                        WHERE session_id = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """,
                        (self.session_id,),
                    )

                    row = cur.fetchone()
                    if row:
                        # Delete the item
                        cur.execute(
                            f"""
                            DELETE FROM {self.messages_table} WHERE id = %s
                        """,
                            (row["id"],),
                        )

                        conn.commit()

                        try:
                            # PostgreSQL JSONB is already parsed
                            return row["message_data"]
                        except (KeyError, TypeError):
                            # Return None for corrupted entries (already deleted)
                            return None

                    return None
            finally:
                if conn:
                    pool.putconn(conn)

        return await asyncio.to_thread(_pop_item_sync)

    async def clear_session(self) -> None:
        """Clear all items for this session."""

        def _clear_session_sync():
            pool = self._get_pool()
            conn = None
            try:
                conn = pool.getconn()
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        DELETE FROM {self.messages_table} WHERE session_id = %s
                    """,
                        (self.session_id,),
                    )
                    cur.execute(
                        f"""
                        DELETE FROM {self.sessions_table} WHERE session_id = %s
                    """,
                        (self.session_id,),
                    )

                    conn.commit()
            finally:
                if conn:
                    pool.putconn(conn)

        await asyncio.to_thread(_clear_session_sync)

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            self._pool.closeall()
            self._pool = None
