"""
DART API로 직접 2024년 순이익 데이터를 가져와서 테스트하는 명령어

현재 수집 코드에서 순이익이 0으로 저장되는 문제를 진단하기 위해
DART API를 직접 호출하여 원본 데이터를 확인합니다.
"""
from django.core.management.base import BaseCommand
from stocks.models import Stock
from financials.models import FinancialStatement
import requests
import os
import logging
import json
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'DART API로 직접 2024년 순이익 데이터를 가져와서 테스트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='테스트할 종목코드들 (없으면 샘플 종목)',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2024,
            help='테스트할 연도 (기본값: 2024)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='결과를 JSON 파일로 저장할 경로',
        )

    def handle(self, *args, **options):
        api_key = os.getenv('DART_API_KEY')
        if not api_key:
            self.stdout.write(
                self.style.ERROR('❌ DART_API_KEY 환경변수가 필요합니다.')
            )
            return

        stock_codes = options.get('stock_codes')
        year = options.get('year', 2024)
        output_path = options.get('output')

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS(f'🔍 DART API 직접 호출 테스트 - {year}년 순이익'))
        self.stdout.write('=' * 70 + '\n')

        # 테스트할 종목 선택
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            # 샘플 종목 선택 (순이익이 0으로 저장된 종목들)
            stocks_with_zero = FinancialStatement.objects.filter(
                year=year, net_income=0
            ).select_related('stock')[:10]
            stocks = [fs.stock for fs in stocks_with_zero]

        if not stocks.exists() if hasattr(stocks, 'exists') else len(stocks) == 0:
            self.stdout.write(self.style.WARNING('⚠️  테스트할 종목이 없습니다.'))
            return

        # DART 기업 고유번호 매핑 조회
        self.stdout.write('📋 DART 기업 고유번호 매핑 조회 중...')
        corp_mapping = self._get_corp_mapping(api_key)
        if not corp_mapping:
            self.stdout.write(self.style.ERROR('❌ 기업 목록 조회 실패'))
            return
        self.stdout.write(f'✅ {len(corp_mapping)}개 기업 정보 조회 완료\n')

        results = []
        stock_list = list(stocks) if not hasattr(stocks, 'exists') else list(stocks)

        for i, stock in enumerate(stock_list, 1):
            self.stdout.write(f'\n[{i}/{len(stock_list)}] {stock.stock_name} ({stock.stock_code}) 테스트 중...')

            corp_code = corp_mapping.get(stock.stock_code)
            if not corp_code:
                self.stdout.write(f"  ❌ DART 고유번호 없음")
                results.append({
                    'stock_code': stock.stock_code,
                    'stock_name': stock.stock_name,
                    'error': 'corp_code_not_found'
                })
                continue

            # DB에 저장된 현재 데이터 확인
            db_financial = FinancialStatement.objects.filter(
                stock=stock, year=year
            ).first()

            # DART API로 직접 조회
            api_result = self._fetch_from_dart_api(api_key, corp_code, year)

            result = {
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'corp_code': corp_code,
                'year': year,
                'db_data': {
                    'revenue': db_financial.revenue if db_financial else None,
                    'operating_income': db_financial.operating_income if db_financial else None,
                    'net_income': db_financial.net_income if db_financial else None,
                    'eps': db_financial.eps if db_financial else None,
                },
                **api_result
            }
            results.append(result)

            # 결과 출력
            if api_result.get('error'):
                self.stdout.write(f"  ❌ API 오류: {api_result['error']}")
            elif api_result.get('parsed_data'):
                parsed = api_result['parsed_data']
                self.stdout.write(f"  ✅ API 조회 성공")
                self.stdout.write(f"     매출액: {parsed.get('revenue', 'N/A'):,}원" if parsed.get('revenue') else "     매출액: N/A")
                self.stdout.write(f"     영업이익: {parsed.get('operating_income', 'N/A'):,}원" if parsed.get('operating_income') else "     영업이익: N/A")
                self.stdout.write(f"     순이익: {parsed.get('net_income', 'N/A'):,}원" if parsed.get('net_income') else "     순이익: N/A")
                self.stdout.write(f"     EPS: {parsed.get('eps', 'N/A')}원" if parsed.get('eps') else "     EPS: N/A")

                # DB 데이터와 비교
                if db_financial:
                    if db_financial.net_income == 0 and parsed.get('net_income') and parsed.get('net_income') != 0:
                        self.stdout.write(
                            self.style.ERROR(
                                f"     ⚠️  문제 발견: DB에는 순이익 0, API에는 {parsed.get('net_income'):,}원"
                            )
                        )
                    elif db_financial.net_income != parsed.get('net_income'):
                        self.stdout.write(
                            self.style.WARNING(
                                f"     ⚠️  불일치: DB={db_financial.net_income:,}원, API={parsed.get('net_income'):,}원"
                            )
                        )

        # 결과 저장
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f'\n💾 테스트 결과가 {output_path}에 저장되었습니다.')

        # 요약
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 테스트 결과 요약'))
        self.stdout.write('=' * 70)
        
        successful = [r for r in results if r.get('parsed_data')]
        errors = [r for r in results if r.get('error')]
        mismatches = [
            r for r in successful
            if r.get('db_data', {}).get('net_income') == 0
            and r.get('parsed_data', {}).get('net_income')
            and r.get('parsed_data', {}).get('net_income') != 0
        ]

        self.stdout.write(f'✅ 성공: {len(successful)}개')
        self.stdout.write(f'❌ 오류: {len(errors)}개')
        self.stdout.write(f'⚠️  순이익 불일치: {len(mismatches)}개')

        if mismatches:
            self.stdout.write('\n⚠️  순이익 불일치 종목:')
            for r in mismatches:
                self.stdout.write(
                    f'  - {r["stock_name"]} ({r["stock_code"]}): '
                    f'DB={r["db_data"]["net_income"]:,}원, '
                    f'API={r["parsed_data"]["net_income"]:,}원'
                )

    def _get_corp_mapping(self, api_key: str) -> Dict[str, str]:
        """DART 기업 고유번호 매핑 조회"""
        import io
        import zipfile
        import xml.etree.ElementTree as ET

        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        params = {"crtfc_key": api_key}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                xml_content = zip_file.read('CORPCODE.xml')

            root = ET.fromstring(xml_content)
            corp_mapping = {}

            for item in root.findall('.//list'):
                corp_code = item.findtext('corp_code', '').strip()
                stock_code = item.findtext('stock_code', '').strip()

                if stock_code and corp_code:
                    corp_mapping[stock_code] = corp_code

            return corp_mapping

        except Exception as e:
            logger.error(f"기업 목록 조회 실패: {str(e)}")
            return {}

    def _fetch_from_dart_api(self, api_key: str, corp_code: str, year: int) -> Dict:
        """DART API로 직접 재무 데이터 조회 및 파싱"""
        base_url = "https://opendart.fss.or.kr/api"
        url = f"{base_url}/fnlttSinglAcntAll.json"

        result = {
            'raw_response': None,
            'parsed_data': None,
            'error': None,
            'account_names': []
        }

        # CFS (연결재무제표) 시도
        params = {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # 사업보고서
            "fs_div": "CFS"  # 연결재무제표
        }

        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get('status') != '000':
                # CFS 실패 - OFS 시도
                params['fs_div'] = 'OFS'
                response = requests.get(url, params=params, timeout=20)
                data = response.json()

                if data.get('status') != '000':
                    result['error'] = f"API 오류: {data.get('message', 'Unknown error')}"
                    return result

            result['raw_response'] = data.get('list', [])
            
            # 데이터 파싱
            parsed = self._parse_financial_data(result['raw_response'], year)
            result['parsed_data'] = parsed
            result['account_names'] = [item.get('account_nm', '') for item in result['raw_response']]

            return result

        except requests.exceptions.Timeout:
            result['error'] = 'API 요청 타임아웃'
            return result
        except Exception as e:
            result['error'] = f'예상치 못한 오류: {str(e)}'
            logger.exception(f"DART API 조회 오류: {str(e)}")
            return result

    def _parse_financial_data(self, raw_data: List[Dict], year: int) -> Dict:
        """DART API 원본 데이터를 파싱하여 재무 데이터 추출"""
        
        # 계정명 매핑 (다양한 표기 고려)
        account_mappings = {
            'revenue': [
                '매출액', '매출', '수익(매출액)', '수익', '영업수익'
            ],
            'operating_income': [
                '영업이익', '영업손익', '영업손익(손실)', '영업이익(손실)'
            ],
            'net_income': [
                '당기순이익', '순이익', '당기순손익', '순손익',
                '법인세비용차감전순이익', '법인세비용차감전순손익',
                '지배기업주주에게귀속되는당기순이익',
                '지배기업주주에게귀속되는당기순손익'
            ],
            'eps': [
                '기본주당순이익', '주당순이익', 'EPS', '주당순손익'
            ]
        }

        parsed = {
            'revenue': None,
            'operating_income': None,
            'net_income': None,
            'eps': None
        }

        # 단위 정보 수집
        units = {}
        for item in raw_data:
            account_nm = item.get('account_nm', '')
            if '단위' in account_nm or 'unit' in account_nm.lower():
                # 단위 정보 추출
                pass

        for item in raw_data:
            account_nm = item.get('account_nm', '').strip()
            account_id = item.get('account_id', '').strip()
            thstrm_amount = item.get('thstrm_amount', '').strip()  # 당기금액
            
            # 계정명으로 매칭
            for key, names in account_mappings.items():
                if any(name in account_nm for name in names):
                    value = self._parse_amount(thstrm_amount)
                    if value is not None:
                        parsed[key] = value
                        self.stdout.write(f"       발견: {account_nm} = {value:,}원 (계정ID: {account_id})")
                        break

        # 순이익이 없으면 다른 방법 시도
        if parsed['net_income'] is None:
            # 법인세비용차감전순이익 - 법인세비용 = 당기순이익
            # 또는 지배기업주주에게귀속되는당기순이익
            for item in raw_data:
                account_nm = item.get('account_nm', '').strip()
                if '지배기업' in account_nm and '순이익' in account_nm:
                    value = self._parse_amount(item.get('thstrm_amount', ''))
                    if value is not None:
                        parsed['net_income'] = value
                        self.stdout.write(f"       대체 발견: {account_nm} = {value:,}원")

        return parsed

    def _parse_amount(self, amount_str: str) -> Optional[int]:
        """금액 문자열을 정수로 변환"""
        if not amount_str or amount_str == '-':
            return None

        try:
            # 쉼표 제거 후 변환
            cleaned = amount_str.replace(',', '').strip()
            if not cleaned:
                return None
            
            # 음수 처리
            is_negative = False
            if cleaned.startswith('-'):
                is_negative = True
                cleaned = cleaned[1:]
            
            value = int(cleaned)
            
            # 단위가 '원'인 경우 그대로, '천원'이면 * 1000, '백만원'이면 * 1000000
            # DART API는 보통 원 단위로 제공되지만 확인 필요
            
            if is_negative:
                value = -value
            
            return value
        except (ValueError, AttributeError):
            return None

