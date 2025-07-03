from django.db import models
from stocks.models import Stock

class FinancialStatement(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='financials')
    year = models.IntegerField()
    revenue = models.BigIntegerField()
    operating_income = models.BigIntegerField()
    net_income = models.BigIntegerField()
    eps = models.FloatField()
    
    # 새로 추가되는 필드들
    total_assets = models.BigIntegerField(null=True, blank=True)  # 총자산
    total_liabilities = models.BigIntegerField(null=True, blank=True)  # 총부채
    total_equity = models.BigIntegerField(null=True, blank=True)  # 총자본 (자기자본)

    class Meta:
        unique_together = ('stock', 'year')
        ordering = ['-year']
        
    def __str__(self):
        return f"{self.stock.stock_name} - {self.year}년 재무제표"
    
    def calculate_debt_ratio(self):
        """부채비율 계산 (총부채 / 총자본 * 100)"""
        if self.total_equity and self.total_equity > 0:
            return (self.total_liabilities / self.total_equity) * 100
        return None
    
    def calculate_equity_ratio(self):
        """자기자본비율 계산 (총자본 / 총자산 * 100)"""
        if self.total_assets and self.total_assets > 0:
            return (self.total_equity / self.total_assets) * 100
        return None

    def calculate_roa(self):
        """ROA 계산 (순이익 / 총자산 * 100)"""
        if self.total_assets and self.total_assets > 0:
            return (self.net_income / self.total_assets) * 100
        return None
    
    def calculate_operating_margin(self):
        """영업이익률 계산 (영업이익 / 매출액 * 100)"""
        if self.revenue and self.revenue > 0:
            return (self.operating_income / self.revenue) * 100
        return None
    
    def calculate_net_margin(self):
        """순이익률 계산 (순이익 / 매출액 * 100)"""
        if self.revenue and self.revenue > 0:
            return (self.net_income / self.revenue) * 100
        return None
    
    def get_financial_health_score(self):
        """재무건전성 점수 (0-100점)"""
        score = 0
        factors = 0
        
        # 수익성 (40점)
        roa = self.calculate_roa()
        if roa is not None:
            score += min(roa * 4, 20)  # ROA 5% = 20점
            factors += 1
            
        operating_margin = self.calculate_operating_margin()
        if operating_margin is not None:
            score += min(operating_margin * 2, 20)  # 영업이익률 10% = 20점
            factors += 1
        
        # 안정성 (40점)
        equity_ratio = self.calculate_equity_ratio()
        if equity_ratio is not None:
            score += min(equity_ratio * 0.4, 20)  # 자기자본비율 50% = 20점
            factors += 1
            
        debt_ratio = self.calculate_debt_ratio()
        if debt_ratio is not None:
            score += max(20 - debt_ratio * 0.1, 0)  # 부채비율 200% = 0점
            factors += 1
        
        # 성장성 (20점) - 매출액 기준
        if self.revenue > 0:
            score += min(20, 20)  # 기본 점수
            factors += 1
        
        return score / factors if factors > 0 else 0
