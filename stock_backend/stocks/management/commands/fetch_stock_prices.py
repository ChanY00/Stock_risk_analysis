from django.core.management.base import BaseCommand
from stocks.models import Stock, StockPrice
from datetime import datetime, timedelta
import FinanceDataReader as fdr
import pandas as pd
import time

class Command(BaseCommand):
    help = '모든 종목의 1년치 주가 데이터를 가져와서 DB에 저장합니다.'

    def handle(self, *args, **options):
        # 기간 설정: 오늘 기준 1년 전부터 오늘까지
        end_date = datetime.today().strftime('%Y-%m-%d')
        start_date = (datetime.today() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        self.stdout.write(f"Fetching stock prices from {start_date} to {end_date}")
        
        # 모든 종목에 대해 반복
        total_stocks = Stock.objects.count()
        processed_stocks = 0
        
        for stock in Stock.objects.all():
            try:
                self.stdout.write(f"Processing {stock.stock_name} ({stock.stock_code})...")
                
                # 주가 데이터 가져오기
                df_price = fdr.DataReader(stock.stock_code, start_date, end_date)
                
                if df_price.empty:
                    self.stdout.write(
                        self.style.WARNING(f'No price data found for {stock.stock_name} ({stock.stock_code})')
                    )
                    continue
                
                # 기존 데이터 삭제
                StockPrice.objects.filter(stock=stock).delete()
                
                # 새로운 데이터 저장
                price_count = 0
                for date, row in df_price.iterrows():
                    try:
                        StockPrice.objects.create(
                            stock=stock,
                            date=date.date(),
                            open_price=int(row['Open']),
                            high_price=int(row['High']),
                            low_price=int(row['Low']),
                            close_price=int(row['Close']),
                            volume=int(row['Volume'])
                        )
                        price_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error saving price for {date.date()}: {str(e)}')
                        )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully saved {price_count} prices for {stock.stock_name} ({stock.stock_code})')
                )
                
                # API 호출 제한을 위한 딜레이
                time.sleep(0.5)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Error fetching prices for {stock.stock_name} ({stock.stock_code}): {str(e)}')
                )
            
            processed_stocks += 1
            self.stdout.write(f"Progress: {processed_stocks}/{total_stocks} stocks processed")
        
        self.stdout.write(self.style.SUCCESS('Finished fetching all stock prices')) 