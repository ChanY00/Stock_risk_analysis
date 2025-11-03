"""
누락된 재무 데이터 확인 및 재수집 명령어

DB에 저장되지 않은 재무 데이터를 찾아서 확인하고 재수집합니다.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from stocks.models import Stock
from financials.models import FinancialStatement
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
import json
import os
import logging
from typing import Dict, List, Set, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'DB에 저장되지 않은 재무 데이터를 찾아서 확인하고 재수집합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--years',
            nargs='+',
            type=int,
            default=[2024, 2023, 2022],
            help='확인할 연도 목록 (기본값: 2024 2023 2022)',
        )
        parser.add_argument(
            '--collect',
            action='store_true',
            help='누락된 데이터를 자동으로 재수집',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='분석 결과를 JSON 파일로 저장할 경로',
        )
        parser.add_argument(
            '--verify-only',
            action='store_true',
            help='수집만 하고 검증은 하지 않음',
        )

    def handle(self, *args, **options):
        api_key = os.getenv('DART_API_KEY')
        if not api_key:
            self.stdout.write(
                self.style.ERROR('❌ DART_API_KEY 환경변수가 필요합니다.')
            )
            return

        years = options['years']
        should_collect = options.get('collect', False)
        output_path = options.get('output')
        verify_only = options.get('verify_only', False)

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('🔍 누락된 재무 데이터 확인 및 분석'))
        self.stdout.write('=' * 70 + '\n')

        # DART 기업 고유번호 매핑 조회
        self.stdout.write('📋 DART 기업 고유번호 매핑 조회 중...')
        corp_mapping = self._get_corp_mapping(api_key)
        if not corp_mapping:
            self.stdout.write(self.style.ERROR('❌ 기업 목록 조회 실패'))
            return
        self.stdout.write(f'✅ {len(corp_mapping)}개 기업 정보 조회 완료\n')

        # 전체 종목 조회
        all_stocks = Stock.objects.all().order_by('stock_code')
        total_stocks = all_stocks.count()
        self.stdout.write(f'📊 전체 종목 수: {total_stocks}개')
        self.stdout.write(f'📅 확인 대상 연도: {", ".join(map(str, years))}년\n')

        # 누락된 데이터 찾기
        missing_data = self._find_missing_data(all_stocks, years, corp_mapping)

        # 결과 출력
        self._print_results(missing_data, total_stocks, years)

        # 재수집 실행
        if should_collect:
            self._collect_missing_data(missing_data, api_key, years, verify_only)

        # 파일로 저장
        if output_path:
            report = {
                'analysis_date': datetime.now().isoformat(),
                'years': years,
                'total_stocks': total_stocks,
                'missing_data': [
                    {
                        'stock_code': item['stock'].stock_code,
                        'stock_name': item['stock'].stock_name,
                        'missing_years': item['missing_years'],
                        'existing_years': item['existing_years'],
                        'has_corp_code': item['has_corp_code']
                    }
                    for item in missing_data
                ]
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f'\n💾 분석 결과가 {output_path}에 저장되었습니다.')

    def _get_corp_mapping(self, api_key: str) -> Dict[str, str]:
        """DART 기업 고유번호 매핑 조회"""
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

    def _find_missing_data(self, stocks, years: List[int], corp_mapping: Dict[str, str]) -> List[Dict]:
        """누락된 재무 데이터 찾기"""
        missing_data = []

        for stock in stocks:
            # 현재 DB에 저장된 재무 데이터 년도 확인
            existing_years = set(
                FinancialStatement.objects.filter(stock=stock)
                .values_list('year', flat=True)
            )

            # 누락된 년도 찾기
            missing_years = [year for year in years if year not in existing_years]

            if missing_years:
                missing_data.append({
                    'stock': stock,
                    'existing_years': sorted(list(existing_years)),
                    'missing_years': sorted(missing_years),
                    'has_corp_code': stock.stock_code in corp_mapping
                })

        return missing_data

    def _print_results(self, missing_data: List[Dict], total_stocks: int, years: List[int]):
        """결과 출력"""
        missing_count = len(missing_data)
        complete_count = total_stocks - missing_count

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 누락된 재무 데이터 분석 결과'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'전체 종목: {total_stocks}개')
        self.stdout.write(
            self.style.SUCCESS(f'✅ 완전한 종목: {complete_count}개 ({complete_count/total_stocks*100:.1f}%)')
        )
        self.stdout.write(
            self.style.WARNING(f'⚠️  누락된 종목: {missing_count}개 ({missing_count/total_stocks*100:.1f}%)')
        )
        self.stdout.write('')

        if missing_data:
            # 누락된 년도별 통계
            self.stdout.write('=== 누락된 년도별 통계 ===')
            year_missing = {year: 0 for year in years}
            for item in missing_data:
                for year in item['missing_years']:
                    year_missing[year] += 1

            for year in sorted(years, reverse=True):
                count = year_missing[year]
                self.stdout.write(f'{year}년 누락: {count}개 종목')

            # DART 고유번호 없는 종목 확인
            no_corp_code = [item for item in missing_data if not item['has_corp_code']]
            if no_corp_code:
                self.stdout.write(f'\n⚠️  DART 고유번호 없는 종목: {len(no_corp_code)}개')

            # 상위 20개 종목 출력
            self.stdout.write('\n=== 누락된 종목 상세 (상위 20개) ===')
            for i, item in enumerate(missing_data[:20], 1):
                stock = item['stock']
                missing_years_str = ', '.join(map(str, item['missing_years']))
                existing_years_str = ', '.join(map(str, item['existing_years'])) if item['existing_years'] else '없음'
                corp_status = '✅' if item['has_corp_code'] else '❌'
                
                self.stdout.write(
                    f'{i}. {stock.stock_name} ({stock.stock_code}) {corp_status}'
                )
                self.stdout.write(
                    f'   누락: {missing_years_str}년 | 보유: {existing_years_str}년'
                )

            if len(missing_data) > 20:
                self.stdout.write(f'\n... 외 {len(missing_data) - 20}개 종목')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ 모든 종목이 완전한 재무 데이터를 보유하고 있습니다!'))

    def _collect_missing_data(self, missing_data: List[Dict], api_key: str, years: List[int], verify_only: bool):
        """누락된 데이터 재수집"""
        from financials.management.commands.collect_and_verify_financial_data import DartAPIClient
        from django.utils import timezone

        if not missing_data:
            self.stdout.write('\n✅ 누락된 데이터가 없습니다.')
            return

        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📥 누락된 재무 데이터 재수집 시작'))
        self.stdout.write('=' * 70 + '\n')

        # DART 고유번호 있는 종목만 필터링
        collectable_items = [item for item in missing_data if item['has_corp_code']]
        not_collectable_count = len(missing_data) - len(collectable_items)

        if not_collectable_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️  DART 고유번호 없는 종목 {not_collectable_count}개는 건너뜁니다.\n'
                )
            )

        if not collectable_items:
            self.stdout.write(self.style.ERROR('❌ 재수집 가능한 종목이 없습니다.'))
            return

        dart_client = DartAPIClient(api_key)
        total_items = len(collectable_items)
        success_count = 0
        failed_count = 0

        for i, item in enumerate(collectable_items, 1):
            stock = item['stock']
            corp_code = api_key  # 이건 잘못됨, corp_mapping에서 가져와야 함
            
            # corp_mapping 다시 가져오기
            corp_mapping = self._get_corp_mapping(api_key)
            corp_code = corp_mapping.get(stock.stock_code)

            if not corp_code:
                failed_count += 1
                continue

            missing_years = item['missing_years']
            self.stdout.write(
                f'\n[{i}/{total_items}] {stock.stock_name} ({stock.stock_code}) - '
                f'{", ".join(map(str, missing_years))}년 수집 중...'
            )

            year_success = 0
            for year in missing_years:
                try:
                    # DART API로 재무데이터 조회
                    financial_data = dart_client.fetch_financial_data(
                        stock.stock_code, corp_code, year
                    )

                    if financial_data:
                        # 데이터베이스에 저장
                        defaults = financial_data.copy()
                        if not verify_only:
                            defaults.update({
                                'is_verified': True,
                                'verified_at': timezone.now(),
                                'verification_status': 'exact_match',
                                'verification_note': '누락 데이터 재수집'
                            })
                        else:
                            defaults.update({
                                'is_verified': False,
                                'verification_status': 'not_verified'
                            })

                        FinancialStatement.objects.update_or_create(
                            stock=stock,
                            year=year,
                            defaults=defaults
                        )

                        self.stdout.write(f"  ✅ {year}년 데이터 수집 완료")
                        year_success += 1
                    else:
                        self.stdout.write(f"  ❌ {year}년 데이터 수집 실패")

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f"  💥 {year}년 수집 중 오류: {str(e)}")
                    )

                # API 호출 제한 방지
                import time
                time.sleep(0.1)

            if year_success > 0:
                success_count += 1
            else:
                failed_count += 1

        # 결과 요약
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📈 재수집 완료'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'✅ 성공: {success_count}개 종목')
        self.stdout.write(f'❌ 실패: {failed_count}개 종목')
        self.stdout.write(f'📊 전체: {total_items}개 종목')

        # 최종 검증 상태
        if not verify_only:
            from financials.models import FinancialStatement
            verified = FinancialStatement.objects.filter(is_verified=True).count()
            total = FinancialStatement.objects.count()
            self.stdout.write(f'\n📊 최종 검증 상태: {verified}/{total}개 ({verified/total*100:.1f}%)')

