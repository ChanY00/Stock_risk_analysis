import requests
from django.core.management.base import BaseCommand
from stocks.models import Stock
from datetime import datetime, timedelta
import pandas as pd
import FinanceDataReader as fdr

class Command(BaseCommand):
    help = '코스피 200 종목 목록을 가져와서 DB에 저장합니다.'

    def handle(self, *args, **options):
        try:
            # 코스피 200 구성 종목 리스트 조회
            df_constituents = fdr.SnapDataReader('KRX/INDEX/STOCK/1028')
            self.stdout.write(f"Found {len(df_constituents)} KOSPI200 constituents")
            self.stdout.write(f"Constituents columns: {df_constituents.columns.tolist()}")
            
            # 전체 상장 종목 리스트 불러오기
            df_listing = fdr.StockListing('KRX')
            self.stdout.write(f"Found {len(df_listing)} total listed stocks")
            self.stdout.write(f"Listing columns: {df_listing.columns.tolist()}")
            
            # 병합: 'Code' 컬럼을 키로 왼쪽 조인
            df_kospi200 = pd.merge(
                df_constituents,
                df_listing,
                on='Code',
                how='left',
                suffixes=('_const', '_list')
            )
            
            self.stdout.write(f"Successfully merged data. Total KOSPI200 stocks: {len(df_kospi200)}")
            self.stdout.write(f"Merged columns: {df_kospi200.columns.tolist()}")
            
            # 기존 데이터 삭제
            Stock.objects.all().delete()
            
            # 새로운 데이터 저장
            for _, row in df_kospi200.iterrows():
                stock = Stock.objects.create(
                    stock_code=row['Code'],
                    stock_name=row['Name_list']  # 'Name' 대신 'Name_list' 사용
                )
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created stock {stock.stock_name} ({stock.stock_code})')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error occurred: {str(e)}')
            ) 