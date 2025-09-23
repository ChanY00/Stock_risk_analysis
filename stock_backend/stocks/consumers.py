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
from . import ws_loop
from .ws_schema import (
    WS_TYPE_CONNECTION_STATUS,
    WS_TYPE_PRICE_UPDATE,
    WS_TYPE_SUBSCRIBE_RESPONSE,
    WS_TYPE_UNSUBSCRIBE_RESPONSE,
    WS_TYPE_ERROR,
)
from .ws_utils import get_group_name_for_stock

logger = logging.getLogger(__name__)
performance_logger = logging.getLogger('performance')

# Debug-gated logging helpers (INFO/WARN only when DEBUG=True)
from django.conf import settings as _settings
def _dinfo(msg: str):
    try:
        if getattr(_settings, 'DEBUG', False):
            logger.info(msg)
    except Exception:
        pass
def _dwarn(msg: str):
    try:
        if getattr(_settings, 'DEBUG', False):
            logger.warning(msg)
    except Exception:
        pass

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
        # Delegate to reusable utility to manage loop/thread
        ws_loop.ensure_started()
        if getattr(_settings, 'DEBUG', False):
            performance_logger.info("Single broadcast thread ensured started")
        
    def add_client(self, client_id: str):
        """클라이언트 추가"""
        with self.lock:
            self.connected_clients[client_id] = set()
            _dinfo(f"📱 Client {client_id} added. Total clients: {len(self.connected_clients)}")
            
            # 첫 번째 클라이언트일 때 KIS 연결
            if len(self.connected_clients) == 1:
                self._initialize_kis_client()
    
    def remove_client(self, client_id: str):
        """클라이언트 제거 및 불필요한 구독 정리"""
        with self.lock:
            if client_id in self.connected_clients:
                client_subscriptions = self.connected_clients[client_id]
                del self.connected_clients[client_id]
                
                _dinfo(f"📱 Client {client_id} removed. Remaining clients: {len(self.connected_clients)}")
                
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
            
            _dinfo(f"📊 Client {client_id} subscribed to {len(new_subscriptions)} new stocks")
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
            _dinfo("🔌 Initializing Global KIS WebSocket client...")
            
            # 시장 상태 우선 확인
            is_open, reason = market_utils.is_market_open()
            
            if not is_open:
                _dinfo(f"🔴 시장 휴장 중 ({reason}) - API 연결 없이 휴장일 모드 활성화")
                self.kis_client = None
                self.market_closed_mode = True
                return
            
            # Django 설정 확인
            use_mock = getattr(settings, 'KIS_USE_MOCK', False)
            is_paper_trading = getattr(settings, 'KIS_IS_PAPER_TRADING', True)
            app_key = getattr(settings, 'KIS_APP_KEY', None)
            app_secret = getattr(settings, 'KIS_APP_SECRET', None)
            
            _dinfo("📋 KIS 설정 확인:")
            _dinfo(f"   - USE_MOCK: {use_mock}")
            _dinfo(f"   - PAPER_TRADING: {is_paper_trading} ({'모의투자' if is_paper_trading else '실계좌'})")
            _dinfo(f"   - APP_KEY: {'설정됨' if app_key else '없음'} ({app_key[:10] + '...' if app_key else 'None'})")
            _dinfo(f"   - APP_SECRET: {'설정됨' if app_secret else '없음'}")
            
            # Wrapper 사용 강제
            try:
                self.kis_client = KISWebSocketClient(is_mock=use_mock)
            except Exception as e:
                logger.error(f"❌ KIS 클라이언트 생성 오류: {e}")
                self.kis_client = None
                self.market_closed_mode = True
                self.connection_status = "error"
                return
            
            # USE_MOCK인 경우에도 wrapper가 내부에서 mock 처리
            if not use_mock and (not app_key or not app_secret):
                logger.error("❌ KIS API 키가 설정되지 않았습니다!")
                self.market_closed_mode = True
                return
            
            # 연결 시도
            if self.kis_client.connect():
                _dinfo("✅ 전역 KIS API 클라이언트 연결 성공!")
                self.connection_status = "connected"
                self.market_closed_mode = False
                return
            else:
                logger.error("❌ KIS API 연결 실패")
                self.kis_client = None
                self.market_closed_mode = True
                self.connection_status = "error"
            
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
            _dinfo("🔌 Global KIS WebSocket client closed")
            if getattr(_settings, 'DEBUG', False):
                performance_logger.info("KIS WebSocket client closed")
    
    def _subscribe_to_kis(self, stock_code: str) -> bool:
        """KIS에 종목 구독 (휴장일 대응 포함)"""
        try:
            # 휴장일 모드일 때 처리
            if self.market_closed_mode or not self.kis_client:
                _dinfo(f"🔴 휴장일 모드 - {stock_code} 이전 거래일 종가 제공 시도")
                
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
                _dwarn(f"⚠️ Broadcast loop not available for {stock_code}")
                
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
                _dwarn(f"❌ 종목 {stock_code}를 데이터베이스에서 찾을 수 없습니다")
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
            
            _dinfo(f"💾 {stock_code}({stock_name}) 휴장일 종가 데이터 제공: {mock_price_data['current_price']:,}원")
            
        except Exception as e:
            logger.error(f"❌ {stock_code} 휴장일 처리 오류: {e}")
    
    def _unsubscribe_from_kis(self, stock_code: str) -> bool:
        """KIS에서 종목 구독 해제"""
        if not self.kis_client:
            return False
        
        try:
            success = self.kis_client.unsubscribe_stock(stock_code)
            if success:
                _dinfo(f"📊 Global subscription removed for {stock_code}")
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
                if getattr(_settings, 'DEBUG', False):
                    performance_logger.info(
                        f"Price callback performance: {self._callback_count} callbacks, "
                        f"{len(self.connected_clients)} clients"
                    )
                self._last_performance_log = current_time
                self._callback_count = 0
            
            # 정보 로그 빈도 줄이기 (100번에 1번)
            if getattr(_settings, 'DEBUG', False) and self._callback_count % 100 == 1:
                logger.info(f"💰 Received price data: {stock_code} = {price_data.get('current_price')}")
            
            # 🔧 실제 거래량 데이터 보강 (모의투자 모드에서만)
            enhanced_price_data = self._enhance_with_real_volume(price_data)
            
            # 시장 상태에 따른 데이터 보강
            enhanced_data = get_enhanced_price_data(stock_code, enhanced_price_data)
            
            # Django Channels를 통해 브로드캐스트 (최적화된 방식)
            # Submit to background loop via utility
            future = ws_loop.submit_coroutine(self._async_broadcast(enhanced_data, stock_code))
                
            # 논블로킹 완료 체크 (성능 최적화)
            if future and self._callback_count % 50 == 1:
                try:
                    future.result(timeout=0.1)  # 100ms 타임아웃
                except Exception:
                    pass  # 타임아웃이나 기타 에러 무시
                
        except Exception as e:
            # 에러 로그도 빈도 줄이기
            if self._callback_count % 100 == 1:
                logger.error(f"Price callback error: {e}")
    
    def _enhance_with_real_volume(self, price_data: Dict) -> Dict:
        """실제 거래량 데이터로 보강: 캐시 병합만 수행 (핫패스 비동기)"""
        try:
            if not getattr(settings, 'WS_ENABLE_VOLUME_ENHANCEMENT', False):
                return price_data
            stock_code = price_data.get('stock_code')
            if not stock_code:
                return price_data
            cached = get_cached_volume(stock_code)
            if not cached:
                return price_data
            enhanced_data = price_data.copy()
            enhanced_data.update({
                'volume': cached.get('volume', price_data.get('volume', 0)),
                'trading_value': cached.get('trading_value', price_data.get('trading_value', 0)),
                'volume_source': cached.get('source', 'cache'),
            })
            return enhanced_data
        except Exception as e:
            logger.warning(f"거래량 보강 실패: {e}")
            return price_data

    # REST 직접 호출 로직 제거(백그라운드 캐시 방식으로 대체)

    # 제거됨: TokenManager 기반으로 통일

    # 제거됨: TokenManager 기반으로 통일
    
    async def _async_broadcast(self, enhanced_data: Dict, stock_code: str):
        """
        최적화된 비동기 브로드캐스트
        - 변경점(Step 1): 단일 그룹("stock_prices") → 종목별 그룹으로 전송
        - 그룹 네이밍: Channels 제약(영문/숫자/하이픈/언더스코어 권장)을 고려해 `stock_<code>` 사용
        """
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                return

            # 종목별 그룹으로만 전송하여, 구독하지 않은 클라이언트에게는 전송되지 않도록 함
            group_name = get_group_name_for_stock(stock_code)
            await channel_layer.group_send(
                group_name,
                {
                    "type": WS_TYPE_PRICE_UPDATE,  # Consumer의 handler 메서드명과 매칭
                    "data": enhanced_data
                }
            )

            # 성공 로그 빈도 줄이기 (200번에 1번)
            if getattr(_settings, 'DEBUG', False) and self._callback_count % 200 == 1:
                logger.info(f"✅ Price broadcasted to {group_name}")

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
            # 이 연결(채널)이 구독 중인 종목코드를 추적하기 위한 로컬 상태
            # - 변경점(Step 1): 단일 그룹에서 종목별 그룹으로 전환되었으므로
            #   disconnect 시 각 종목 그룹에서 정확히 제거하기 위해 필요
            self.subscribed_codes = set()
            
            # 연결 수락
            await self.accept()
            _dinfo(f"📱 WebSocket connection accepted for {self.client_id}")
            
            # 변경점(Step 1): 더 이상 단일 그룹("stock_prices")에 참가하지 않음
            # 각 종목 구독 시점에 종목별 그룹에 참가하도록 변경
            
            # 글로벌 관리자에 클라이언트 추가
            global_subscription_manager.add_client(self.client_id)
            
            # 연결 확인 메시지
            await self.send(text_data=json.dumps({
                'type': WS_TYPE_CONNECTION_STATUS,
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
            # 변경점(Step 1): 이 채널이 가입했던 모든 종목별 그룹에서 제거
            for code in list(self.subscribed_codes):
                group_name = f"stock_{code}"
                try:
                    await self.channel_layer.group_discard(group_name, self.channel_name)
                except Exception:
                    pass
            self.subscribed_codes.clear()
            
            # 글로벌 관리자에서 클라이언트 제거
            if hasattr(self, 'client_id'):
                global_subscription_manager.remove_client(self.client_id)
                _dinfo(f"📱 Client {self.client_id} disconnected")
                
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
                    'type': WS_TYPE_ERROR,
                    'message': 'stock_codes must be a non-empty list'
                }))
                return
            
            # 글로벌 관리자를 통해 구독 (KIS 측 구독 디듀플/연결 관리를 담당)
            new_subscriptions = global_subscription_manager.subscribe_stocks(
                self.client_id, stock_codes
            )
            
            # 변경점(Step 1): 클라이언트 채널을 종목별 그룹에 가입시킴
            # - 글로벌 신규/기존 여부와 관계없이 이 채널은 각 요청된 코드 그룹에 참가
            for code in stock_codes:
                group_name = get_group_name_for_stock(code)
                await self.channel_layer.group_add(group_name, self.channel_name)
                self.subscribed_codes.add(code)
            
            # 응답 전송
            await self.send(text_data=json.dumps({
                'type': WS_TYPE_SUBSCRIBE_RESPONSE,
                'subscribed': new_subscriptions,
                # total_subscriptions는 전역(KIS) 기준; 클라이언트 로컬 구독은 self.subscribed_codes 참고
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
            # 글로벌 관리자를 통해 KIS 구독 해제
            removed_subscriptions = global_subscription_manager.unsubscribe_stocks(
                self.client_id, stock_codes
            )
            
            # 변경점(Step 1): 이 채널을 종목별 그룹에서 제거
            for code in stock_codes:
                group_name = get_group_name_for_stock(code)
                try:
                    await self.channel_layer.group_discard(group_name, self.channel_name)
                except Exception:
                    pass
                self.subscribed_codes.discard(code)
            
            await self.send(text_data=json.dumps({
                'type': WS_TYPE_UNSUBSCRIBE_RESPONSE,
                'unsubscribed': removed_subscriptions,
                'total_subscriptions': global_subscription_manager.get_all_subscribed_stocks(),
                'message': f'{len(removed_subscriptions)}개 종목 구독 해제 완료'
            }))
            
        except Exception as e:
            logger.error(f"Unsubscribe error: {e}")

    async def price_update(self, event):
        """실시간 가격 업데이트 메시지 전송"""
        await self.send(text_data=json.dumps({
            'type': WS_TYPE_PRICE_UPDATE,
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
        """
        비동기 브로드캐스트
        - 변경점(Step 1): 단일 그룹 → 종목별 그룹 전송으로 변경
        - 이벤트 타입도 Consumer의 `price_update` 핸들러와 일치시킴
        """
        try:
            # channel_layer가 없으면 초기화
            if not self.channel_layer:
                self.channel_layer = get_channel_layer()

            stock_code = price_data.get('stock_code')
            if not stock_code:
                logger.warning("Broadcast skipped: missing stock_code in price_data")
                return

            group_name = get_group_name_for_stock(stock_code)
            await self.channel_layer.group_send(
                group_name,
                {
                    "type": WS_TYPE_PRICE_UPDATE,
                    "data": price_data
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
