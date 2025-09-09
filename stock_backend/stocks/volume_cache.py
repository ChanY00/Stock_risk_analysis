"""
Background refresher and cache accessors for real-time volume/trading_value.

Hot-path(WS 콜백)에서 REST 호출을 제거하고, 주기적으로 최신 값을
캐시에 적재한 뒤 콜백에서는 캐시 병합만 수행하도록 합니다.
"""

import threading
import time
import logging
from typing import Callable, Optional, Dict, List

from django.core.cache import caches
from django.conf import settings

from kis_api.client import KISApiClient


logger = logging.getLogger(__name__)

_CACHE = caches['stock_data'] if 'stock_data' in caches else None
_KEY_PREFIX = 'rt_volume:'


def _get_cache_key(stock_code: str) -> str:
    return f"{_KEY_PREFIX}{stock_code}"


def get_cached_volume(stock_code: str) -> Optional[Dict]:
    """Get cached volume/trading_value for a stock code."""
    if not _CACHE:
        return None
    return _CACHE.get(_get_cache_key(stock_code))


class VolumeRefresher:
    """
    Background refresher that periodically fetches volume/trading_value
    for a set of stock codes supplied by a callback.
    """

    def __init__(self, get_codes_supplier: Callable[[], List[str]]):
        self._get_codes = get_codes_supplier
        self._thread = None
        self._running = False
        # settings 기반 구성
        self._interval = int(getattr(settings, 'WS_VOLUME_REFRESH_INTERVAL_SEC', 5))
        # 모의/실계좌 판별 → KISApiClient 선택
        is_mock = bool(getattr(settings, 'KIS_IS_PAPER_TRADING', True))
        self._client = KISApiClient(is_mock=is_mock)

    def start(self):
        if self._running:
            return
        self._running = True

        def _run():
            logger.info("Volume refresher started")
            while self._running:
                try:
                    codes = list(set(self._get_codes() or []))
                    if codes:
                        self._refresh_codes(codes)
                except Exception as e:
                    logger.warning(f"Volume refresher iteration error: {e}")
                finally:
                    time.sleep(max(1, self._interval))
            logger.info("Volume refresher stopped")

        self._thread = threading.Thread(target=_run, daemon=True, name="volume-refresher")
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=2)
            except Exception:
                pass

    def _refresh_codes(self, codes: List[str]):
        if not _CACHE:
            return
        # 간단: 순차 호출(레이트리밋 고려해 간격은 interval로 전체 제어)
        for code in codes:
            try:
                data = self._fetch_volume(code)
                if data is not None:
                    # 짧은 TTL (기본 10초)
                    ttl = int(getattr(settings, 'WS_VOLUME_CACHE_TTL_SEC', 10))
                    _CACHE.set(_get_cache_key(code), data, ttl)
            except Exception as e:
                # 개별 실패는 조용히 스킵
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Volume fetch failed for {code}: {e}")

    def _fetch_volume(self, stock_code: str) -> Optional[Dict]:
        """Fetch volume/trading_value via REST API for a stock code."""
        try:
            resp = self._client.get_current_price(stock_code)
            if not resp or 'output' not in resp:
                return None
            output = resp['output']
            volume = int(output.get('acml_vol', 0))
            trading_value = int(output.get('acml_tr_pbmn', 0))
            if volume <= 0 and trading_value <= 0:
                return None
            return {
                'volume': volume,
                'trading_value': trading_value,
                'source': 'kis_rest_api_cache'
            }
        except Exception:
            return None


__all__ = [
    'get_cached_volume',
    'VolumeRefresher',
]




