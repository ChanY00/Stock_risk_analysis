"""
시장 상태별 데이터 관리 모듈
- 시장 운영시간: 실시간 데이터
- 시장 종료 후: 당일 종가 데이터 
- 휴일: 전일 종가 데이터
"""
import os
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
import logging
from .market_hours import market_hours

logger = logging.getLogger(__name__)

class MarketDataManager:
    """시장 상태에 따른 데이터 관리"""
    
    def __init__(self):
        self.last_market_data = {}  # 마지막 실시간 데이터 저장
        self.closing_prices = {}    # 종가 데이터 저장
        self.market_status_cache = None
        self.cache_expiry = None
        
    def get_market_status_cached(self) -> dict:
        """캐시된 시장 상태 정보 (5분간 캐시)"""
        now = datetime.now()
        
        if (self.market_status_cache is None or 
            self.cache_expiry is None or 
            now > self.cache_expiry):
            
            self.market_status_cache = market_hours.get_market_status()
            self.cache_expiry = now + timedelta(minutes=5)
            
        return self.market_status_cache
    
    def update_real_time_data(self, stock_code: str, price_data: Dict) -> Dict:
        """실시간 데이터 업데이트 및 보강"""
        enhanced_data = price_data.copy()
        
        # 시장 상태 정보 추가
        market_status = self.get_market_status_cached()
        enhanced_data['market_status'] = market_status['status']
        enhanced_data['is_market_open'] = market_status['is_open']
        
        if market_status['is_open']:
            # 시장이 열려있을 때: 실시간 데이터
            enhanced_data['data_type'] = 'realtime'
            enhanced_data['data_label'] = '실시간'
            enhanced_data['update_reason'] = '실시간 업데이트'
            
            # 마지막 데이터로 저장
            self.last_market_data[stock_code] = enhanced_data.copy()
            
        else:
            # 시장이 닫혀있을 때도 적절한 라벨 설정
            now = datetime.now(market_hours.market_timezone)
            
            # 오늘이 거래일인지 확인
            today_is_trading_day = market_hours.is_market_open_at(
                now.replace(hour=10, minute=0, second=0, microsecond=0)
            )
            
            if today_is_trading_day and now.hour >= 15 and now.hour < 24:
                # 오늘 장 마감 후
                enhanced_data['data_type'] = 'closing'
                enhanced_data['data_label'] = '종가'
                enhanced_data['update_reason'] = '당일 종가 (시장 마감 후)'
            else:
                # 휴일이거나 다음날 장 시작 전
                enhanced_data['data_type'] = 'prev_closing'
                enhanced_data['data_label'] = '전일종가'
                enhanced_data['update_reason'] = '전일 종가 (휴장일/장 시작 전)'
            
            # 종가 데이터로 저장
            self.closing_prices[stock_code] = enhanced_data.copy()
            
        return enhanced_data
    
    def get_appropriate_data(self, stock_code: str, fallback_data: Dict = None) -> Dict:
        """시장 상태에 따른 적절한 데이터 반환"""
        market_status = self.get_market_status_cached()
        
        if market_status['is_open']:
            # 시장이 열려있을 때: 실시간 데이터 (있다면)
            if stock_code in self.last_market_data:
                return self.last_market_data[stock_code]
            elif fallback_data:
                return self._enhance_fallback_data(fallback_data, 'realtime', '실시간')
        
        else:
            # 시장이 닫혀있을 때
            return self._get_closing_price_data(stock_code, market_status, fallback_data)
    
    def _get_closing_price_data(self, stock_code: str, market_status: Dict, fallback_data: Dict = None) -> Dict:
        """시장 종료 후 적절한 종가 데이터 반환"""
        now = datetime.now(market_hours.market_timezone)
        
        # 오늘이 거래일인지 확인
        today_is_trading_day = market_hours.is_market_open_at(
            now.replace(hour=10, minute=0, second=0, microsecond=0)  # 오전 10시 기준으로 체크
        )
        
        if today_is_trading_day and now.hour >= 15 and now.hour < 24:
            # 오늘 장 마감 후 (15:30 ~ 23:59)
            data_type = 'closing'
            data_label = '종가'
            update_reason = '당일 종가'
        else:
            # 휴일이거나 다음날 장 시작 전
            data_type = 'prev_closing'
            data_label = '전일종가'
            update_reason = '전일 종가'
        
        # 저장된 종가 데이터가 있다면 사용
        if stock_code in self.closing_prices:
            closing_data = self.closing_prices[stock_code].copy()
            closing_data.update({
                'data_type': data_type,
                'data_label': data_label,
                'update_reason': update_reason,
                'market_status': 'CLOSED',
                'is_market_open': False
            })
            return closing_data
        
        # 마지막 실시간 데이터가 있다면 종가로 사용
        elif stock_code in self.last_market_data:
            last_data = self.last_market_data[stock_code].copy()
            last_data.update({
                'data_type': data_type,
                'data_label': data_label,
                'update_reason': update_reason,
                'market_status': 'CLOSED',
                'is_market_open': False
            })
            return last_data
        
        # 폴백 데이터 사용
        elif fallback_data:
            return self._enhance_fallback_data(fallback_data, data_type, data_label)
        
        # 데이터가 전혀 없는 경우
        else:
            return self._create_no_data_response(stock_code, data_type, data_label)
    
    def _enhance_fallback_data(self, fallback_data: Dict, data_type: str, data_label: str) -> Dict:
        """폴백 데이터에 시장 상태 정보 추가"""
        enhanced = fallback_data.copy()
        market_status = self.get_market_status_cached()
        
        enhanced.update({
            'data_type': data_type,
            'data_label': data_label,
            'update_reason': f'{data_label} (DB 데이터)',
            'market_status': market_status['status'],
            'is_market_open': market_status['is_open'],
            'fallback': True
        })
        
        return enhanced
    
    def _create_no_data_response(self, stock_code: str, data_type: str, data_label: str) -> Dict:
        """데이터가 없을 때의 기본 응답"""
        market_status = self.get_market_status_cached()
        
        return {
            'stock_code': stock_code,
            'current_price': 0,
            'change_amount': 0,
            'change_percent': 0.0,
            'volume': 0,
            'trading_value': 0,
            'timestamp': time.strftime('%Y%m%d%H%M%S'),
            'source': 'no_data',
            'data_type': data_type,
            'data_label': data_label,
            'update_reason': '데이터 없음',
            'market_status': market_status['status'],
            'is_market_open': market_status['is_open'],
            'error': True
        }
    
    def save_closing_price(self, stock_code: str, price_data: Dict):
        """종가 데이터 저장 (시장 마감 시 호출)"""
        closing_data = price_data.copy()
        closing_data.update({
            'saved_at': datetime.now().isoformat(),
            'data_type': 'closing',
            'data_label': '종가'
        })
        
        self.closing_prices[stock_code] = closing_data
        logger.info(f"📊 {stock_code} 종가 저장: {price_data.get('current_price', 0):,}원")
    
    def get_market_summary(self) -> Dict:
        """시장 상태 요약 정보"""
        market_status = self.get_market_status_cached()
        
        summary = {
            'market_status': market_status['status'],
            'is_market_open': market_status['is_open'],
            'current_time': market_status['current_time_str'],
            'message': market_status['message'],
            'total_stocks_tracked': len(self.last_market_data),
            'closing_prices_saved': len(self.closing_prices)
        }
        
        if market_status['is_open']:
            summary['data_mode'] = 'realtime'
            summary['description'] = '실시간 데이터 제공 중'
        else:
            now = datetime.now(market_hours.market_timezone)
            today_is_trading_day = market_hours.is_market_open_at(
                now.replace(hour=10, minute=0, second=0, microsecond=0)
            )
            
            if today_is_trading_day and now.hour >= 15:
                summary['data_mode'] = 'closing'
                summary['description'] = '당일 종가 제공 중'
            else:
                summary['data_mode'] = 'prev_closing'
                summary['description'] = '전일 종가 제공 중'
        
        return summary

# 글로벌 인스턴스
market_data_manager = MarketDataManager()

def get_enhanced_price_data(stock_code: str, real_time_data: Dict = None, fallback_data: Dict = None) -> Dict:
    """시장 상태에 따른 적절한 가격 데이터 반환"""
    if real_time_data:
        return market_data_manager.update_real_time_data(stock_code, real_time_data)
    else:
        return market_data_manager.get_appropriate_data(stock_code, fallback_data) 