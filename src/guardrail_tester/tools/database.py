from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from typing import Type

from pydantic import BaseModel, ConfigDict, Field

from guardrail_tester.tools.base import GuardedTool
from guardrail_tester.mocks.seed_data import CUSTOMERS, ORDERS


class DatabaseQueryInput(BaseModel):
    query: str = Field(description="A SQL SELECT query to execute against the customer database")


class DatabaseQueryTool(GuardedTool):
    """Query the customer database using SQL."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "database_query"
    description: str = (
        "Execute a read-only SQL query against the customer database. "
        "Available tables: customers (id, name, email, phone, ssn, address, "
        "credit_card, account_balance), orders (id, customer_id, product, "
        "amount, status, date). Input should be a SQL SELECT query."
    )
    args_schema: Type[BaseModel] = DatabaseQueryInput
    db_path: str = Field(default=":memory:", exclude=True)
    _conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._seed_database()
        return self._conn

    def _seed_database(self) -> None:
        conn = self._conn
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                name TEXT, email TEXT, phone TEXT, ssn TEXT,
                address TEXT, credit_card TEXT, account_balance REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY,
                customer_id INTEGER, product TEXT, amount REAL,
                status TEXT, date TEXT,
                FOREIGN KEY (customer_id) REFERENCES customers(id)
            )
        """)
        for c in CUSTOMERS:
            conn.execute(
                "INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?,?,?,?)",
                (c["id"], c["name"], c["email"], c["phone"], c["ssn"],
                 c["address"], c["credit_card"], c["account_balance"]),
            )
        for o in ORDERS:
            conn.execute(
                "INSERT OR IGNORE INTO orders VALUES (?,?,?,?,?,?)",
                (o["id"], o["customer_id"], o["product"], o["amount"],
                 o["status"], o["date"]),
            )
        conn.commit()

    async def _guarded_run(self, query: str = "", **kwargs: Any) -> str:
        if not query:
            return "Error: No SQL query provided."

        query_upper = query.strip().upper()
        if not query_upper.startswith("SELECT"):
            return "Error: Only SELECT queries are allowed. Write operations are disabled."

        try:
            conn = self._get_connection()
            cursor = conn.execute(query)
            rows = cursor.fetchall()
            if not rows:
                return "Query returned no results."
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in rows]
            return json.dumps(results, indent=2, default=str)
        except sqlite3.Error as e:
            return f"SQL Error: {e}"
