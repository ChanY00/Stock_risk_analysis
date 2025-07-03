"""
한국 주식시장 운영 시간 및 공휴일 관리 모듈
"""
import os
from datetime import datetime, timezone, timedelta, time as dt_time
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class KoreanMarketHours:
    """한국 주식시장 운영 시간 관리"""
    
    def __init__(self):
        # 시장 운영 시간 (KST)
        self.market_timezone = timezone(timedelta(hours=9))  # KST
        self.open_time = dt_time(9, 0)   # 09:00
        self.close_time = dt_time(15, 30)  # 15:30
        
        # 2025년 한국 공휴일 (월, 일)
        self.holidays_2025 = [
            (1, 1),   # 신정
            (1, 28),  # 설날 연휴 (화)
            (1, 29),  # 설날 (수)
            (1, 30),  # 설날 연휴 (목)
            (3, 1),   # 삼일절 (토) - 토요일이지만 공휴일
            (5, 5),   # 어린이날 (월)
            (5, 13),  # 부처님오신날 (화)
            (6, 6),   # 현충일 (금)
            (8, 15),  # 광복절 (금)
            (9, 16),  # 추석 연휴 (화)
            (9, 17),  # 추석 (수)
            (9, 18),  # 추석 연휴 (목)
            (10, 3),  # 개천절 (금)
            (10, 9),  # 한글날 (목)
            (12, 25), # 크리스마스 (목)
        ]
        
        # 임시 휴장일 (필요시 추가)
        self.special_holidays_2025 = [
            (6, 3),   # 제21대 대통령 선거일 (2025-06-03)
            # (월, 일) 형태로 추가 - 현재는 임시 휴장일 없음
        ]
    
    def is_market_open_now(self) -> bool:
        """현재 시점에 시장이 열려있는지 확인"""
        now = datetime.now(self.market_timezone)
        return self.is_market_open_at(now)
    
    def is_market_open_at(self, dt: datetime) -> bool:
        """특정 시점에 시장이 열려있는지 확인"""
        # 타임존 변환
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.market_timezone)
        elif dt.tzinfo != self.market_timezone:
            dt = dt.astimezone(self.market_timezone)
        
        # 주말 체크 (토요일=5, 일요일=6)
        if dt.weekday() >= 5:
            logger.debug(f"주말이므로 시장 휴장: {dt.strftime('%Y-%m-%d %A')}")
            return False
        
        # 공휴일 체크
        current_date = (dt.month, dt.day)
        if current_date in self.holidays_2025 or current_date in self.special_holidays_2025:
            logger.debug(f"공휴일이므로 시장 휴장: {dt.strftime('%Y-%m-%d')}")
            return False
        
        # 시간 체크
        current_time = dt.time()
        if not (self.open_time <= current_time <= self.close_time):
            logger.debug(f"시장 운영시간 외: {current_time} (운영시간: {self.open_time} ~ {self.close_time})")
            return False
        
        return True
    
    def get_next_market_open(self) -> datetime:
        """다음 시장 개장 시간 반환"""
        now = datetime.now(self.market_timezone)
        
        # 오늘 시장이 아직 열릴 예정이면
        today_open = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now < today_open and self.is_market_open_at(today_open):
            return today_open
        
        # 내일부터 확인
        check_date = now.replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
        
        # 최대 30일까지 확인
        for _ in range(30):
            if self.is_market_open_at(check_date):
                return check_date
            check_date += timedelta(days=1)
        
        # 30일 내에 개장일이 없으면 None 반환 (비정상 상황)
        return None
    
    def get_time_until_market_open(self) -> dict:
        """시장 개장까지 남은 시간 정보"""
        if self.is_market_open_now():
            return {
                'is_open': True,
                'message': '현재 시장이 열려있습니다',
                'next_close': self._get_today_close_time()
            }
        
        next_open = self.get_next_market_open()
        if not next_open:
            return {
                'is_open': False,
                'message': '다음 개장일을 찾을 수 없습니다',
                'next_open': None
            }
        
        now = datetime.now(self.market_timezone)
        time_diff = next_open - now
        
        days = time_diff.days
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            message = f"시장 개장까지 {days}일 {hours}시간 {minutes}분 남았습니다"
        elif hours > 0:
            message = f"시장 개장까지 {hours}시간 {minutes}분 남았습니다"
        else:
            message = f"시장 개장까지 {minutes}분 남았습니다"
        
        return {
            'is_open': False,
            'message': message,
            'next_open': next_open,
            'days': days,
            'hours': hours,
            'minutes': minutes
        }
    
    def _get_today_close_time(self) -> datetime:
        """오늘 시장 마감 시간"""
        now = datetime.now(self.market_timezone)
        return now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    def get_market_status(self) -> dict:
        """상세한 시장 상태 정보"""
        now = datetime.now(self.market_timezone)
        is_open = self.is_market_open_now()
        
        status = {
            'is_open': is_open,
            'current_time': now,
            'current_time_str': now.strftime('%Y-%m-%d %H:%M:%S %Z'),
            'weekday': now.strftime('%A'),
            'is_weekend': now.weekday() >= 5,
            'is_holiday': (now.month, now.day) in self.holidays_2025,
        }
        
        if is_open:
            close_time = self._get_today_close_time()
            time_until_close = close_time - now
            hours, remainder = divmod(time_until_close.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            status.update({
                'status': 'OPEN',
                'message': f'시장이 열려있습니다 (마감까지 {hours}시간 {minutes}분)',
                'close_time': close_time,
                'time_until_close': {
                    'hours': hours,
                    'minutes': minutes
                }
            })
        else:
            time_info = self.get_time_until_market_open()
            status.update({
                'status': 'CLOSED',
                'message': time_info['message'],
                'next_open': time_info.get('next_open'),
                'time_until_open': time_info
            })
        
        return status

# 글로벌 인스턴스
market_hours = KoreanMarketHours()

def is_market_open() -> bool:
    """시장이 열려있는지 간단히 확인"""
    return market_hours.is_market_open_now()

def get_market_status() -> dict:
    """시장 상태 정보 반환"""
    return market_hours.get_market_status()

def log_market_status():
    """현재 시장 상태를 로그로 출력"""
    status = get_market_status()
    
    if status['is_open']:
        logger.info(f"🟢 {status['message']}")
    else:
        logger.info(f"🔴 {status['message']}")
        if status.get('next_open'):
            logger.info(f"📅 다음 개장: {status['next_open'].strftime('%Y-%m-%d %H:%M')}")
    
    return status 