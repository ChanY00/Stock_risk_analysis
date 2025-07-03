import os
import json
import requests
import logging
import threading
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from django.conf import settings
from .market_utils import market_utils

logger = logging.getLogger(__name__)

class KISMarketIndexClient:
    """KIS API를 통한 시장 지수 실시간 조회 클라이언트"""
    
    def __init__(self):
        self.app_key = getattr(settings, 'KIS_APP_KEY', os.getenv('KIS_APP_KEY'))
        self.app_secret = getattr(settings, 'KIS_APP_SECRET', os.getenv('KIS_APP_SECRET'))
        self.base_url = getattr(settings, 'KIS_BASE_URL', 'https://openapi.koreainvestment.com:9443')
        self.is_paper_trading = getattr(settings, 'KIS_IS_PAPER_TRADING', True)
        
        self.access_token = None
        self.token_expires_at = None
        self.running = False
        self.update_interval = 30  # 30초마다 업데이트
        self.callbacks = []  # 업데이트 콜백 리스트
        
        # 시장 지수 코드 정의
        self.market_indices = {
            'KOSPI': {
                'code': '0001',  # KOSPI 지수 코드
                'name': 'KOSPI',
                'market_div': 'J'
            },
            'KOSDAQ': {
                'code': '1001',  # KOSDAQ 지수 코드  
                'name': 'KOSDAQ',
                'market_div': 'Q'
            }
        }
        
        logger.info(f"🔧 KIS 시장 지수 클라이언트 초기화 ({'모의투자' if self.is_paper_trading else '실계좌'} 모드)")

    def _get_access_token(self) -> bool:
        """KIS API 액세스 토큰 발급"""
        try:
            # 기존 토큰이 유효한지 확인
            if self.access_token and self.token_expires_at:
                if datetime.now() < self.token_expires_at - timedelta(minutes=5):
                    return True

            url = f"{self.base_url}/oauth2/tokenP"
            
            headers = {
                'content-type': 'application/json'
            }
            
            data = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('access_token'):
                self.access_token = result['access_token']
                # 토큰 만료 시간 설정 (24시간 - 5분 여유)
                self.token_expires_at = datetime.now() + timedelta(hours=23, minutes=55)
                logger.info("✅ KIS 시장 지수용 액세스 토큰 발급 성공")
                return True
            else:
                logger.error(f"❌ 토큰 발급 실패: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 토큰 발급 오류: {e}")
            return False

    def get_market_index_data(self, index_code: str, market_div: str) -> Optional[Dict]:
        """특정 시장 지수 데이터 조회"""
        try:
            if not self._get_access_token():
                return None
                
            # KIS API 시장 지수 조회
            url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price"
            
            headers = {
                'content-type': 'application/json',
                'authorization': f'Bearer {self.access_token}',
                'appkey': self.app_key,
                'appsecret': self.app_secret,
                'tr_id': 'FHPUP02100000',  # 지수시세조회
                'custtype': 'P'
            }
            
            params = {
                'fid_cond_mrkt_div_code': market_div,  # J: KOSPI, Q: KOSDAQ
                'fid_input_iscd': index_code,          # 지수코드
                'fid_input_date_1': '',                # 조회 시작일 (공백: 당일)
                'fid_input_date_2': '',                # 조회 종료일 (공백: 당일)
                'fid_period_div_code': 'D'             # 기간구분 (D: 일간)
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('rt_cd') == '0' and result.get('output'):
                output = result['output']
                
                # KIS API 응답을 표준 형식으로 변환
                index_data = {
                    'code': index_code,
                    'name': self._get_index_name(index_code),
                    'current_value': float(output.get('bstp_nmix_prpr', 0)),      # 현재지수
                    'change': float(output.get('bstp_nmix_prdy_vrss', 0)),        # 전일대비
                    'change_percent': float(output.get('prdy_vrss_sign', 0)),     # 등락률
                    'volume': int(output.get('acml_vol', 0)),                     # 누적거래량
                    'trade_value': int(output.get('acml_tr_pbmn', 0)),            # 누적거래대금
                    'high': float(output.get('bstp_nmix_hgpr', 0)),               # 최고지수
                    'low': float(output.get('bstp_nmix_lwpr', 0)),                # 최저지수
                    'timestamp': datetime.now().isoformat(),
                    'source': 'kis_api'
                }
                
                logger.info(f"📊 {index_data['name']} 지수 조회 성공: {index_data['current_value']:,.2f} ({index_data['change']:+.2f}, {index_data['change_percent']:+.2f}%)")
                return index_data
            else:
                logger.error(f"❌ 지수 조회 실패: {result.get('msg1', 'Unknown error')}")
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
        """모든 시장 지수 데이터 조회 (Mock 데이터로 구현)"""
        try:
            # 개발/테스트용 Mock 데이터
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
            
            logger.info(f"📊 Mock 시장 지수 데이터 생성 완료")
            return mock_data
            
        except Exception as e:
            logger.error(f"❌ 시장 지수 데이터 생성 오류: {e}")
            return {}

    def start_real_time_updates(self, callback: Callable[[Dict], None]) -> bool:
        """실시간 시장 지수 업데이트 시작"""
        try:
            if self.running:
                logger.warning("⚠️ 이미 실시간 업데이트가 실행 중입니다")
                return False
            
            self.callbacks.append(callback)
            self.running = True
            
            # 별도 스레드에서 주기적 업데이트
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
                    # 시장 개장 중: 실시간 데이터 조회
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
        logger.info("🛑 시장 지수 실시간 업데이트 중지")

# 전역 인스턴스
market_index_client = KISMarketIndexClient() 