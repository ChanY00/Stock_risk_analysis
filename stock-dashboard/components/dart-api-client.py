"""
DART API 클라이언트
금융감독원 전자공시시스템 API를 활용한 재무데이터 수집
"""

import requests
import pandas as pd
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
import time
import logging

logger = logging.getLogger(__name__)

class DartAPIClient:
    """DART API 클라이언트"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://opendart.fss.or.kr/api"
        self.session = requests.Session()
        
    def get_corp_list(self) -> Dict[str, str]:
        """
        전체 기업 목록과 고유번호 매핑 조회
        Returns: {stock_code: corp_code} 딕셔너리
        """
        url = f"{self.base_url}/corpCode.xml"
        params = {"crtfc_key": self.api_key}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # ZIP 파일 압축 해제
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                xml_content = zip_file.read('CORPCODE.xml')
            
            # XML 파싱
            root = ET.fromstring(xml_content)
            corp_mapping = {}
            
            for item in root.findall('.//list'):
                corp_code = item.findtext('corp_code', '').strip()
                stock_code = item.findtext('stock_code', '').strip()
                corp_name = item.findtext('corp_name', '').strip()
                
                if stock_code and corp_code:  # 상장기업만
                    corp_mapping[stock_code] = corp_code
                    
            logger.info(f"✅ 기업 목록 조회 완료: {len(corp_mapping)}개 상장기업")
            return corp_mapping
            
        except Exception as e:
            logger.error(f"❌ 기업 목록 조회 실패: {str(e)}")
            return {}
    
    def get_financial_statement(self, corp_code: str, bsns_year: int, 
                              reprt_code: str = '11011') -> Optional[Dict]:
        """
        단일회사 재무제표 조회
        
        Args:
            corp_code: 기업 고유번호
            bsns_year: 사업연도 (2023)
            reprt_code: 보고서코드 (11011: 사업보고서, 11012: 반기보고서, 11013: 1분기, 11014: 3분기)
        """
        url = f"{self.base_url}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": str(bsns_year),
            "reprt_code": reprt_code,
            "fs_div": "CFS"  # CFS: 연결재무제표, OFS: 별도재무제표
        }
        
        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != '000':
                logger.warning(f"⚠️  API 응답 오류: {data.get('message', 'Unknown error')}")
                return None
                
            return data.get('list', [])
            
        except Exception as e:
            logger.error(f"❌ 재무제표 조회 실패 (corp_code: {corp_code}): {str(e)}")
            return None
    
    def parse_financial_data(self, raw_data: List[Dict], year: int) -> Optional[Dict]:
        """
        DART API 응답 데이터를 우리 시스템 형식으로 변환
        """
        if not raw_data:
            return None
            
        # 주요 재무항목 매핑 (DART 계정명 -> 우리 시스템)
        account_mapping = {
            # 손익계산서
            '매출액': 'revenue',
            '영업이익': 'operating_income', 
            '당기순이익': 'net_income',
            '주당순이익': 'eps',
            # 재무상태표
            '자산총계': 'total_assets',
            '부채총계': 'total_liabilities', 
            '자본총계': 'total_equity',
        }
        
        financial_data = {
            'year': year,
            'revenue': 0,
            'operating_income': 0,
            'net_income': 0,
            'eps': 0.0,
            'total_assets': None,
            'total_liabilities': None,
            'total_equity': None,
        }
        
        try:
            for item in raw_data:
                account_nm = item.get('account_nm', '').strip()
                thstrm_amount = item.get('thstrm_amount', '0').replace(',', '')
                
                # 계정명 매핑 확인
                if account_nm in account_mapping:
                    field_name = account_mapping[account_nm]
                    
                    try:
                        # 숫자 변환
                        if field_name == 'eps':
                            financial_data[field_name] = float(thstrm_amount) if thstrm_amount and thstrm_amount != '-' else 0.0
                        else:
                            # DART API 데이터는 이미 원(KRW) 단위입니다
                            amount = int(thstrm_amount) if thstrm_amount and thstrm_amount != '-' else 0
                            financial_data[field_name] = amount  # 변환 없이 그대로 사용
                            
                    except (ValueError, TypeError):
                        logger.warning(f"⚠️  숫자 변환 실패: {account_nm} = {thstrm_amount}")
                        continue
            
            # 기본 검증: 매출액이 있어야 유효한 데이터로 간주
            if financial_data['revenue'] > 0:
                return financial_data
            else:
                logger.warning(f"⚠️  유효하지 않은 재무데이터 (매출액 없음)")
                return None
                
        except Exception as e:
            logger.error(f"❌ 재무데이터 파싱 실패: {str(e)}")
            return None
    
    def fetch_company_financials(self, stock_code: str, corp_code: str, 
                               years: List[int] = [2023, 2022]) -> Dict[int, Dict]:
        """
        특정 기업의 여러 연도 재무데이터 수집
        
        Returns:
            {2023: {재무데이터}, 2022: {재무데이터}} 형식
        """
        results = {}
        
        for year in years:
            logger.info(f"📊 {stock_code} {year}년 재무데이터 조회 중...")
            
            # 사업보고서 우선 시도
            raw_data = self.get_financial_statement(corp_code, year, '11011')
            
            if raw_data:
                parsed_data = self.parse_financial_data(raw_data, year)
                if parsed_data:
                    results[year] = parsed_data
                    logger.info(f"✅ {stock_code} {year}년 데이터 수집 성공")
                else:
                    logger.warning(f"⚠️  {stock_code} {year}년 데이터 파싱 실패")
            else:
                logger.warning(f"⚠️  {stock_code} {year}년 데이터 없음")
            
            # API 호출 제한 방지
            time.sleep(0.1)
        
        return results
    
    def test_connection(self) -> bool:
        """API 연결 테스트"""
        try:
            corp_list = self.get_corp_list()
            if corp_list:
                logger.info(f"✅ DART API 연결 성공 ({len(corp_list)}개 기업 확인)")
                return True
            else:
                logger.error("❌ DART API 연결 실패: 기업 목록을 가져올 수 없음")
                return False
        except Exception as e:
            logger.error(f"❌ DART API 연결 테스트 실패: {str(e)}")
            return False

# 사용 예시
if __name__ == "__main__":
    # DART API 키 설정 (실제 사용시에는 환경변수나 설정파일에서 가져오기)
    API_KEY = "your_dart_api_key_here"
    
    client = DartAPIClient(API_KEY)
    
    # 연결 테스트
    if client.test_connection():
        # 삼성전자 재무데이터 조회 예시
        corp_mapping = client.get_corp_list()
        samsung_corp_code = corp_mapping.get('005930')
        
        if samsung_corp_code:
            financials = client.fetch_company_financials('005930', samsung_corp_code)
            print(f"삼성전자 재무데이터: {financials}") 