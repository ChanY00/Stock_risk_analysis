from django.core.management.base import BaseCommand
from django.db import transaction
from stocks.models import Stock
from analysis.models import TechnicalIndicator
from analysis.utils import TechnicalAnalysis
import time

class Command(BaseCommand):
    help = '모든 주식의 기술적 지표를 계산합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-code',
            type=str,
            help='특정 주식 코드만 계산'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='배치 크기 (기본값: 10)'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='기존 데이터를 강제로 덮어쓰기'
        )

    def handle(self, *args, **options):
        stock_code = options.get('stock_code')
        batch_size = options.get('batch_size')
        force = options.get('force')
        
        if stock_code:
            # 특정 주식만 처리
            try:
                stock = Stock.objects.get(stock_code=stock_code)
                self.calculate_for_stock(stock, force)
                self.stdout.write(
                    self.style.SUCCESS(f'{stock.stock_name} ({stock_code}) 기술적 지표 계산 완료')
                )
            except Stock.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'주식 코드 {stock_code}을 찾을 수 없습니다.')
                )
        else:
            # 모든 주식 처리
            self.calculate_all_stocks(batch_size, force)

    def calculate_all_stocks(self, batch_size, force):
        """모든 주식의 기술적 지표 계산"""
        # 주가 데이터가 있는 주식들만 선택
        stocks = Stock.objects.filter(prices__isnull=False).distinct()
        total_stocks = stocks.count()
        
        self.stdout.write(f"총 {total_stocks}개 주식의 기술적 지표를 계산합니다...")
        
        processed = 0
        success_count = 0
        error_count = 0
        
        # 배치로 처리
        for i in range(0, total_stocks, batch_size):
            batch_stocks = stocks[i:i + batch_size]
            
            with transaction.atomic():
                for stock in batch_stocks:
                    try:
                        success = self.calculate_for_stock(stock, force)
                        if success:
                            success_count += 1
                        processed += 1
                        
                        if processed % 50 == 0:
                            self.stdout.write(f"진행률: {processed}/{total_stocks}")
                            
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(
                            self.style.WARNING(f"오류 - {stock.stock_name}: {str(e)}")
                        )
            
            # 배치 간 잠시 대기 (시스템 부하 방지)
            time.sleep(0.1)
        
        self.stdout.write(
            self.style.SUCCESS(
                f"완료: {success_count}개 성공, {error_count}개 오류"
            )
        )

    def calculate_for_stock(self, stock, force=False):
        """개별 주식의 기술적 지표 계산"""
        try:
            # 기존 데이터 확인
            existing_indicator = TechnicalIndicator.objects.filter(stock=stock).first()
            
            if existing_indicator and not force:
                self.stdout.write(f"건너뜀: {stock.stock_name} (이미 계산됨)")
                return False
            
            # 기술적 지표 계산
            indicators = TechnicalAnalysis.calculate_all_indicators(stock)
            
            if not indicators:
                self.stdout.write(f"건너뜀: {stock.stock_name} (주가 데이터 부족)")
                return False
            
            # TechnicalIndicator 객체 생성 또는 업데이트
            technical_indicator, created = TechnicalIndicator.objects.update_or_create(
                stock=stock,
                defaults={
                    'ma5': indicators.get('ma5'),
                    'ma20': indicators.get('ma20'),
                    'ma60': indicators.get('ma60'),
                    'rsi': indicators.get('rsi'),
                    'macd': indicators.get('macd'),
                    'macd_signal': indicators.get('macd_signal'),
                    'macd_histogram': indicators.get('macd_histogram'),
                    'bollinger_upper': indicators.get('bollinger_upper'),
                    'bollinger_middle': indicators.get('bollinger_middle'),
                    'bollinger_lower': indicators.get('bollinger_lower'),
                    'stochastic_k': indicators.get('stochastic_k'),
                    'stochastic_d': indicators.get('stochastic_d'),
                }
            )
            
            action = "생성" if created else "업데이트"
            self.stdout.write(f"{action}: {stock.stock_name} - RSI: {indicators.get('rsi', 'N/A')}")
            
            return True
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"계산 실패 - {stock.stock_name}: {str(e)}")
            )
            return False

    def get_indicator_summary(self, indicators):
        """지표 요약 문자열 생성"""
        summary_parts = []
        
        if indicators.get('ma5'):
            summary_parts.append(f"MA5: {indicators['ma5']:.2f}")
        if indicators.get('rsi'):
            summary_parts.append(f"RSI: {indicators['rsi']:.2f}")
        if indicators.get('macd'):
            summary_parts.append(f"MACD: {indicators['macd']:.2f}")
            
        return ", ".join(summary_parts) if summary_parts else "계산된 지표 없음" 