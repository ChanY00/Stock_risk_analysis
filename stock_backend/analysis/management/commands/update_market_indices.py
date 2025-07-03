from django.core.management.base import BaseCommand
from django.utils import timezone
from analysis.models import MarketIndex
import random
from datetime import datetime

class Command(BaseCommand):
    help = '시장 지수 데이터를 업데이트합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-sample',
            action='store_true',
            help='샘플 시장 지수 데이터를 생성합니다'
        )

    def handle(self, *args, **options):
        if options.get('create_sample'):
            self.create_sample_data()
        else:
            self.update_market_indices()

    def create_sample_data(self):
        """샘플 시장 지수 데이터 생성"""
        self.stdout.write("샘플 시장 지수 데이터를 생성합니다...")
        
        # KOSPI 데이터
        kospi, created = MarketIndex.objects.get_or_create(
            name='KOSPI',
            defaults={
                'current_value': 2580.50,
                'change': -15.30,
                'change_percent': -0.59,
                'volume': 524_000_000,
                'trade_value': 8_950_000_000_000,
                'high': 2595.80,
                'low': 2575.20
            }
        )
        
        # KOSDAQ 데이터
        kosdaq, created = MarketIndex.objects.get_or_create(
            name='KOSDAQ',
            defaults={
                'current_value': 745.80,
                'change': 8.90,
                'change_percent': 1.21,
                'volume': 850_000_000,
                'trade_value': 12_300_000_000_000,
                'high': 748.50,
                'low': 737.20
            }
        )
        
        # KRX 100 데이터
        krx100, created = MarketIndex.objects.get_or_create(
            name='KRX100',
            defaults={
                'current_value': 4125.30,
                'change': -22.10,
                'change_percent': -0.53,
                'volume': 125_000_000,
                'trade_value': 2_800_000_000_000,
                'high': 4147.40,
                'low': 4118.90
            }
        )
        
        self.stdout.write(
            self.style.SUCCESS("샘플 시장 지수 데이터 생성 완료")
        )

    def update_market_indices(self):
        """시장 지수 업데이트 (실제로는 외부 API에서 가져와야 함)"""
        self.stdout.write("시장 지수를 업데이트합니다...")
        
        indices = MarketIndex.objects.all()
        
        if not indices.exists():
            self.stdout.write(
                self.style.WARNING("시장 지수 데이터가 없습니다. --create-sample 옵션을 사용하여 생성하세요.")
            )
            return
        
        updated_count = 0
        
        for index in indices:
            try:
                # 실제로는 외부 API에서 데이터를 가져와야 하지만, 
                # 여기서는 시뮬레이션용 랜덤 변동을 적용
                old_value = index.current_value
                
                # -2% ~ +2% 범위의 랜덤 변동
                change_percent = random.uniform(-2.0, 2.0)
                change_amount = old_value * (change_percent / 100)
                new_value = old_value + change_amount
                
                # 고가/저가 계산
                high = new_value * random.uniform(1.002, 1.008)  # 0.2~0.8% 위
                low = new_value * random.uniform(0.992, 0.998)   # 0.2~0.8% 아래
                
                # 거래량 및 거래대금 (현실적인 범위로 조정)
                if index.name == 'KOSPI':
                    volume = random.randint(400_000_000, 800_000_000)
                    trade_value = random.randint(6_000_000_000_000, 15_000_000_000_000)
                elif index.name == 'KOSDAQ':
                    volume = random.randint(600_000_000, 1_200_000_000)
                    trade_value = random.randint(8_000_000_000_000, 20_000_000_000_000)
                else:  # KRX100
                    volume = random.randint(80_000_000, 200_000_000)
                    trade_value = random.randint(2_000_000_000_000, 5_000_000_000_000)
                
                # 업데이트
                index.current_value = round(new_value, 2)
                index.change = round(change_amount, 2)
                index.change_percent = round(change_percent, 2)
                index.volume = volume
                index.trade_value = trade_value
                index.high = round(high, 2)
                index.low = round(low, 2)
                index.updated_at = timezone.now()
                index.save()
                
                updated_count += 1
                
                self.stdout.write(
                    f"업데이트: {index.name} = {index.current_value:,.2f} "
                    f"({index.change:+.2f}, {index.change_percent:+.2f}%)"
                )
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"오류 - {index.name}: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS(f"시장 지수 업데이트 완료: {updated_count}개")
        )

    def get_market_summary(self):
        """시장 요약 정보 출력"""
        indices = MarketIndex.objects.all().order_by('name')
        
        self.stdout.write("\n=== 시장 지수 현황 ===")
        for index in indices:
            direction = "↑" if index.change > 0 else "↓" if index.change < 0 else "→"
            self.stdout.write(
                f"{index.name:8s}: {index.current_value:8,.2f} "
                f"{direction} {index.change:+7.2f} ({index.change_percent:+5.2f}%) "
                f"거래량: {index.volume:,}"
            ) 