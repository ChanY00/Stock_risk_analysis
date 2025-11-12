"""
주식의 current_price를 StockPrice 테이블의 최신 종가로 업데이트하는 관리 명령어
"""
from django.core.management.base import BaseCommand
from django.db.models import Max
from stocks.models import Stock, StockPrice
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Stock 테이블의 current_price를 StockPrice의 최신 종가로 업데이트'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='업데이트할 주식 수 제한 (기본: 전체)',
        )
        parser.add_argument(
            '--stock-code',
            type=str,
            default=None,
            help='특정 종목 코드만 업데이트',
        )

    def handle(self, *args, **options):
        limit = options.get('limit')
        stock_code = options.get('stock_code')
        
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('주식 현재가 업데이트 시작'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # 업데이트할 주식 쿼리셋 생성
        if stock_code:
            stocks = Stock.objects.filter(stock_code=stock_code)
            self.stdout.write(f'대상 종목: {stock_code}')
        else:
            stocks = Stock.objects.all()
            if limit:
                stocks = stocks[:limit]
                self.stdout.write(f'대상 종목 수: {limit}개')
            else:
                self.stdout.write(f'대상 종목 수: 전체 ({stocks.count()}개)')
        
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        for stock in stocks:
            try:
                # 해당 종목의 최신 종가 조회
                latest_price = StockPrice.objects.filter(
                    stock=stock
                ).order_by('-date').first()
                
                if latest_price and latest_price.close_price:
                    old_price = stock.current_price
                    new_price = latest_price.close_price
                    
                    # 가격이 변경된 경우에만 업데이트
                    if old_price != new_price:
                        stock.current_price = new_price
                        stock.save(update_fields=['current_price'])
                        
                        self.stdout.write(
                            f'✅ {stock.stock_code} ({stock.stock_name}): '
                            f'{old_price:,}원 → {new_price:,}원 '
                            f'(날짜: {latest_price.date})'
                        )
                        updated_count += 1
                    else:
                        skipped_count += 1
                        if options.get('verbosity', 1) >= 2:
                            self.stdout.write(
                                f'⏭️  {stock.stock_code} ({stock.stock_name}): '
                                f'변경 없음 ({old_price:,}원)'
                            )
                else:
                    skipped_count += 1
                    if options.get('verbosity', 1) >= 2:
                        self.stdout.write(
                            self.style.WARNING(
                                f'⚠️  {stock.stock_code} ({stock.stock_name}): '
                                f'StockPrice 데이터 없음'
                            )
                        )
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ {stock.stock_code} ({stock.stock_name}): 오류 - {e}'
                    )
                )
        
        # 결과 요약
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('업데이트 완료'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'✅ 업데이트됨: {updated_count}개')
        self.stdout.write(f'⏭️  건너뜀: {skipped_count}개')
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'❌ 오류: {error_count}개'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
