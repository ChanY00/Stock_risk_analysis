"""
OpenDartReader를 사용하여 모든 주식의 유통주식수를 DART API에서 가져와 DB에 업데이트

시가총액 계산에는 유통주식수를 사용하므로, 이 명령어를 통해 정확한 시가총액을 계산할 수 있습니다.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from stocks.models import Stock
import OpenDartReader
import os
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'OpenDartReader를 사용하여 DART API에서 유통주식수를 가져와 DB에 업데이트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 처리 (지정하지 않으면 모든 종목 처리)',
        )
        parser.add_argument(
            '--use-distb-stock',
            action='store_true',
            help='유통주식수(distb_stock_co) 사용 (기본값: True)',
        )
        parser.add_argument(
            '--use-issued-stock',
            action='store_true',
            help='발행주식수(now_to_isu_stock_totqy) 사용 (기본값: False)',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2024,
            help='조회할 연도 (기본값: 2024)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='기존 데이터가 있어도 덮어쓰기',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제로 업데이트하지 않고 시뮬레이션만 수행',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='배치 크기 (기본값: 100)',
        )

    def handle(self, *args, **options):
        stock_codes = options.get('stock_codes')
        use_distb_stock = options.get('use_distb_stock', True)
        use_issued_stock = options.get('use_issued_stock', False)
        year = options.get('year', 2024)
        overwrite = options.get('overwrite', False)
        dry_run = options.get('dry_run', False)
        batch_size = options.get('batch_size', 100)

        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 DART API 유통주식수 업데이트'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'사용 모드: {"[DRY RUN] 시뮬레이션만" if dry_run else "실제 업데이트"}')
        self.stdout.write(f'조회 연도: {year}')
        self.stdout.write(f'사용할 값: {"유통주식수" if use_distb_stock else "발행주식수"}')
        self.stdout.write('=' * 80 + '\n')

        # DART API 키 확인
        api_key = os.getenv('DART_API_KEY')
        if not api_key:
            self.stdout.write(self.style.ERROR('❌ DART_API_KEY 환경변수가 설정되지 않았습니다.'))
            return

        # OpenDartReader 초기화
        try:
            dart = OpenDartReader(api_key)
            self.stdout.write(self.style.SUCCESS('✅ OpenDartReader 초기화 성공\n'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ OpenDartReader 초기화 실패: {e}'))
            return

        # 대상 종목 필터링
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            stocks = Stock.objects.all()

        total = stocks.count()
        self.stdout.write(f'📊 처리 대상: {total}개 종목\n')

        # DART 기업 고유번호 매핑 캐싱
        self.stdout.write('🔍 DART 기업 고유번호 매핑 조회 중...')
        corp_mapping = self.get_corp_code_mapping(dart, stocks)
        self.stdout.write(f'✅ {len(corp_mapping)}개 기업 정보 로드 완료\n\n')

        updated_count = 0
        failed_count = 0
        skipped_count = 0

        # 배치 처리
        for i in range(0, total, batch_size):
            batch = stocks[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            self.stdout.write(f'📦 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 종목)\n')

            for stock in batch:
                try:
                    stock_code = stock.stock_code
                    corp_code = corp_mapping.get(stock_code)

                    if not corp_code:
                        self.stdout.write(f'  ⚠️  {stock.stock_name} ({stock_code}): DART 고유번호 없음')
                        skipped_count += 1
                        continue

                    # 유통주식수 조회
                    result = self.get_shares_from_dart(dart, corp_code, year, use_distb_stock, use_issued_stock)

                    if not result:
                        self.stdout.write(f'  ⚠️  {stock.stock_name} ({stock_code}): DART API 조회 실패')
                        failed_count += 1
                        continue

                    shares = result['shares']
                    source = result['source']

                    # 기존 데이터 확인
                    if stock.shares_outstanding and not overwrite:
                        self.stdout.write(f'  ⏭️  {stock.stock_name} ({stock_code}): 기존 데이터 있음 (건너뜀)')
                        skipped_count += 1
                        continue

                    # 업데이트
                    old_shares = stock.shares_outstanding
                    
                    if not dry_run:
                        stock.shares_outstanding = shares
                        
                        # 시가총액 재계산
                        current_price = stock.get_current_price()
                        if current_price:
                            stock.market_cap = current_price * shares
                        
                        stock.save()
                    
                    diff = abs(shares - old_shares) if old_shares else 0
                    diff_percent = (diff / max(shares, old_shares)) * 100 if old_shares and max(shares, old_shares) > 0 else 0
                    
                    status = "[DRY RUN] " if dry_run else ""
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ {status}{stock.stock_name} ({stock_code}): '
                            f'{old_shares:,}주 → {shares:,}주 ({diff:,}주, {diff_percent:.2f}%) '
                            f'[{source}]'
                        )
                    )
                    
                    updated_count += 1
                    time.sleep(0.1)  # API 호출 제한 방지

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ {stock.stock_name} ({stock_code}): 오류 - {e}')
                    )
                    failed_count += 1
                    logger.exception(f"Error updating {stock_code}")

            # 배치 간 간격
            if i + batch_size < total:
                time.sleep(0.5)

        # 결과 요약
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 업데이트 완료'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'전체: {total}개')
        self.stdout.write(self.style.SUCCESS(f'✅ 업데이트: {updated_count}개'))
        self.stdout.write(self.style.WARNING(f'⏭️  건너뜀: {skipped_count}개'))
        self.stdout.write(self.style.ERROR(f'❌ 실패: {failed_count}개'))
        self.stdout.write('=' * 80)

        if updated_count > 0:
            self.stdout.write('\n💡 시가총액 재계산 안내')
            self.stdout.write('=' * 80)
            self.stdout.write('유통주식수가 업데이트되었으므로, 시가총액이 자동으로 재계산되었습니다.')
            self.stdout.write('추가로 시가총액을 확인하려면 다음 명령어를 실행하세요:')
            self.stdout.write('  python manage.py verify_market_cap_and_dividend --fix')
            self.stdout.write('=' * 80)

    def get_corp_code_mapping(self, dart: OpenDartReader, stocks) -> Dict[str, str]:
        """종목코드 -> DART 고유번호 매핑 생성"""
        mapping = {}
        
        try:
            corp_list = dart.corp_codes
            
            for stock in stocks:
                matching = corp_list[corp_list['stock_code'] == stock.stock_code]
                if not matching.empty:
                    mapping[stock.stock_code] = matching.iloc[0]['corp_code']
        except Exception as e:
            logger.error(f"Error getting corp code mapping: {e}")
        
        return mapping

    def get_shares_from_dart(
        self,
        dart: OpenDartReader,
        corp_code: str,
        year: int,
        use_distb_stock: bool = True,
        use_issued_stock: bool = False
    ) -> Optional[Dict]:
        """
        DART API에서 주식수 조회
        
        Returns:
            dict: {
                'shares': 주식수,
                'source': 출처 (예: '유통주식수/distb_stock_co')
            }
        """
        try:
            stock_tot_report = dart.report(corp_code, '주식총수', str(year))
            
            if stock_tot_report is None or stock_tot_report.empty:
                return None
            
            # 보통주만 필터링
            if 'se' in stock_tot_report.columns:
                common_stock = stock_tot_report[stock_tot_report['se'] == '보통주']
                if not common_stock.empty:
                    stock_tot_report = common_stock
            
            if stock_tot_report.empty:
                return None
            
            first_row = stock_tot_report.iloc[0]
            
            # 유통주식수 우선 사용
            if use_distb_stock:
                distb_stock = first_row.get('distb_stock_co')
                if distb_stock and distb_stock != '-':
                    try:
                        shares = int(str(distb_stock).replace(',', ''))
                        if 1_000_000 <= shares <= 100_000_000_000:
                            return {
                                'shares': shares,
                                'source': '유통주식수/distb_stock_co',
                            }
                    except (ValueError, AttributeError):
                        pass
            
            # 발행주식수 사용
            if use_issued_stock:
                now_to_isu_stock_totqy = first_row.get('now_to_isu_stock_totqy')
                if now_to_isu_stock_totqy and now_to_isu_stock_totqy != '-':
                    try:
                        shares = int(str(now_to_isu_stock_totqy).replace(',', ''))
                        if 1_000_000 <= shares <= 100_000_000_000:
                            return {
                                'shares': shares,
                                'source': '발행주식수/now_to_isu_stock_totqy',
                            }
                    except (ValueError, AttributeError):
                        pass
            
            # 폴백: 유통주식수 없으면 발행주식수 사용
            if use_distb_stock and not use_issued_stock:
                now_to_isu_stock_totqy = first_row.get('now_to_isu_stock_totqy')
                if now_to_isu_stock_totqy and now_to_isu_stock_totqy != '-':
                    try:
                        shares = int(str(now_to_isu_stock_totqy).replace(',', ''))
                        if 1_000_000 <= shares <= 100_000_000_000:
                            return {
                                'shares': shares,
                                'source': '발행주식수/now_to_isu_stock_totqy (폴백)',
                            }
                    except (ValueError, AttributeError):
                        pass
            
            return None

        except Exception as e:
            logger.debug(f"Error getting shares from DART for {corp_code}: {e}")
            return None

