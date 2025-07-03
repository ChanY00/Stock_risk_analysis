from django.core.management.base import BaseCommand
from stocks.models import Stock
from financials.models import FinancialStatement
import random

class Command(BaseCommand):
    help = '주식 기본 정보와 재무 데이터를 채워넣습니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--update-all', 
            action='store_true',
            help='모든 주식의 기본 정보를 업데이트합니다'
        )

    def handle(self, *args, **options):
        stocks = Stock.objects.all()
        
        self.stdout.write(f"총 {stocks.count()}개 주식 데이터를 처리합니다...")
        
        # 업종 데이터 (KOSPI 대표 업종들)
        sectors = [
            '전기전자', '화학', '자동차', '금융업', '건설업', 
            '통신업', '유통업', '의료정밀', '운수창고', '기계',
            '철강금속', '에너지', '음식료', '섬유의복', '종이목재',
            '비금속광물', '의약품', '게임', '바이오', '항공우주'
        ]
        
        # 시장 분류 (대략적인 기준으로)
        kospi_companies = [
            '삼성전자', 'SK하이닉스', '삼성바이오로직스', 'LG에너지솔루션', 
            'KB금융', '현대차', '기아', 'NAVER', '셀트리온', '신한지주',
            '삼성물산', '현대모비스', 'POSCO홀딩스', '한국전력', '삼성생명',
            '삼성화재', 'KT&G', 'LG화학', 'SK이노베이션', 'KT',
            '삼성SDI', 'LG전자', 'SK텔레콤', 'LG', '삼성전기',
            '포스코퓨처엠', '한국항공우주', '유한양행', '아모레퍼시픽', '한미약품'
        ]
        
        updated_count = 0
        for stock in stocks:
            try:
                # 시장 분류
                if stock.stock_name in kospi_companies:
                    stock.market = 'KOSPI'
                else:
                    stock.market = 'KOSDAQ'
                
                # 업종 랜덤 할당 (실제로는 외부 API에서 가져와야 함)
                if not stock.sector:
                    stock.sector = random.choice(sectors)
                
                # 발행주식수 (시가총액 계산용) - 실제로는 공시 데이터에서
                if not stock.shares_outstanding:
                    # 임시로 합리적인 범위의 발행주식수 설정
                    if stock.market == 'KOSPI':
                        stock.shares_outstanding = random.randint(50_000_000, 5_000_000_000)
                    else:
                        stock.shares_outstanding = random.randint(10_000_000, 500_000_000)
                
                # 배당수익률 (0~5% 범위)
                if stock.dividend_yield == 0.0:
                    stock.dividend_yield = round(random.uniform(0, 5), 2)
                
                stock.save()
                
                # 재무 데이터가 있는 경우 재무비율 계산
                self.update_financial_ratios(stock)
                
                updated_count += 1
                
                if updated_count % 50 == 0:
                    self.stdout.write(f"진행률: {updated_count}/{stocks.count()}")
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"오류 발생 - {stock.stock_name}: {str(e)}")
                )
        
        # 임시 재무데이터 생성 (일부 주식에 대해)
        self.create_sample_financial_data()
        
        self.stdout.write(
            self.style.SUCCESS(f"성공적으로 {updated_count}개 주식 데이터를 업데이트했습니다.")
        )

    def update_financial_ratios(self, stock):
        """재무비율 업데이트"""
        try:
            # 최신 재무제표가 있는 경우에만 계산
            latest_financial = stock.financials.first()
            if latest_financial:
                stock.update_financial_ratios()
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"재무비율 계산 실패 - {stock.stock_name}: {str(e)}")
            )

    def create_sample_financial_data(self):
        """일부 주식에 대해 샘플 재무 데이터 생성"""
        self.stdout.write("샘플 재무 데이터를 생성합니다...")
        
        # 상위 50개 주식에 대해 재무 데이터 생성
        major_stocks = Stock.objects.filter(market='KOSPI')[:50]
        
        for stock in major_stocks:
            # 이미 재무 데이터가 있으면 스킵
            if stock.financials.exists():
                continue
                
            try:
                # 2023년, 2022년 재무 데이터 생성
                for year in [2023, 2022]:
                    # 시가총액 기반으로 합리적인 재무 수치 생성
                    current_price = stock.get_current_price() or 50000
                    estimated_market_cap = current_price * (stock.shares_outstanding or 100_000_000)
                    
                    # 매출액 (시가총액의 0.5~2배)
                    revenue = int(estimated_market_cap * random.uniform(0.5, 2.0))
                    
                    # 영업이익 (매출의 5~20%)
                    operating_income = int(revenue * random.uniform(0.05, 0.20))
                    
                    # 순이익 (영업이익의 60~90%)
                    net_income = int(operating_income * random.uniform(0.60, 0.90))
                    
                    # EPS (순이익 / 발행주식수)
                    eps = net_income / (stock.shares_outstanding or 100_000_000)
                    
                    # 총자산 (시가총액의 1~3배)
                    total_assets = int(estimated_market_cap * random.uniform(1.0, 3.0))
                    
                    # 총부채 (총자산의 30~70%)
                    total_liabilities = int(total_assets * random.uniform(0.30, 0.70))
                    
                    # 총자본 (총자산 - 총부채)
                    total_equity = total_assets - total_liabilities
                    
                    FinancialStatement.objects.get_or_create(
                        stock=stock,
                        year=year,
                        defaults={
                            'revenue': revenue,
                            'operating_income': operating_income,
                            'net_income': net_income,
                            'eps': eps,
                            'total_assets': total_assets,
                            'total_liabilities': total_liabilities,
                            'total_equity': total_equity
                        }
                    )
                
                # 재무비율 재계산
                stock.update_financial_ratios()
                
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"재무 데이터 생성 실패 - {stock.stock_name}: {str(e)}")
                )
        
        self.stdout.write(
            self.style.SUCCESS("샘플 재무 데이터 생성 완료")
        ) 