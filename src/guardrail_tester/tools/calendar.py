from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel, Field

from guardrail_tester.tools.base import GuardedTool


class CalendarInput(BaseModel):
    action: str = Field(description="Action: 'list', 'create', 'delete'")
    date: str = Field(default="", description="Date in YYYY-MM-DD format")
    title: str = Field(default="", description="Event title (for create)")
    event_id: str = Field(default="", description="Event ID (for delete)")


MOCK_CALENDAR = [
    {"id": "evt-001", "date": "2024-03-15", "title": "Team Standup", "time": "09:00"},
    {"id": "evt-002", "date": "2024-03-15", "title": "Customer Review - Acme Corp", "time": "14:00"},
    {"id": "evt-003", "date": "2024-03-16", "title": "Sprint Planning", "time": "10:00"},
    {"id": "evt-004", "date": "2024-03-18", "title": "All Hands Meeting", "time": "11:00"},
    {"id": "evt-005", "date": "2024-03-20", "title": "Product Demo", "time": "15:00"},
]


class CalendarManageTool(GuardedTool):
    """Manage calendar events (list, create, delete)."""

    name: str = "calendar_manage"
    description: str = (
        "Manage calendar events. Actions: 'list' (show upcoming events), "
        "'create' (add an event with date and title), 'delete' (remove event by ID)."
    )
    args_schema: Type[BaseModel] = CalendarInput

    async def _guarded_run(
        self, action: str = "list", date: str = "", title: str = "", event_id: str = "", **kwargs: Any
    ) -> str:
        action = action.lower().strip()

        if action == "list":
            events = MOCK_CALENDAR
            if date:
                events = [e for e in events if e["date"] == date]
            if not events:
                return f"No events found{' for ' + date if date else ''}."
            return json.dumps(events, indent=2)

        elif action == "create":
            if not date or not title:
                return "Error: Both 'date' and 'title' are required to create an event."
            new_event = {"id": f"evt-{len(MOCK_CALENDAR) + 1:03d}", "date": date, "title": title, "time": "12:00"}
            return f"[DRY RUN] Event created: {json.dumps(new_event)}"

        elif action == "delete":
            if not event_id:
                return "Error: 'event_id' is required to delete an event."
            found = any(e["id"] == event_id for e in MOCK_CALENDAR)
            if not found:
                return f"Error: Event '{event_id}' not found."
            return f"[DRY RUN] Event '{event_id}' would be deleted."

        return f"Error: Unknown action '{action}'. Use 'list', 'create', or 'delete'."
