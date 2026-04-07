"""LangChain AgentMiddleware that calls the Votal Shield API at each checkpoint.

Checkpoint coverage:
  - awrap_tool_call  → /tool/check (pre), execute, /tool/output (post), /agent/check (budget+loop)
  - abefore_agent    → /classify (input guardrails)
  - aafter_model     → /classify_output (output guardrails) + chain-of-thought + context window

Checkpoints 1 and 4 (input/output) are ALSO handled by the LiteLLM proxy at the
LLM call level. Running them here too gives defense-in-depth: the proxy guards every
LLM call; the middleware guards the user-facing boundaries.
"""

from __future__ import annotations

import hashlib
from typing import Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from guardrail_tester.shield.client import VotalShield
from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


class VotalShieldMiddleware(AgentMiddleware):
    """Wraps agent execution with Votal Shield guardrails at all 5 checkpoints."""

    def __init__(
        self,
        shield: VotalShield,
        system_prompt: str = "",
        max_context_tokens: int = 128_000,
    ) -> None:
        self._shield = shield
        self._step_count = 0
        self._total_tokens = 0
        self._system_prompt_hash = (
            hashlib.sha256(system_prompt.encode()).hexdigest()[:16]
            if system_prompt else ""
        )
        self._max_context_tokens = max_context_tokens

    # ------------------------------------------------------------------
    # Checkpoint 1: Guard user input before it reaches the agent
    # ------------------------------------------------------------------

    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, HumanMessage):
            return None

        result = await self._shield.guard_input(last_msg.content)

        if result.action == "block":
            reasons = [gr.get("message", "") for gr in result.guardrail_results]
            return {
                "messages": [
                    AIMessage(content=f"[BLOCKED] {'; '.join(reasons) or 'Request blocked by safety policy.'}")
                ]
            }

        return None

    # ------------------------------------------------------------------
    # Checkpoints 2, 3, 5: Guard tool calls, sanitize output, track budget
    # ------------------------------------------------------------------

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Any]],
    ) -> ToolMessage | Any:
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")

        # --- Checkpoint 2: Pre-check tool call ---
        pre_result = await self._shield.guard_tool(tool_name, tool_args)

        if not pre_result.allowed:
            if pre_result.action == "pending_confirmation":
                details = pre_result.guardrail_results[-1].get("details", {}) if pre_result.guardrail_results else {}
                token = details.get("confirmation_token", "")
                return ToolMessage(
                    content=f"[REQUIRES CONFIRMATION] This action needs human approval. Token: {token}",
                    tool_call_id=tool_call_id,
                )
            reasons = [gr.get("message", "") for gr in pre_result.guardrail_results]
            return ToolMessage(
                content=f"[TOOL BLOCKED] {'; '.join(reasons) or 'Tool call denied by safety policy.'}",
                tool_call_id=tool_call_id,
            )

        # --- Execute the tool ---
        result = await handler(request)

        raw_output = result.content if isinstance(result, ToolMessage) else str(result)

        # --- Checkpoint 3: Sanitize tool output ---
        sanitize_result = await self._shield.sanitize_tool_output(tool_name, raw_output)

        if sanitize_result.sanitized_output and sanitize_result.sanitized_output != raw_output:
            if isinstance(result, ToolMessage):
                result = ToolMessage(
                    content=sanitize_result.sanitized_output,
                    tool_call_id=result.tool_call_id,
                    name=result.name,
                )

        # --- Checkpoint 5: Track budget and loop detection ---
        self._step_count += 1
        estimated_tokens = len(raw_output) // 4
        self._total_tokens += estimated_tokens
        agent_result = await self._shield.check_agent(
            tokens_used=estimated_tokens,
            tool_name=tool_name,
        )

        if not agent_result.allowed:
            action = agent_result.action
            if action == "block":
                reasons = [gr.get("message", "") for gr in agent_result.guardrail_results]
                return ToolMessage(
                    content=f"[AGENT LIMIT] {'; '.join(reasons) or 'Budget or loop limit reached.'}",
                    tool_call_id=tool_call_id,
                )

        logger.log_tool_call(
            tool_name=tool_name,
            tool_args=tool_args,
            phase="post",
            result=raw_output[:500],
        )

        return result

    # ------------------------------------------------------------------
    # Checkpoint 4: Guard LLM response — output check, chain-of-thought, context window
    # ------------------------------------------------------------------

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        # Track cumulative token usage from response metadata
        usage = last_msg.response_metadata.get("token_usage", {}) if last_msg.response_metadata else {}
        msg_tokens = usage.get("total_tokens", 0)
        if msg_tokens:
            self._total_tokens += msg_tokens

        # --- Chain-of-thought monitoring ---
        # When the LLM responds with tool calls AND reasoning content, send
        # the reasoning to /agent/check for unsafe-pattern detection.
        if last_msg.tool_calls and last_msg.content:
            cot_result = await self._shield.check_agent(
                chain_of_thought=last_msg.content,
            )
            if not cot_result.allowed and cot_result.action == "block":
                reasons = [gr.get("message", "") for gr in cot_result.guardrail_results]
                return {
                    "messages": [
                        AIMessage(content=f"[BLOCKED] Unsafe reasoning detected: {'; '.join(reasons)}")
                    ]
                }

        # --- Context window guardrails ---
        # Send cumulative token count to detect context stuffing / overflow.
        if self._total_tokens > 0:
            ctx_result = await self._shield.check_agent(
                total_tokens=self._total_tokens,
                max_context_tokens=self._max_context_tokens,
                system_prompt_hash=self._system_prompt_hash,
            )
            if not ctx_result.allowed and ctx_result.action == "block":
                reasons = [gr.get("message", "") for gr in ctx_result.guardrail_results]
                return {
                    "messages": [
                        AIMessage(content=f"[BLOCKED] Context limit: {'; '.join(reasons)}")
                    ]
                }

        # If the LLM is still calling tools, don't run output guardrails yet
        if last_msg.tool_calls:
            return None

        content = last_msg.content or ""
        if not content:
            return None

        # --- Output classification ---
        result = await self._shield.guard_output(content)

        if result.action == "block":
            reasons = [gr.get("message", "") for gr in result.guardrail_results]
            return {
                "messages": [
                    AIMessage(content=f"[OUTPUT BLOCKED] {'; '.join(reasons) or 'Response blocked by safety policy.'}")
                ]
            }

        return None
