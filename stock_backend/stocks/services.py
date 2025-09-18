from decimal import Decimal
from typing import Dict, List, Optional
from django.conf import settings
from .models import Stock
from kis_api.client import KISApiClient
import logging
import os
import time
import random

logger = logging.getLogger(__name__)

class StockPriceService:
    """실시간 주가 데이터 서비스"""
    
    def __init__(self):
        # 환경변수에서 모의투자 여부 확인 (기본값: True)
        is_mock = os.getenv('KIS_IS_MOCK', 'True').lower() == 'true'
        self.kis_client = KISApiClient(is_mock=is_mock)
        self.max_retries = 3
        self.base_delay = 0.5
    
    def _safe_api_call(self, func, *args, **kwargs):
        """API 호출을 안전하게 실행하는 헬퍼 메서드"""
        for attempt in range(self.max_retries):
            try:
                result = func(*args, **kwargs)
                if result is not None:
                    return result
                logger.warning(f"API call returned None on attempt {attempt + 1}")
                # brief wait to allow token issuance to complete in other process
                time.sleep(1.0)
            except Exception as e:
                error_msg = str(e)
                logger.warning(f"API call failed on attempt {attempt + 1}: {error_msg}")
                
                # 특정 에러 타입에 따른 처리
                if "초당 거래건수를 초과" in error_msg or "EGW00201" in error_msg:
                    # Rate limit 에러 시 더 긴 대기
                    wait_time = (attempt + 1) * 2.0 + random.uniform(0.5, 1.5)
                    logger.info(f"Rate limit hit, waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
                elif "EGW00133" in error_msg:
                    # 토큰 관련 에러 시 더 긴 대기
                    wait_time = 60 + random.uniform(10, 30)
                    logger.warning(f"Token error, waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    # 일반적인 에러 시 점진적 백오프
                    wait_time = self.base_delay * (2 ** attempt) + random.uniform(0.1, 0.5)
                    time.sleep(wait_time)
        
        logger.error(f"API call failed after {self.max_retries} attempts")
        return None
    
    def get_real_time_price(self, stock_code: str) -> Optional[Dict]:
        """실시간 주가 조회 (안전한 버전)"""
        def _call_api():
            response = self.kis_client.get_current_price(stock_code)
            if not response or 'output' not in response:
                return None
                
            output = response['output']
            
            # KIS API 응답을 표준 형식으로 변환
            return {
                'code': stock_code,
                'name': output.get('hts_kor_isnm', ''),
                'current_price': int(output.get('stck_prpr', 0)),
                'change_amount': int(output.get('prdy_vrss', 0)),
                'change_percent': float(output.get('prdy_ctrt', 0)),
                'volume': int(output.get('acml_vol', 0)),
                'trading_value': int(output.get('acml_tr_pbmn', 0)),
                'market_cap': int(output.get('lstn_stcn', 0)) * int(output.get('stck_prpr', 0)),
                'high_price': int(output.get('stck_hgpr', 0)),
                'low_price': int(output.get('stck_lwpr', 0)),
                'open_price': int(output.get('stck_oprc', 0)),
                'prev_close': int(output.get('stck_sdpr', 0)),
                'timestamp': output.get('stck_cntg_hour', '')
            }
        
        return self._safe_api_call(_call_api)
    
    def get_multiple_prices(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """여러 종목 실시간 주가 조회 (개선된 안정성)"""
        results = {}
        failed_codes = []
        
        # 더 보수적인 설정
        batch_size = 8  # 더 작은 배치
        base_interval = 0.3  # 기본 300ms 간격
        
        logger.info(f"Starting price retrieval for {len(stock_codes)} stocks in batches of {batch_size}")
        
        for i in range(0, len(stock_codes), batch_size):
            batch = stock_codes[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(stock_codes) + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches}: {batch}")
            
            # 배치 내 개별 호출
            for j, code in enumerate(batch):
                try:
                    # 동적 간격 조정 (배치 내에서 점진적으로 증가)
                    dynamic_interval = base_interval + (j * 0.1) + random.uniform(0.05, 0.15)
                    
                    price_data = self.get_real_time_price(code)
                    if price_data:
                        results[code] = price_data
                        logger.debug(f"✅ {code}: {price_data.get('current_price', 0):,}원")
                    else:
                        failed_codes.append(code)
                        logger.warning(f"❌ {code}: 데이터 없음")
                    
                    # 마지막 종목이 아니면 대기
                    if j < len(batch) - 1:
                        time.sleep(dynamic_interval)
                        
                except Exception as e:
                    failed_codes.append(code)
                    logger.warning(f"❌ {code}: {str(e)}")
                    continue
            
            # 배치 간 대기 (배치 번호에 따라 증가)
            if i + batch_size < len(stock_codes):
                batch_wait = 1.5 + (batch_num * 0.2) + random.uniform(0.3, 0.7)
                logger.info(f"Batch {batch_num} completed. Waiting {batch_wait:.1f}s before next batch...")
                time.sleep(batch_wait)
        
        success_rate = len(results) / len(stock_codes) * 100 if stock_codes else 0
        logger.info(f"✅ Price retrieval completed: {len(results)}/{len(stock_codes)} ({success_rate:.1f}%)")
        
        if failed_codes:
            logger.warning(f"Failed codes: {failed_codes}")
        
        return results
    
    def get_kospi200_prices(self) -> Dict[str, Dict]:
        """KOSPI 200 종목 실시간 주가 조회 (DB 폴백 포함)"""
        try:
            # DB에서 활성 KOSPI 종목 코드 조회 (필드명 수정)
            kospi_stocks = Stock.objects.filter(
                market='KOSPI'
            ).values_list('stock_code', flat=True)[:50]  # 처음 50개만 테스트
            
            if not kospi_stocks:
                logger.warning("No KOSPI stocks found in database")
                return {}
            
            return self.get_multiple_prices(list(kospi_stocks))
            
        except Exception as e:
            logger.error(f"Error getting KOSPI 200 prices: {e}")
            return {}
    
    def get_db_fallback_data(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """DB에서 폴백 데이터 조회"""
        fallback_data = {}
        
        try:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
            
            for stock in stocks:
                # 최신 주가 데이터 조회
                latest_price = stock.prices.first()
                if latest_price:
                    fallback_data[stock.stock_code] = {
                        'code': stock.stock_code,
                        'name': stock.stock_name,
                        'current_price': latest_price.close_price,
                        'change_amount': 0,  # DB에서는 전일 대비 계산 어려움
                        'change_percent': 0.0,
                        'volume': latest_price.volume,
                        'trading_value': 0,
                        'market_cap': stock.market_cap or 0,
                        'high_price': latest_price.high_price,
                        'low_price': latest_price.low_price,
                        'open_price': latest_price.open_price,
                        'prev_close': latest_price.close_price,
                        'timestamp': latest_price.date.strftime('%Y%m%d'),
                        'fallback': True  # 폴백 데이터임을 표시
                    }
        except Exception as e:
            logger.error(f"Error getting fallback data: {e}")
        
        return fallback_data
    
    def get_daily_chart_data(self, stock_code: str, period: str = "D") -> Optional[List[Dict]]:
        """일봉 차트 데이터 조회 (안전한 버전)"""
        def _call_api():
            response = self.kis_client.get_daily_price(stock_code, period)
            if not response or 'output2' not in response:
                return None
                
            chart_data = []
            for item in response['output2']:
                chart_data.append({
                    'date': item.get('stck_bsop_date', ''),
                    'open': int(item.get('stck_oprc', 0)),
                    'high': int(item.get('stck_hgpr', 0)),
                    'low': int(item.get('stck_lwpr', 0)),
                    'close': int(item.get('stck_clpr', 0)),
                    'volume': int(item.get('acml_vol', 0))
                })
                
            return chart_data
        
        return self._safe_api_call(_call_api)
    
    def get_orderbook_data(self, stock_code: str) -> Optional[Dict]:
        """호가 정보 조회 (안전한 버전)"""
        def _call_api():
            response = self.kis_client.get_orderbook(stock_code)
            if not response or 'output1' not in response:
                return None
                
            output = response['output1']
            
            # 매수/매도 호가 정보 파싱
            bid_prices = []
            ask_prices = []
            
            for i in range(1, 11):  # 10단계 호가
                bid_price = output.get(f'bidp{i}', '0')
                bid_qty = output.get(f'bidp_rsqn{i}', '0')
                ask_price = output.get(f'askp{i}', '0')
                ask_qty = output.get(f'askp_rsqn{i}', '0')
                
                if bid_price != '0':
                    bid_prices.append({
                        'price': int(bid_price),
                        'quantity': int(bid_qty)
                    })
                    
                if ask_price != '0':
                    ask_prices.append({
                        'price': int(ask_price),
                        'quantity': int(ask_qty)
                    })
            
            return {
                'stock_code': stock_code,
                'bid_prices': bid_prices,
                'ask_prices': ask_prices,
                'total_bid_qty': int(output.get('total_bidp_rsqn', 0)),
                'total_ask_qty': int(output.get('total_askp_rsqn', 0)),
                'timestamp': output.get('hour', '')
            }
        
        return self._safe_api_call(_call_api)

class StockSearchService:
    """종목 검색 서비스"""
    
    def __init__(self):
        self.kis_client = KISApiClient()
    
    def search_stocks(self, keyword: str) -> List[Dict]:
        """종목 검색"""
        try:
            response = self.kis_client.search_stock_info(keyword)
            if not response or 'output' not in response:
                return []
                
            results = []
            for item in response['output']:
                results.append({
                    'code': item.get('pdno', ''),
                    'name': item.get('prdt_name', ''),
                    'market': item.get('mket_id_cd', ''),
                    'sector': item.get('bstp_kor_isnm', ''),
                    'current_price': int(item.get('stck_prpr', 0)),
                    'change_percent': float(item.get('prdy_ctrt', 0))
                })
                
            return results
            
        except Exception as e:
            logger.error(f"Error searching stocks with keyword {keyword}: {e}")
            return [] 