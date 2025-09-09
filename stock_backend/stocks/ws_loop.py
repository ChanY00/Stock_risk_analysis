"""
A lightweight, reusable event loop runner for scheduling coroutines from
non-async contexts (e.g., KIS callbacks) to the Channels layer.
"""

import asyncio
import threading
import logging
from concurrent.futures import Future
from typing import Optional


logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None
_lock = threading.Lock()


def _run_loop():
    global _loop
    try:
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        logger.info("Broadcast event loop initialized")
        _loop.run_forever()
    except Exception as e:
        logger.error(f"Broadcast loop error: {e}")
    finally:
        _loop = None


def ensure_started() -> None:
    """Ensure the background event loop thread is started."""
    global _thread
    if _thread and _thread.is_alive():
        return
    with _lock:
        if _thread and _thread.is_alive():
            return
        _thread = threading.Thread(target=_run_loop, daemon=True, name="ws-broadcast-loop")
        _thread.start()
        logger.info("Broadcast thread started")


def submit_coroutine(coro) -> Optional[Future]:
    """Submit a coroutine to the background loop, starting it if needed."""
    ensure_started()
    if _loop and not _loop.is_closed():
        try:
            return asyncio.run_coroutine_threadsafe(coro, _loop)
        except Exception as e:
            logger.error(f"Failed to submit coroutine: {e}")
            return None
    return None


def stop() -> None:
    """Stop the background event loop thread."""
    global _thread
    if _loop and not _loop.is_closed():
        try:
            _loop.call_soon_threadsafe(_loop.stop)
        except Exception:
            pass
    if _thread and _thread.is_alive():
        _thread.join(timeout=2)
    _thread = None


__all__ = ["ensure_started", "submit_coroutine", "stop"]




