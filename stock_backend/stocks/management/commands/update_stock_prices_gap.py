"""
마지막 업데이트 날짜 이후부터 오늘까지의 주가 데이터를 가져와 DB에 저장

StockPrice 테이블에서 마지막 업데이트 날짜를 확인하고,
그 날짜 다음 날부터 오늘까지의 주가와 거래량 데이터를 가져와 저장합니다.
FinanceDataReader를 사용하여 주가 데이터를 가져옵니다.
"""
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.utils import timezone
from stocks.models import Stock, StockPrice
from datetime import datetime, timedelta
import FinanceDataReader as fdr
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '마지막 업데이트 날짜 이후부터 오늘까지의 주가 데이터를 가져와 DB에 저장합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 처리 (지정하지 않으면 모든 종목 처리)',
        )
        parser.add_argument(
            '--force-start-date',
            type=str,
            help='강제로 시작 날짜 지정 (YYYY-MM-DD 형식)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='배치 크기 (기본값: 10)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='같은 날짜의 데이터가 있어도 덮어쓰기',
        )

    def handle(self, *args, **options):
        stock_codes = options.get('stock_codes')
        force_start_date = options.get('force_start_date')
        batch_size = options.get('batch_size', 10)
        overwrite = options.get('overwrite', False)

        self.stdout.write('=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 주가 데이터 갭 업데이트'))
        self.stdout.write('=' * 80 + '\n')

        # 전체 마지막 업데이트 날짜 확인 (정보 제공용)
        overall_last_date_result = StockPrice.objects.aggregate(Max('date'))
        overall_last_date = overall_last_date_result.get('date__max')
        
        if overall_last_date:
            self.stdout.write(f'📅 전체 마지막 업데이트 날짜: {overall_last_date}')
        else:
            self.stdout.write(self.style.WARNING('⚠️  기존 주가 데이터가 없습니다.'))
        
        end_date = timezone.now().date()
        self.stdout.write(f'📅 오늘 날짜: {end_date}\n')
        
        # 강제 시작 날짜가 있으면 전체 시작 날짜로 사용 (각 종목별 체크는 여전히 수행)
        if force_start_date:
            try:
                force_start = datetime.strptime(force_start_date, '%Y-%m-%d').date()
                self.stdout.write(f'📅 강제 시작 날짜: {force_start} (각 종목별 마지막 날짜와 비교하여 더 늦은 날짜 사용)')
            except ValueError:
                self.stdout.write(self.style.ERROR(f'❌ 잘못된 날짜 형식: {force_start_date} (YYYY-MM-DD 형식 필요)'))
                return
        else:
            force_start = None

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
        total_prices_saved = 0

        # 배치 처리
        for i in range(0, total, batch_size):
            batch = stocks[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            self.stdout.write(f'📦 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 종목)\n')

            for stock in batch:
                try:
                    stock_code = stock.stock_code
                    
                    # 해당 종목의 마지막 날짜 확인
                    stock_last_date_result = StockPrice.objects.filter(stock=stock).aggregate(Max('date'))
                    stock_last_date = stock_last_date_result.get('date__max')
                    
                    # 강제 시작 날짜가 있으면 우선 사용
                    if force_start:
                        # force_start 다음 날부터 시작
                        stock_start_date = force_start + timedelta(days=1)
                    elif stock_last_date:
                        # 마지막 날짜 다음 날부터 시작
                        stock_start_date = stock_last_date + timedelta(days=1)
                    else:
                        # 데이터가 없으면 1년 전부터 시작
                        stock_start_date = (end_date - timedelta(days=365))
                    
                    if stock_start_date > end_date:
                        self.stdout.write(
                            self.style.SUCCESS(f'  ✅ {stock.stock_name} ({stock_code}): 최신 상태')
                        )
                        skipped_count += 1
                        continue

                    # 주가 데이터 가져오기
                    self.stdout.write(f'  🔍 {stock.stock_name} ({stock_code}): {stock_start_date} ~ {end_date} 데이터 조회 중...')
                    
                    try:
                        df_price = fdr.DataReader(stock_code, stock_start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
                    except Exception as e:
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  {stock.stock_name} ({stock_code}): FinanceDataReader 오류 - {e}')
                        )
                        failed_count += 1
                        continue
                    
                    if df_price.empty:
                        self.stdout.write(
                            self.style.WARNING(f'  ⚠️  {stock.stock_name} ({stock_code}): 데이터 없음')
                        )
                        failed_count += 1
                        continue

                    # 데이터 저장
                    price_count = 0
                    for date_idx, row in df_price.iterrows():
                        # 날짜 처리 (pandas Timestamp를 date로 변환)
                        if isinstance(date_idx, pd.Timestamp):
                            price_date = date_idx.date()
                        else:
                            price_date = date_idx

                        # 중복 체크
                        existing = StockPrice.objects.filter(stock=stock, date=price_date).first()
                        if existing and not overwrite:
                            continue

                        try:
                            if existing:
                                # 업데이트
                                existing.open_price = int(row['Open'])
                                existing.high_price = int(row['High'])
                                existing.low_price = int(row['Low'])
                                existing.close_price = int(row['Close'])
                                existing.volume = int(row['Volume'])
                                existing.save()
                            else:
                                # 생성
                                StockPrice.objects.create(
                                    stock=stock,
                                    date=price_date,
                                    open_price=int(row['Open']),
                                    high_price=int(row['High']),
                                    low_price=int(row['Low']),
                                    close_price=int(row['Close']),
                                    volume=int(row['Volume'])
                                )
                            price_count += 1
                        except Exception as e:
                            logger.debug(f"Error saving price for {stock_code} on {price_date}: {e}")
                            continue

                    if price_count > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✅ {stock.stock_name} ({stock_code}): {price_count}일 데이터 저장 완료'
                            )
                        )
                        updated_count += 1
                        total_prices_saved += price_count
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'  ⏭️  {stock.stock_name} ({stock_code}): 저장할 새 데이터 없음')
                        )
                        skipped_count += 1

                    # API 호출 제한 방지
                    time.sleep(0.3)

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ {stock.stock_name} ({stock_code}): 오류 - {e}')
                    )
                    failed_count += 1
                    logger.exception(f"Error updating prices for {stock_code}")

            # 배치 간 간격
            if i + batch_size < total:
                time.sleep(0.5)

        # 결과 요약
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📊 업데이트 완료'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'처리 기간: ~ {end_date}')
        self.stdout.write(f'전체 종목: {total}개')
        self.stdout.write(self.style.SUCCESS(f'✅ 업데이트: {updated_count}개 종목'))
        self.stdout.write(self.style.SUCCESS(f'✅ 저장된 주가 데이터: {total_prices_saved}일'))
        self.stdout.write(self.style.WARNING(f'⏭️  건너뜀: {skipped_count}개'))
        self.stdout.write(self.style.ERROR(f'❌ 실패: {failed_count}개'))
        self.stdout.write('=' * 80)

        if updated_count > 0:
            # 업데이트 후 마지막 날짜 확인
            new_last_date = StockPrice.objects.aggregate(Max('date'))['date__max']
            self.stdout.write(f'\n📅 업데이트 후 마지막 날짜: {new_last_date}')
            self.stdout.write('=' * 80)

