"""
Database Schemas for Chatjob (UK-based chatting platform)

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user"
- Chat -> "chat"
- Message -> "message"
- Payment -> "payment"

Currency: All monetary values are stored in euros (EUR).
"""

from pydantic import BaseModel, Field
from typing import Optional

class User(BaseModel):
    name: str = Field(..., description="Display name")
    role: str = Field(..., description="creator or customer", pattern="^(creator|customer)$")
    rate_eur_per_min: Optional[float] = Field(None, ge=0, description="For creators: rate per minute in EUR")
    wallet_eur: float = Field(0.0, ge=0, description="User wallet balance in EUR")
    bio: Optional[str] = Field(None, description="Short bio for creators")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")

class Chat(BaseModel):
    creator_id: str = Field(...)
    customer_id: str = Field(...)
    status: str = Field("active", description="active or ended")
    rate_eur_per_min: float = Field(..., ge=0)
    started_at: Optional[str] = Field(None, description="ISO timestamp when chat started")
    ended_at: Optional[str] = Field(None, description="ISO timestamp when chat ended")
    total_minutes: Optional[int] = Field(None, ge=0)
    total_cost_eur: Optional[float] = Field(None, ge=0)

class Message(BaseModel):
    chat_id: str
    sender_id: str
    content: str
    sent_at: Optional[str] = Field(None, description="ISO timestamp when message sent")

class Payment(BaseModel):
    user_id: str
    kind: str = Field(..., description="topup or settlement", pattern="^(topup|settlement)$")
    amount_eur: float = Field(..., description="Positive for credit to user, negative for debit")
    chat_id: Optional[str] = Field(None, description="Associated chat if settlement")
