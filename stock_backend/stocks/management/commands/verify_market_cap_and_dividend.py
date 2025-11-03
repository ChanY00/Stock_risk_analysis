"""
시가총액과 배당수익률 검증 및 수정 관리 명령어

모든 종목의 시가총액과 배당수익률을 검증하고, 
필요시 현재 주가를 기준으로 재계산하여 업데이트합니다.
"""
from django.core.management.base import BaseCommand
from stocks.models import Stock
from financials.models import FinancialStatement
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '시가총액과 배당수익률을 검증하고 수정합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='불일치 항목 자동 수정',
        )
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 처리',
        )
        parser.add_argument(
            '--threshold',
            type=float,
            default=5.0,
            help='시가총액 차이 허용 임계값 (퍼센트, 기본값: 5.0)',
        )

    def handle(self, *args, **options):
        fix = options.get('fix', False)
        stock_codes = options.get('stock_codes')
        threshold = options.get('threshold', 5.0)

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('🔍 시가총액 및 배당수익률 검증'))
        self.stdout.write('=' * 70 + '\n')

        # 대상 종목 필터링
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            stocks = Stock.objects.filter(
                market_cap__isnull=False,
                shares_outstanding__isnull=False
            ).exclude(shares_outstanding=0)

        total = stocks.count()
        self.stdout.write(f'📊 검증 대상: {total}개 종목\n')

        market_cap_mismatches = []
        missing_data = []
        dividend_yield_issues = []

        for i, stock in enumerate(stocks, 1):
            if i % 50 == 0:
                self.stdout.write(f'진행률: {i}/{total}...')

            # 시가총액 검증
            current_price = stock.get_current_price()
            if not current_price:
                missing_data.append({
                    'stock': stock,
                    'issue': '주가 데이터 없음'
                })
                continue

            if not stock.shares_outstanding:
                missing_data.append({
                    'stock': stock,
                    'issue': '발행주식수 없음'
                })
                continue

            # 시가총액 계산
            calculated_market_cap = current_price * stock.shares_outstanding

            if stock.market_cap:
                diff = abs(stock.market_cap - calculated_market_cap)
                diff_pct = diff / calculated_market_cap * 100 if calculated_market_cap > 0 else 0

                if diff_pct > threshold:
                    market_cap_mismatches.append({
                        'stock': stock,
                        'current_price': current_price,
                        'shares_outstanding': stock.shares_outstanding,
                        'calculated': calculated_market_cap,
                        'db_value': stock.market_cap,
                        'diff_pct': diff_pct
                    })

            # 배당수익률 검증 (EPS와 배당수익률 관계 확인)
            if stock.dividend_yield and stock.dividend_yield > 0:
                # EPS가 있으면 배당수익률 검증 가능
                latest_financial = stock.financials.first()
                if latest_financial and latest_financial.eps and latest_financial.eps > 0:
                    # 배당수익률 = (주당배당금 / 주가) * 100
                    # 주당배당금 = EPS * 배당성향 (보통 10~50%)
                    # 배당수익률이 20% 이상이면 이상
                    if stock.dividend_yield > 20:
                        dividend_yield_issues.append({
                            'stock': stock,
                            'dividend_yield': stock.dividend_yield,
                            'eps': latest_financial.eps,
                            'issue': '배당수익률 과다'
                        })

        # 결과 출력
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 검증 결과'))
        self.stdout.write('=' * 70 + '\n')

        self.stdout.write(f'전체 검증: {total}개')
        self.stdout.write(f'✅ 정상: {total - len(market_cap_mismatches) - len(missing_data)}개')
        self.stdout.write(f'⚠️  시가총액 불일치: {len(market_cap_mismatches)}개')
        self.stdout.write(f'❌ 데이터 부재: {len(missing_data)}개')
        if dividend_yield_issues:
            self.stdout.write(f'⚠️  배당수익률 이상: {len(dividend_yield_issues)}개')
        self.stdout.write()

        # 시가총액 불일치 종목 출력
        if market_cap_mismatches:
            self.stdout.write(self.style.WARNING(f'\n⚠️  시가총액 불일치 종목 ({len(market_cap_mismatches)}개):'))
            for item in sorted(market_cap_mismatches, key=lambda x: x['diff_pct'], reverse=True)[:20]:
                stock = item['stock']
                self.stdout.write(
                    f'  - {stock.stock_name} ({stock.stock_code}): '
                    f'차이 {item["diff_pct"]:.2f}% | '
                    f'계산: {item["calculated"]/1e12:.2f}조원 | '
                    f'DB: {item["db_value"]/1e12:.2f}조원'
                )

        # 배당수익률 이상 종목 출력
        if dividend_yield_issues:
            self.stdout.write(self.style.WARNING(f'\n⚠️  배당수익률 이상 종목 ({len(dividend_yield_issues)}개):'))
            for item in dividend_yield_issues[:20]:
                stock = item['stock']
                self.stdout.write(
                    f'  - {stock.stock_name} ({stock.stock_code}): '
                    f'배당수익률 {item["dividend_yield"]:.2f}% | '
                    f'EPS {item["eps"]:,}원'
                )

        # 데이터 부재 종목 출력
        if missing_data:
            self.stdout.write(self.style.ERROR(f'\n❌ 데이터 부재 종목 ({len(missing_data)}개):'))
            for item in missing_data[:20]:
                stock = item['stock']
                self.stdout.write(f'  - {stock.stock_name} ({stock.stock_code}): {item["issue"]}')

        # 수정 실행
        if fix and market_cap_mismatches:
            self.stdout.write('\n' + '=' * 70)
            self.stdout.write(self.style.SUCCESS('🔧 시가총액 자동 수정 중...'))
            self.stdout.write('=' * 70 + '\n')

            fixed_count = 0
            for item in market_cap_mismatches:
                stock = item['stock']
                try:
                    stock.market_cap = item['calculated']
                    stock.save()
                    fixed_count += 1
                    self.stdout.write(
                        f'✅ {stock.stock_name} ({stock.stock_code}): '
                        f'{item["db_value"]/1e12:.2f}조원 → {item["calculated"]/1e12:.2f}조원'
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ {stock.stock_name} ({stock.stock_code}): 수정 실패 - {str(e)}'
                        )
                    )

            self.stdout.write(f'\n✅ {fixed_count}개 종목 시가총액 수정 완료')

        # 배당수익률 계산 방법 안내
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('📝 배당수익률 계산 방법')
        self.stdout.write('=' * 70)
        self.stdout.write('배당수익률 = (연간 주당배당금 / 현재 주가) × 100')
        self.stdout.write('※ 주당배당금은 재무제표나 공시에서 확인 필요')
        self.stdout.write('※ 현재 배당수익률은 외부 API나 공시 데이터에서 가져와야 함\n')

        # 결과 요약
        self.stdout.write(f'\n📊 최종 요약:')
        self.stdout.write(f'  - 전체: {total}개')
        self.stdout.write(f'  - 정상: {total - len(market_cap_mismatches) - len(missing_data)}개')
        self.stdout.write(f'  - 시가총액 불일치: {len(market_cap_mismatches)}개')
        self.stdout.write(f'  - 데이터 부재: {len(missing_data)}개')
        
        if fix and market_cap_mismatches:
            self.stdout.write(f'\n✅ 수정 완료: {fixed_count}개 종목')
        
        # 검증 완료
        self.stdout.write('\n✅ 검증 완료')

