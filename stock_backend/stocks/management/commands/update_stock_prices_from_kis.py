"""
KIS API를 사용하여 개별 종목의 실시간 주가와 거래량을 가져와 DB에 저장

StockPriceService를 사용하여 KIS API에서 실시간 주가와 거래량을 가져와
Stock 모델의 current_price와 StockPrice 모델에 저장합니다.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from stocks.models import Stock, StockPrice
from stocks.services import StockPriceService
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'KIS API를 사용하여 개별 종목의 실시간 주가와 거래량을 가져와 DB에 저장합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 처리 (지정하지 않으면 모든 종목 처리)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='배치 크기 (기본값: 10)',
        )
        parser.add_argument(
            '--save-to-history',
            action='store_true',
            help='StockPrice 테이블에 오늘 날짜로 저장 (기본값: False)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='기존 current_price가 있어도 덮어쓰기',
        )

    def handle(self, *args, **options):
        stock_codes = options.get('stock_codes')
        batch_size = options.get('batch_size', 10)
        save_to_history = options.get('save_to_history', False)
        overwrite = options.get('overwrite', False)

        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 KIS API 실시간 주가 및 거래량 업데이트'))
        self.stdout.write('=' * 80 + '\n')

        # StockPriceService 초기화
        price_service = StockPriceService()

        # 대상 종목 필터링
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            stocks = Stock.objects.all()

        total = stocks.count()
        self.stdout.write(f'📊 처리 대상: {total}개 종목')
        self.stdout.write(f'📦 배치 크기: {batch_size}개\n')

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
                    
                    # 실시간 주가 조회
                    price_data = price_service.get_real_time_price(stock_code)
                    
                    if not price_data:
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  {stock.stock_name} ({stock_code}): 주가 조회 실패')
                        )
                        failed_count += 1
                        continue

                    current_price = price_data.get('current_price', 0)
                    volume = price_data.get('volume', 0)
                    trading_value = price_data.get('trading_value', 0)
                    
                    if current_price <= 0:
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  {stock.stock_name} ({stock_code}): 유효하지 않은 주가 ({current_price})')
                        )
                        failed_count += 1
                        continue

                    # 기존 current_price 확인
                    if stock.current_price and not overwrite:
                        self.stdout.write(
                            self.style.WARNING(f'  ⏭️  {stock.stock_name} ({stock_code}): 기존 주가 있음 (건너뜀)')
                        )
                        skipped_count += 1
                        continue

                    # Stock 모델 업데이트
                    old_price = stock.current_price
                    stock.current_price = current_price
                    
                    # 시가총액 재계산 (발행주식수가 있는 경우)
                    if stock.shares_outstanding:
                        stock.market_cap = current_price * stock.shares_outstanding
                    
                    stock.save()
                    
                    # StockPrice 테이블에 오늘 날짜로 저장 (선택적)
                    if save_to_history:
                        today = timezone.now().date()
                        StockPrice.objects.update_or_create(
                            stock=stock,
                            date=today,
                            defaults={
                                'open_price': price_data.get('open_price', current_price),
                                'high_price': price_data.get('high_price', current_price),
                                'low_price': price_data.get('low_price', current_price),
                                'close_price': current_price,
                                'volume': volume,
                            }
                        )
                    
                    price_change = f"({current_price - old_price:+,})" if old_price else ""
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ {stock.stock_name} ({stock_code}): '
                            f'{old_price:,}원 → {current_price:,}원 {price_change} '
                            f'(거래량: {volume:,}주)'
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
            self.stdout.write('\n💡 추가 안내')
            self.stdout.write('=' * 80)
            self.stdout.write('실시간 주가가 업데이트되었습니다.')
            if save_to_history:
                self.stdout.write('StockPrice 테이블에 오늘 날짜로 저장되었습니다.')
            else:
                self.stdout.write('StockPrice 테이블에 저장하려면 --save-to-history 옵션을 사용하세요.')
            self.stdout.write('=' * 80)


