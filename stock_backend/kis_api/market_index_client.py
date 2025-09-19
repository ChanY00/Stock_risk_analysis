import os
import json
import requests
import logging
import threading
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import websocket
from django.conf import settings
from .market_utils import market_utils
from .client import KISApiClient

logger = logging.getLogger(__name__)

class KISMarketIndexClient:
    """KIS API를 통한 시장 지수 실시간 조회 클라이언트"""
    
    def __init__(self):
        self.app_key = getattr(settings, 'KIS_APP_KEY', os.getenv('KIS_APP_KEY'))
        self.app_secret = getattr(settings, 'KIS_APP_SECRET', os.getenv('KIS_APP_SECRET'))
        self.base_url = getattr(settings, 'KIS_BASE_URL', 'https://openapi.koreainvestment.com:9443')
        self.is_paper_trading = getattr(settings, 'KIS_IS_PAPER_TRADING', True)
        
        # 전역 TokenManager를 공유하는 REST 클라이언트 사용
        self._client = KISApiClient(is_mock=self.is_paper_trading)
        self.running = False
        self.update_interval = 30  # 30초마다 업데이트
        self.callbacks = []  # 업데이트 콜백 리스트
        # WS 경로 제거: REST 폴링만 사용
        self._ws_client = None
        self._snapshot: Dict[str, Dict] = {}
        self._last_ws_update_ts: float = 0.0

        # 시장 지수 코드 정의 (초기화 시점에 설정되어야 함)
        self.market_indices = {
            'KOSPI': {
                'code': '0001',  # KOSPI 지수 코드
                'name': 'KOSPI',
                'market_div': 'J'
            },
            'KOSDAQ': {
                'code': '1001',  # KOSDAQ 지수 코드 (업종지수시세: 2001)
                'name': 'KOSDAQ',
                'market_div': 'Q'
            }
        }

    def _emit_update(self, partial: Dict[str, Dict]):
        return  # WS 비활성화
        
        logger.info(f"🔧 KIS 시장 지수 클라이언트 초기화 ({'모의투자' if self.is_paper_trading else '실계좌'} 모드)")

    def _ensure_token(self) -> bool:
        """TokenManager를 통해 전역적으로 보호된 토큰 확보"""
        try:
            return self._client.ensure_token()
        except Exception as e:
            logger.error(f"❌ 토큰 확보 오류: {e}")
            return False

    def get_market_index_data(self, index_code: str, market_div: str) -> Optional[Dict]:
        """특정 시장 지수 데이터 조회"""
        try:
            if not self._ensure_token():
                # brief wait then retry once, to allow lock-holder to cache token
                time.sleep(1.0)
                if not self._ensure_token():
                    return None
                
            # KIS API 시장 지수 조회
            url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price"
            
            # 문서 기준: inquire-index-price는 VTS에서도 FHPUP02100000 사용 사례가 확인됨
            # 환경 변수로 재정의 가능
            tr_id = os.getenv('KIS_INDEX_TR_ID') or 'FHPUP02100000'

            headers = {
                'Content-Type': 'application/json',
                'authorization': f'Bearer {self._client.token_manager.access_token}',
                'appkey': self.app_key,
                'appsecret': self.app_secret,
                'tr_id': tr_id,
                'custtype': 'P'
            }
            
            # 일부 환경에서 U가 아닌 시장구분코드(J:KOSPI, Q:KOSDAQ)를 요구할 수 있어 순차 시도
            param_variants = [
                {'FID_COND_MRKT_DIV_CODE': 'U', 'FID_INPUT_ISCD': index_code},
            ]
            if market_div in ('J', 'Q'):
                param_variants.append({'FID_COND_MRKT_DIV_CODE': market_div, 'FID_INPUT_ISCD': index_code})

            last_error: Optional[str] = None
            for params in param_variants:
                try:
                    response = requests.get(url, headers=headers, params=params, timeout=10)
                    # 일부 VTS에서 잘못된 파라미터는 500을 던질 수 있으므로 상태 확인 후 계속 시도
                    response.raise_for_status()
                    result = response.json()
                    if result.get('rt_cd') == '0' and result.get('output'):
                        output = result['output']
                        index_data = {
                            'code': index_code,
                            'name': self._get_index_name(index_code),
                            'current_value': float(output.get('bstp_nmix_prpr', 0)),
                            'change': float(output.get('bstp_nmix_prdy_vrss', 0)),
                            'change_percent': float(output.get('prdy_ctrt', 0)),
                            'volume': int(output.get('acml_vol', 0)),
                            'trade_value': int(output.get('acml_tr_pbmn', 0)),
                            'high': float(output.get('bstp_nmix_hgpr', 0)),
                            'low': float(output.get('bstp_nmix_lwpr', 0)),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'kis_api'
                        }
                        logger.info(
                            f"📊 {index_data['name']} 지수 조회 성공: {index_data['current_value']:,.2f} ({index_data['change']:+.2f}, {index_data['change_percent']:+.2f}%) params={params}"
                        )
                        return index_data
                    else:
                        last_error = f"rt_cd={result.get('rt_cd')} msg_cd={result.get('msg_cd')} msg1={result.get('msg1')}"
                        logger.warning(f"⚠️ 지수 조회 미성공: {last_error} params={params}")
                except Exception as req_err:
                    last_error = str(req_err)
                    logger.warning(f"⚠️ 지수 조회 시도 실패 params={params} error={req_err}")

            logger.error(
                f"❌ 지수 조회 최종 실패 index={index_code} tr_id={tr_id} last_error={last_error}"
            )
            return None
                
        except Exception as e:
            logger.error(f"❌ 지수 조회 오류 ({index_code}): {e}")
            return None

    def _get_index_name(self, index_code: str) -> str:
        """지수 코드에서 이름 반환"""
        for name, info in self.market_indices.items():
            if info['code'] == index_code:
                return name
        return f"INDEX_{index_code}"

    def get_all_market_indices(self) -> Dict[str, Dict]:
        """실제 시장 지수 데이터 조회(가급적 실데이터, 실패 시 Mock 폴백)"""
        try:
            indices: Dict[str, Dict] = {}
            kospi = self.get_market_index_data(self.market_indices['KOSPI']['code'], self.market_indices['KOSPI']['market_div'])
            kosdaq = self.get_market_index_data(self.market_indices['KOSDAQ']['code'], self.market_indices['KOSDAQ']['market_div'])

            if kospi:
                indices['kospi'] = {
                    'current': kospi.get('current_value', 0),
                    'change': kospi.get('change', 0),
                    'change_percent': kospi.get('change_percent', 0),
                    'volume': kospi.get('volume', 0),
                    'high': kospi.get('high', 0),
                    'low': kospi.get('low', 0),
                    'trade_value': kospi.get('trade_value', 0),
                }
            if kosdaq:
                indices['kosdaq'] = {
                    'current': kosdaq.get('current_value', 0),
                    'change': kosdaq.get('change', 0),
                    'change_percent': kosdaq.get('change_percent', 0),
                    'volume': kosdaq.get('volume', 0),
                    'high': kosdaq.get('high', 0),
                    'low': kosdaq.get('low', 0),
                    'trade_value': kosdaq.get('trade_value', 0),
                }

            # 둘 다 실패 시 Mock 폴백 (명시적으로 허용되는 경우에만)
            if not indices:
                if getattr(settings, 'KIS_USE_MOCK', False):
                    mock_data = {
                        'kospi': {
                            'current': 2650.5 + random.uniform(-10, 10),
                            'change': random.uniform(-20, 20),
                            'change_percent': random.uniform(-1, 1),
                            'volume': random.randint(400000000, 500000000),
                            'high': 2665.0,
                            'low': 2640.0,
                            'trade_value': random.randint(8000000000000, 9000000000000)
                        },
                        'kosdaq': {
                            'current': 850.2 + random.uniform(-5, 5),
                            'change': random.uniform(-10, 10),
                            'change_percent': random.uniform(-0.8, 0.8),
                            'volume': random.randint(600000000, 700000000),
                            'high': 855.0,
                            'low': 845.0,
                            'trade_value': random.randint(3000000000000, 4000000000000)
                        }
                    }
                    logger.info("📊 Mock 시장 지수 데이터 폴백 사용")
                    return mock_data
                else:
                    logger.error("❌ KIS 지수 데이터를 가져오지 못했으며 Mock 폴백이 비활성화되어 빈 결과를 반환합니다")
                    return {}

            logger.info(f"📊 시장 지수 업데이트 완료 ({list(indices.keys())})")
            return indices
        except Exception as e:
            logger.error(f"❌ 시장 지수 데이터 조회 오류: {e}")
            return {}

    def start_real_time_updates(self, callback: Callable[[Dict], None]) -> bool:
        """실시간 시장 지수 업데이트 시작"""
        try:
            if self.running:
                logger.warning("⚠️ 이미 실시간 업데이트가 실행 중입니다")
                return False
            
            self.callbacks.append(callback)
            self.running = True
            
            # WS 구독 제거: REST 폴링만 사용

            # 2) 별도 스레드에서 주기적 REST 폴백 업데이트 (WS 실패 시)
            update_thread = threading.Thread(
                target=self._update_loop,
                daemon=True,
                name="KIS-MarketIndex-Updater"
            )
            update_thread.start()
            
            logger.info(f"🚀 시장 지수 실시간 업데이트 시작 ({self.update_interval}초 간격)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 실시간 업데이트 시작 오류: {e}")
            return False

    def _update_loop(self):
        """실시간 업데이트 루프"""
        logger.info("🔄 시장 지수 업데이트 루프 시작")
        
        while self.running:
            try:
                # 시장 개장 여부 확인
                is_open, reason = market_utils.is_market_open()
                
                if is_open:
                    # REST 폴링만 수행 (모의/실계좌 공통)
                    indices_data = self.get_all_market_indices()
                    if indices_data:
                        for callback in self.callbacks:
                            try:
                                callback(indices_data)
                            except Exception as e:
                                logger.error(f"❌ 시장 지수 콜백 오류: {e}")
                    time.sleep(self.update_interval)
                    continue

                    # 실계좌 환경: WS가 없다면 REST로 주기 갱신
                    if self._ws_client and self._ws_client.is_connected:
                        time.sleep(self.update_interval)
                        continue
                    indices_data = self.get_all_market_indices()
                    
                    if indices_data:
                        # 모든 콜백 호출
                        for callback in self.callbacks:
                            try:
                                callback(indices_data)
                            except Exception as e:
                                logger.error(f"❌ 시장 지수 콜백 오류: {e}")
                    
                    logger.info(f"📊 시장 지수 업데이트 완료 ({len(indices_data)}개 지수)")
                else:
                    # 시장 휴장 중: 장기 대기
                    logger.info(f"🔴 시장 휴장 중 ({reason}) - 업데이트 대기")
                    time.sleep(300)  # 5분 대기
                    continue
                    
                # 다음 업데이트까지 대기
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ 시장 지수 업데이트 루프 오류: {e}")
                time.sleep(60)  # 오류 시 1분 대기

    def add_callback(self, callback: Callable[[Dict], None]):
        """콜백 추가"""
        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback: Callable[[Dict], None]):
        """콜백 제거"""
        if callback in self.callbacks:
            self.callbacks.remove(callback)

    def stop(self):
        """실시간 업데이트 중지"""
        self.running = False
        try:
            # WS 클라이언트 제거
            self._ws_client = None
        except Exception:
            pass
        logger.info("🛑 시장 지수 실시간 업데이트 중지")

