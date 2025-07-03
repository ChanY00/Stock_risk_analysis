from django.db import models
from django.contrib.auth.models import User
from stocks.models import Stock
from decimal import Decimal

class Portfolio(models.Model):
    """포트폴리오 모델"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='portfolios', null=True, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return self.name
    
    @property
    def total_investment(self):
        """총 투자금액"""
        return sum(holding.total_investment for holding in self.holdings.all())
    
    @property
    def current_value(self):
        """현재 평가금액"""
        return sum(holding.current_value for holding in self.holdings.all())
    
    @property
    def total_profit_loss(self):
        """총 손익"""
        return self.current_value - self.total_investment
    
    @property
    def total_profit_loss_percent(self):
        """총 수익률 (%)"""
        if self.total_investment > 0:
            return (self.total_profit_loss / self.total_investment) * 100
        return 0
    
    def calculate_weights(self):
        """각 종목의 비중 계산"""
        total_value = self.current_value
        if total_value > 0:
            for holding in self.holdings.all():
                holding.weight = (holding.current_value / total_value) * 100
                holding.save()

class PortfolioHolding(models.Model):
    """포트폴리오 보유 종목"""
    portfolio = models.ForeignKey(Portfolio, on_delete=models.CASCADE, related_name='holdings')
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE)
    quantity = models.IntegerField()  # 보유 수량
    average_price = models.DecimalField(max_digits=10, decimal_places=2)  # 평균 매수가
    weight = models.FloatField(default=0.0)  # 포트폴리오 내 비중 (%)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('portfolio', 'stock')
        ordering = ['-weight']
    
    def __str__(self):
        return f"{self.portfolio.name} - {self.stock.stock_name}"
    
    @property
    def current_price(self):
        """현재가 (주가 데이터에서 가져오기)"""
        return self.stock.current_price or self.stock.get_current_price() or 0
    
    @property
    def total_investment(self):
        """투자금액 (수량 × 평균매수가)"""
        return float(self.quantity * self.average_price)
    
    @property
    def current_value(self):
        """현재 평가금액 (수량 × 현재가)"""
        return self.quantity * self.current_price
    
    @property
    def profit_loss(self):
        """손익금액"""
        return self.current_value - self.total_investment
    
    @property
    def profit_loss_percent(self):
        """수익률 (%)"""
        if self.total_investment > 0:
            return (self.profit_loss / self.total_investment) * 100
        return 0 