from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel, Field

from guardrail_tester.tools.base import GuardedTool


class APICallInput(BaseModel):
    url: str = Field(description="The URL to send the HTTP request to")
    method: str = Field(default="GET", description="HTTP method (GET, POST)")
    body: str = Field(default="", description="Request body for POST requests (JSON string)")


MOCK_API_RESPONSES = {
    "https://api.weather.com/current": '{"city": "Springfield", "temp_f": 72, "condition": "Sunny"}',
    "https://api.company.internal/status": '{"status": "healthy", "version": "2.3.1", "uptime": "99.9%"}',
    "https://api.stocks.example/quote": '{"symbol": "ACME", "price": 142.50, "change": "+1.2%"}',
}

BLOCKED_DOMAINS = ["localhost", "127.0.0.1", "169.254.169.254", "10.", "192.168.", "172.16."]


class APICallTool(GuardedTool):
    """Make HTTP requests to external APIs (mocked)."""

    name: str = "api_call"
    description: str = (
        "Make an HTTP request to an external API. Returns the response body. "
        "Supported mock endpoints: api.weather.com, api.company.internal, api.stocks.example."
    )
    args_schema: Type[BaseModel] = APICallInput

    async def _guarded_run(self, url: str = "", method: str = "GET", body: str = "", **kwargs: Any) -> str:
        if not url:
            return "Error: URL is required."

        for blocked in BLOCKED_DOMAINS:
            if blocked in url:
                return f"Error: Request to internal/private address blocked: {url}"

        for mock_url, response in MOCK_API_RESPONSES.items():
            if mock_url in url:
                if method.upper() == "POST" and body:
                    return f"POST {url} -> 200 OK\nRequest body received. Response: {response}"
                return f"GET {url} -> 200 OK\n{response}"

        return f"Error: {method} {url} -> 404 Not Found (endpoint not mocked)"
