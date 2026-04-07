"""Async Votal Shield client for tool-level and agent-level guardrails.

Covers the checkpoints that the LiteLLM proxy does NOT handle:
  - /v1/shield/tool/check    — pre-execution tool validation (RBAC, rate limits, schema)
  - /v1/shield/tool/output   — post-execution output sanitization (PII scrubbing)
  - /v1/shield/agent/check   — budget enforcement, loop detection, delegation control
  - /v1/shield/memory/check  — memory read/write safety

The LiteLLM proxy already handles:
  - /classify                — input guardrails (pre_call)
  - /classify_output         — output guardrails (post_call)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


@dataclass
class ShieldResult:
    allowed: bool
    action: str = "pass"
    guardrail_results: list[dict[str, Any]] = field(default_factory=list)
    sanitized_output: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class VotalShield:
    """Async client for the Votal Shield API.

    Provides methods for each checkpoint in the agentic guardrail flow:
      1. guard_input()           — classify user input
      2. guard_tool()            — pre-check tool call (RBAC, rate limits, validation)
      3. sanitize_tool_output()  — scrub PII/secrets from tool results
      4. guard_output()          — classify LLM response
      5. check_agent()           — budget, loop detection, delegation
      6. check_memory()          — memory read/write safety
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        agent_key: str = "",
        session_id: str = "",
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.agent_key = agent_key
        self.session_id = session_id

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
        }
        if agent_key:
            headers["X-Agent-Key"] = agent_key

        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            r = await self._client.post(f"{self.base_url}{path}", json=payload)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            logger.log_error(f"Shield API error: {e.response.status_code} {e.response.text}")
            return {"allowed": False, "action": "block", "error": str(e)}
        except httpx.ConnectError:
            logger.log_error(f"Shield API unreachable at {self.base_url}")
            return {"allowed": True, "action": "pass", "error": "shield_unreachable"}

    def _parse(self, raw: dict[str, Any]) -> ShieldResult:
        return ShieldResult(
            allowed=raw.get("allowed", True),
            action=raw.get("action", "pass"),
            guardrail_results=raw.get("guardrail_results", []),
            sanitized_output=raw.get("sanitized_output"),
            raw=raw,
        )

    # ------------------------------------------------------------------
    # Checkpoint 1: Input classification
    # ------------------------------------------------------------------

    async def guard_input(self, message: str) -> ShieldResult:
        raw = await self._post("/classify", {"message": message})
        result = self._parse(raw)
        logger.log_guardrail_check(
            guardrail_name="shield_input",
            layer="input",
            passed=result.action != "block",
            action=result.action,
            message=str(result.guardrail_results),
        )
        return result

    # ------------------------------------------------------------------
    # Checkpoint 2: Tool pre-check
    # ------------------------------------------------------------------

    async def guard_tool(
        self, tool_name: str, tool_args: dict[str, Any] | None = None
    ) -> ShieldResult:
        raw = await self._post("/v1/shield/tool/check", {
            "agent_key": self.agent_key,
            "session_id": self.session_id,
            "tool_name": tool_name,
            "tool_args": tool_args or {},
        })
        result = self._parse(raw)
        logger.log_guardrail_check(
            guardrail_name="shield_tool_check",
            layer="tool",
            passed=result.allowed,
            action=result.action,
            message=f"tool={tool_name} allowed={result.allowed}",
        )
        return result

    async def confirm_tool(
        self, session_id: str, confirmation_token: str, tool_name: str
    ) -> ShieldResult:
        """Submit human confirmation for a sensitive tool action."""
        raw = await self._post("/v1/shield/tool/confirm", {
            "session_id": session_id or self.session_id,
            "confirmation_token": confirmation_token,
            "tool_name": tool_name,
        })
        result = self._parse(raw)
        logger.log_guardrail_check(
            guardrail_name="shield_tool_confirm",
            layer="tool",
            passed=result.allowed,
            action=result.action,
            message=f"tool={tool_name} confirmed={result.allowed}",
        )
        return result

    # ------------------------------------------------------------------
    # Checkpoint 3: Tool output sanitization
    # ------------------------------------------------------------------

    async def sanitize_tool_output(
        self, tool_name: str, output: str
    ) -> ShieldResult:
        raw = await self._post("/v1/shield/tool/output", {
            "tool_name": tool_name,
            "output": output,
            "agent_key": self.agent_key,
        })
        result = self._parse(raw)
        if result.sanitized_output is None:
            result.sanitized_output = output
        logger.log_guardrail_check(
            guardrail_name="shield_tool_output",
            layer="tool",
            passed=result.allowed,
            action=result.action,
            message=f"tool={tool_name} sanitized={result.sanitized_output != output}",
        )
        return result

    # ------------------------------------------------------------------
    # Checkpoint 4: Output classification
    # ------------------------------------------------------------------

    async def guard_output(self, output: str) -> ShieldResult:
        raw = await self._post("/classify_output", {"output": output})
        result = self._parse(raw)
        logger.log_guardrail_check(
            guardrail_name="shield_output",
            layer="output",
            passed=result.action != "block",
            action=result.action,
            message=str(result.guardrail_results),
        )
        return result

    # ------------------------------------------------------------------
    # Checkpoint 5: Agent scope, budget, loops, delegation
    # ------------------------------------------------------------------

    async def check_agent(
        self,
        tokens_used: int = 0,
        cost_usd: float = 0.0,
        tool_name: str = "",
        delegate_to: str = "",
        chain_of_thought: str = "",
        total_tokens: int = 0,
        max_context_tokens: int = 0,
        system_prompt_hash: str = "",
    ) -> ShieldResult:
        payload: dict[str, Any] = {
            "agent_key": self.agent_key,
            "session_id": self.session_id,
        }
        if tokens_used:
            payload["tokens_used"] = tokens_used
        if cost_usd:
            payload["cost_usd"] = cost_usd
        if tool_name:
            payload["tool_name"] = tool_name
        if delegate_to:
            payload["delegate_to"] = delegate_to
        if chain_of_thought:
            payload["chain_of_thought"] = chain_of_thought
        if total_tokens:
            payload["total_tokens"] = total_tokens
        if max_context_tokens:
            payload["max_context_tokens"] = max_context_tokens
        if system_prompt_hash:
            payload["system_prompt_hash"] = system_prompt_hash

        raw = await self._post("/v1/shield/agent/check", payload)
        return self._parse(raw)

    async def get_budget(self) -> dict[str, Any]:
        return await self._post("/v1/shield/agent/budget", {
            "agent_key": self.agent_key,
            "session_id": self.session_id,
        })

    # ------------------------------------------------------------------
    # Checkpoint 6: Memory safety
    # ------------------------------------------------------------------

    async def check_memory(
        self,
        operation: str,
        key: str,
        value: str = "",
        namespace: str = "",
        source_agent: str = "",
    ) -> ShieldResult:
        payload: dict[str, Any] = {
            "agent_key": self.agent_key,
            "operation": operation,
            "memory_key": key,
            "memory_value": value,
            "session_id": self.session_id,
        }
        if namespace:
            payload["memory_namespace"] = namespace
        if source_agent:
            payload["source_agent"] = source_agent

        raw = await self._post("/v1/shield/memory/check", payload)
        result = self._parse(raw)

        if not result.allowed:
            for gr in result.guardrail_results:
                scrubbed = (gr.get("details") or {}).get("scrubbed_value")
                if scrubbed:
                    result.sanitized_output = scrubbed
                    break

        return result
