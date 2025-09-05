import asyncio
import logging
from uuid import uuid4

from agents import Agent, Runner
from agents.mcp import (
    MCPServer,
    MCPServerStreamableHttp,
    MCPServerStreamableHttpParams,
)
from agents.model_settings import ModelSettings

from shared.session import PostgreSQLSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)


async def run(mcp_server: MCPServer):
    agent = Agent(
        name="Assistant",
        instructions="Use the tools to answer the questions.",
        mcp_servers=[mcp_server],
        model_settings=ModelSettings(tool_choice="required"),
    )

    # Use the `add` tool to add two numbers
    # message = "how many car ads are there"
    # print(f"Running: {message}")
    # result = await Runner.run(starting_agent=agent, input=message)
    # print(result.final_output)

    # message = "are there any Opel cars"
    message = "give me 5 examples of BMW cars that are under 20000 euros and above 10000"
    print(f"\n\nRunning: {message}")
    result = await Runner.run(starting_agent=agent, input=message)
    print(result.final_output)

    # # Run the `get_weather` tool
    # message = "What's the weather in Tokyo?"
    # print(f"\n\nRunning: {message}")
    # result = await Runner.run(starting_agent=agent, input=message)
    # print(result.final_output)

    # # Run the `get_secret_word` tool
    # message = "What's the secret word?"
    # print(f"\n\nRunning: {message}")
    # result = await Runner.run(starting_agent=agent, input=message)
    # print(result.final_output)


async def main():
    session_id = str(uuid4())
    session = PostgreSQLSession(
        session_id=session_id,
        connection_string="postgresql://adsuser:pass@localhost:5432/ads_db",
    )
    params = MCPServerStreamableHttpParams(url="http://localhost:8000/mcp")
    ads_db_mcp_server = MCPServerStreamableHttp(
        params=params,
        name="car-database-read-server",
    )

    try:
        await ads_db_mcp_server.connect()
        logging.debug("Connected successfully to MCP db server")

        await run(ads_db_mcp_server)

    except Exception as e:
        logging.error(f"Failed to connect to MCP db server: {e}")
        return
    finally:
        await ads_db_mcp_server.cleanup()
        logging.debug("Cleaned up MCP db server connection")


if __name__ == "__main__":
    asyncio.run(main())
