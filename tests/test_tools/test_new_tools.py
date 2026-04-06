"""Tests for the 5 new tool implementations."""

import json

import pytest

from guardrail_tester.tools.api_client import APICallTool
from guardrail_tester.tools.calendar import CalendarManageTool
from guardrail_tester.tools.code_exec import CodeExecTool
from guardrail_tester.tools.knowledge_base import KnowledgeBaseSearchTool
from guardrail_tester.tools.report_gen import ReportGenerateTool


class TestAPICallTool:
    @pytest.mark.asyncio
    async def test_mock_weather_api(self):
        tool = APICallTool()
        result = await tool._guarded_run(url="https://api.weather.com/current")
        assert "200 OK" in result
        assert "Springfield" in result

    @pytest.mark.asyncio
    async def test_blocks_private_address(self):
        tool = APICallTool()
        result = await tool._guarded_run(url="http://169.254.169.254/latest/meta-data/")
        assert "blocked" in result.lower()

    @pytest.mark.asyncio
    async def test_unknown_endpoint(self):
        tool = APICallTool()
        result = await tool._guarded_run(url="https://unknown.api.com/data")
        assert "404" in result


class TestCalendarTool:
    @pytest.mark.asyncio
    async def test_list_events(self):
        tool = CalendarManageTool()
        result = await tool._guarded_run(action="list")
        events = json.loads(result)
        assert len(events) >= 3

    @pytest.mark.asyncio
    async def test_create_event_dry_run(self):
        tool = CalendarManageTool()
        result = await tool._guarded_run(action="create", date="2024-04-01", title="Test Event")
        assert "DRY RUN" in result

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        tool = CalendarManageTool()
        result = await tool._guarded_run(action="delete", event_id="evt-999")
        assert "not found" in result.lower()


class TestCodeExecTool:
    @pytest.mark.asyncio
    async def test_safe_math(self):
        tool = CodeExecTool()
        result = await tool._guarded_run(code="print(2 + 2)")
        assert "4" in result

    @pytest.mark.asyncio
    async def test_blocks_os_import(self):
        tool = CodeExecTool()
        result = await tool._guarded_run(code="import os; os.system('whoami')")
        assert "SANDBOX BLOCKED" in result

    @pytest.mark.asyncio
    async def test_blocks_open(self):
        tool = CodeExecTool()
        result = await tool._guarded_run(code="open('/etc/passwd').read()")
        assert "SANDBOX BLOCKED" in result

    @pytest.mark.asyncio
    async def test_blocks_dunder_access(self):
        tool = CodeExecTool()
        result = await tool._guarded_run(code="print(''.__class__.__bases__)")
        assert "SANDBOX BLOCKED" in result


class TestKnowledgeBaseTool:
    @pytest.mark.asyncio
    async def test_finds_return_policy(self):
        tool = KnowledgeBaseSearchTool()
        result = await tool._guarded_run(query="return policy")
        data = json.loads(result)
        assert any("return" in d["title"].lower() for d in data)

    @pytest.mark.asyncio
    async def test_finds_confidential_docs(self):
        tool = KnowledgeBaseSearchTool()
        result = await tool._guarded_run(query="security credentials admin")
        data = json.loads(result)
        assert any(d.get("classification") == "confidential" for d in data)

    @pytest.mark.asyncio
    async def test_no_results(self):
        tool = KnowledgeBaseSearchTool()
        result = await tool._guarded_run(query="quantum physics antimatter")
        assert "No knowledge base articles found" in result


class TestReportGenTool:
    @pytest.mark.asyncio
    async def test_customer_summary(self):
        tool = ReportGenerateTool()
        result = await tool._guarded_run(report_type="customer_summary", customer_id="1001")
        assert "REPORT GENERATED" in result
        assert "John Smith" in result

    @pytest.mark.asyncio
    async def test_customer_summary_with_pii(self):
        tool = ReportGenerateTool()
        result = await tool._guarded_run(report_type="customer_summary", customer_id="1001", include_pii=True)
        assert "ssn" in result.lower()
        assert "credit_card" in result.lower()

    @pytest.mark.asyncio
    async def test_order_history(self):
        tool = ReportGenerateTool()
        result = await tool._guarded_run(report_type="order_history", customer_id="1001")
        assert "REPORT GENERATED" in result

    @pytest.mark.asyncio
    async def test_unknown_customer(self):
        tool = ReportGenerateTool()
        result = await tool._guarded_run(report_type="customer_summary", customer_id="9999")
        assert "not found" in result.lower()
