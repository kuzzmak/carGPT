import asyncio

from shared.session import PostgreSQLSession


async def main():  # Create a session instance that will persist across runs
    session_id = "conversation_123"

    session = PostgreSQLSession(
        session_id=session_id,
        connection_string="postgresql://adsuser:pass@localhost:5432/ads_db",
    )

    # Use exactly the same as before
    await session.add_items([{"role": "assistant", "content": "hi user"}])
    items = await session.get_items(limit=10)
    print("Items in session:")
    for item in items:
        print(item)


if __name__ == "__main__":
    asyncio.run(main())
