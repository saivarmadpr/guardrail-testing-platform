from __future__ import annotations

import json
from typing import Any, Type

from pydantic import BaseModel, Field

from guardrail_tester.tools.base import GuardedTool
from guardrail_tester.mocks.seed_data import CUSTOMERS


class UserDataLookupInput(BaseModel):
    query: str = Field(description="Customer name, email address, or numeric customer ID to search for")


class UserDataLookupTool(GuardedTool):
    """Look up customer/user information by name, email, or ID."""

    name: str = "user_data_lookup"
    description: str = (
        "Look up customer records by name, email, or customer ID. "
        "Returns customer profile information."
    )
    args_schema: Type[BaseModel] = UserDataLookupInput

    async def _guarded_run(self, query: str = "", **kwargs: Any) -> str:
        if not query:
            return "Error: No search query provided. Provide a name, email, or customer ID."

        query_lower = query.strip().lower()
        matches = []

        for customer in CUSTOMERS:
            if (
                query_lower in customer["name"].lower()
                or query_lower == customer["email"].lower()
                or query_lower == str(customer["id"])
            ):
                matches.append({
                    "id": customer["id"],
                    "name": customer["name"],
                    "email": customer["email"],
                    "phone": customer["phone"],
                    "ssn": customer["ssn"],
                    "address": customer["address"],
                    "credit_card": customer["credit_card"],
                    "account_balance": customer["account_balance"],
                })

        if not matches:
            return f"No customer records found for: {query}"

        return json.dumps(matches, indent=2)
