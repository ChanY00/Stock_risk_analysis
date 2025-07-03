from django.core.management.base import BaseCommand
from django.db import models
from stocks.models import Stock
from financials.models import FinancialStatement
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional
import time
import logging
from django.conf import settings
import os

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'DART API를 사용하여 재무제표 데이터를 가져옵니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='DART API 키 (환경변수 DART_API_KEY 사용 가능)',
        )
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 업데이트 (예: 005930 000660)',
        )
        parser.add_argument(
            '--years',
            nargs='+',
            type=int,
            default=[2025, 2024, 2023, 2022],
            help='가져올 재무제표 연도들 (기본값: 2025 2024 2023 2022)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='기존 데이터가 있어도 덮어쓰기',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 저장하지 않고 테스트만 실행',
        )

    def handle(self, *args, **options):
        # API 키 확인
        api_key = options.get('api_key') or os.getenv('DART_API_KEY')
        if not api_key:
            self.stdout.write(
                self.style.ERROR(
                    '❌ DART API 키가 필요합니다. --api-key 옵션을 사용하거나 DART_API_KEY 환경변수를 설정해주세요.'
                )
            )
            self.stdout.write('DART API 키 발급: https://opendart.fss.or.kr/uss/umt/EgovMberInsertView.do')
            return

        years = options['years']
        overwrite = options['overwrite']
        dry_run = options['dry_run']
        stock_codes = options.get('stock_codes')

        if dry_run:
            self.stdout.write(self.style.WARNING('🧪 DRY RUN 모드: 실제 저장하지 않습니다.'))

        # DART API 클라이언트 초기화
        dart_client = DartAPIClient(api_key)

        # 연결 테스트
        self.stdout.write('🔍 DART API 연결 테스트 중...')
        if not dart_client.test_connection():
            self.stdout.write(self.style.ERROR('❌ DART API 연결 실패'))
            return

        # 기업 고유번호 매핑 조회
        self.stdout.write('📋 기업 고유번호 매핑 조회 중...')
        corp_mapping = dart_client.get_corp_list()
        if not corp_mapping:
            self.stdout.write(self.style.ERROR('❌ 기업 목록 조회 실패'))
            return

        # 대상 종목 필터링
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            # 재무데이터가 없거나 부족한 종목들 선택
            stocks = Stock.objects.filter(
                models.Q(financials__isnull=True) | 
                models.Q(financials__year__lt=max(years))
            ).distinct()

        total_stocks = stocks.count()
        self.stdout.write(f'📊 처리 대상: {total_stocks}개 종목')

        if total_stocks == 0:
            self.stdout.write(self.style.SUCCESS('✅ 모든 종목이 최신 재무데이터를 보유하고 있습니다.'))
            return

        success_count = 0
        error_count = 0
        skipped_count = 0

        for i, stock in enumerate(stocks, 1):
            self.stdout.write(f"\n[{i}/{total_stocks}] {stock.stock_name} ({stock.stock_code}) 처리 중...")

            # DART 고유번호 확인
            corp_code = corp_mapping.get(stock.stock_code)
            if not corp_code:
                self.stdout.write(f"  ⏭️  DART 고유번호를 찾을 수 없습니다.")
                skipped_count += 1
                continue

            try:
                # 연도별 데이터 수집
                year_success = 0
                
                for year in years:
                    # 기존 데이터 확인
                    existing = FinancialStatement.objects.filter(
                        stock=stock, 
                        year=year
                    ).first()
                    
                    if existing and not overwrite:
                        self.stdout.write(f"  ⏭️  {year}년 데이터가 이미 존재합니다.")
                        continue

                    # DART API로 재무데이터 조회
                    financial_data = dart_client.fetch_financial_data(
                        stock.stock_code, corp_code, year
                    )

                    if financial_data:
                        if not dry_run:
                            # 데이터베이스에 저장/업데이트
                            financial_obj, created = FinancialStatement.objects.update_or_create(
                                stock=stock,
                                year=year,
                                defaults=financial_data
                            )
                            
                            if created:
                                self.stdout.write(f"  ✅ {year}년 재무데이터 새로 생성됨")
                            else:
                                self.stdout.write(f"  🔄 {year}년 재무데이터 업데이트됨")
                        else:
                            self.stdout.write(f"  🧪 {year}년 재무데이터 수집 성공 (DRY RUN)")
                        
                        year_success += 1
                    else:
                        self.stdout.write(f"  ❌ {year}년 재무데이터 수집 실패")

                if year_success > 0:
                    success_count += 1
                    
                    # 재무비율 재계산
                    if not dry_run:
                        stock.update_financial_ratios()
                else:
                    error_count += 1

                # API 호출 제한 방지
                time.sleep(0.1)

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  💥 오류 발생: {str(e)}")
                )
                error_count += 1

        # 결과 요약
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(f"📈 DART API 재무데이터 수집 완료")
        self.stdout.write(f"{'='*50}")
        self.stdout.write(f"✅ 성공: {success_count}개 종목")
        self.stdout.write(f"❌ 실패: {error_count}개 종목") 
        self.stdout.write(f"⏭️  스킵: {skipped_count}개 종목")
        self.stdout.write(f"📊 전체: {total_stocks}개 종목")
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n🧪 DRY RUN 모드였습니다. 실제 데이터는 저장되지 않았습니다.'))
        else:
            self.stdout.write(f"\n💾 데이터베이스에 저장 완료")


