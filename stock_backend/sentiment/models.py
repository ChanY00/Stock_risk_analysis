from django.db import models
from stocks.models import Stock

class SentimentAnalysis(models.Model):
    stock = models.OneToOneField(Stock, on_delete=models.CASCADE, related_name='sentiment')
    updated_at = models.DateTimeField()  # auto_now 제거

    positive = models.DecimalField(max_digits=5, decimal_places=4)  # 0.0000 ~ 1.0000 (Serializer와 일치)
    negative = models.DecimalField(max_digits=5, decimal_places=4)  # 0.0000 ~ 1.0000 (Serializer와 일치)
    top_keywords = models.TextField()  # 쉼표로 구분된 키워드 문자열

    def __str__(self):
        return f"{self.stock.stock_name} 감정 분석 결과"