# 전역 인스턴스
market_index_client = KISMarketIndexClient() 


class KISMarketIndexWSClient:
    """KIS WebSocket 클라이언트 (시장 지수 전용) - H0IXASP0 구독"""

    def __init__(self, app_key: str, app_secret: str, base_url: str, ws_url: str, is_paper_trading: bool, on_update: Callable[[Dict], None]):
        self.app_key = app_key
        self.app_secret = app_secret
        self.base_url = base_url
        self.ws_url = ws_url
        self.is_paper_trading = is_paper_trading
        self.on_update = on_update

        # Token/Approval 관리
        from .client import KISApiClient
        self._client = KISApiClient(is_mock=is_paper_trading)
        self._approval_key: Optional[str] = None

        # WS 상태
        self.ws: Optional[websocket.WebSocketApp] = None
        self.is_connected: bool = False
        self._thread: Optional[threading.Thread] = None
        self._subscribed: set[str] = set()
        self.timeout = 15
        self.ping_interval = getattr(settings, 'KIS_PING_INTERVAL', 30)
        self._last_codes: List[str] = []

    def _get_approval_key(self) -> bool:
        try:
            if not self._client.ensure_token():
                return False
            url = f"{self.base_url}/oauth2/Approval"
            headers = {
                'Content-Type': 'application/json',
                'authorization': f'Bearer {self._client.token_manager.access_token}',
                'appkey': self.app_key,
                'appsecret': self.app_secret,
            }
            data = {
                'grant_type': 'client_credentials',
                'appkey': self.app_key,
                'secretkey': self.app_secret,
            }
            resp = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            if resp.status_code == 200:
                body = resp.json()
                self._approval_key = body.get('approval_key')
                logger.info("✅ 지수용 Approval Key 발급 성공")
                return True
            logger.error(f"❌ 지수 Approval 실패: {resp.status_code} {resp.text[:200]}")
            return False
        except Exception as e:
            logger.error(f"❌ 지수 Approval 오류: {e}")
            return False

    def connect_and_subscribe(self, index_codes: List[str]) -> bool:
        try:
            if not self._get_approval_key():
                return False

            websocket.setdefaulttimeout(self.timeout)
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
            )

            self._thread = threading.Thread(target=self._run, daemon=True, name="KIS-Index-WS")
            self._thread.start()

            # 접속 대기 후 구독 전송
            waited = 0
            while not self.is_connected and waited < 10:
                time.sleep(1)
                waited += 1
            if not self.is_connected:
                return False

            self._last_codes = list(index_codes)
            for code in index_codes:
                self._subscribe_index(code)
            return True
        except Exception as e:
            logger.error(f"❌ 지수 WS 연결 실패: {e}")
            return False

    def _run(self):
        try:
            self.ws.run_forever(ping_interval=self.ping_interval, ping_timeout=10, ping_payload="ping")  # type: ignore[union-attr]
        except Exception as e:
            logger.error(f"❌ 지수 WS 실행 오류: {e}")

    def _on_open(self, ws):
        self.is_connected = True
        logger.info("🟢 지수 WebSocket 연결됨")

    def _on_error(self, ws, error):
        logger.error(f"🔴 지수 WebSocket 오류: {error}")

    def _on_close(self, ws, code, msg):
        self.is_connected = False
        logger.warning(f"🟡 지수 WebSocket 종료: {code} {msg}")
        # 간단한 재연결 시도
        try:
            time.sleep(2)
            if self._last_codes:
                self.connect_and_subscribe(self._last_codes)
        except Exception:
            pass

    def _subscribe_index(self, index_code: str):
        try:
            if not self.is_connected or not self._approval_key:
                return
            # KIS 문서 포맷에 맞는 메시지 작성
            msg = {
                "header": {
                    "approval_key": self._approval_key,
                    "custtype": "P",
                    "tr_type": "1",
                    "content-type": "utf-8",
                },
                "body": {
                    "input": {
                        "tr_id": "H0IXASP0",
                        "tr_key": index_code,
                    }
                },
            }
            self.ws.send(json.dumps(msg))  # type: ignore[union-attr]
            self._subscribed.add(index_code)
            logger.info(f"📤 지수 구독 전송: tr_id=H0IXASP0 tr_key={index_code}")
        except Exception as e:
            logger.error(f"❌ 지수 구독 오류({index_code}): {e}")

    def _on_message(self, ws, message: str):
        try:
            # JSON 형태 우선 처리
            if message.startswith('{'):
                obj = json.loads(message)
                tr_id = obj.get('body', {}).get('tr_id') or obj.get('header', {}).get('tr_id')
                if tr_id == 'H0IXASP0':
                    # 실제 필드명은 문서에 따르되, 최소 변환 시도 후 콜백
                    body = obj.get('body', {})
                    output = body.get('output') or {}
                    idx_code = body.get('tr_key') or output.get('index_code') or 'UNKNOWN'
                    data = {
                        'code': idx_code,
                        'name': 'KOSPI' if idx_code == '0001' else ('KOSDAQ' if idx_code == '1001' else idx_code),
                        'current_value': float(output.get('bstp_nmix_prpr', output.get('current', 0)) or 0),
                        'change': float(output.get('bstp_nmix_prdy_vrss', output.get('change', 0)) or 0),
                        'change_percent': float(output.get('prdy_vrss_sign', output.get('change_percent', 0)) or 0),
                        'volume': int(output.get('acml_vol', output.get('volume', 0)) or 0),
                        'trade_value': int(output.get('acml_tr_pbmn', output.get('trade_value', 0)) or 0),
                        'high': float(output.get('bstp_nmix_hgpr', output.get('high', 0)) or 0),
                        'low': float(output.get('bstp_nmix_lwpr', output.get('low', 0)) or 0),
                        'timestamp': datetime.now().isoformat(),
                        'source': 'kis_ws_index',
                    }
                    self.on_update({data['name'].lower(): data})
                    return

            # 텍스트 파이프 구분 형식 폴백
            if message.startswith('0|'):
                parts = message.split('|')
                # 최소한 인덱스 코드가 포함되어 있는지 탐색
                idx_code = None
                for code in ['0001', '1001']:
                    if code in message:
                        idx_code = code
                        break
                name = 'KOSPI' if idx_code == '0001' else ('KOSDAQ' if idx_code == '1001' else 'INDEX')
                data = {
                    'code': idx_code or 'UNKNOWN',
                    'name': name,
                    'current_value': 0,
                    'change': 0,
                    'change_percent': 0,
                    'volume': 0,
                    'trade_value': 0,
                    'high': 0,
                    'low': 0,
                    'timestamp': datetime.now().isoformat(),
                    'source': 'kis_ws_index_raw',
                }
                self.on_update({name.lower(): data})
        except Exception as e:
            logger.error(f"❌ 지수 메시지 처리 오류: {e}")

    def close(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass