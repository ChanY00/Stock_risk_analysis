# backend/stocks/management/commands/seed_samsung_prices.py
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from stocks.models import Stock, StockPrice

class Command(BaseCommand):
    help = '삼성전자(005930)에 1년치 모의 주가 데이터를 생성합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=365, help='일수')
        parser.add_argument('--volatility', type=float, default=0.02, help='일일 변동성')

    def handle(self, *args, **opts):
        days = opts['days']
        vol  = opts['volatility']
        try:
            stock = Stock.objects.get(stock_code='005930')
        except Stock.DoesNotExist:
            self.stdout.write(self.style.ERROR('삼성전자(005930) 종목이 없습니다.'))
            return

        today = date.today()
        last_record = StockPrice.objects.filter(stock=stock).order_by('-date').first()
        last_price  = last_record.close_price if last_record else random.randint(50000, 100000)
        start_date  = today - timedelta(days=days - 1)

        for i in range(days):
            d = start_date + timedelta(days=i)
            if d.weekday() >= 5:  # 주말 스킵
                continue
            change_pct = random.normalvariate(0, vol)
            price = max(1000, round(last_price * (1 + change_pct)))
            StockPrice.objects.update_or_create(
                stock=stock, date=d, defaults={'close_price': price}
            )
            last_price = price

        self.stdout.write(self.style.SUCCESS(f'✅ 삼성전자 1년치 데이터 생성 완료'))
