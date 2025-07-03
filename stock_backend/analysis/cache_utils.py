from django.core.cache import cache, caches
from django.conf import settings
import json
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """캐시 관리 클래스"""
    
    # 캐시 키 상수
    STOCK_LIST_KEY = "stock_list"
    STOCK_DETAIL_KEY = "stock_detail_{}"
    MARKET_OVERVIEW_KEY = "market_overview"
    STOCK_ANALYSIS_KEY = "stock_analysis_{}"
    SECTOR_PERFORMANCE_KEY = "sector_performance"
    TOP_STOCKS_KEY = "top_stocks_{}"  # per, pbr, roe 등
    
    @classmethod
    def get_cache_key(cls, key_template, *args):
        """캐시 키 생성"""
        cache_key = f"{settings.CACHE_KEY_PREFIX}{key_template}"
        if args:
            cache_key = cache_key.format(*args)
        return cache_key
    
    @classmethod
    def get_stock_list(cls, filters=None):
        """주식 목록 캐시 조회"""
        cache_key = cls.get_cache_key(cls.STOCK_LIST_KEY)
        if filters:
            # 필터가 있는 경우 별도 키 생성
            filter_hash = hash(json.dumps(filters, sort_keys=True))
            cache_key = f"{cache_key}_{filter_hash}"
        
        return cache.get(cache_key)
    
    @classmethod
    def set_stock_list(cls, data, filters=None, timeout=None):
        """주식 목록 캐시 저장"""
        cache_key = cls.get_cache_key(cls.STOCK_LIST_KEY)
        if filters:
            filter_hash = hash(json.dumps(filters, sort_keys=True))
            cache_key = f"{cache_key}_{filter_hash}"
        
        timeout = timeout or settings.STOCK_CACHE_TIMEOUT
        cache.set(cache_key, data, timeout)
        logger.debug(f"Cache set: {cache_key} for {timeout}s")
    
    @classmethod
    def get_stock_detail(cls, stock_id):
        """주식 상세 정보 캐시 조회"""
        cache_key = cls.get_cache_key(cls.STOCK_DETAIL_KEY, stock_id)
        return cache.get(cache_key)
    
    @classmethod
    def set_stock_detail(cls, stock_id, data, timeout=None):
        """주식 상세 정보 캐시 저장"""
        cache_key = cls.get_cache_key(cls.STOCK_DETAIL_KEY, stock_id)
        timeout = timeout or settings.STOCK_CACHE_TIMEOUT
        cache.set(cache_key, data, timeout)
        logger.debug(f"Cache set: {cache_key} for {timeout}s")
    
    @classmethod
    def get_market_overview(cls):
        """시장 개요 캐시 조회"""
        market_cache = caches['market_data']
        cache_key = cls.get_cache_key(cls.MARKET_OVERVIEW_KEY)
        return market_cache.get(cache_key)
    
    @classmethod
    def set_market_overview(cls, data, timeout=None):
        """시장 개요 캐시 저장"""
        market_cache = caches['market_data']
        cache_key = cls.get_cache_key(cls.MARKET_OVERVIEW_KEY)
        timeout = timeout or settings.MARKET_CACHE_TIMEOUT
        market_cache.set(cache_key, data, timeout)
        logger.debug(f"Market cache set: {cache_key} for {timeout}s")
    
    @classmethod
    def get_stock_analysis(cls, stock_id):
        """주식 분석 데이터 캐시 조회"""
        cache_key = cls.get_cache_key(cls.STOCK_ANALYSIS_KEY, stock_id)
        return cache.get(cache_key)
    
    @classmethod
    def set_stock_analysis(cls, stock_id, data, timeout=None):
        """주식 분석 데이터 캐시 저장"""
        cache_key = cls.get_cache_key(cls.STOCK_ANALYSIS_KEY, stock_id)
        timeout = timeout or settings.ANALYSIS_CACHE_TIMEOUT
        cache.set(cache_key, data, timeout)
        logger.debug(f"Analysis cache set: {cache_key} for {timeout}s")
    
    @classmethod
    def get_top_stocks(cls, ranking_type):
        """상위 주식 랭킹 캐시 조회"""
        cache_key = cls.get_cache_key(cls.TOP_STOCKS_KEY, ranking_type)
        return cache.get(cache_key)
    
    @classmethod
    def set_top_stocks(cls, ranking_type, data, timeout=None):
        """상위 주식 랭킹 캐시 저장"""
        cache_key = cls.get_cache_key(cls.TOP_STOCKS_KEY, ranking_type)
        timeout = timeout or settings.ANALYSIS_CACHE_TIMEOUT
        cache.set(cache_key, data, timeout)
        logger.debug(f"Top stocks cache set: {cache_key} for {timeout}s")
    
    @classmethod
    def invalidate_stock_cache(cls, stock_id=None):
        """주식 관련 캐시 무효화"""
        if stock_id:
            # 특정 주식 캐시만 삭제
            cache_keys = [
                cls.get_cache_key(cls.STOCK_DETAIL_KEY, stock_id),
                cls.get_cache_key(cls.STOCK_ANALYSIS_KEY, stock_id),
            ]
            for key in cache_keys:
                cache.delete(key)
                logger.debug(f"Cache invalidated: {key}")
        else:
            # 모든 주식 관련 캐시 삭제
            cache.clear()
            logger.debug("All cache cleared")
    
    @classmethod
    def invalidate_market_cache(cls):
        """시장 관련 캐시 무효화"""
        market_cache = caches['market_data']
        market_cache.clear()
        
        # 시장 개요가 변경되면 섹터 성과, 상위 주식 랭킹도 무효화
        cache_keys = [
            cls.get_cache_key(cls.SECTOR_PERFORMANCE_KEY),
            cls.get_cache_key(cls.TOP_STOCKS_KEY, "per"),
            cls.get_cache_key(cls.TOP_STOCKS_KEY, "pbr"),
            cls.get_cache_key(cls.TOP_STOCKS_KEY, "roe"),
            cls.get_cache_key(cls.TOP_STOCKS_KEY, "market_cap"),
        ]
        
        for key in cache_keys:
            cache.delete(key)
        
        logger.debug("Market and related cache invalidated")

class CacheStats:
    """캐시 통계 클래스"""
    
    @classmethod
    def get_cache_info(cls):
        """캐시 정보 조회"""
        cache_info = {}
        
        # 기본 캐시
        cache_info['default'] = {
            'backend': cache.__class__.__name__,
            'location': getattr(cache, '_cache', {}).get('_location', 'N/A'),
        }
        
        # 추가 캐시들
        for cache_name in ['stock_data', 'market_data']:
            cache_instance = caches[cache_name]
            cache_info[cache_name] = {
                'backend': cache_instance.__class__.__name__,
                'location': getattr(cache_instance, '_cache', {}).get('_location', 'N/A'),
            }
        
        return cache_info
    
    @classmethod
    def clear_all_caches(cls):
        """모든 캐시 클리어"""
        for cache_name in ['default', 'stock_data', 'market_data']:
            cache_instance = caches[cache_name]
            cache_instance.clear()
        
        logger.info("All caches cleared")
        return True 