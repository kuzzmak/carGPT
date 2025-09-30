import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

from mcp_servers.paths import MCP_SERVERS_DIR

from shared.logging_config import get_logger, setup_logging

# Setup MCP-specific logging with base configuration extension
logging_config_path = MCP_SERVERS_DIR / "logging_config.yaml"
setup_logging(logging_config_path)
logger = get_logger("mcp_servers.perplexity")

# Get the server port from environment or use default
server_port = int(os.environ.get("PERPLEXITY_MCP_SERVER_PORT", "8002"))

mcp = FastMCP("Perplexity Search Server", port=server_port)

# Perplexity API configuration
PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"

if not PERPLEXITY_API_KEY:
    logger.error("PERPLEXITY_API_KEY environment variable is required")
    sys.exit(1)


@mcp.tool()
def perplexity_ask(messages: list[dict[str, str]]) -> dict[str, Any]:
    """
    Engage in a conversation with the Perplexity Sonar API for live web searches.

    This tool provides real-time web search capabilities using Perplexity's Sonar API.
    It can search the web, get current information, and provide sourced answers.

    Args:
        messages: An array of conversation messages. Each message must include:
            - role (str): The role of the message (e.g., 'system', 'user', 'assistant')
            - content (str): The content of the message

    Returns:
        Dict containing the search response with sources and current information

    Examples:
        # 1. Simple web search
        perplexity_ask([{
            "role": "user",
            "content": "What are the latest car market trends in 2024?"
        }])

        # 2. Search with context
        perplexity_ask([
            {"role": "system", "content": "You are a car expert assistant."},
            {"role": "user", "content": "What are the best electric cars under $50,000 in 2024?"}
        ])

        # 3. Follow-up search
        perplexity_ask([
            {"role": "user", "content": "What is the Tesla Model 3 price?"},
            {"role": "assistant", "content": "Previous response about Tesla Model 3..."},
            {"role": "user", "content": "How does it compare to BMW i3?"}
        ])
    """
    if not messages:
        return {"error": "Messages array cannot be empty"}

    # Validate message format
    for i, message in enumerate(messages):
        if not isinstance(message, dict):
            return {"error": f"Message {i} must be a dictionary"}
        if "role" not in message or "content" not in message:
            return {
                "error": f"Message {i} must have 'role' and 'content' fields"
            }
        if message["role"] not in ["system", "user", "assistant"]:
            return {
                "error": f"Message {i} has invalid role: {message['role']}"
            }

    logger.debug(f"perplexity_ask called with {len(messages)} messages")

    try:
        # Prepare the request payload
        payload = {
            "model": "sonar",
            "messages": messages,
            # "max_tokens": 4000,
            # "temperature": 0.2,
            "return_citations": True,
            # "search_domain_filter": [
            #     "perplexity.ai"
            # ],  # Optional: filter search domains
            # "return_images": False,
            # "return_related_questions": True,
            # "search_recency_filter": "year",  # Get recent information
            # "top_p": 0.9,
            # "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
            "Content-Type": "application/json",
        }

        logger.debug("Sending request to Perplexity API")

        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                PERPLEXITY_API_URL, json=payload, headers=headers
            )

            response.raise_for_status()
            result = response.json()

            logger.debug("Received response from Perplexity API")

            # Extract the response content
            if "choices" in result and len(result["choices"]) > 0:
                choice = result["choices"][0]
                content = choice.get("message", {}).get("content", "")

                # Extract citations and related questions if available
                citations = result.get("citations", [])
                # related_questions = result.get("related_questions", [])

                logger.debug("Extracted content and citations from response")
                logger.debug(f"Content: {content}")
                logger.debug(f"Citations: {citations}")

                return {
                    "content": content,
                    "citations": citations,
                    # "related_questions": related_questions,
                    # "usage": result.get("usage", {}),
                    # "model": result.get("model", ""),
                    "success": True,
                }

            return {
                "error": "No response content received from Perplexity API"
            }

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error from Perplexity API: {e.response.status_code} - {e.response.text}"
        )
        return {
            "error": f"Perplexity API error: {e.response.status_code}",
            "details": e.response.text
            if hasattr(e.response, "text")
            else str(e),
        }
    except httpx.TimeoutException:
        err = "Timeout while calling Perplexity API"
        logger.error(err)
        return {"error": err}
    except Exception as e:
        err = f"Unexpected error calling Perplexity API: {e}"
        logger.error(err)
        return {"error": err}


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Perform a simple web search using Perplexity's API.

    This is a simplified interface for quick web searches.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Dict containing search results with sources

    Examples:
        # 1. Search for car information
        web_search("BMW X5 2024 review")

        # 2. Search for market data
        web_search("used car prices Croatia 2024", max_results=3)

        # 3. Search for specific model information
        web_search("Volkswagen Golf GTI specifications")
    """
    if not query.strip():
        return {"error": "Query cannot be empty"}

    logger.debug(
        f"web_search called with query: '{query}', max_results: {max_results}"
    )

    # Create a simple message for the search
    messages = [{"role": "user", "content": f"Search for: {query}"}]

    # Use the main perplexity_ask function
    result = perplexity_ask(messages)

    if "error" in result:
        return result

    # Limit citations if max_results is specified
    if "citations" in result and len(result["citations"]) > max_results:
        result["citations"] = result["citations"][:max_results]

    return result


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
