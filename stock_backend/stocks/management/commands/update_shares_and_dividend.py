"""
발행주식수 및 배당수익률 업데이트 관리 명령어

KIS API에서 발행주식수를 가져오고,
DART API나 외부 소스에서 배당수익률을 수집하여 DB에 업데이트합니다.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from stocks.models import Stock
from kis_api.client import KISApiClient
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Optional
import time
import logging
import os

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '발행주식수 및 배당수익률을 수집하고 업데이트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 처리',
        )
        parser.add_argument(
            '--update-shares-only',
            action='store_true',
            help='발행주식수만 업데이트',
        )
        parser.add_argument(
            '--update-dividend-only',
            action='store_true',
            help='배당수익률만 업데이트',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='기존 데이터가 있어도 덮어쓰기',
        )

    def handle(self, *args, **options):
        stock_codes = options.get('stock_codes')
        update_shares_only = options.get('update_shares_only', False)
        update_dividend_only = options.get('update_dividend_only', False)
        overwrite = options.get('overwrite', False)

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 발행주식수 및 배당수익률 업데이트'))
        self.stdout.write('=' * 70 + '\n')

        # 대상 종목 필터링
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            stocks = Stock.objects.all()

        total = stocks.count()
        self.stdout.write(f'📊 처리 대상: {total}개 종목\n')

        # KIS API 클라이언트 초기화
        is_mock = os.getenv('KIS_IS_MOCK', 'True').lower() == 'true'
        kis_client = KISApiClient(is_mock=is_mock)

        # DART API 키 확인 (배당수익률 수집용)
        dart_api_key = os.getenv('DART_API_KEY')
        
        updated_shares = 0
        updated_dividend = 0
        failed_count = 0

        # DART 기업 고유번호 매핑을 한 번만 조회 (캐싱)
        corp_mapping = {}
        if dart_api_key and not update_shares_only:
            self.stdout.write('DART 기업 고유번호 매핑 조회 중...\n')
            corp_mapping = self.get_all_corp_mapping(dart_api_key)
            self.stdout.write(f'✅ {len(corp_mapping)}개 기업 정보 로드 완료\n\n')

        for i, stock in enumerate(stocks, 1):
            if i % 10 == 0:
                self.stdout.write(f'진행률: {i}/{total}...')

            try:
                # 1. 발행주식수 업데이트 (KIS API에서 가져오기)
                if not update_dividend_only:
                    shares_updated = self.update_shares_outstanding(
                        stock, kis_client, overwrite
                    )
                    if shares_updated:
                        updated_shares += 1

                # 2. 배당수익률 업데이트 (corp_mapping 재사용)
                if not update_shares_only:
                    dividend_updated = self.update_dividend_yield(
                        stock, kis_client, dart_api_key, overwrite, corp_mapping
                    )
                    if dividend_updated:
                        updated_dividend += 1

                # API 호출 제한 방지 (배당수익률 조회 시 DART API 호출하므로 더 긴 대기)
                if not update_shares_only:
                    time.sleep(0.15)  # DART API 제한 고려
                else:
                    time.sleep(0.1)  # KIS API만 사용할 때는 짧게

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ {stock.stock_name} ({stock.stock_code}): {str(e)}')
                )
                failed_count += 1
                logger.exception(f"Error updating {stock.stock_code}: {e}")

        # 결과 출력
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 업데이트 완료'))
        self.stdout.write('=' * 70 + '\n')

        if not update_dividend_only:
            self.stdout.write(f'발행주식수 업데이트: {updated_shares}개')
        if not update_shares_only:
            self.stdout.write(f'배당수익률 업데이트: {updated_dividend}개')
        
        self.stdout.write(f'실패: {failed_count}개')
        self.stdout.write(f'전체: {total}개\n')

        # 시가총액 재계산 안내
        self.stdout.write('=' * 70)
        self.stdout.write('💡 시가총액 재계산 안내')
        self.stdout.write('=' * 70)
        self.stdout.write('발행주식수가 업데이트되었으므로, 시가총액을 재계산하는 것을 권장합니다:')
        self.stdout.write('  python manage.py verify_market_cap_and_dividend --fix')
        self.stdout.write()

    def update_shares_outstanding(self, stock: Stock, kis_client: KISApiClient, overwrite: bool) -> bool:
        """발행주식수 업데이트 (KIS API 또는 DART API에서)"""
        
        # 이미 값이 있고 overwrite가 아니면 스킵
        if stock.shares_outstanding and not overwrite:
            return False

        try:
            shares = None
            
            # 방법 1: DART API에서 발행주식수 가져오기 (더 정확)
            dart_api_key = os.getenv('DART_API_KEY')
            if dart_api_key:
                shares = self.get_shares_from_dart(stock, dart_api_key)
            
            # 방법 2: DART에서 가져올 수 없으면 KIS API에서 상장주식수 사용
            if shares is None:
                response = kis_client.get_current_price(stock.stock_code)
                
                if response and 'output' in response:
                    output = response['output']
                    lstn_stcn = output.get('lstn_stcn', '0')  # 상장주식수
                    
                    if lstn_stcn and lstn_stcn != '0':
                        shares = int(lstn_stcn)
            
            if shares and shares > 0:
                # 기존 값과 다르면 업데이트
                old_shares = stock.shares_outstanding
                if not old_shares or old_shares != shares:
                    stock.shares_outstanding = shares
                    stock.save()
                    
                    # 시가총액도 재계산
                    current_price = stock.get_current_price()
                    if current_price:
                        stock.market_cap = current_price * shares
                        stock.save()
                    
                    old_display = f'{old_shares:,}주' if old_shares else 'None'
                    self.stdout.write(
                        f'  ✅ {stock.stock_name}: 발행주식수 {old_display} → {shares:,}주'
                    )
                    return True
            
            return False

        except Exception as e:
            logger.warning(f"Failed to get shares for {stock.stock_code}: {e}")
            return False
    
    def get_shares_from_dart(self, stock: Stock, api_key: str) -> Optional[int]:
        """DART API에서 발행주식수 가져오기 (EPS 기반 역산 또는 직접 조회)"""
        try:
            # 방법 1: EPS와 순이익으로 발행주식수 역산
            latest_financial = stock.financials.first()
            if latest_financial and latest_financial.eps and latest_financial.net_income:
                if latest_financial.eps > 0:
                    calculated_shares = int(latest_financial.net_income / latest_financial.eps)
                    # 합리적인 범위 확인 (100만~100억주)
                    if 1_000_000 <= calculated_shares <= 10_000_000_000:
                        return calculated_shares
            
            # 방법 2: DART API에서 직접 조회 (실제 주식수 항목)
            corp_code = self.get_corp_code(stock.stock_code, api_key)
            if not corp_code:
                return None
            
            # 최근 연도 (2024, 2023) 순서로 시도
            for year in [2024, 2023]:
                url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
                params = {
                    'crtfc_key': api_key,
                    'corp_code': corp_code,
                    'bsns_year': str(year),
                    'reprt_code': '11011',
                    'fs_div': 'CFS'
                }
                
                response = requests.get(url, params=params, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '000':
                        list_data = data.get('list', [])
                        
                        # 주식수 관련 항목 찾기 (주 단위, 자본금 아님)
                        for item in list_data:
                            account_nm = item.get('account_nm', '').strip()
                            account_id = item.get('account_id', '').strip()
                            
                            # 주식수 관련 (account_id에 'number' 또는 'shares' 포함)
                            if ('주식' in account_nm or 'share' in account_id.lower()) and 'number' in account_id.lower():
                                thstrm_amount = item.get('thstrm_amount', '').replace(',', '').strip()
                                if thstrm_amount and thstrm_amount != '-' and thstrm_amount != '':
                                    try:
                                        shares = int(thstrm_amount)
                                        # 합리적인 범위 확인 (100만~100억주)
                                        if 1_000_000 <= shares <= 10_000_000_000:
                                            return shares
                                    except ValueError:
                                        continue
                        
                        time.sleep(0.1)  # API 호출 제한 방지
                
        except Exception as e:
            logger.debug(f"Failed to get shares from DART for {stock.stock_code}: {e}")
        
        return None

    def update_dividend_yield(self, stock: Stock, kis_client: KISApiClient, 
                             dart_api_key: Optional[str], overwrite: bool,
                             corp_mapping: Optional[Dict[str, str]] = None) -> bool:
        """배당수익률 업데이트"""
        
        # 이미 값이 있고 overwrite가 아니면 스킵
        if stock.dividend_yield and stock.dividend_yield > 0 and not overwrite:
            return False

        try:
            # 방법 1: KIS API에서 배당수익률 직접 가져오기 시도
            dividend_yield = self.get_dividend_yield_from_kis(stock, kis_client)
            
            # 방법 2: KIS API에서 가져올 수 없으면 DART API에서 배당금 수집
            if dividend_yield is None and dart_api_key:
                dividend_yield = self.get_dividend_yield_from_dart(stock, dart_api_key, corp_mapping)
            
            # 방법 3: 현재가와 EPS로 추정 (최후의 수단)
            if dividend_yield is None:
                dividend_yield = self.estimate_dividend_yield(stock)

            if dividend_yield is not None and dividend_yield > 0:
                old_yield = stock.dividend_yield
                stock.dividend_yield = round(dividend_yield, 2)
                stock.save()
                
                if old_yield != dividend_yield:
                    self.stdout.write(
                        f'  ✅ {stock.stock_name}: 배당수익률 {old_yield}% → {stock.dividend_yield}%'
                    )
                return True
            
            return False

        except Exception as e:
            logger.warning(f"Failed to get dividend yield for {stock.stock_code}: {e}")
            return False

    def get_dividend_yield_from_kis(self, stock: Stock, kis_client: KISApiClient) -> Optional[float]:
        """KIS API에서 배당수익률 가져오기"""
        # KIS API 응답에 배당수익률 필드가 있는지 확인 필요
        # 현재는 알 수 없는 필드명이므로 None 반환
        # TODO: KIS API 문서 확인 후 배당수익률 필드 사용
        return None

    def get_dividend_yield_from_dart(self, stock: Stock, api_key: str,
                                     corp_mapping: Optional[Dict[str, str]] = None) -> Optional[float]:
        """DART API에서 배당금 정보 가져오기"""
        try:
            # DART 기업 고유번호는 매핑에서 가져오기 (매번 조회하지 않음)
            if corp_mapping and stock.stock_code in corp_mapping:
                corp_code = corp_mapping[stock.stock_code]
            else:
                corp_code = self.get_corp_code(stock.stock_code, api_key)
            
            if not corp_code:
                return None

            # 재무제표에서 배당금 정보 찾기
            # 발행주식수가 있어야 주당배당금 계산 가능
            shares_outstanding = stock.shares_outstanding
            if not shares_outstanding:
                # 발행주식수가 없으면 계산 불가
                return None
            
            dividend_per_share = self.get_dividend_per_share_from_dart(corp_code, api_key, shares_outstanding)
            
            if dividend_per_share:
                # 현재가로 배당수익률 계산
                current_price = stock.get_current_price()
                if current_price and current_price > 0:
                    dividend_yield = (dividend_per_share / current_price) * 100
                    return dividend_yield
            
            return None

        except Exception as e:
            logger.warning(f"Failed to get dividend from DART for {stock.stock_code}: {e}")
            return None

    def get_dividend_per_share_from_dart(self, corp_code: str, api_key: str, shares_outstanding: int) -> Optional[float]:
        """DART API에서 배당금 총액을 가져와서 주당배당금 계산"""
        # 최근 연도 (2024, 2023) 순서로 시도
        for year in [2024, 2023]:
            try:
                url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
                params = {
                    'crtfc_key': api_key,
                    'corp_code': corp_code,
                    'bsns_year': str(year),
                    'reprt_code': '11011',  # 사업보고서
                    'fs_div': 'CFS'
                }
                
                response = requests.get(url, params=params, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '000':
                        list_data = data.get('list', [])
                        
                        # 배당금 총액 찾기 (현금흐름표 기준)
                        total_dividend = None
                        for item in list_data:
                            account_nm = item.get('account_nm', '').strip()
                            account_id = item.get('account_id', '').strip()
                            
                            # 배당금 지급 (현금흐름표)
                            if '배당금의지급' in account_nm or ('DividendsPaid' in account_id and 'ClassifiedAsFinancingActivities' in account_id):
                                thstrm_amount = item.get('thstrm_amount', '').replace(',', '').strip()
                                if thstrm_amount and thstrm_amount != '-' and thstrm_amount != '':
                                    try:
                                        total_dividend = int(thstrm_amount)
                                        break
                                    except ValueError:
                                        continue
                        
                        # 배당금 총액이 있고 발행주식수로 나누어 주당배당금 계산
                        if total_dividend and total_dividend > 0 and shares_outstanding and shares_outstanding > 0:
                            dividend_per_share = total_dividend / shares_outstanding
                            return dividend_per_share
                        
                        time.sleep(0.1)  # API 호출 제한 방지
                
            except Exception as e:
                logger.debug(f"Failed to get dividend from DART for year {year}: {e}")
                continue
        
        return None

    def get_all_corp_mapping(self, api_key: str) -> Dict[str, str]:
        """전체 기업 목록을 한 번에 조회하여 매핑 생성 (캐싱)"""
        try:
            url = 'https://opendart.fss.or.kr/api/corpCode.xml'
            params = {'crtfc_key': api_key}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                xml_content = zip_file.read('CORPCODE.xml')
            
            root = ET.fromstring(xml_content)
            mapping = {}
            for item in root.findall('.//list'):
                stock_code = item.findtext('stock_code', '').strip()
                corp_code = item.findtext('corp_code', '').strip()
                if stock_code and corp_code:
                    mapping[stock_code] = corp_code
            
            return mapping
            
        except Exception as e:
            logger.warning(f"Failed to get corp mapping: {e}")
            return {}
    
    def get_corp_code(self, stock_code: str, api_key: str) -> Optional[str]:
        """종목코드로 DART 기업 고유번호 조회 (단일 조회용)"""
        try:
            url = 'https://opendart.fss.or.kr/api/corpCode.xml'
            params = {'crtfc_key': api_key}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                xml_content = zip_file.read('CORPCODE.xml')
            
            root = ET.fromstring(xml_content)
            for item in root.findall('.//list'):
                if item.findtext('stock_code', '').strip() == stock_code:
                    return item.findtext('corp_code', '').strip()
            
            return None
            
        except Exception as e:
            logger.warning(f"Failed to get corp_code for {stock_code}: {e}")
            return None

    def estimate_dividend_yield(self, stock: Stock) -> Optional[float]:
        """현재가와 재무데이터로 배당수익률 추정"""
        try:
            # 최신 재무제표 데이터
            latest_financial = stock.financials.first()
            if not latest_financial:
                return None
            
            current_price = stock.get_current_price()
            if not current_price or current_price <= 0:
                return None
            
            # EPS가 있으면 배당성향 가정하여 추정
            if latest_financial.eps and latest_financial.eps > 0:
                # 일반적인 배당성향 20~50% 가정
                estimated_payout_ratio = 0.35  # 35% 배당성향 가정
                estimated_dividend_per_share = latest_financial.eps * estimated_payout_ratio
                dividend_yield = (estimated_dividend_per_share / current_price) * 100
                
                # 합리적인 범위 내인지 확인 (0.1%~20%)
                if 0.1 <= dividend_yield <= 20:
                    return dividend_yield
            
            return None

        except Exception as e:
            logger.debug(f"Failed to estimate dividend yield for {stock.stock_code}: {e}")
            return None

