"""Agent runtime — a clean LangChain 1.x agent with tools. No guardrails built in."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from guardrail_tester.agent.prompts import SYSTEM_PROMPT
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
        model=config.get("agent", {}).get("model", "qwen2.5:3b"),
        temperature=config.get("agent", {}).get("temperature", 0.1),
    )


def build_agent(
    config: dict[str, Any] | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
):
    config = config or load_config()
    llm = create_llm(config, base_url=base_url)
    tools = create_tools(config)

    return create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt or SYSTEM_PROMPT,
        debug=config.get("agent", {}).get("verbose", False),
    )


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
    base_url: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    config = config or load_config()
    logger.log_input(user_input)

    agent = build_agent(config=config, base_url=base_url, system_prompt=system_prompt)

    try:
        result = await agent.ainvoke(
            {"messages": [HumanMessage(content=user_input)]}
        )
    except Exception as e:
        error_msg = str(e)
        logger.log_error(error_msg)

        blocked = False
        if "400" in error_msg or "blocked" in error_msg.lower():
            blocked = True

        return {
            "input": user_input,
            "output": f"[ERROR] {error_msg}",
            "blocked": blocked,
            "error": error_msg,
            "intermediate_steps": [],
        }

    messages = result.get("messages", [])
    agent_output = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content and not msg.tool_calls:
            agent_output = msg.content
            break

    logger.log_output(agent_output)
    tool_steps = _extract_tool_calls(messages)

    return {
        "input": user_input,
        "output": agent_output,
        "blocked": False,
        "intermediate_steps": tool_steps,
    }
