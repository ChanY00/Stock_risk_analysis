# stocks/models.py

from django.db import models

class Stock(models.Model):
    stock_code = models.CharField(max_length=10, unique=True)
    stock_name = models.CharField(max_length=100)
    
    # 현재가 정보
    current_price = models.IntegerField(null=True, blank=True)  # 현재가
    
    # 새로 추가되는 필드들
    market = models.CharField(max_length=10, default='KOSDAQ')  # KOSPI, KOSDAQ
    sector = models.CharField(max_length=50, blank=True, null=True)  # 업종
    market_cap = models.BigIntegerField(null=True, blank=True)  # 시가총액
    per = models.FloatField(null=True, blank=True)  # PER
    pbr = models.FloatField(null=True, blank=True)  # PBR  
    roe = models.FloatField(null=True, blank=True)  # ROE
    dividend_yield = models.FloatField(null=True, blank=True, default=0.0)  # 배당수익률
    
    # 발행주식수 (시가총액 계산에 필요)
    shares_outstanding = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.stock_name} ({self.stock_code})"
    
    def get_current_price(self):
        """최신 주가를 반환"""
        latest_price = self.prices.first()
        return latest_price.close_price if latest_price else None
    
    def calculate_market_cap(self):
        """시가총액 계산"""
        current_price = self.get_current_price()
        if current_price and self.shares_outstanding:
            return current_price * self.shares_outstanding
        return None
    
    def update_financial_ratios(self):
        """재무비율 업데이트"""
        current_price = self.get_current_price()
        if not current_price:
            return
            
        # 최신 재무제표 데이터 가져오기
        latest_financial = self.financials.first()
        if not latest_financial:
            return
            
        # PER 계산 (주가 / EPS)
        if latest_financial.eps and latest_financial.eps > 0:
            self.per = current_price / latest_financial.eps
            
        # ROE 계산 (순이익 / 자기자본)
        if (hasattr(latest_financial, 'total_equity') and 
            latest_financial.total_equity and 
            latest_financial.total_equity > 0):
            self.roe = (latest_financial.net_income / latest_financial.total_equity) * 100
            
        # PBR 계산 (주가 / BPS)
        if (hasattr(latest_financial, 'total_equity') and 
            latest_financial.total_equity and 
            self.shares_outstanding and 
            self.shares_outstanding > 0):
            bps = latest_financial.total_equity / self.shares_outstanding
            if bps > 0:
                self.pbr = current_price / bps
                
        # 시가총액 업데이트
        calculated_market_cap = self.calculate_market_cap()
        if calculated_market_cap:
            self.market_cap = calculated_market_cap
            
        self.save()

class StockPrice(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='prices') # stock.prices로 접근
    date = models.DateField()
    open_price = models.IntegerField()
    high_price = models.IntegerField()
    low_price = models.IntegerField()
    close_price = models.IntegerField()
    volume = models.BigIntegerField()

    class Meta:
        unique_together = ('stock', 'date')
        ordering = ['-date']