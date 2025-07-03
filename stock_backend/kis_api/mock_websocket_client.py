import time
import random
import threading
import logging
from typing import Dict, List, Callable, Optional
import json

# 성능 모니터링용 로거 추가
logger = logging.getLogger(__name__)
performance_logger = logging.getLogger('performance')

class MockKISWebSocketClient:
    """모의 한국투자증권 WebSocket 클라이언트 (테스트용) - 성능 최적화"""
    
    def __init__(self, is_mock=True):
        self.is_mock = is_mock
        self.is_connected = False
        self.subscriptions = {}  # {stock_code: callback_function}
        self.running = False
        self._thread = None
        self._generation_count = 0
        self._last_performance_log = time.time()
        
        # 확장된 모의 주가 데이터 (17개 종목)
        self.mock_prices = {
            '005930': {'name': '삼성전자', 'base_price': 72000, 'current_price': 72000},
            '000660': {'name': 'SK하이닉스', 'base_price': 132000, 'current_price': 132000},
            '035420': {'name': 'NAVER', 'base_price': 195000, 'current_price': 195000},
            '373220': {'name': 'LG에너지솔루션', 'base_price': 450000, 'current_price': 450000},
            '207940': {'name': '삼성바이오로직스', 'base_price': 850000, 'current_price': 850000},
            '005490': {'name': 'POSCO홀딩스', 'base_price': 400000, 'current_price': 400000},
            '051910': {'name': 'LG화학', 'base_price': 380000, 'current_price': 380000},
            '006400': {'name': '삼성SDI', 'base_price': 420000, 'current_price': 420000},
            '035720': {'name': '카카오', 'base_price': 45000, 'current_price': 45000},
            '012330': {'name': '현대모비스', 'base_price': 250000, 'current_price': 250000},
            '028260': {'name': '삼성물산', 'base_price': 145000, 'current_price': 145000},
            '068270': {'name': '셀트리온', 'base_price': 180000, 'current_price': 180000},
            '000270': {'name': '기아', 'base_price': 95000, 'current_price': 95000},
            '005380': {'name': '현대차', 'base_price': 195000, 'current_price': 195000},
            '105560': {'name': 'KB금융', 'base_price': 65000, 'current_price': 65000},
            '055550': {'name': '신한지주', 'base_price': 42000, 'current_price': 42000},
            '006480': {'name': 'POSCO', 'base_price': 320000, 'current_price': 320000}
        }
        
        performance_logger.info(f"Mock WebSocket Client initialized with {len(self.mock_prices)} stocks")
        
    def connect(self) -> bool:
        """WebSocket 연결 (모의)"""
        try:
            logger.info("🔌 Connecting to Mock KIS WebSocket...")
            time.sleep(0.5)  # 연결 지연 단축 (1초 → 0.5초)
            
            self.is_connected = True
            self.running = True
            
            # 실시간 데이터 생성 스레드 시작
            self._thread = threading.Thread(target=self._generate_mock_data, daemon=True)
            self._thread.start()
            
            logger.info("🟢 Mock WebSocket connected successfully")
            performance_logger.info("Mock WebSocket connection established")
            return True
            
        except Exception as e:
            logger.error(f"Mock WebSocket connection error: {e}")
            return False
    
    def subscribe_stock(self, stock_code: str, callback: Callable[[Dict], None]) -> bool:
        """종목 구독 (모의)"""
        try:
            if stock_code not in self.mock_prices:
                # 새로운 종목은 기본값으로 초기화
                self.mock_prices[stock_code] = {
                    'name': f'종목{stock_code}',
                    'base_price': 50000,
                    'current_price': 50000
                }
            
            self.subscriptions[stock_code] = callback
            logger.info(f"📊 Mock subscription added for {stock_code}")
            return True
            
        except Exception as e:
            logger.error(f"Mock subscription error for {stock_code}: {e}")
            return False
    
    def unsubscribe_stock(self, stock_code: str) -> bool:
        """종목 구독 해제 (모의)"""
        try:
            if stock_code in self.subscriptions:
                del self.subscriptions[stock_code]
                logger.info(f"📊 Mock unsubscribed from {stock_code}")
            return True
            
        except Exception as e:
            logger.error(f"Mock unsubscribe error for {stock_code}: {e}")
            return False
    
    def get_subscribed_stocks(self) -> List[str]:
        """현재 구독 중인 종목 목록"""
        return list(self.subscriptions.keys())
    
    def close(self):
        """연결 종료 (모의)"""
        self.running = False
        self.is_connected = False
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
            
        logger.info("🔌 Mock WebSocket connection closed")
        performance_logger.info("Mock WebSocket connection closed")
    
    def _generate_mock_data(self):
        """실시간 모의 데이터 생성 - 고성능 최적화"""
        logger.info("🚀 Mock data generation started (optimized)")
        performance_logger.info("Mock data generation thread started")
        
        while self.running:
            try:
                start_time = time.time()
                
                # 구독 중인 종목들에 대해 모의 데이터 생성
                subscribed_stocks = list(self.subscriptions.keys())
                
                if not subscribed_stocks:
                    time.sleep(5)  # 구독이 없으면 5초 대기 (3초 → 5초)
                    continue
                
                self._generation_count += 1
                
                # 성능 로그 (1분에 한 번)
                current_time = time.time()
                if current_time - self._last_performance_log >= 60:
                    performance_logger.info(
                        f"Mock data performance: {self._generation_count} generations, "
                        f"{len(subscribed_stocks)} subscribed stocks"
                    )
                    self._last_performance_log = current_time
                
                # 정보 로그 빈도 줄이기 (20번에 1번 → 50번에 1번)
                if self._generation_count % 50 == 1:
                    logger.info(f"📊 Generating data for {len(subscribed_stocks)} subscribed stocks")
                
                # 배치로 여러 종목 처리
                batch_size = min(5, len(subscribed_stocks))  # 한 번에 최대 5개 종목 처리
                for i in range(0, len(subscribed_stocks), batch_size):
                    if not self.running:  # 빠른 종료 체크
                        break
                    
                    batch = subscribed_stocks[i:i + batch_size]
                    self._process_stock_batch(batch)
                
                # 업데이트 주기 최적화 (2-4초 → 4-6초)
                sleep_time = random.uniform(4, 6)
                
                # 디버그 로그 빈도 줄이기 (20번에 1번 → 100번에 1번)
                if self._generation_count % 100 == 1:
                    processing_time = time.time() - start_time
                    logger.debug(f"💤 Batch processed in {processing_time:.3f}s, sleeping for {sleep_time:.1f}s")
                
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Mock data generation error: {e}")
                time.sleep(5)  # 오류 시 5초 대기 (3초 → 5초)
        
        logger.info("🔄 Mock data generation stopped")
        performance_logger.info("Mock data generation thread stopped")
    
    def _process_stock_batch(self, stock_codes: List[str]):
        """주식 배치 처리 - 성능 최적화"""
        for stock_code in stock_codes:
            if not self.running:
                break
                
            if stock_code in self.mock_prices:
                # 가격 변동 시뮬레이션 최적화 (-1.5% ~ +1.5%)
                base_price = self.mock_prices[stock_code]['base_price']
                change_percent = random.uniform(-1.5, 1.5)
                change_amount = int(base_price * (change_percent / 100))
                new_price = max(100, base_price + change_amount)  # 최소 100원
                
                # 거래량 최적화 (더 현실적인 범위)
                volume = random.randint(10000, 100000)
                
                # 현재가 업데이트
                self.mock_prices[stock_code]['current_price'] = new_price
                
                # 실시간 데이터 생성 (최적화된 구조)
                price_data = {
                    'stock_code': stock_code,
                    'stock_name': self.mock_prices[stock_code]['name'],
                    'current_price': new_price,
                    'change_amount': change_amount,
                    'change_percent': round(change_percent, 2),
                    'volume': volume,
                    'trading_value': new_price * volume,
                    'timestamp': time.strftime('%Y%m%d%H%M%S'),
                    'source': 'mock_websocket_optimized'
                }
                
                # 극도로 줄인 디버그 로그 (500번에 1번)
                if self._generation_count % 500 == 1:
                    logger.debug(f"💰 Mock price: {stock_code} = {new_price:,}원 ({change_percent:+.2f}%)")
                
                # 콜백 호출 (에러 처리 최적화)
                callback = self.subscriptions.get(stock_code)
                if callback:
                    try:
                        callback(price_data)
                    except Exception as e:
                        # 콜백 에러도 빈도 줄이기
                        if self._generation_count % 100 == 1:
                            logger.error(f"Mock callback error for {stock_code}: {e}")

# Mock 클라이언트를 실제 클라이언트처럼 사용할 수 있도록 alias 생성
KISWebSocketClient = MockKISWebSocketClient 