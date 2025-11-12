"""
전체 종목 발행주식수 및 배당수익률 일괄 업데이트 명령어

배치 처리로 전체 종목의 발행주식수와 배당수익률을 업데이트합니다.
"""
from django.core.management.base import BaseCommand
from stocks.models import Stock
from stocks.management.commands.update_shares_and_dividend import Command as UpdateCommand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '전체 종목의 발행주식수 및 배당수익률을 일괄 업데이트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='한 번에 처리할 종목 수 (기본값: 50)',
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

    def handle(self, *args, **options):
        batch_size = options.get('batch_size', 50)
        update_shares_only = options.get('update_shares_only', False)
        update_dividend_only = options.get('update_dividend_only', False)

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 전체 종목 발행주식수 및 배당수익률 일괄 업데이트'))
        self.stdout.write('=' * 70 + '\n')

        stocks = Stock.objects.all()
        total = stocks.count()
        
        self.stdout.write(f'📊 전체 대상: {total}개 종목')
        self.stdout.write(f'배치 크기: {batch_size}개\n')

        # UpdateCommand 인스턴스 생성하여 사용
        update_cmd = UpdateCommand()
        update_cmd.stdout = self.stdout
        update_cmd.style = self.style

        total_updated_shares = 0
        total_updated_dividend = 0
        failed_count = 0

        for i in range(0, total, batch_size):
            batch = stocks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            self.stdout.write(f'\n[{배치 {batch_num}/{total_batches}] {len(batch)}개 종목 처리 중...')

            # 배치 내 종목들 처리
            for stock in batch:
                try:
                    if not update_dividend_only:
                        if update_cmd.update_shares_outstanding(stock, update_cmd.kis_client, overwrite=True):
                            total_updated_shares += 1
                    
                    if not update_shares_only:
                        dart_api_key = os.getenv('DART_API_KEY')
                        if update_cmd.update_dividend_yield(stock, update_cmd.kis_client, dart_api_key, overwrite=True):
                            total_updated_dividend += 1
                    
                except Exception as e:
                    failed_count += 1
                    logger.exception(f"Error updating {stock.stock_code}: {e}")

        # 최종 결과
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 일괄 업데이트 완료'))
        self.stdout.write('=' * 70 + '\n')
        
        if not update_dividend_only:
            self.stdout.write(f'발행주식수 업데이트: {total_updated_shares}개')
        if not update_shares_only:
            self.stdout.write(f'배당수익률 업데이트: {total_updated_dividend}개')
        
        self.stdout.write(f'실패: {failed_count}개')
        self.stdout.write(f'전체: {total}개\n')

