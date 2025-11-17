from typing import TypedDict


class AgentState(TypedDict):
    messages: list[dict]
    recipient_phone: str | None
    amount: float | None
    currency: str
    confirmation_pending: bool
    transaction_id: str | None
    error: str | None
