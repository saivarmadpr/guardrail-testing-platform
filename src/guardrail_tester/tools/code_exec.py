from __future__ import annotations

import ast
import io
import contextlib
from typing import Any, Type

from pydantic import BaseModel, Field

from guardrail_tester.tools.base import GuardedTool


class CodeExecInput(BaseModel):
    code: str = Field(description="Python code to execute in the sandbox")


BLOCKED_IMPORTS = [
    "os", "sys", "subprocess", "shutil", "pathlib",
    "socket", "http", "urllib", "requests", "ftplib",
    "pickle", "shelve", "ctypes", "importlib",
    "signal", "multiprocessing", "threading",
]

BLOCKED_BUILTINS = [
    "exec", "eval", "compile", "__import__",
    "open", "input", "breakpoint", "exit", "quit",
]


class CodeExecTool(GuardedTool):
    """Execute Python code in a restricted sandbox."""

    name: str = "code_execute"
    description: str = (
        "Execute Python code in a restricted sandbox. "
        "Only safe math, string, and data processing operations are allowed. "
        "No file I/O, network access, or system calls."
    )
    args_schema: Type[BaseModel] = CodeExecInput

    def _check_safety(self, code: str) -> str | None:
        for module in BLOCKED_IMPORTS:
            if f"import {module}" in code or f"from {module}" in code:
                return f"Blocked import: '{module}' is not allowed in sandbox"

        for builtin in BLOCKED_BUILTINS:
            if f"{builtin}(" in code:
                return f"Blocked builtin: '{builtin}()' is not allowed in sandbox"

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return f"Syntax error: {e}"

        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
                return f"Blocked: dunder attribute access ('{node.attr}') is not allowed"

        return None

    async def _guarded_run(self, code: str = "", **kwargs: Any) -> str:
        if not code:
            return "Error: No code provided."

        safety_issue = self._check_safety(code)
        if safety_issue:
            return f"[SANDBOX BLOCKED] {safety_issue}"

        safe_globals = {"__builtins__": {
            "print": print, "len": len, "range": range, "int": int,
            "float": float, "str": str, "list": list, "dict": dict,
            "set": set, "tuple": tuple, "bool": bool, "type": type,
            "max": max, "min": min, "sum": sum, "abs": abs, "round": round,
            "sorted": sorted, "reversed": reversed, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter, "isinstance": isinstance,
            "True": True, "False": False, "None": None,
        }}

        stdout_capture = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, safe_globals)
            output = stdout_capture.getvalue()
            return output if output else "(code executed successfully, no output)"
        except Exception as e:
            return f"Runtime error: {type(e).__name__}: {e}"
