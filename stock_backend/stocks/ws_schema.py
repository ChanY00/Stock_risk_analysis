"""
WebSocket message schema and constants for stock real-time service.

This module centralizes message types and payload shapes to keep
the backend<->frontend contract consistent.
"""

from typing import TypedDict, Literal, NotRequired, List, Dict, Any, Optional


# =============================
# Message type constants
# =============================
WS_TYPE_CONNECTION_STATUS: Literal["connection_status"] = "connection_status"
WS_TYPE_PRICE_UPDATE: Literal["price_update"] = "price_update"
WS_TYPE_SUBSCRIBE_RESPONSE: Literal["subscribe_response"] = "subscribe_response"
WS_TYPE_UNSUBSCRIBE_RESPONSE: Literal["unsubscribe_response"] = "unsubscribe_response"
WS_TYPE_ERROR: Literal["error"] = "error"
WS_TYPE_SUBSCRIPTIONS: Literal["subscriptions"] = "subscriptions"


# =============================
# Message payload schemas
# =============================
class ConnectionStatusMessage(TypedDict, total=False):
    type: Literal["connection_status"]
    status: Literal["connected", "disconnected"]
    message: str
    subscribed_stocks: List[str]
    timestamp: str


class PriceUpdateMessage(TypedDict):
    type: Literal["price_update"]
    data: Dict[str, Any]


class SubscribeResponseMessage(TypedDict, total=False):
    type: Literal["subscribe_response"]
    subscribed: List[str]
    total_subscriptions: List[str]
    message: str


class UnsubscribeResponseMessage(TypedDict, total=False):
    type: Literal["unsubscribe_response"]
    unsubscribed: List[str]
    total_subscriptions: List[str]
    message: str


class ErrorMessage(TypedDict, total=False):
    type: Literal["error"]
    message: str
    code: str


class SubscriptionsMessage(TypedDict, total=False):
    type: Literal["subscriptions"]
    subscribed_stocks: List[str]


# =============================
# Price data schema (common fields)
# =============================
class PriceData(TypedDict, total=False):
    stock_code: str
    stock_name: str
    current_price: int
    change_amount: int
    change_percent: float
    volume: int
    trading_value: int
    timestamp: str
    source: str
    # Enriched fields (when available)
    market_status: str
    is_market_open: bool
    data_type: Literal["realtime", "closing", "prev_closing"]
    data_label: str
    update_reason: str
    fallback: bool


# Group naming prefix (kept here for contract visibility; helper added separately)
GROUP_STOCK_PREFIX = "stock_"


__all__ = [
    # constants
    "WS_TYPE_CONNECTION_STATUS",
    "WS_TYPE_PRICE_UPDATE",
    "WS_TYPE_SUBSCRIBE_RESPONSE",
    "WS_TYPE_UNSUBSCRIBE_RESPONSE",
    "WS_TYPE_ERROR",
    "WS_TYPE_SUBSCRIPTIONS",
    "GROUP_STOCK_PREFIX",
    # schemas
    "ConnectionStatusMessage",
    "PriceUpdateMessage",
    "SubscribeResponseMessage",
    "UnsubscribeResponseMessage",
    "ErrorMessage",
    "SubscriptionsMessage",
    "PriceData",
]




