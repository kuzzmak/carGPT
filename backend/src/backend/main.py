import os
from contextlib import asynccontextmanager
from datetime import datetime

from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai.types.responses import ResponseTextDeltaEvent

from backend.constants import CHAT_MODEL, SYSTEM_PROMPT
from backend.models import (
    AdResponse,
    ChatMessage,
    ChatRequest,
    Conversation,
    HealthResponse,
    SearchCriteria,
    StatsResponse,
    TextSearchRequest,
)
from backend.paths import BACKEND_DIR

from shared.database import Database
from shared.logging_config import get_logger, setup_logging
from shared.session import PostgreSQLSession

CONVERSATIONS_TABLE_NAME = os.environ["CONVERSATIONS_TABLE_NAME"]
REQUEST_TIMEOUT_SECONDS = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "60"))

# Setup main backend logging with base configuration extension
setup_logging(BACKEND_DIR / "logging_config.yaml")
logger = get_logger("backend")

ads_db_mcp_server: MCPServerStreamableHttp
perplexity_mcp_server: MCPServerStreamableHttp


@asynccontextmanager
async def lifespan(app: FastAPI):
    global ads_db_mcp_server, perplexity_mcp_server
    # ads_db_mcp_server = await initialize_ads_db_mcp_server()
    # perplexity_mcp_server = await initialize_perplexity_mcp_server()

    yield

    # await ads_db_mcp_server.cleanup()
    # await perplexity_mcp_server.cleanup()
    logger.info("MCP server connections closed")


