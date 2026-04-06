from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel, Field

from guardrail_tester.tools.base import GuardedTool
from guardrail_tester.logging.structured import get_logger

logger = get_logger(__name__)


class EmailSendInput(BaseModel):
    to: str = Field(description="Recipient email address")
    subject: str = Field(description="Email subject line")
    body: str = Field(description="Email body text")
    cc: str = Field(default="", description="CC email address (optional)")
    bcc: str = Field(default="", description="BCC email address (optional)")


class EmailSendTool(GuardedTool):
    """Draft and send emails (dry-run mode — no actual emails sent)."""

    name: str = "email_send"
    description: str = (
        "Draft and send an email. Always runs in dry-run mode (emails are logged, "
        "not actually sent)."
    )
    args_schema: Type[BaseModel] = EmailSendInput
    sent_emails: list[dict[str, Any]] = []

    async def _guarded_run(
        self,
        to: str = "",
        subject: str = "",
        body: str = "",
        cc: str = "",
        bcc: str = "",
        **kwargs: Any,
    ) -> str:
        if not to:
            return "Error: Recipient email address ('to') is required."
        if not subject:
            return "Error: Email subject is required."
        if not body:
            return "Error: Email body is required."

        email_record = {
            "to": to,
            "subject": subject,
            "body": body,
            "cc": cc,
            "bcc": bcc,
            "status": "dry_run",
        }
        self.sent_emails.append(email_record)

        logger.log_tool_call(
            "email_send",
            {"to": to, "subject": subject, "body_preview": body[:100]},
            phase="executed",
            result="dry_run",
        )

        return (
            f"[DRY RUN] Email drafted successfully:\n"
            f"  To: {to}\n"
            f"  Subject: {subject}\n"
            f"  Body preview: {body[:200]}{'...' if len(body) > 200 else ''}\n"
            f"  Status: NOT SENT (dry-run mode)\n"
            f"  To send for real, switch execution mode to 'live'."
        )
