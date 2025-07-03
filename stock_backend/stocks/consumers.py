import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from kis_api.websocket_client import KISWebSocketClient
from kis_api.market_data_manager import market_data_manager, get_enhanced_price_data
from typing import Dict, Set, Optional
import threading
import time
from django.conf import settings
from kis_api.market_utils import market_utils

logger = logging.getLogger(__name__)
performance_logger = logging.getLogger('performance')

# 글로벌 구독 관리자
class GlobalSubscriptionManager:
    """전역 구독 관리자 - 모든 클라이언트 간 공유 (성능 최적화)"""
    
    def __init__(self):
        self.connected_clients = {}  # {client_id: subscription_set}
        self.subscribed_stocks = set()  # 전체 구독 종목
        self.kis_client = None
        self.lock = threading.Lock()
        self._callback_count = 0
        self._last_performance_log = time.time()
        
        # 휴장일 대응 속성
        self.market_closed_mode = False
        self.connection_status = "disconnected"
        
        # 단일 이벤트 루프 및 브로드캐스트 스레드 최적화
        self._broadcast_loop = None
        self._broadcast_thread = None
        self._initialize_broadcast_thread()
        
    def _initialize_broadcast_thread(self):
        """단일 브로드캐스트 스레드 초기화 - 성능 최적화"""
        def run_broadcast_loop():
            try:
                self._broadcast_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._broadcast_loop)
                performance_logger.info("Broadcast event loop initialized")
                self._broadcast_loop.run_forever()
            except Exception as e:
                logger.error(f"Broadcast loop error: {e}")
            finally:
                self._broadcast_loop = None
        
        self._broadcast_thread = threading.Thread(target=run_broadcast_loop, daemon=True)
        self._broadcast_thread.start()
        performance_logger.info("Single broadcast thread started")
        
    def add_client(self, client_id: str):
        """클라이언트 추가"""
        with self.lock:
            self.connected_clients[client_id] = set()
            logger.info(f"📱 Client {client_id} added. Total clients: {len(self.connected_clients)}")
            
            # 첫 번째 클라이언트일 때 KIS 연결
            if len(self.connected_clients) == 1:
                self._initialize_kis_client()
    
    def remove_client(self, client_id: str):
        """클라이언트 제거 및 불필요한 구독 정리"""
        with self.lock:
            if client_id in self.connected_clients:
                client_subscriptions = self.connected_clients[client_id]
                del self.connected_clients[client_id]
                
                logger.info(f"📱 Client {client_id} removed. Remaining clients: {len(self.connected_clients)}")
                
                # 더 이상 구독하지 않는 종목들 찾기
                still_subscribed = set()
                for other_client_subs in self.connected_clients.values():
                    still_subscribed.update(other_client_subs)
                
                # 구독 해제할 종목들
                to_unsubscribe = client_subscriptions - still_subscribed
                for stock_code in to_unsubscribe:
                    self._unsubscribe_from_kis(stock_code)
                
                # 마지막 클라이언트였다면 KIS 연결 해제
                if len(self.connected_clients) == 0:
                    self._cleanup_kis_client()
    
    def subscribe_stocks(self, client_id: str, stock_codes: list) -> list:
        """종목 구독 (새로 추가된 종목만 실제 구독)"""
        with self.lock:
            if client_id not in self.connected_clients:
                return []
            
            client_stocks = self.connected_clients[client_id]
            new_subscriptions = []
            
            for stock_code in stock_codes:
                if stock_code and stock_code not in client_stocks:
                    client_stocks.add(stock_code)
                    
                    # 다른 클라이언트가 이미 구독하지 않은 경우에만 KIS에 구독
                    if stock_code not in self.subscribed_stocks:
                        if self._subscribe_to_kis(stock_code):
                            new_subscriptions.append(stock_code)
                            self.subscribed_stocks.add(stock_code)
                    else:
                        new_subscriptions.append(stock_code)
            
            logger.info(f"📊 Client {client_id} subscribed to {len(new_subscriptions)} new stocks")
            return new_subscriptions
    
    def unsubscribe_stocks(self, client_id: str, stock_codes: list) -> list:
        """종목 구독 해제"""
        with self.lock:
            if client_id not in self.connected_clients:
                return []
            
            client_stocks = self.connected_clients[client_id]
            unsubscribed = []
            
            for stock_code in stock_codes:
                if stock_code in client_stocks:
                    client_stocks.remove(stock_code)
                    unsubscribed.append(stock_code)
                    
                    # 다른 클라이언트가 구독하지 않으면 KIS에서 구독 해제
                    still_needed = any(
                        stock_code in other_subs 
                        for other_subs in self.connected_clients.values()
                    )
                    
                    if not still_needed and stock_code in self.subscribed_stocks:
                        self._unsubscribe_from_kis(stock_code)
                        self.subscribed_stocks.remove(stock_code)
            
            return unsubscribed
    
    def get_all_subscribed_stocks(self) -> list:
        """전체 구독 종목 목록"""
        return list(self.subscribed_stocks)
    
    def _initialize_kis_client(self):
        """KIS 클라이언트 초기화 (실제 API 전용)"""
        try:
            logger.info("🔌 Initializing Global KIS WebSocket client...")
            
            # 시장 상태 우선 확인
            is_open, reason = market_utils.is_market_open()
            
            if not is_open:
                logger.info(f"🔴 시장 휴장 중 ({reason}) - API 연결 없이 휴장일 모드 활성화")
                self.kis_client = None
                self.market_closed_mode = True
                return
            
            # Django 설정 확인
            use_mock = getattr(settings, 'KIS_USE_MOCK', False)
            is_paper_trading = getattr(settings, 'KIS_IS_PAPER_TRADING', True)
            app_key = getattr(settings, 'KIS_APP_KEY', None)
            app_secret = getattr(settings, 'KIS_APP_SECRET', None)
            
            logger.info(f"📋 KIS 설정 확인:")
            logger.info(f"   - USE_MOCK: {use_mock}")
            logger.info(f"   - PAPER_TRADING: {is_paper_trading} ({'모의투자' if is_paper_trading else '실계좌'})")
            logger.info(f"   - APP_KEY: {'설정됨' if app_key else '없음'} ({app_key[:10] + '...' if app_key else 'None'})")
            logger.info(f"   - APP_SECRET: {'설정됨' if app_secret else '없음'}")
            
            # Mock 모드 체크
            if use_mock:
                logger.info("🎭 Mock 모드 활성화")
                self.kis_client = None
                self.market_closed_mode = True
                return
            
            # API 키 확인
            if not app_key or not app_secret:
                logger.error("❌ KIS API 키가 설정되지 않았습니다!")
                logger.error("환경변수 KIS_APP_KEY와 KIS_APP_SECRET를 확인해주세요.")
                self.kis_client = None
                self.market_closed_mode = True
                return
            
            # 실제 KIS API 전용 사용 (Mock fallback 제거)
            trading_mode = "모의투자" if is_paper_trading else "실계좌"
            logger.info(f"🚀 실제 KIS API 클라이언트 전용 모드 ({trading_mode})...")
            
            # 최대 3번 재시도
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    logger.info(f"🔄 KIS API 연결 시도 #{attempt}/{max_attempts}")
                    
                    # RealKISWebSocketClient 직접 사용
                    from kis_api.real_websocket_client import RealKISWebSocketClient
                    self.kis_client = RealKISWebSocketClient()
                    
                    # 연결 시도
                    if self.kis_client.connect():
                        logger.info("✅ 전역 KIS API 클라이언트 연결 성공!")
                        self.connection_status = "connected"
                        return
                    else:
                        logger.warning(f"❌ 실제 KIS API 연결 실패 (시도 #{attempt})")
                        
                except Exception as e:
                    logger.error(f"💥 KIS API 연결 오류 (시도 #{attempt}): {e}")
                
                # 재시도 대기 (점진적 증가)
                if attempt < max_attempts:
                    wait_time = attempt * 5
                    logger.info(f"⏳ {wait_time}초 후 재시도...")
                    import time
                    time.sleep(wait_time)
            
            # 모든 시도 실패
            logger.error("❌ 모든 KIS API 연결 시도 실패")
            logger.error("📋 가능한 원인:")
            logger.error("   1. KIS API 키가 잘못되었거나 만료됨")
            logger.error("   2. KIS 서버 점검 또는 장애")
            logger.error("   3. 네트워크 연결 문제")
            logger.error("   4. 시장 운영시간 외 (실시간 데이터는 운영시간에만 제공)")
            logger.error("   5. 모의투자 모드 설정 확인 필요")
            
            # 휴장일 모드로 폴백
            logger.info("🔄 휴장일 모드로 폴백...")
            self.kis_client = None
            self.market_closed_mode = True
            self.connection_status = "market_closed"
            
        except Exception as e:
            logger.error(f"❌ KIS 클라이언트 초기화 오류: {e}")
            self.kis_client = None
            self.market_closed_mode = True
            self.connection_status = "error"
    
    def _cleanup_kis_client(self):
        """KIS 클라이언트 정리"""
        if self.kis_client:
            self.kis_client.close()
            self.kis_client = None
            self.subscribed_stocks.clear()
            logger.info("🔌 Global KIS WebSocket client closed")
            performance_logger.info("KIS WebSocket client closed")
    
    def _subscribe_to_kis(self, stock_code: str) -> bool:
        """KIS에 종목 구독 (휴장일 대응 포함)"""
        try:
            # 휴장일 모드일 때 처리
            if self.market_closed_mode or not self.kis_client:
                logger.info(f"🔴 휴장일 모드 - {stock_code} 이전 거래일 종가 제공 시도")
                
                # 이전 거래일 종가 데이터 생성 및 브로드캐스트
                self._handle_market_closed_subscription(stock_code)
                return True
            
            # 정상 시장 개장 시 실시간 구독
            success = self.kis_client.subscribe_stock(stock_code, self._price_callback)
            if success:
                logger.info(f"📊 Global subscription added for {stock_code}")
            return success
            
        except Exception as e:
            logger.error(f"KIS subscription error for {stock_code}: {e}")
            # 오류 시 휴장일 모드로 폴백
            logger.info(f"🔄 {stock_code} 구독 오류로 휴장일 모드 폴백")
            self._handle_market_closed_subscription(stock_code)
            return True
    
    def _handle_market_closed_subscription(self, stock_code: str):
        """휴장일 종목 구독 처리"""
        try:
            # 비동기 실행을 위해 스케줄링
            if self._broadcast_loop and not self._broadcast_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._async_handle_market_closed(stock_code),
                    self._broadcast_loop
                )
            else:
                logger.warning(f"⚠️ Broadcast loop not available for {stock_code}")
                
        except Exception as e:
            logger.error(f"❌ {stock_code} 휴장일 처리 오류: {e}")
    
    @database_sync_to_async
    def _get_stock_info(self, stock_code: str):
        """비동기 DB 접근을 위한 래퍼 함수"""
        try:
            from stocks.models import Stock
            stock = Stock.objects.get(stock_code=stock_code)
            return stock.stock_name, getattr(stock, 'current_price', 50000)
        except Exception:
            return None, None
    
    async def _async_handle_market_closed(self, stock_code: str):
        """비동기 휴장일 처리"""
        try:
            # 비동기 DB 조회
            stock_info = await self._get_stock_info(stock_code)
            stock_name, current_price = stock_info
            
            if stock_name is None:
                logger.warning(f"❌ 종목 {stock_code}를 데이터베이스에서 찾을 수 없습니다")
                return
            
            # 이전 거래일 기준 종가 데이터 생성
            last_trading_day = market_utils.get_last_trading_day()
            
            # Mock 데이터 생성 (실제로는 DB에서 마지막 종가를 가져와야 함)
            mock_price_data = {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'current_price': current_price,  # DB에서 가져온 현재가
                'change_price': 0,  # 휴장일에는 변동 없음
                'change_rate': 0.0,
                'volume': 0,  # 휴장일에는 거래량 없음
                'trading_value': 0,
                'timestamp': last_trading_day.strftime('%Y%m%d150000'),  # 마지막 거래일 15:00 기준
                'trade_date': last_trading_day.strftime('%Y-%m-%d'),
                'market_status': '휴장',
                'is_cached': True,
                'source': 'market_closed_fallback',
                'last_update': market_utils.get_current_kst_time().isoformat()
            }
            
            # 브로드캐스트를 위해 콜백 호출
            self._price_callback(mock_price_data)
            
            logger.info(f"💾 {stock_code}({stock_name}) 휴장일 종가 데이터 제공: {mock_price_data['current_price']:,}원")
            
        except Exception as e:
            logger.error(f"❌ {stock_code} 휴장일 처리 오류: {e}")
    
    def _unsubscribe_from_kis(self, stock_code: str) -> bool:
        """KIS에서 종목 구독 해제"""
        if not self.kis_client:
            return False
        
        try:
            success = self.kis_client.unsubscribe_stock(stock_code)
            if success:
                logger.info(f"📊 Global subscription removed for {stock_code}")
            return success
        except Exception as e:
            logger.error(f"KIS unsubscription error for {stock_code}: {e}")
            return False
    
    def _price_callback(self, price_data: Dict):
        """KIS로부터 받은 실시간 가격 데이터 처리 - 고성능 최적화 + 실제 거래량 보강"""
        try:
            if not self.connected_clients:
                return  # 클라이언트가 없으면 조용히 종료
            
            self._callback_count += 1
            stock_code = price_data.get('stock_code')
            
            # 성능 로그 (1분에 한 번)
            current_time = time.time()
            if current_time - self._last_performance_log >= 60:
                performance_logger.info(
                    f"Price callback performance: {self._callback_count} callbacks, "
                    f"{len(self.connected_clients)} clients"
                )
                self._last_performance_log = current_time
                self._callback_count = 0
            
            # 정보 로그 빈도 줄이기 (100번에 1번)
            if self._callback_count % 100 == 1:
                logger.info(f"💰 Received price data: {stock_code} = {price_data.get('current_price')}")
            
            # 🔧 실제 거래량 데이터 보강 (모의투자 모드에서만)
            enhanced_price_data = self._enhance_with_real_volume(price_data)
            
            # 시장 상태에 따른 데이터 보강
            enhanced_data = get_enhanced_price_data(stock_code, enhanced_price_data)
            
            # Django Channels를 통해 브로드캐스트 (최적화된 방식)
            if self._broadcast_loop and not self._broadcast_loop.is_closed():
                # 기존 이벤트 루프에 스케줄링 (스레드 생성 없음)
                future = asyncio.run_coroutine_threadsafe(
                    self._async_broadcast(enhanced_data, stock_code),
                    self._broadcast_loop
                )
                
                # 논블로킹 완료 체크 (성능 최적화)
                if self._callback_count % 50 == 1:
                    try:
                        future.result(timeout=0.1)  # 100ms 타임아웃
                    except Exception:
                        pass  # 타임아웃이나 기타 에러 무시
            else:
                logger.warning("Broadcast loop not available")
                
        except Exception as e:
            # 에러 로그도 빈도 줄이기
            if self._callback_count % 100 == 1:
                logger.error(f"Price callback error: {e}")
    
    def _enhance_with_real_volume(self, price_data: Dict) -> Dict:
        """실제 거래량 데이터로 보강 (모의투자 모드에서만)"""
        try:
            # 모의투자 모드이고 source가 kis_paper_trading인 경우에만 보강
            if (price_data.get('source', '').startswith('kis_paper_trading') 
                and self._callback_count % 10 == 1):  # 10번에 1번만 API 호출 (성능 최적화)
                
                stock_code = price_data.get('stock_code')
                if not stock_code:
                    return price_data
                
                # REST API로 실제 거래량 조회
                real_volume_data = self._get_real_volume_from_api(stock_code)
                
                if real_volume_data:
                    # 실제 거래량으로 교체
                    enhanced_data = price_data.copy()
                    enhanced_data.update({
                        'volume': real_volume_data.get('volume', price_data.get('volume', 0)),
                        'trading_value': real_volume_data.get('trading_value', price_data.get('trading_value', 0)),
                        'source': f"{price_data.get('source', '')}_volume_enhanced",
                        'volume_source': 'kis_rest_api'
                    })
                    
                    # 성공 로그 (드물게)
                    if self._callback_count % 100 == 1:
                        logger.info(f"🔧 {stock_code} 거래량 보강: {real_volume_data['volume']:,}주")
                    
                    return enhanced_data
            
            return price_data
            
        except Exception as e:
            logger.warning(f"거래량 보강 실패: {e}")
            return price_data

    def _get_real_volume_from_api(self, stock_code: str) -> Optional[Dict]:
        """KIS REST API로 실제 거래량 조회"""
        try:
            import requests
            import json
            from django.conf import settings
            
            # 액세스 토큰 가져오기 (캐시된 토큰 사용)
            access_token = self._get_cached_access_token()
            if not access_token:
                return None
            
            # 주식현재가 시세조회 API 호출
            url = f"{settings.KIS_BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
            
            headers = {
                'content-type': 'application/json',
                'authorization': f'Bearer {access_token}',
                'appkey': settings.KIS_APP_KEY,
                'appsecret': settings.KIS_APP_SECRET,
                'tr_id': 'FHKST01010100'
            }
            
            params = {
                'fid_cond_mrkt_div_code': 'J',  # 시장구분코드
                'fid_input_iscd': stock_code
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=3)
            
            if response.status_code == 200:
                result = response.json()
                output = result.get('output')
                
                if output:
                    volume = int(output.get('acml_vol', 0))  # 누적거래량
                    trading_value = int(output.get('acml_tr_pbmn', 0))  # 누적거래대금
                    
                    return {
                        'volume': volume,
                        'trading_value': trading_value
                    }
            
            return None
            
        except Exception as e:
            # API 호출 실패는 조용히 처리 (너무 자주 로그 남지 않도록)
            if self._callback_count % 200 == 1:
                logger.debug(f"거래량 API 호출 실패: {e}")
            return None

    def _get_cached_access_token(self) -> Optional[str]:
        """캐시된 액세스 토큰 반환 (성능 최적화)"""
        try:
            # 클래스 레벨 토큰 캐시 (30분 유효)
            if not hasattr(self, '_cached_token') or not hasattr(self, '_token_expires'):
                self._cached_token = None
                self._token_expires = 0
            
            current_time = time.time()
            
            # 토큰이 만료되었거나 없으면 새로 발급
            if current_time >= self._token_expires or not self._cached_token:
                new_token = self._issue_access_token()
                if new_token:
                    self._cached_token = new_token
                    self._token_expires = current_time + 1800  # 30분 후 만료
                    return new_token
                return None
            
            return self._cached_token
            
        except Exception as e:
            logger.warning(f"토큰 캐시 오류: {e}")
            return None

    def _issue_access_token(self) -> Optional[str]:
        """새로운 액세스 토큰 발급"""
        try:
            import requests
            import json
            from django.conf import settings
            
            url = f"{settings.KIS_BASE_URL}/oauth2/tokenP"
            
            headers = {
                'content-type': 'application/json'
            }
            
            data = {
                "grant_type": "client_credentials",
                "appkey": settings.KIS_APP_KEY,
                "appsecret": settings.KIS_APP_SECRET
            }
            
            response = requests.post(url, headers=headers, data=json.dumps(data), timeout=5)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('access_token')
            
            return None
            
        except Exception as e:
            logger.warning(f"토큰 발급 실패: {e}")
            return None
    
    async def _async_broadcast(self, enhanced_data: Dict, stock_code: str):
        """최적화된 비동기 브로드캐스트"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return
            
            await channel_layer.group_send(
                "stock_prices",
                {
                    "type": "price_update",
                    "data": enhanced_data
                }
            )
            
            # 성공 로그 빈도 줄이기 (200번에 1번)
            if self._callback_count % 200 == 1:
                logger.info(f"✅ Price broadcasted: {stock_code}")
                
        except Exception as e:
            logger.error(f"Async broadcast error: {e}")

# 글로벌 구독 관리자 인스턴스
global_subscription_manager = GlobalSubscriptionManager()

class StockPriceConsumer(AsyncWebsocketConsumer):
    """실시간 주가 WebSocket Consumer - 단순화된 버전"""
    
    async def connect(self):
        """클라이언트 연결"""
        try:
            self.client_id = f"client_{id(self)}"
            
            # 연결 수락
            await self.accept()
            logger.info(f"📱 WebSocket connection accepted for {self.client_id}")
            
            # 그룹 추가
            await self.channel_layer.group_add("stock_prices", self.channel_name)
            
            # 글로벌 관리자에 클라이언트 추가
            global_subscription_manager.add_client(self.client_id)
            
            # 연결 확인 메시지
            await self.send(text_data=json.dumps({
                'type': 'connection_status',
                'status': 'connected',
                'subscribed_stocks': global_subscription_manager.get_all_subscribed_stocks(),
                'message': '실시간 주가 서비스에 연결되었습니다.'
            }))
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            await self.close()

    async def disconnect(self, close_code):
        """클라이언트 연결 해제"""
        try:
            # 그룹에서 제거
            await self.channel_layer.group_discard("stock_prices", self.channel_name)
            
            # 글로벌 관리자에서 클라이언트 제거
            if hasattr(self, 'client_id'):
                global_subscription_manager.remove_client(self.client_id)
                logger.info(f"📱 Client {self.client_id} disconnected")
                
        except Exception as e:
            logger.error(f"Disconnect error: {e}")

    async def receive(self, text_data):
        """클라이언트로부터 메시지 수신"""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'subscribe':
                stock_codes = data.get('stock_codes', [])
                await self._handle_subscribe(stock_codes)
                
            elif action == 'unsubscribe':
                stock_codes = data.get('stock_codes', [])
                await self._handle_unsubscribe(stock_codes)
                
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'Unknown action: {action}'
                }))
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON format'
            }))
        except Exception as e:
            logger.error(f"Receive error: {e}")

    async def _handle_subscribe(self, stock_codes):
        """주식 구독 처리"""
        try:
            if not isinstance(stock_codes, list) or not stock_codes:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'stock_codes must be a non-empty list'
                }))
                return
            
            # 글로벌 관리자를 통해 구독
            new_subscriptions = global_subscription_manager.subscribe_stocks(
                self.client_id, stock_codes
            )
            
            # 응답 전송
            await self.send(text_data=json.dumps({
                'type': 'subscribe_response',
                'subscribed': new_subscriptions,
                'total_subscriptions': global_subscription_manager.get_all_subscribed_stocks(),
                'message': f'{len(new_subscriptions)}개 종목 구독 완료'
            }))
            
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Subscription failed: {str(e)}'
            }))

    async def _handle_unsubscribe(self, stock_codes):
        """주식 구독 해제 처리"""
        try:
            # 글로벌 관리자를 통해 구독 해제
            removed_subscriptions = global_subscription_manager.unsubscribe_stocks(
                self.client_id, stock_codes
            )
            
            await self.send(text_data=json.dumps({
                'type': 'unsubscribe_response',
                'unsubscribed': removed_subscriptions,
                'total_subscriptions': global_subscription_manager.get_all_subscribed_stocks(),
                'message': f'{len(removed_subscriptions)}개 종목 구독 해제 완료'
            }))
            
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")

    async def price_update(self, event):
        """실시간 가격 업데이트 메시지 전송"""
        await self.send(text_data=json.dumps({
            'type': 'price_update',
            'data': event['data']
        }))

# 실시간 주가 브로드캐스터 (독립적인 백그라운드 서비스)
class RealTimePriceBroadcaster:
    """실시간 주가 데이터 브로드캐스터"""
    
    def __init__(self):
        self.kis_client = None
        self.channel_layer = None  # 지연 초기화로 변경
        self.subscribed_stocks = set()
        self.running = False
    
    def start(self):
        """브로드캐스터 시작"""
        if self.running:
            return
            
        self.running = True
        
        # 여기서 channel_layer 초기화
        if not self.channel_layer:
            self.channel_layer = get_channel_layer()
        
        def run_broadcaster():
            self.kis_client = KISWebSocketClient(is_mock=True)
            if self.kis_client.connect():
                logger.info("🚀 Real-time price broadcaster started")
                
                # 메인 종목들 구독
                major_stocks = ['005930', '000660', '035420', '005490', '051910']
                for stock_code in major_stocks:
                    self.subscribe_stock(stock_code)
                
                # 연결 유지
                while self.running:
                    time.sleep(1)
            else:
                logger.error("❌ Failed to start broadcaster")
        
        import threading
        import time
        
        self.thread = threading.Thread(target=run_broadcaster, daemon=True)
        self.thread.start()
    
    def subscribe_stock(self, stock_code: str):
        """종목 구독"""
        if self.kis_client and stock_code not in self.subscribed_stocks:
            def callback(price_data):
                # 비동기 브로드캐스트
                asyncio.run_coroutine_threadsafe(
                    self._async_broadcast(price_data),
                    asyncio.get_event_loop()
                )
            
            success = self.kis_client.subscribe_stock(stock_code, callback)
            if success:
                self.subscribed_stocks.add(stock_code)
                logger.info(f"📊 Broadcaster subscribed to {stock_code}")
    
    async def _async_broadcast(self, price_data: Dict):
        """비동기 브로드캐스트"""
        try:
            # channel_layer가 없으면 초기화
            if not self.channel_layer:
                self.channel_layer = get_channel_layer()
                
            await self.channel_layer.group_send(
                "stock_prices",
                {
                    "type": "price_message",
                    "message": {
                        'type': 'price_update',
                        'data': price_data,
                        'timestamp': price_data.get('timestamp', '')
                    }
                }
            )
        except Exception as e:
            logger.error(f"Broadcast error: {e}")
    
    def stop(self):
        """브로드캐스터 중지"""
        self.running = False
        if self.kis_client:
            self.kis_client.close()

# 글로벌 브로드캐스터 인스턴스 (지연 초기화)
broadcaster = None

def get_broadcaster():
    """브로드캐스터 인스턴스를 지연 초기화로 반환"""
    global broadcaster
    if broadcaster is None:
        broadcaster = RealTimePriceBroadcaster()
    return broadcaster 