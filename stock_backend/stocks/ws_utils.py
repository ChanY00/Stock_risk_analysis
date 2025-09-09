"""
WebSocket utilities for group naming and helpers.
"""

from .ws_schema import GROUP_STOCK_PREFIX


def get_group_name_for_stock(stock_code: str) -> str:
    """
    Build the channels group name for a given stock code.
    Keeps the convention centralized in one place.
    """
    return f"{GROUP_STOCK_PREFIX}{stock_code}"


__all__ = ["get_group_name_for_stock"]




