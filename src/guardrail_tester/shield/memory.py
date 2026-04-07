"""Guarded LangChain memory that checks reads/writes with Votal Shield.

On write: PII in conversation history is scrubbed before persisting.
On read: Memory content is checked for prompt injection before loading into agent context.

Uses POST /v1/shield/memory/check for both operations.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_classic.memory import ConversationBufferMemory

from guardrail_tester.shield.client import VotalShield
from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


class VotalGuardedMemory(ConversationBufferMemory):
    """ConversationBufferMemory wrapper that validates reads/writes through Votal Shield."""

    shield: Any = None
    agent_key: str = ""
    session_id: str = ""

    class Config:
        arbitrary_types_allowed = True

    def _run_async(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)

    def save_context(self, inputs: dict[str, Any], outputs: dict[str, str]) -> None:
        """Check for PII before writing to memory. Uses scrubbed values if available."""
        if self.shield is not None:
            scrubbed_outputs = dict(outputs)
            for key, value in {**inputs, **outputs}.items():
                result = self._run_async(
                    self.shield.check_memory(
                        operation="write",
                        key=f"conversation:{key}",
                        value=str(value),
                    )
                )
                if not result.allowed and result.sanitized_output and key in scrubbed_outputs:
                    scrubbed_outputs[key] = result.sanitized_output
                    logger.log_guardrail_check(
                        guardrail_name="shield_memory_write",
                        layer="memory",
                        passed=False,
                        action="rewrite",
                        message=f"PII scrubbed from memory key=conversation:{key}",
                    )
            outputs = scrubbed_outputs

        super().save_context(inputs, outputs)

    def load_memory_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Check loaded memory for injection attacks before returning to agent."""
        variables = super().load_memory_variables(inputs)

        if self.shield is None:
            return variables

        for key, value in variables.items():
            result = self._run_async(
                self.shield.check_memory(
                    operation="read",
                    key=f"conversation:{key}",
                    value=str(value),
                )
            )
            if not result.allowed:
                variables[key] = "[MEMORY BLOCKED - potential injection detected]"
                logger.log_guardrail_check(
                    guardrail_name="shield_memory_read",
                    layer="memory",
                    passed=False,
                    action="block",
                    message=f"Injection detected in memory key=conversation:{key}",
                )

        return variables
