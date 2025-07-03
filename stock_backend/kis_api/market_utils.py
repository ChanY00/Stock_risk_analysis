from datetime import datetime, time, timedelta
import logging
from typing import Optional, Tuple
import pytz

logger = logging.getLogger(__name__)

class KoreanMarketUtils:
    """한국 주식시장 관련 유틸리티"""
    
    # 한국 시간대
    KST = pytz.timezone('Asia/Seoul')
    
    # 시장 개장 시간 (평일 9:00 ~ 15:30)
    MARKET_OPEN_TIME = time(9, 0)
    MARKET_CLOSE_TIME = time(15, 30)
    
    @classmethod
    def get_current_kst_time(cls) -> datetime:
        """현재 한국 시간 반환"""
        return datetime.now(cls.KST)
    
    @classmethod
    def is_market_day(cls, date: datetime = None) -> bool:
        """주어진 날짜가 거래일인지 확인 (평일만 거래일)"""
        if date is None:
            date = cls.get_current_kst_time()
        
        # 주말 체크 (월요일=0, 일요일=6)
        if date.weekday() >= 5:  # 토요일(5), 일요일(6)
            return False
        
        # TODO: 한국 공휴일 체크 (추후 구현)
        # 현재는 단순히 평일만 거래일로 판단
        return True
    
    @classmethod
    def is_market_open(cls, now: datetime = None) -> Tuple[bool, str]:
        """현재 시장이 개장 중인지 확인"""
        if now is None:
            now = cls.get_current_kst_time()
        
        # 거래일 여부 확인
        if not cls.is_market_day(now):
            if now.weekday() == 5:  # 토요일
                return False, "주말 휴장 (토요일)"
            elif now.weekday() == 6:  # 일요일
                return False, "주말 휴장 (일요일)"
            else:
                return False, "공휴일 휴장"
        
        # 거래 시간 확인
        current_time = now.time()
        
        if current_time < cls.MARKET_OPEN_TIME:
            return False, f"장 시작 전 (개장: {cls.MARKET_OPEN_TIME.strftime('%H:%M')})"
        elif current_time > cls.MARKET_CLOSE_TIME:
            return False, f"장 마감 후 (마감: {cls.MARKET_CLOSE_TIME.strftime('%H:%M')})"
        else:
            return True, "정규장 시간"
    
    @classmethod
    def get_last_trading_day(cls, from_date: datetime = None) -> datetime:
        """마지막 거래일 반환"""
        if from_date is None:
            from_date = cls.get_current_kst_time()
        
        # 오늘부터 역순으로 거래일 찾기
        check_date = from_date
        
        while True:
            if cls.is_market_day(check_date):
                # 오늘이 거래일이면서 장이 열린 후라면 오늘을 반환
                if check_date.date() == from_date.date():
                    if from_date.time() >= cls.MARKET_OPEN_TIME:
                        return check_date
                # 과거 거래일이면 바로 반환
                else:
                    return check_date
            
            # 하루 전으로 이동
            check_date = check_date - timedelta(days=1)
            
            # 무한 루프 방지 (최대 10일 전까지만)
            if (from_date - check_date).days > 10:
                logger.warning(f"10일 전까지 거래일을 찾을 수 없습니다: {from_date}")
                return from_date - timedelta(days=1)
    
    @classmethod
    def get_market_status_message(cls) -> str:
        """현재 시장 상태 메시지 반환"""
        is_open, reason = cls.is_market_open()
        now = cls.get_current_kst_time()
        
        if is_open:
            return f"🟢 시장 개장 중 ({now.strftime('%Y-%m-%d %H:%M')})"
        else:
            last_trading_day = cls.get_last_trading_day()
            return f"🔴 시장 휴장 중 ({reason}) - 마지막 거래일: {last_trading_day.strftime('%Y-%m-%d')}"
    
    @classmethod
    def should_use_cached_data(cls) -> bool:
        """캐시된 데이터를 사용해야 하는지 판단"""
        is_open, _ = cls.is_market_open()
        return not is_open

# 전역 유틸리티 인스턴스
market_utils = KoreanMarketUtils() 