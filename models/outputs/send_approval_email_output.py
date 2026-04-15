from pydantic import BaseModel, Field
from typing import Optional


class SendApprovalEmailOutput(BaseModel):
    """Output schema for send_approval_email tool"""
    token: str = Field(default="", description="Signed approval token.")
    expires_at: str = Field(default="", description="ISO timestamp when the approval expires.")
    email_sent: bool = Field(default=False, description="Whether the email was sent successfully.")
    error: Optional[str] = Field(default=None, description="Error message if email sending failed.")
