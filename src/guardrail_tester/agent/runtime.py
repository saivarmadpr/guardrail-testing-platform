"""Agent runtime — sets up and runs the LangChain 1.x agent with guardrail middleware."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from guardrail_tester.agent.prompts import SYSTEM_PROMPT
from guardrail_tester.guardrails.base import (
    GuardrailContext,
    GuardrailLayer,
    GuardrailRegistry,
)
from guardrail_tester.guardrails.engine import GuardrailEngine
from guardrail_tester.logging.structured import get_logger
from guardrail_tester.tools.web_search import WebSearchTool
from guardrail_tester.tools.database import DatabaseQueryTool
from guardrail_tester.tools.email import EmailSendTool
from guardrail_tester.tools.user_data import UserDataLookupTool
from guardrail_tester.tools.file_ops import FileReadTool
from guardrail_tester.tools.api_client import APICallTool
from guardrail_tester.tools.calendar import CalendarManageTool
from guardrail_tester.tools.code_exec import CodeExecTool
from guardrail_tester.tools.knowledge_base import KnowledgeBaseSearchTool
from guardrail_tester.tools.report_gen import ReportGenerateTool

logger = get_logger(__name__)


class GuardrailMiddleware(AgentMiddleware):
    """LangChain middleware that runs guardrails at input, tool, and output layers."""

    def __init__(self, engine: GuardrailEngine) -> None:
        self._engine = engine
        self.tools: list = []

    async def abefore_agent(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, HumanMessage):
            return None

        context = GuardrailContext(
            content=last_msg.content,
            layer=GuardrailLayer.INPUT,
        )
        results = await self._engine.run_layer(GuardrailLayer.INPUT, context)

        if self._engine.has_block(results):
            blocked = next(r for r in results if not r.passed)
            return {
                "messages": [
                    AIMessage(content=f"[BLOCKED] {blocked.message}")
                ]
            }

        rewritten = self._engine.get_rewritten_content(results, last_msg.content)
        if rewritten != last_msg.content:
            new_messages = list(messages[:-1]) + [HumanMessage(content=rewritten)]
            return {"messages": new_messages}

        return None

    async def aafter_model(self, state: Any, runtime: Any) -> dict[str, Any] | None:
        messages = state.get("messages", [])
        if not messages:
            return None

        last_msg = messages[-1]
        if not isinstance(last_msg, AIMessage):
            return None

        if last_msg.tool_calls:
            return None

        context = GuardrailContext(
            content=last_msg.content or "",
            layer=GuardrailLayer.OUTPUT,
        )
        results = await self._engine.run_layer(GuardrailLayer.OUTPUT, context)

        if self._engine.has_block(results):
            blocked = next(r for r in results if not r.passed)
            return {
                "messages": [
                    AIMessage(content=f"[OUTPUT BLOCKED] {blocked.message}")
                ]
            }

        rewritten = self._engine.get_rewritten_content(results, last_msg.content or "")
        if rewritten != (last_msg.content or ""):
            return {
                "messages": [AIMessage(content=rewritten)]
            }

        return None

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Any]],
    ) -> ToolMessage | Any:
        tool_call = request.tool_call
        tool_name = tool_call.get("name", "unknown")
        tool_args = tool_call.get("args", {})

        context = GuardrailContext(
            content=str(tool_args),
            layer=GuardrailLayer.TOOL,
            tool_name=tool_name,
            tool_args=tool_args,
        )
        pre_results = await self._engine.run_layer(GuardrailLayer.TOOL, context)

        if self._engine.has_block(pre_results):
            blocked = next(r for r in pre_results if not r.passed)
            return ToolMessage(
                content=f"[TOOL BLOCKED by {blocked.guardrail_name}] {blocked.message}",
                tool_call_id=tool_call.get("id", ""),
            )

        result = await handler(request)

        logger.log_tool_call(
            tool_name=tool_name,
            tool_args=tool_args,
            phase="post",
            result=result.content if isinstance(result, ToolMessage) else str(result),
        )

        return result


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "agent.yaml"
    config_path = Path(config_path)
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


def create_tools(config: dict[str, Any] | None = None) -> list:
    config = config or {}
    enabled = config.get("tools", {}).get("enabled", [
        "web_search", "database_query", "email_send", "user_data_lookup", "file_read",
        "api_call", "calendar_manage", "code_execute", "knowledge_base_search", "report_generate",
    ])

    all_tools = {
        "web_search": WebSearchTool(),
        "database_query": DatabaseQueryTool(),
        "email_send": EmailSendTool(),
        "user_data_lookup": UserDataLookupTool(),
        "file_read": FileReadTool(),
        "api_call": APICallTool(),
        "calendar_manage": CalendarManageTool(),
        "code_execute": CodeExecTool(),
        "knowledge_base_search": KnowledgeBaseSearchTool(),
        "report_generate": ReportGenerateTool(),
    }

    return [all_tools[name] for name in enabled if name in all_tools]


def create_llm(
    config: dict[str, Any] | None = None, base_url: str | None = None
) -> ChatOpenAI:
    config = config or {}
    llm_config = config.get("llm", {})

    return ChatOpenAI(
        base_url=base_url or llm_config.get("base_url", "http://localhost:11434/v1"),
        api_key=llm_config.get("api_key", "ollama"),
        model=config.get("agent", {}).get("model", "qwen2.5:7b"),
        temperature=config.get("agent", {}).get("temperature", 0.1),
    )


def build_agent(
    config: dict[str, Any] | None = None,
    guardrail_registry: GuardrailRegistry | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
):
    config = config or load_config()
    llm = create_llm(config, base_url=base_url)
    tools = create_tools(config)

    middleware = []
    if guardrail_registry:
        engine = GuardrailEngine(guardrail_registry)
        middleware.append(GuardrailMiddleware(engine))

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt or SYSTEM_PROMPT,
        middleware=middleware,
        debug=config.get("agent", {}).get("verbose", False),
    )

    return agent


def _extract_tool_calls(messages: list) -> list[dict[str, Any]]:
    steps = []
    tool_calls_pending: dict[str, dict[str, Any]] = {}

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls_pending[tc["id"]] = {
                    "tool": tc["name"],
                    "input": tc["args"],
                    "output": "",
                }
        elif isinstance(msg, ToolMessage):
            tc_id = msg.tool_call_id
            if tc_id in tool_calls_pending:
                tool_calls_pending[tc_id]["output"] = str(msg.content)[:500]
                steps.append(tool_calls_pending.pop(tc_id))

    for pending in tool_calls_pending.values():
        steps.append(pending)

    return steps


async def run_agent(
    user_input: str,
    config: dict[str, Any] | None = None,
    guardrail_registry: GuardrailRegistry | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = config or load_config()

    if guardrail_registry is None:
        guardrail_registry = GuardrailRegistry()

    engine = GuardrailEngine(guardrail_registry)
    logger.log_input(user_input)

    input_context = GuardrailContext(
        content=user_input, layer=GuardrailLayer.INPUT
    )
    input_results = await engine.run_layer(GuardrailLayer.INPUT, input_context)

    if engine.has_block(input_results):
        blocked = next(r for r in input_results if not r.passed)
        output = f"[BLOCKED] {blocked.message}"
        logger.log_output(output, {"blocked_by": blocked.guardrail_name})
        return {
            "input": user_input,
            "output": output,
            "blocked": True,
            "blocked_by": blocked.guardrail_name,
            "guardrail_results": [
                {"name": r.guardrail_name, "passed": r.passed, "action": r.action.value, "message": r.message}
                for r in input_results
            ],
            "intermediate_steps": [],
        }

    effective_input = engine.get_rewritten_content(input_results, user_input)

    agent = build_agent(
        config=config,
        guardrail_registry=guardrail_registry,
        base_url=base_url,
        system_prompt=system_prompt,
    )

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=effective_input)]}
        )
    except Exception as e:
        error_msg = str(e)
        logger.log_error(error_msg)
        return {
            "input": user_input,
            "output": f"[ERROR] {error_msg}",
            "blocked": "blocked by guardrail" in error_msg.lower(),
            "blocked_by": "tool_guardrail" if "blocked by guardrail" in error_msg.lower() else None,
            "error": error_msg,
            "guardrail_results": [
                {"name": r.guardrail_name, "passed": r.passed, "action": r.action.value, "message": r.message}
                for r in input_results
            ],
            "intermediate_steps": [],
        }

    messages = result.get("messages", [])
    agent_output = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            agent_output = msg.content
            break

    output_context = GuardrailContext(
        content=agent_output, layer=GuardrailLayer.OUTPUT
    )
    output_results = await engine.run_layer(GuardrailLayer.OUTPUT, output_context)

    blocked = False
    blocked_by = None
    if engine.has_block(output_results):
        blocked_result = next(r for r in output_results if not r.passed)
        agent_output = f"[OUTPUT BLOCKED] {blocked_result.message}"
        blocked = True
        blocked_by = blocked_result.guardrail_name
    else:
        agent_output = engine.get_rewritten_content(output_results, agent_output)

    logger.log_output(agent_output)

    all_guardrail_results = input_results + output_results
    tool_steps = _extract_tool_calls(messages)

    return {
        "input": user_input,
        "output": agent_output,
        "blocked": blocked,
        "blocked_by": blocked_by,
        "guardrail_results": [
            {"name": r.guardrail_name, "passed": r.passed, "action": r.action.value, "message": r.message}
            for r in all_guardrail_results
        ],
        "intermediate_steps": tool_steps,
    }
