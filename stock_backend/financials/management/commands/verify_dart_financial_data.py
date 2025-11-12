"""
DART API 재무 데이터 검증 관리 명령어

DB에 저장된 재무 데이터와 DART API에서 가져온 최신 데이터를 비교하여
데이터 정확성을 검증합니다.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from stocks.models import Stock
from financials.models import FinancialStatement
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
import time
import logging
import os
from decimal import Decimal

logger = logging.getLogger(__name__)


class DartAPIClient:
    """DART API 클라이언트 (검증용)"""
    
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
        """단일회사 재무제표 조회 (원본 데이터 반환)"""
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
            
        # 계정명 매핑 - 다양한 패턴 지원
        account_patterns = {
            'revenue': [
                '매출액', '수익(매출액)', '매출', '영업수익', '총매출액',
                '보험수익', '총영업수익', '보험영업수익',
                '이자수익', '수수료수익', '순이자이익'
            ],
            'operating_income': [
                '영업이익', '영업이익(손실)', '영업손익',
                '순보험이익', '순보험이익(손실)', '보험영업이익'
            ], 
            'net_income': [
                '당기순이익', '당기순이익(손실)', '순이익', '당기순손익',
                '연결당기순이익'
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
                thstrm_amount = item.get('thstrm_amount', '0').replace(',', '')
                
                # 각 필드별로 패턴 매칭
                for field_name, patterns in account_patterns.items():
                    if any(pattern in account_nm for pattern in patterns):
                        try:
                            if field_name == 'eps':
                                financial_data[field_name] = float(thstrm_amount) if thstrm_amount else 0.0
                            else:
                                amount = int(thstrm_amount) if thstrm_amount else 0
                                financial_data[field_name] = amount
                        except (ValueError, TypeError):
                            continue
                        break
            
            # 유효성 검사
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


class Command(BaseCommand):
    help = 'DB에 저장된 재무 데이터와 DART API 데이터를 비교하여 검증합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-key',
            type=str,
            help='DART API 키 (환경변수 DART_API_KEY 사용 가능)',
        )
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 검증 (예: 005930 000660)',
        )
        parser.add_argument(
            '--years',
            nargs='+',
            type=int,
            help='특정 연도만 검증 (기본값: DB에 저장된 모든 연도)',
        )
        parser.add_argument(
            '--sample-size',
            type=int,
            default=10,
            help='샘플 크기 (기본값: 10개 종목)',
        )
        parser.add_argument(
            '--tolerance',
            type=float,
            default=0.01,
            help='허용 오차율 (기본값: 0.01 = 1%%)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='결과를 파일로 저장할 경로 (JSON 형식)',
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
            return

        stock_codes = options.get('stock_codes')
        years = options.get('years')
        sample_size = options.get('sample_size')
        tolerance = options.get('tolerance')
        output_path = options.get('output')

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

        # 검증 대상 종목 선택
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            # 재무데이터가 있는 종목 중 샘플 선택
            stocks = Stock.objects.filter(financials__isnull=False).distinct()[:sample_size]

        total_stocks = stocks.count()
        self.stdout.write(f'\n📊 검증 대상: {total_stocks}개 종목')

        if total_stocks == 0:
            self.stdout.write(self.style.ERROR('❌ 검증할 재무데이터가 없습니다.'))
            return

        # 검증 결과 저장
        verification_results = {
            'total_checked': 0,
            'exact_matches': 0,
            'within_tolerance': 0,
            'differences': 0,
            'api_errors': 0,
            'missing_data': 0,
            'details': []
        }

        for i, stock in enumerate(stocks, 1):
            self.stdout.write(f"\n{'='*60}")
            self.stdout.write(f"[{i}/{total_stocks}] {stock.stock_name} ({stock.stock_code}) 검증 중...")

            # DART 고유번호 확인
            corp_code = corp_mapping.get(stock.stock_code)
            if not corp_code:
                self.stdout.write(f"  ⚠️  DART 고유번호를 찾을 수 없습니다.")
                verification_results['missing_data'] += 1
                continue

            # DB에 저장된 재무데이터 조회
            db_financials = FinancialStatement.objects.filter(stock=stock)
            if years:
                db_financials = db_financials.filter(year__in=years)

            if not db_financials.exists():
                self.stdout.write(f"  ⚠️  DB에 저장된 재무데이터가 없습니다.")
                verification_results['missing_data'] += 1
                continue

            # 각 연도별 검증
            for db_financial in db_financials:
                year = db_financial.year
                self.stdout.write(f"\n  📅 {year}년 검증 중...")

                # DART API로 재무데이터 조회
                try:
                    api_data = dart_client.fetch_financial_data(
                        stock.stock_code, corp_code, year
                    )

                    if not api_data:
                        self.stdout.write(f"    ❌ DART API에서 데이터를 가져올 수 없습니다.")
                        verification_results['api_errors'] += 1
                        continue

                    verification_results['total_checked'] += 1

                    # 필드별 비교
                    comparison = self._compare_financial_data(
                        db_financial, api_data, tolerance, stock.stock_code, year
                    )

                    verification_results['details'].append(comparison)

                    # 결과 요약
                    if comparison['status'] == 'exact_match':
                        verification_results['exact_matches'] += 1
                        self.stdout.write(f"    ✅ 완벽 일치")
                    elif comparison['status'] == 'within_tolerance':
                        verification_results['within_tolerance'] += 1
                        self.stdout.write(f"    ⚠️  허용 오차 내 차이")
                        for field, diff_info in comparison['differences'].items():
                            if diff_info['has_diff']:
                                self.stdout.write(
                                    f"      - {field}: DB={diff_info['db_value']:,} vs API={diff_info['api_value']:,} "
                                    f"(차이: {diff_info['diff_pct']:.2f}%)"
                                )
                    else:
                        verification_results['differences'] += 1
                        self.stdout.write(f"    ❌ 차이 발견")
                        for field, diff_info in comparison['differences'].items():
                            if diff_info['has_diff']:
                                self.stdout.write(
                                    f"      - {field}: DB={diff_info['db_value']:,} vs API={diff_info['api_value']:,} "
                                    f"(차이: {diff_info['diff_pct']:.2f}%)"
                                )

                    # API 호출 제한 방지
                    time.sleep(0.1)

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"    💥 오류 발생: {str(e)}")
                    )
                    verification_results['api_errors'] += 1

        # 결과 요약 출력
        self._print_summary(verification_results)

        # 파일로 저장
        if output_path:
            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(verification_results, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f"\n💾 검증 결과가 {output_path}에 저장되었습니다.")

    def _compare_financial_data(
        self, db_financial: FinancialStatement, api_data: Dict, 
        tolerance: float, stock_code: str, year: int
    ) -> Dict:
        """DB 데이터와 API 데이터 비교"""
        fields_to_compare = [
            'revenue', 'operating_income', 'net_income', 'eps',
            'total_assets', 'total_liabilities', 'total_equity'
        ]

        comparison = {
            'stock_code': stock_code,
            'stock_name': db_financial.stock.stock_name,
            'year': year,
            'status': 'exact_match',  # exact_match, within_tolerance, difference
            'differences': {}
        }

        has_exact_diff = False
        has_tolerance_diff = False

        for field in fields_to_compare:
            db_value = getattr(db_financial, field)
            api_value = api_data.get(field)

            # None 값 처리
            if db_value is None and api_value is None:
                comparison['differences'][field] = {
                    'has_diff': False,
                    'db_value': None,
                    'api_value': None,
                    'diff': 0,
                    'diff_pct': 0.0
                }
                continue

            if db_value is None or api_value is None:
                comparison['differences'][field] = {
                    'has_diff': True,
                    'db_value': db_value,
                    'api_value': api_value,
                    'diff': None,
                    'diff_pct': None
                }
                has_exact_diff = True
                continue

            # EPS는 float 비교
            if field == 'eps':
                diff = abs(db_value - api_value)
                base_value = max(abs(db_value), abs(api_value), 0.001)  # 0으로 나누기 방지
                diff_pct = (diff / base_value) * 100 if base_value > 0 else 0
            else:
                # 정수 필드는 절대 차이와 퍼센트 차이 계산
                diff = abs(db_value - api_value)
                base_value = max(abs(db_value), abs(api_value), 1)  # 0으로 나누기 방지
                diff_pct = (diff / base_value) * 100 if base_value > 0 else 0

            comparison['differences'][field] = {
                'has_diff': diff > 0,
                'db_value': db_value,
                'api_value': api_value,
                'diff': diff,
                'diff_pct': diff_pct
            }

            if diff > 0:
                if diff_pct <= tolerance * 100:  # tolerance는 백분율로 변환
                    has_tolerance_diff = True
                else:
                    has_exact_diff = True

        # 상태 결정
        if has_exact_diff:
            comparison['status'] = 'difference'
        elif has_tolerance_diff:
            comparison['status'] = 'within_tolerance'
        else:
            comparison['status'] = 'exact_match'

        return comparison

    def _print_summary(self, results: Dict):
        """검증 결과 요약 출력"""
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS("📊 DART API 재무 데이터 검증 결과"))
        self.stdout.write(f"{'='*60}")
        self.stdout.write(f"검증한 항목 수: {results['total_checked']}")
        self.stdout.write(
            self.style.SUCCESS(f"✅ 완벽 일치: {results['exact_matches']}")
        )
        self.stdout.write(
            self.style.WARNING(f"⚠️  허용 오차 내: {results['within_tolerance']}")
        )
        self.stdout.write(
            self.style.ERROR(f"❌ 차이 발견: {results['differences']}")
        )
        self.stdout.write(
            self.style.ERROR(f"💥 API 오류: {results['api_errors']}")
        )
        self.stdout.write(
            self.style.ERROR(f"⚠️  데이터 없음: {results['missing_data']}")
        )

        if results['total_checked'] > 0:
            accuracy = (
                (results['exact_matches'] + results['within_tolerance']) 
                / results['total_checked'] * 100
            )
            self.stdout.write(f"\n정확도: {accuracy:.2f}%")
