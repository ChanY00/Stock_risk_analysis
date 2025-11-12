#!/usr/bin/env python
"""모든 주식의 최신 종가를 KIS API에서 가져와 업데이트"""
import os
import django
import time
from datetime import date, datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings.base')
django.setup()

from stocks.models import Stock, StockPrice
from kis_api.client import KISApiClient

# KIS API 클라이언트 초기화 (모의투자 모드)
client = KISApiClient(is_mock=True)

# 모든 주식 가져오기
stocks = Stock.objects.all()
total = stocks.count()

print(f'=' * 80)
print(f'📊 전체 {total}개 주식의 최신 종가 업데이트 시작')
print(f'=' * 80)

updated_count = 0
skipped_count = 0
error_count = 0

for idx, stock in enumerate(stocks, 1):
    try:
        print(f'\n[{idx}/{total}] {stock.stock_code} ({stock.stock_name}) 처리 중...')
        
        # KIS API에서 일봉 데이터 가져오기
        daily_data = client.get_daily_price(stock.stock_code)
        
        if not daily_data or 'output2' not in daily_data or not daily_data['output2']:
            print(f'  ⚠️  데이터 없음')
            skipped_count += 1
            continue
        
        # 가장 최신 데이터 (첫 번째 항목)
        latest = daily_data['output2'][0]
        
        # 날짜 파싱 (YYYYMMDD -> date 객체)
        date_str = latest['stck_bsop_date']
        price_date = datetime.strptime(date_str, '%Y%m%d').date()
        
        # 가격 데이터
        close_price = int(latest['stck_clpr'])
        open_price = int(latest['stck_oprc'])
        high_price = int(latest['stck_hgpr'])
        low_price = int(latest['stck_lwpr'])
        volume = int(latest['acml_vol'])
        
        # StockPrice 업데이트 또는 생성
        price_obj, created = StockPrice.objects.update_or_create(
            stock=stock,
            date=price_date,
            defaults={
                'open_price': open_price,
                'high_price': high_price,
                'low_price': low_price,
                'close_price': close_price,
                'volume': volume
            }
        )
        
        # Stock 모델의 current_price 업데이트
        old_price = stock.current_price
        stock.current_price = close_price
        stock.save(update_fields=['current_price'])
        
        action = '생성' if created else '업데이트'
        print(f'  ✅ {action}: {price_date} - {close_price:,}원 (이전: {old_price:,}원 if old_price else "없음")')
        updated_count += 1
        
        # API 호출 제한 방지 (초당 20건 제한)
        if idx % 20 == 0:
            print(f'  ⏸️  API 제한 방지를 위해 1초 대기...')
            time.sleep(1)
        
    except Exception as e:
        print(f'  ❌ 오류: {e}')
        error_count += 1
        continue

print(f'\n' + '=' * 80)
print(f'📊 업데이트 완료')
print(f'=' * 80)
print(f'✅ 업데이트됨: {updated_count}개')
print(f'⏭️  건너뜀: {skipped_count}개')
print(f'❌ 오류: {error_count}개')
print(f'=' * 80)