class DartAPIClient:
    """DART API 클라이언트 (명령어용 간소화 버전)"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://opendart.fss.or.kr/api"
        self.session = requests.Session()
        self._corp_mapping = None
        
    def get_corp_list(self) -> Dict[str, str]:
        """전체 기업 목록과 고유번호 매핑 조회"""
        if self._corp_mapping is not None:
            return self._corp_mapping
            
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
                
                if stock_code and corp_code:  # 상장기업만
                    corp_mapping[stock_code] = corp_code
                    
            self._corp_mapping = corp_mapping
            return corp_mapping
            
        except Exception as e:
            logger.error(f"기업 목록 조회 실패: {str(e)}")
            return {}
    
    def get_financial_statement(self, corp_code: str, year: int) -> Optional[List[Dict]]:
        """단일회사 재무제표 조회"""
        url = f"{self.base_url}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # 사업보고서
            "fs_div": "CFS"  # 연결재무제표
        }
        
        try:
            response = self.session.get(url, params=params, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != '000':
                # 연결재무제표가 없으면 별도재무제표 시도
                params['fs_div'] = 'OFS'
                response = self.session.get(url, params=params, timeout=20)
                data = response.json()
                
                if data.get('status') != '000':
                    return None
                    
            return data.get('list', [])
            
        except Exception as e:
            logger.error(f"재무제표 조회 실패: {str(e)}")
            return None
    
    def parse_financial_data(self, raw_data: List[Dict], year: int) -> Optional[Dict]:
        """DART API 응답을 우리 시스템 형식으로 변환"""
        if not raw_data:
            return None
            
        # 계정명 매핑 - 다양한 패턴 지원 (일반기업 + 금융업)
        account_patterns = {
            'revenue': [
                # 일반기업
                '매출액', '수익(매출액)', '매출', '영업수익', '총매출액',
                # 금융업
                '보험수익', '영업수익', '총영업수익', '보험영업수익',
                # 금융지주
                '이자수익', '수수료수익', '순이자이익'
            ],
            'operating_income': [
                # 일반기업
                '영업이익', '영업이익(손실)', '영업손익',
                # 금융업
                '순보험이익', '순보험이익(손실)', '보험영업이익', '영업이익'
            ], 
            'net_income': [
                # 일반기업
                '당기순이익', '당기순이익(손실)', '순이익', '당기순손익',
                # 금융업
                '당기순이익', '당기순이익(손실)', '연결당기순이익'
            ],
            'eps': ['주당순이익', '기본주당순이익', '주당이익'],
            'total_assets': ['자산총계', '총자산', '자산총액'],
            'total_liabilities': ['부채총계', '총부채', '부채총액'], 
            'total_equity': ['자본총계', '총자본', '자기자본총계', '자본총액'],
        }
        
        financial_data = {
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
                # 음수 처리를 제대로 하도록 수정
                thstrm_amount = item.get('thstrm_amount', '0').replace(',', '')
                
                # 각 필드별로 패턴 매칭
                for field_name, patterns in account_patterns.items():
                    if any(pattern in account_nm for pattern in patterns):
                        try:
                            if field_name == 'eps':
                                financial_data[field_name] = float(thstrm_amount) if thstrm_amount else 0.0
                            else:
                                # DART API 데이터는 이미 원(KRW) 단위입니다
                                amount = int(thstrm_amount) if thstrm_amount else 0
                                financial_data[field_name] = amount  # 변환 없이 그대로 사용
                                
                        except (ValueError, TypeError):
                            continue
                        break  # 첫 번째 매칭된 패턴으로 설정하고 다음으로
            
            # 유효성 검사 - 매출액이나 영업수익이 있어야 유효한 데이터로 간주
            if financial_data['revenue'] > 0:
                return financial_data
                
        except Exception as e:
            logger.error(f"재무데이터 파싱 실패: {str(e)}")
            
        return None
    
    def fetch_financial_data(self, stock_code: str, corp_code: str, year: int) -> Optional[Dict]:
        """특정 기업의 특정 연도 재무데이터 수집"""
        raw_data = self.get_financial_statement(corp_code, year)
        if raw_data:
            return self.parse_financial_data(raw_data, year)
        return None
    
    def test_connection(self) -> bool:
        """API 연결 테스트"""
        try:
            corp_list = self.get_corp_list()
            return len(corp_list) > 0
        except:
            return False 