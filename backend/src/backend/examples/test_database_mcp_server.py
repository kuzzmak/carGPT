import asyncio
from uuid import uuid4

from agents import Agent, OpenAIChatCompletionsModel, Runner
from agents.mcp import (
    MCPServer,
    MCPServerStreamableHttp,
    MCPServerStreamableHttpParams,
)
from agents.memory.session import SessionABC
from agents.model_settings import ModelSettings
from openai import AsyncOpenAI

from backend.paths import BACKEND_DIR

from shared.logging_config import get_logger, setup_logging
from shared.session import PostgreSQLSession

setup_logging(BACKEND_DIR / "logging_config.yaml")
logger = get_logger("backend")


async def run_gemini(mcp_server: MCPServer, session: SessionABC):
    logger.info("Running with Gemini 2.5")
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    API_KEY = "..."
    MODEL_NAME = "gemini-2.5-flash"
    client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
    agent = Agent(
        name="Assistant",
        instructions="Use the tools to answer the questions.",
        model=OpenAIChatCompletionsModel(
            model=MODEL_NAME, openai_client=client
        ),
        mcp_servers=[mcp_server],
    )
    message = (
        "give me 5 examples of BMW cars that are above 10k but lower than 50k"
    )
    logger.info(f"\n\nRunning: {message}")
    result = await Runner.run(
        starting_agent=agent, input=message, session=session
    )
    logger.info(f"Result: {result.final_output}")
    result = await Runner.run(
        starting_agent=agent, input="give me link to the ad", session=session
    )
    logger.info(f"Result: {result.final_output}")


async def run_openai(mcp_server: MCPServer, session: SessionABC):
    logger.info("Running with OpenAI GPT-4o")
    agent = Agent(
        name="Assistant",
        instructions="Use the tools to answer the questions.",
        mcp_servers=[mcp_server],
        # model_settings=ModelSettings(tool_choice="required"),
    )

    # message = "are there any Opel cars"
    message = (
        "give me 5 examples of BMW cars that are above 10k but lower than 50k"
    )
    logger.info(f"\n\nRunning: {message}")
    result = await Runner.run(
        starting_agent=agent, input=message, session=session
    )
    logger.info(f"Result: {result.final_output}")
    result = await Runner.run(
        starting_agent=agent, input="give me link to the ad", session=session
    )
    logger.info(f"Result: {result.final_output}")


async def main():
    session_id = str(uuid4())
    session = PostgreSQLSession(
        session_id=session_id,
        connection_string="postgresql://adsuser:pass@localhost:5432/ads_db",
    )
    params = MCPServerStreamableHttpParams(url="http://localhost:8001/mcp")
    ads_db_mcp_server = MCPServerStreamableHttp(
        params=params,
        name="car-database-read-server",
    )

    try:
        await ads_db_mcp_server.connect()
        logger.debug("Connected successfully to MCP db server")

        await run_openai(ads_db_mcp_server, session)

    except Exception as e:
        logger.error(f"Failed to connect to MCP db server: {e}")
        return
    finally:
        await ads_db_mcp_server.cleanup()
        logger.debug("Cleaned up MCP db server connection")


if __name__ == "__main__":
    asyncio.run(main())