app = FastAPI(
    title="CarGPT Backend API",
    description="REST API for car ads data",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


try:
    db = Database()
    logger.info("Database connection initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise


async def initialize_ads_db_mcp_server():
    """Initialize the Ads Database MCP server connection."""
    try:
        params = MCPServerStreamableHttpParams(
            url=os.environ["CARGPT_ADS_DB_MCP_SERVER_URL"],
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        ads_db_mcp_server = MCPServerStreamableHttp(
            params=params,
            name="carGPT Ads Database",
            client_session_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        )
        await ads_db_mcp_server.connect()
        logger.info("Ads Database MCP server initialized successfully")
        return ads_db_mcp_server
    except Exception as e:
        err = "Failed to initialize Ads Database MCP server"
        logger.error(f"{err}: {e}")
        raise Exception(err) from e


async def initialize_perplexity_mcp_server():
    """Initialize the Perplexity MCP server connection."""
    try:
        params = MCPServerStreamableHttpParams(
            url=os.environ["CARGPT_PERPLEXITY_MCP_SERVER_URL"],
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        perplexity_mcp_server = MCPServerStreamableHttp(
            params=params,
            name="Perplexity Search Server",
            client_session_timeout_seconds=REQUEST_TIMEOUT_SECONDS,
        )
        await perplexity_mcp_server.connect()
        logger.info("Perplexity MCP server initialized successfully")
        return perplexity_mcp_server
    except Exception as e:
        err = "Failed to initialize Perplexity MCP server"
        logger.error(f"{err}: {e}")
        raise Exception(err) from e


def get_agent():
    """Initialize the AI agent with MCP server connections."""
    try:
        agent = Agent(
            name="CarGPT Assistant",
            instructions=SYSTEM_PROMPT,
            model=CHAT_MODEL,
            # mcp_servers=[ads_db_mcp_server, perplexity_mcp_server],
        )
        logger.info("AI agent initialized successfully with both MCP servers")
        return agent
    except Exception as e:
        err = "Failed to initialize AI agent"
        logger.error(f"{err}: {e}")
        raise Exception(err) from e


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        db.get_ads_count()
        database_connected = True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        database_connected = False

    return HealthResponse(
        status="healthy" if database_connected else "unhealthy",
        timestamp=datetime.now(),
        database_connected=database_connected,
    )


@app.get("/ads", response_model=list[AdResponse])
async def get_ads(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of ads to return",
    ),
):
    """Get all ads with optional limit."""
    try:
        return db.get_all_ads(limit=limit)
    except Exception as e:
        logger.error(f"Error fetching ads: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.get("/ads/{ad_id}", response_model=AdResponse)
async def get_ad_by_id(ad_id: int):
    """Get a specific ad by ID."""
    try:
        ad = db.get_ad_by_id(ad_id)
        if not ad:
            raise HTTPException(status_code=404, detail="Ad not found")
        return ad
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching ad {ad_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.post("/ads/search", response_model=list[AdResponse])
async def search_ads(
    criteria: SearchCriteria,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    ),
):
    """Search ads by criteria with support for exact matches, ranges, and text search."""
    try:
        # Build exact criteria
        exact_criteria = {}
        if criteria.make:
            exact_criteria["make"] = criteria.make
        if criteria.model:
            exact_criteria["model"] = criteria.model
        if criteria.location:
            exact_criteria["location"] = criteria.location
        if criteria.engine:
            exact_criteria["engine"] = criteria.engine
        if criteria.transmission:
            exact_criteria["transmission"] = criteria.transmission
        if criteria.condition:
            exact_criteria["condition"] = criteria.condition

        # Build range criteria
        range_criteria = {}
        if criteria.price_min is not None or criteria.price_max is not None:
            range_criteria["price"] = {}
            if criteria.price_min is not None:
                range_criteria["price"]["min"] = criteria.price_min
            if criteria.price_max is not None:
                range_criteria["price"]["max"] = criteria.price_max

        if (
            criteria.manufacture_year_min is not None
            or criteria.manufacture_year_max is not None
        ):
            range_criteria["manufacture_year"] = {}
            if criteria.manufacture_year_min is not None:
                range_criteria["manufacture_year"]["min"] = (
                    criteria.manufacture_year_min
                )
            if criteria.manufacture_year_max is not None:
                range_criteria["manufacture_year"]["max"] = (
                    criteria.manufacture_year_max
                )

        if (
            criteria.mileage_min is not None
            or criteria.mileage_max is not None
        ):
            range_criteria["mileage"] = {}
            if criteria.mileage_min is not None:
                range_criteria["mileage"]["min"] = criteria.mileage_min
            if criteria.mileage_max is not None:
                range_criteria["mileage"]["max"] = criteria.mileage_max

        if criteria.power_min is not None or criteria.power_max is not None:
            range_criteria["power"] = {}
            if criteria.power_min is not None:
                range_criteria["power"]["min"] = criteria.power_min
            if criteria.power_max is not None:
                range_criteria["power"]["max"] = criteria.power_max

        # Build text search criteria
        text_search = None
        if criteria.text_search:
            text_search = {"term": criteria.text_search}
            if criteria.text_search_fields:
                text_search["fields"] = criteria.text_search_fields

        logger.debug(
            f"Search - Exact: {exact_criteria}, Range: {range_criteria}, Text: {text_search}"
        )

        # Use the new search_ads method
        return db.search_ads(
            exact_criteria=exact_criteria if exact_criteria else None,
            range_criteria=range_criteria if range_criteria else None,
            text_search=text_search,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error searching ads: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.post("/ads/search/text", response_model=list[AdResponse])
async def search_ads_by_text(
    search_request: TextSearchRequest,
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of results to return",
    ),
):
    """Search ads by text in specified fields."""
    try:
        return db.search_ads_by_text(
            search_term=search_request.search_term,
            fields=search_request.fields,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error searching ads by text: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.get("/stats", response_model=StatsResponse)
async def get_database_stats():
    """Get database statistics."""
    try:
        total_ads = db.get_ads_count()

        # Get unique makes and models count (this would require additional database methods)
        # For now, we'll return basic stats
        return StatsResponse(
            total_ads=total_ads,
            unique_makes=0,  # Placeholder - would need additional DB method
            unique_models=0,  # Placeholder - would need additional DB method
            avg_price=None,  # Placeholder - would need additional DB method
        )
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


def get_session(session_id: str) -> PostgreSQLSession:
    user = os.environ["CARGPT_DB_USER"]
    password = os.environ["CARGPT_DB_PASSWORD"]
    host = os.environ["CARGPT_DB_HOST"]
    port = os.environ["CARGPT_DB_PORT"]
    db = os.environ["CARGPT_DB_NAME"]
    return PostgreSQLSession(
        session_id=session_id,
        connection_string=f"postgresql://{user}:{password}@{host}:{port}/{db}",
    )


def save_conversation(session_id: str, user_id: str):
    try:
        # Try to insert a new conversation
        record = {
            "session_id": session_id,
            "user_id": user_id,
        }
        id = db.insert(record, table_name="conversations")
        if id:
            logger.debug(f"Created new conversation with ID: {id}")
        else:
            # Insert failed, update existing conversation's timestamp
            update_data = {"updated_at": datetime.now()}
            existing_conversations = db.get_by_criteria(
                {"session_id": session_id}, 
                table_name="conversations"
            )
            if existing_conversations:
                conversation_id = existing_conversations[0]["id"]
                success = db.update_by_id(
                    conversation_id, 
                    update_data, 
                    table_name="conversations"
                )
                if success:
                    logger.debug(f"Updated conversation {session_id} timestamp")
                else:
                    logger.warning(f"Failed to update conversation {session_id} timestamp")
            else:
                logger.warning(f"Could not find existing conversation {session_id}")
    except Exception as e:
        logger.error(f"Failed to save conversation metadata: {e}")


def get_session_messages(session_id: str):
    try:
        messages = db.get_by_criteria(
            {"session_id": session_id},
            table_name="agent_messages",
        )
        if messages:
            logger.debug(
                f"Fetched {len(messages)} messages for session {session_id}"
            )
        return messages if messages else []
    except Exception:
        logger.error(f"Failed to fetch messages for session {session_id}")
        return []


@app.get("/conversations/{user_id}", response_model=list[Conversation])
async def get_user_conversations(user_id: str):
    """Get all conversations for a specific user."""
    try:
        sessions = db.get_by_criteria(
            {"user_id": user_id},
            table_name=CONVERSATIONS_TABLE_NAME,
            order_by="updated_at DESC",
        )
        if not len(sessions):
            return []

        conversations = []
        for session in sessions:
            session_messages = get_session_messages(session["session_id"])
            chat_messages = [
                ChatMessage(
                    role=msg["message_data"]["role"],
                    content=msg["message_data"]["content"]
                    if msg["message_data"]["role"] == "user"
                    else msg["message_data"]["content"][0]["text"],
                )
                for msg in session_messages
            ]

            logger.debug(
                f"Session {session['session_id']} has {len(chat_messages)} messages"
            )

            conversations.append(
                Conversation(
                    conversation_id=session["session_id"],
                    messages=chat_messages,
                )
            )

        logger.debug(
            f"Total conversations fetched for user {user_id}: {len(conversations)}"
        )

        return conversations

    except Exception as e:
        logger.error(f"Error fetching conversations for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


@app.post("/chat")
async def chat(request: ChatRequest, agent: Agent = Depends(get_agent)):
    session_id = request.session_id
    user_id = request.user_id

    save_conversation(session_id, user_id)

    try:
        session = get_session(session_id)

        logger.debug(f"Session ID: {session_id}")
        logger.debug(f"User message: {request.message}")

        async def generate_response():
            result = Runner.run_streamed(
                agent, request.message, session=session
            )
            current_text = ""
            async for event in result.stream_events():
                if event.type == "raw_response_event" and isinstance(
                    event.data, ResponseTextDeltaEvent
                ):
                    delta = event.data.delta
                    current_text += delta
                    # Escape newlines for SSE format, but preserve them in the data
                    escaped_delta = delta.replace("\n", "\\n").replace(
                        "\r", "\\r"
                    )
                    yield f"data: {escaped_delta}\n\n"

        return StreamingResponse(
            generate_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error"
        ) from e


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ["BACKEND_PORT"]),
        reload=True,
        log_level="info",
    )
