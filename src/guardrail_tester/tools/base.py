from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool


class ToolBlockedError(Exception):
    """Raised when a tool-level guardrail blocks execution."""

    def __init__(self, tool_name: str, guardrail_name: str, message: str):
        self.tool_name = tool_name
        self.guardrail_name = guardrail_name
        super().__init__(f"Tool '{tool_name}' blocked by guardrail '{guardrail_name}': {message}")


class GuardedTool(BaseTool):
    """Base tool class. Tool-level guardrails are handled by the agent middleware.

    Subclasses implement `_guarded_run` with typed kwargs.
    The `_run` method delegates to `_guarded_run` parsing the string input.
    """

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Use async invoke via `_arun`")

    async def _arun(self, **kwargs: Any) -> str:
        return await self._guarded_run(**kwargs)

    async def _guarded_run(self, **kwargs: Any) -> str:
        raise NotImplementedError("Subclasses must implement _guarded_run")
