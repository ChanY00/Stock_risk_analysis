import requests
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import time
import threading

logger = logging.getLogger(__name__)

class TokenManager:
    """글로벌 토큰 관리자 - 싱글톤 패턴"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.access_token = None
                    cls._instance.token_expired = None
                    cls._instance.last_token_request = None
                    cls._instance.token_requesting = False  # 토큰 요청 중 플래그
                    cls._instance.request_lock = threading.Lock()
        return cls._instance
    
    def get_token(self, client) -> bool:
        """토큰 발급 (동시 요청 방지)"""
        with self.request_lock:
            # 이미 토큰 요청 중이면 대기
            if self.token_requesting:
                return False
                
            # 토큰이 유효하면 그대로 사용
            if self.access_token and self.token_expired and datetime.now() < self.token_expired:
                return True
            
            # 1분 제한 체크
            now = time.time()
            if self.last_token_request and (now - self.last_token_request) < 60:
                wait_time = 60 - (now - self.last_token_request)
                logger.warning(f"Token request rate limit. Wait {wait_time:.1f} seconds")
                return False
            
            # 토큰 요청 시작
            self.token_requesting = True
            try:
                success = self._request_new_token(client)
                return success
            finally:
                self.token_requesting = False
    
    def _request_new_token(self, client) -> bool:
        """실제 토큰 요청"""
        url = f"{client.base_url}/oauth2/tokenP"
        headers = {"Content-Type": "application/json"}
        data = {
            "grant_type": "client_credentials",
            "appkey": client.app_key,
            "appsecret": client.app_secret
        }
        
        try:
            self.last_token_request = time.time()
            response = requests.post(url, headers=headers, data=json.dumps(data))
            if response.status_code == 200:
                result = response.json()
                self.access_token = result.get('access_token')
                # 토큰 만료 시간 설정 (23시간으로 안전하게)
                self.token_expired = datetime.now() + timedelta(hours=23)
                logger.info("🔑 Access token obtained successfully")
                return True
            else:
                logger.error(f"Failed to get access token: {response.status_code}")
                if response.status_code == 403:
                    try:
                        error_info = response.json()
                        logger.error(f"API Error: {error_info}")
                    except:
                        logger.error(f"Response text: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error getting access token: {e}")
            return False

class KISApiClient:
    """한국투자증권 REST API 클라이언트"""
    
    def __init__(self, is_mock=True):
        # 모의투자 여부에 따라 URL 선택
        if is_mock:
            self.base_url = "https://openapivts.koreainvestment.com:29443"  # 모의투자용
        else:
            self.base_url = "https://openapi.koreainvestment.com:9443"   # 실계좌용
            
        self.app_key = os.getenv('KIS_APP_KEY')
        self.app_secret = os.getenv('KIS_APP_SECRET')
        self.is_mock = is_mock
        self.token_manager = TokenManager()  # 글로벌 토큰 관리자 사용
        
        if not self.app_key or not self.app_secret:
            logger.warning("KIS API credentials not found in environment variables")
    
    def _get_headers(self, tr_id: str) -> Dict[str, str]:
        """API 요청 헤더 생성"""
        headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.token_manager.access_token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
            "tr_id": tr_id
        }
        return headers
    
    def ensure_token(self) -> bool:
        """토큰 유효성 확인 및 갱신"""
        return self.token_manager.get_token(self)
    
    def get_current_price(self, stock_code: str) -> Optional[Dict]:
        """현재가 조회 (상세 로깅 포함)"""
        if not self.ensure_token():
            logger.error(f"Token validation failed for {stock_code}")
            return None
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = self._get_headers("FHKST01010100")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # J: 주식, ETF, ETN
            "FID_INPUT_ISCD": stock_code
        }
        
        try:
            logger.debug(f"🔍 Requesting price for {stock_code}: {url}")
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            logger.debug(f"📡 Response status for {stock_code}: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                # 응답 구조 확인
                if 'rt_cd' in result:
                    if result['rt_cd'] == '0':  # 성공
                        logger.debug(f"✅ {stock_code}: API call successful")
                        return result
                    else:
                        logger.error(f"❌ {stock_code}: API error - {result.get('msg1', 'Unknown error')}")
                        return None
                else:
                    logger.warning(f"⚠️ {stock_code}: Unexpected response structure")
                    return result
                    
            elif response.status_code == 429:
                logger.warning(f"⏰ {stock_code}: Rate limited")
                return None
            elif response.status_code == 500:
                logger.error(f"🔥 {stock_code}: Server error 500")
                try:
                    error_detail = response.json()
                    logger.error(f"🔥 {stock_code}: Error details: {error_detail}")
                except:
                    logger.error(f"🔥 {stock_code}: Error response: {response.text[:200]}")
                return None
            else:
                logger.error(f"❌ {stock_code}: HTTP {response.status_code}")
                logger.error(f"❌ {stock_code}: Response: {response.text[:200]}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"⏰ {stock_code}: Request timeout")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"🌐 {stock_code}: Connection error")
            return None
        except Exception as e:
            logger.error(f"💥 {stock_code}: Unexpected error: {type(e).__name__}: {e}")
            return None
    
    def get_daily_price(self, stock_code: str, period: str = "D") -> Optional[Dict]:
        """일봉 데이터 조회"""
        if not self.ensure_token():
            return None
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        headers = self._get_headers("FHKST01010400")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code,
            "FID_PERIOD_DIV_CODE": period,  # D: 일봉, W: 주봉, M: 월봉
            "FID_ORG_ADJ_PRC": "1"  # 0: 수정주가 미반영, 1: 수정주가 반영
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get daily price for {stock_code}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting daily price for {stock_code}: {e}")
            return None
    
    def get_orderbook(self, stock_code: str) -> Optional[Dict]:
        """호가 정보 조회"""
        if not self.ensure_token():
            return None
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn"
        headers = self._get_headers("FHKST01010200")
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": stock_code
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get orderbook for {stock_code}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting orderbook for {stock_code}: {e}")
            return None
    
    def search_stock_info(self, keyword: str) -> Optional[Dict]:
        """종목 검색"""
        if not self.ensure_token():
            return None
            
        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/search-stock-info"
        headers = self._get_headers("CTPF1002R")
        
        params = {
            "PRDT_TYPE_CD": "S",  # S: 주식
            "PDNO": keyword,
            "PRDT_NAME": keyword
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to search stock info for {keyword}: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error searching stock info for {keyword}: {e}")
            return None 