from django.core.management.base import BaseCommand
from stocks.models import Stock
from financials.models import FinancialStatement
import FinanceDataReader as fdr
import pandas as pd
import requests
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = '실제 재무제표 데이터를 가져와서 Mock 데이터를 교체합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 업데이트 (예: 005930 000660)',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2023,
            help='가져올 재무제표 연도 (기본값: 2023)',
        )
        parser.add_argument(
            '--overwrite',
            action='store_true',
            help='기존 데이터가 있어도 덮어쓰기',
        )

    def handle(self, *args, **options):
        year = options['year']
        overwrite = options['overwrite']
        stock_codes = options.get('stock_codes')
        
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
            self.stdout.write(f"🎯 지정된 {len(stock_codes)}개 종목의 재무데이터를 가져옵니다.")
        else:
            stocks = Stock.objects.all()[:20]  # 처음에는 상위 20개만 테스트
            self.stdout.write(f"📊 상위 {stocks.count()}개 종목의 재무데이터를 가져옵니다.")
        
        self.stdout.write(f"📅 대상 연도: {year}년")
        self.stdout.write(f"🔄 덮어쓰기: {'예' if overwrite else '아니오'}")
        
        success_count = 0
        error_count = 0
        
        for i, stock in enumerate(stocks, 1):
            self.stdout.write(f"\n[{i}/{stocks.count()}] {stock.stock_name} ({stock.stock_code}) 처리 중...")
            
            try:
                # 기존 데이터 확인
                existing = FinancialStatement.objects.filter(
                    stock=stock, 
                    year=year
                ).first()
                
                if existing and not overwrite:
                    self.stdout.write(f"  ⏭️  {year}년 데이터가 이미 존재합니다. (스킵)")
                    continue
                
                # 실제 재무데이터 가져오기
                financial_data = self.fetch_financial_data(stock.stock_code, year)
                
                if financial_data:
                    # 데이터베이스에 저장/업데이트
                    financial_obj, created = FinancialStatement.objects.update_or_create(
                        stock=stock,
                        year=year,
                        defaults=financial_data
                    )
                    
                    if created:
                        self.stdout.write(f"  ✅ {year}년 재무데이터 새로 생성됨")
                    else:
                        self.stdout.write(f"  🔄 {year}년 재무데이터 업데이트됨")
                    
                    # 재무비율 재계산
                    stock.update_financial_ratios()
                    success_count += 1
                    
                else:
                    self.stdout.write(f"  ❌ 재무데이터를 가져올 수 없습니다")
                    error_count += 1
                
                # API 호출 제한을 위한 짧은 대기
                time.sleep(0.5)
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  💥 오류 발생: {str(e)}")
                )
                error_count += 1
        
        # 최종 결과 출력
        self.stdout.write(f"\n" + "="*50)
        self.stdout.write(
            self.style.SUCCESS(f"🎉 완료! 성공: {success_count}개, 실패: {error_count}개")
        )

    def fetch_financial_data(self, stock_code: str, year: int) -> dict:
        """실제 재무제표 데이터 가져오기"""
        
        # Method 1: FinanceDataReader 시도
        financial_data = self.fetch_from_fdr(stock_code, year)
        if financial_data:
            return financial_data
        
        # Method 2: 한국거래소 데이터 시도 (추후 구현)
        # financial_data = self.fetch_from_krx(stock_code, year)
        # if financial_data:
        #     return financial_data
        
        # Method 3: 네이버 금융 데이터 시도
        financial_data = self.fetch_from_naver(stock_code, year)
        if financial_data:
            return financial_data
            
        return None

    def fetch_from_fdr(self, stock_code: str, year: int) -> dict:
        """FinanceDataReader를 통한 재무데이터 수집"""
        try:
            self.stdout.write(f"    📊 FDR API 시도...")
            
            # FinanceDataReader의 한국 기업 재무제표 조회
            # 주의: FDR의 재무제표 기능은 제한적일 수 있음
            financial = fdr.DataReader(stock_code, 'naver-financial')
            
            if financial is not None and not financial.empty:
                # 연도별 데이터에서 해당 연도 추출
                year_data = financial[financial.index.year == year]
                
                if not year_data.empty:
                    latest = year_data.iloc[-1]  # 해당 연도의 최신 데이터
                    
                    return {
                        'revenue': int(latest.get('매출액', 0) * 100000000) if pd.notna(latest.get('매출액', 0)) else 0,
                        'operating_income': int(latest.get('영업이익', 0) * 100000000) if pd.notna(latest.get('영업이익', 0)) else 0,
                        'net_income': int(latest.get('당기순이익', 0) * 100000000) if pd.notna(latest.get('당기순이익', 0)) else 0,
                        'eps': float(latest.get('주당순이익', 0)) if pd.notna(latest.get('주당순이익', 0)) else 0.0,
                        'total_assets': int(latest.get('총자산', 0) * 100000000) if pd.notna(latest.get('총자산', 0)) else None,
                        'total_liabilities': int(latest.get('총부채', 0) * 100000000) if pd.notna(latest.get('총부채', 0)) else None,
                        'total_equity': int(latest.get('총자본', 0) * 100000000) if pd.notna(latest.get('총자본', 0)) else None,
                    }
            
        except Exception as e:
            self.stdout.write(f"    ❌ FDR 오류: {str(e)}")
        
        return None

    def fetch_from_naver(self, stock_code: str, year: int) -> dict:
        """네이버 금융에서 재무데이터 수집 (웹 스크래핑)"""
        try:
            self.stdout.write(f"    🌐 네이버 금융 시도...")
            
            # 네이버 금융 재무제표 URL
            url = f"https://finance.naver.com/item/coinfo.naver?code={stock_code}&target=finsum_more"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                # pandas를 사용한 테이블 파싱
                tables = pd.read_html(response.text, encoding='euc-kr')
                
                if len(tables) >= 3:  # 재무제표 테이블이 있는 경우
                    # 포괄손익계산서 테이블 (보통 3번째 테이블)
                    income_statement = tables[2]
                    
                    # 연도 컬럼 찾기
                    year_col = None
                    for col in income_statement.columns:
                        if str(year) in str(col):
                            year_col = col
                            break
                    
                    if year_col is not None:
                        # 매출액, 영업이익, 당기순이익 추출
                        revenue = self.extract_financial_value(income_statement, '매출액', year_col)
                        operating_income = self.extract_financial_value(income_statement, '영업이익', year_col)
                        net_income = self.extract_financial_value(income_statement, '당기순이익', year_col)
                        
                        # 대차대조표에서 자산, 부채, 자본 정보 (보통 4번째 테이블)
                        if len(tables) >= 4:
                            balance_sheet = tables[3]
                            total_assets = self.extract_financial_value(balance_sheet, '자산총계', year_col)
                            total_liabilities = self.extract_financial_value(balance_sheet, '부채총계', year_col)
                            total_equity = self.extract_financial_value(balance_sheet, '자본총계', year_col)
                        else:
                            total_assets = total_liabilities = total_equity = None
                        
                        # EPS 계산 (주식 수 정보가 필요하지만 임시로 계산)
                        eps = 0.0
                        if net_income and hasattr(self, 'stock') and self.stock.shares_outstanding:
                            eps = net_income / self.stock.shares_outstanding
                        
                        if revenue or operating_income or net_income:
                            return {
                                'revenue': revenue or 0,
                                'operating_income': operating_income or 0,
                                'net_income': net_income or 0,
                                'eps': eps,
                                'total_assets': total_assets,
                                'total_liabilities': total_liabilities,
                                'total_equity': total_equity,
                            }
            
        except Exception as e:
            self.stdout.write(f"    ❌ 네이버 금융 오류: {str(e)}")
        
        return None

    def extract_financial_value(self, dataframe, item_name: str, year_col) -> int:
        """재무제표 테이블에서 특정 항목의 값을 추출"""
        try:
            # 항목명이 포함된 행 찾기
            for idx, row in dataframe.iterrows():
                if pd.notna(row.iloc[0]) and item_name in str(row.iloc[0]):
                    value = row[year_col]
                    if pd.notna(value) and str(value).replace(',', '').replace('-', '').isdigit():
                        # 억원 단위로 변환 (보통 네이버는 백만원 단위)
                        return int(str(value).replace(',', '')) * 100000000
            return None
        except:
            return None

    def generate_reasonable_financial_data(self, stock_code: str, year: int) -> dict:
        """합리적인 범위의 재무데이터 생성 (최후의 수단)"""
        self.stdout.write(f"    🎲 합리적 추정치 생성...")
        
        # 종목별 대략적인 시가총액 기반 추정
        stock_profiles = {
            '005930': {'name': '삼성전자', 'market_cap_multiplier': 1.0},  # 대형주
            '000660': {'name': 'SK하이닉스', 'market_cap_multiplier': 0.3},
            '035420': {'name': 'NAVER', 'market_cap_multiplier': 0.2},
            # 추가 종목들...
        }
        
        profile = stock_profiles.get(stock_code, {'market_cap_multiplier': 0.1})
        base_revenue = int(3000000000000 * profile['market_cap_multiplier'])  # 3조원 기준
        
        return {
            'revenue': base_revenue,
            'operating_income': int(base_revenue * 0.1),  # 영업이익률 10%
            'net_income': int(base_revenue * 0.07),       # 순이익률 7%
            'eps': 2500,  # 임시값
            'total_assets': int(base_revenue * 1.5),
            'total_liabilities': int(base_revenue * 0.6),
            'total_equity': int(base_revenue * 0.9),
        } 