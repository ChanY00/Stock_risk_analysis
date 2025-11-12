#!/usr/bin/env python
"""Stock 테이블의 current_price를 StockPrice의 최신 종가로 동기화"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings.base')
django.setup()

from stocks.models import Stock, StockPrice
from django.db.models import Max

# 모든 주식 가져오기
stocks = Stock.objects.all()
total = stocks.count()

print(f'=' * 80)
print(f'📊 전체 {total}개 주식의 current_price를 최신 종가로 동기화')
print(f'=' * 80)

updated_count = 0
skipped_count = 0
no_data_count = 0

for idx, stock in enumerate(stocks, 1):
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
                
                print(f'[{idx}/{total}] ✅ {stock.stock_code} ({stock.stock_name}): '
                      f'{old_price or 0:,}원 → {new_price:,}원 (날짜: {latest_price.date})')
                updated_count += 1
            else:
                skipped_count += 1
        else:
            no_data_count += 1
            if idx <= 10:  # 처음 10개만 출력
                print(f'[{idx}/{total}] ⚠️  {stock.stock_code} ({stock.stock_name}): StockPrice 데이터 없음')
            
    except Exception as e:
        print(f'[{idx}/{total}] ❌ {stock.stock_code} ({stock.stock_name}): 오류 - {e}')
        continue

print(f'\n' + '=' * 80)
print(f'📊 동기화 완료')
print(f'=' * 80)
print(f'✅ 업데이트됨: {updated_count}개')
print(f'⏭️  변경 없음: {skipped_count}개')
print(f'⚠️  데이터 없음: {no_data_count}개')
print(f'=' * 80)
