import websocket
import json
import threading
import time
import logging
from typing import Dict, List, Callable, Optional
from .client import KISApiClient
import os
from .mock_websocket_client import MockKISWebSocketClient
from .real_websocket_client import RealKISWebSocketClient
from django.conf import settings

logger = logging.getLogger(__name__)

class KISWebSocketClient:
    """한국투자증권 WebSocket API 클라이언트 (Mock/Real 선택 가능)"""
    
    def __init__(self, is_mock: bool = None):
        """
        Args:
            is_mock: True면 Mock 클라이언트, False면 실제 KIS API, None이면 설정으로 결정
        """
        if is_mock is None:
            # Django 설정에서 결정
            is_mock = getattr(settings, 'KIS_USE_MOCK', False)
        
        self.is_mock = is_mock
        
        if is_mock:
            logger.info("🔧 Mock KIS WebSocket 클라이언트 사용")
            self.client = MockKISWebSocketClient()
        else:
            logger.info("🚀 실제 KIS WebSocket 클라이언트 사용")
            # Django 설정에서 API 키 확인
            app_key = getattr(settings, 'KIS_APP_KEY', None)
            app_secret = getattr(settings, 'KIS_APP_SECRET', None)
            
            if not app_key or not app_secret:
                logger.error("❌ KIS API 키가 Django 설정에 없습니다!")
                logger.error("Django settings에서 KIS_APP_KEY와 KIS_APP_SECRET를 확인해주세요.")
                raise ValueError("KIS API credentials not configured in Django settings")
            
            logger.info(f"✅ KIS API 키 확인됨: {app_key[:10]}...")
            self.client = RealKISWebSocketClient()
        
        # Django 설정에서 API 정보 가져오기
        self.app_key = getattr(settings, 'KIS_APP_KEY', None)
        self.app_secret = getattr(settings, 'KIS_APP_SECRET', None)
        
        # WebSocket URLs
        if is_mock:
            self.ws_url = "ws://ops.koreainvestment.com:31000"  # 모의투자용
        else:
            self.ws_url = getattr(settings, 'KIS_WEBSOCKET_URL', "ws://ops.koreainvestment.com:21000")  # 실계좌용
            
        self.ws = None
        self.is_connected = False
        self.subscriptions = {}  # {stock_code: callback_function}
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5
        
        # Thread safety
        self._lock = threading.Lock()
        self._running = False
        
        # 실시간 접속키 발급을 위한 REST 클라이언트
        self.rest_client = KISApiClient(is_mock=is_mock)
        self.approval_key = None
        
    def _get_approval_key(self) -> bool:
        """실시간 접속키 발급"""
        try:
            if not self.rest_client.ensure_token():
                logger.error("Failed to get access token")
                return False
                
            url = f"{self.rest_client.base_url}/oauth2/Approval"
            headers = {
                "content-type": "application/json",
                "authorization": f"Bearer {self.rest_client.token_manager.access_token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }
            
            data = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.app_secret
            }
            
            import requests
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                result = response.json()
                self.approval_key = result.get('approval_key')
                logger.info("🔑 WebSocket approval key obtained successfully")
                return True
            else:
                logger.error(f"Failed to get approval key: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error getting approval key: {e}")
            return False
    
    def connect(self) -> bool:
        """WebSocket 연결"""
        if self.is_mock:
            return self.client.connect()
        else:
            # 실제 API의 경우 시장 운영 시간 체크
            if not self.client.is_market_open():
                logger.warning("⏰ 현재 시장이 닫혀있습니다.")
                logger.warning("📅 한국 주식시장 운영시간: 평일 09:00 ~ 15:30 (KST)")
                logger.warning("🏖️ 주말 및 공휴일에는 실시간 데이터를 받을 수 없습니다.")
                logger.info("💡 개발/테스트 목적이라면 Mock 클라이언트 사용을 권장합니다.")
                
                # 시장이 닫혀있어도 연결은 시도 (토큰 검증 등을 위해)
                result = self.client.connect()
                if result:
                    logger.info("🔗 WebSocket 연결은 성공했지만, 실시간 데이터는 시장 운영시간에만 수신됩니다.")
                return result
            else:
                logger.info("🟢 시장이 열려있습니다. 실시간 데이터 수신 가능!")
                return self.client.connect()
    
    def _on_open(self, ws):
        """연결 성공 시 호출"""
        logger.info("🟢 WebSocket connected successfully")
        self.is_connected = True
        self.reconnect_attempts = 0
        
        # 기존 구독들 재등록
        with self._lock:
            for stock_code in list(self.subscriptions.keys()):
                self._subscribe_stock(stock_code)
    
    def _on_message(self, ws, message):
        """메시지 수신 시 호출"""
        try:
            # KIS WebSocket 프로토콜에 따른 메시지 파싱
            if message.startswith('0|'):
                # 시세 데이터
                parts = message.split('|')
                if len(parts) >= 3:
                    stock_code = parts[2]
                    
                    # 메시지 파싱 (KIS 프로토콜에 따라)
                    price_data = self._parse_price_message(message)
                    
                    # 콜백 호출
                    with self._lock:
                        if stock_code in self.subscriptions:
                            callback = self.subscriptions[stock_code]
                            if callback:
                                try:
                                    callback(price_data)
                                except Exception as e:
                                    logger.error(f"Callback error for {stock_code}: {e}")
            
        except Exception as e:
            logger.error(f"Message parsing error: {e}")
    
    def _parse_price_message(self, message: str) -> Dict:
        """KIS WebSocket 메시지 파싱"""
        try:
            parts = message.split('|')
            
            if len(parts) < 10:
                return {}
                
            return {
                'stock_code': parts[2],
                'current_price': int(parts[3]) if parts[3] else 0,
                'change_amount': int(parts[4]) if parts[4] else 0,
                'change_percent': float(parts[5]) if parts[5] else 0.0,
                'volume': int(parts[6]) if parts[6] else 0,
                'trading_value': int(parts[7]) if parts[7] else 0,
                'timestamp': parts[8] if len(parts) > 8 else '',
                'source': 'websocket'
            }
            
        except Exception as e:
            logger.error(f"Price message parsing error: {e}")
            return {}
    
    def _on_error(self, ws, error):
        """에러 발생 시 호출"""
        logger.error(f"🔴 WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """연결 종료 시 호출"""
        logger.warning(f"🟡 WebSocket connection closed: {close_status_code}, {close_msg}")
        self.is_connected = False
        
        if self._running and self.reconnect_attempts < self.max_reconnect_attempts:
            self._reconnect()
    
    def _reconnect(self):
        """재연결 시도"""
        self.reconnect_attempts += 1
        logger.info(f"🔄 Reconnecting... (attempt {self.reconnect_attempts}/{self.max_reconnect_attempts})")
        
        time.sleep(self.reconnect_delay)
        self.connect()
    
    def subscribe_stock(self, stock_code: str, callback: Callable[[Dict], None]) -> bool:
        """종목 구독"""
        return self.client.subscribe_stock(stock_code, callback)
    
    def _subscribe_stock(self, stock_code: str) -> bool:
        """실제 구독 요청 전송"""
        try:
            # KIS WebSocket 구독 메시지 형식
            subscribe_message = {
                "header": {
                    "approval_key": self.approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8"
                },
                "body": {
                    "input": {
                        "tr_id": "H0STCNT0",  # 실시간 체결가
                        "tr_key": stock_code
                    }
                }
            }
            
            message = json.dumps(subscribe_message)
            self.ws.send(message)
            
            logger.info(f"📊 Subscribed to {stock_code}")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe request error for {stock_code}: {e}")
            return False
    
    def unsubscribe_stock(self, stock_code: str) -> bool:
        """종목 구독 해제"""
        return self.client.unsubscribe_stock(stock_code)
    
    def get_subscribed_stocks(self) -> List[str]:
        """현재 구독 중인 종목 목록"""
        return self.client.get_subscribed_stocks()
    
    def close(self):
        """연결 종료"""
        self._running = False
        
        if self.ws:
            self.ws.close()
            
        self.is_connected = False
        logger.info("🔌 WebSocket connection closed")
        
        return self.client.close()
    
    def is_market_open(self) -> bool:
        """시장 운영 시간 확인 (실제 API에서만 의미있음)"""
        if hasattr(self.client, 'is_market_open'):
            return self.client.is_market_open()
        return True  # Mock의 경우 항상 True 