from django.db import models
from stocks.models import Stock

class ClusteringCriterion(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class ClusteringResult(models.Model):
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='clusterings')
    criterion = models.ForeignKey(ClusteringCriterion, on_delete=models.CASCADE)
    cluster_id = models.IntegerField()

    class Meta:
        unique_together = ('stock', 'criterion')

class TechnicalIndicator(models.Model):
    """기술적 지표 모델"""
    stock = models.OneToOneField(Stock, on_delete=models.CASCADE, related_name='technical')
    
    # 이동평균
    ma5 = models.FloatField(null=True, blank=True)   # 5일 이동평균
    ma20 = models.FloatField(null=True, blank=True)  # 20일 이동평균
    ma60 = models.FloatField(null=True, blank=True)  # 60일 이동평균
    
    # 기술적 지표
    rsi = models.FloatField(null=True, blank=True)   # RSI (14일)
    macd = models.FloatField(null=True, blank=True)  # MACD
    macd_signal = models.FloatField(null=True, blank=True)  # MACD Signal
    macd_histogram = models.FloatField(null=True, blank=True)  # MACD Histogram
    
    # 볼린저 밴드
    bollinger_upper = models.FloatField(null=True, blank=True)   # 상단
    bollinger_middle = models.FloatField(null=True, blank=True)  # 중간(20일 이동평균)
    bollinger_lower = models.FloatField(null=True, blank=True)   # 하단
    
    # 기타 지표
    stochastic_k = models.FloatField(null=True, blank=True)  # 스토캐스틱 %K
    stochastic_d = models.FloatField(null=True, blank=True)  # 스토캐스틱 %D
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.stock.stock_name} 기술적 지표"
    
    def calculate_moving_averages(self):
        """이동평균 계산"""
        prices = self.stock.prices.order_by('-date')[:60]
        if len(prices) < 5:
            return
            
        close_prices = [price.close_price for price in reversed(prices)]
        
        # 5일 이동평균
        if len(close_prices) >= 5:
            self.ma5 = sum(close_prices[-5:]) / 5
            
        # 20일 이동평균  
        if len(close_prices) >= 20:
            self.ma20 = sum(close_prices[-20:]) / 20
            self.bollinger_middle = self.ma20
            
        # 60일 이동평균
        if len(close_prices) >= 60:
            self.ma60 = sum(close_prices[-60:]) / 60

class MarketIndex(models.Model):
    """시장 지수 모델"""
    name = models.CharField(max_length=20, unique=True)  # KOSPI, KOSDAQ
    current_value = models.FloatField()  # 현재 지수값
    change = models.FloatField()  # 전일 대비 변화량
    change_percent = models.FloatField()  # 전일 대비 변화율
    volume = models.BigIntegerField()  # 거래량
    trade_value = models.BigIntegerField(null=True, blank=True)  # 거래대금
    
    # 당일 최고/최저
    high = models.FloatField(null=True, blank=True)
    low = models.FloatField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name}: {self.current_value}"

class Watchlist(models.Model):
    """관심종목 리스트"""
    name = models.CharField(max_length=100)
    stocks = models.ManyToManyField(Stock, related_name='watchlists', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Alert(models.Model):
    """주가 알림"""
    CONDITION_CHOICES = [
        ('above', '이상'),
        ('below', '이하'),
    ]
    
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='alerts')
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    target_price = models.FloatField()  # 목표 가격
    is_active = models.BooleanField(default=True)
    message = models.TextField(blank=True)  # 알림 메시지
    
    created_at = models.DateTimeField(auto_now_add=True)
    triggered_at = models.DateTimeField(null=True, blank=True)  # 알림 발생 시간
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.stock.stock_name} {self.get_condition_display()} {self.target_price}"
    
    def check_condition(self):
        """알림 조건 확인"""
        current_price = self.stock.get_current_price()
        if not current_price or not self.is_active:
            return False
            
        if self.condition == 'above' and current_price >= self.target_price:
            return True
        elif self.condition == 'below' and current_price <= self.target_price:
            return True
            
        return False

class SpectralCluster(models.Model):
    """Spectral Clustering 결과"""
    stock = models.OneToOneField('stocks.Stock', on_delete=models.CASCADE, related_name='spectral_cluster')
    cluster_id = models.IntegerField()
    cluster_label = models.CharField(max_length=100, blank=True, null=True)  # 클러스터 의미 라벨
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['cluster_id']),
        ]
    
    def __str__(self):
        return f"{self.stock.stock_name} - Spectral Cluster {self.cluster_id}"

class AgglomerativeCluster(models.Model):
    """Agglomerative Clustering 결과"""
    stock = models.OneToOneField('stocks.Stock', on_delete=models.CASCADE, related_name='agglomerative_cluster')
    cluster_id = models.IntegerField()
    cluster_label = models.CharField(max_length=100, blank=True, null=True)  # 클러스터 의미 라벨
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['cluster_id']),
        ]
    
    def __str__(self):
        return f"{self.stock.stock_name} - Agglomerative Cluster {self.cluster_id}"

class ClusterAnalysis(models.Model):
    """클러스터 분석 결과"""
    CLUSTER_TYPES = [
        ('spectral', 'Spectral Clustering'),
        ('agglomerative', 'Agglomerative Clustering'),
    ]
    
    cluster_type = models.CharField(max_length=20, choices=CLUSTER_TYPES)
    cluster_id = models.IntegerField()
    cluster_name = models.CharField(max_length=100)  # 클러스터 특성 명칭
    description = models.TextField(blank=True)  # 클러스터 설명
    dominant_sectors = models.JSONField(default=list)  # 주요 섹터들
    stock_count = models.IntegerField(default=0)  # 클러스터 내 종목 수
    avg_market_cap = models.BigIntegerField(null=True, blank=True)  # 평균 시가총액
    avg_per = models.FloatField(null=True, blank=True)  # 평균 PER
    avg_pbr = models.FloatField(null=True, blank=True)  # 평균 PBR
    characteristics = models.JSONField(default=dict)  # 클러스터 특성
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['cluster_type', 'cluster_id']
        
    def __str__(self):
        return f"{self.get_cluster_type_display()} - {self.cluster_name}"

class StockSimilarity(models.Model):
    """클러스터 내 종목 간 유사도 정보"""
    CLUSTER_TYPES = [
        ('spectral', 'Spectral Clustering'),
        ('agglomerative', 'Agglomerative Clustering'),
    ]
    
    cluster_type = models.CharField(max_length=20, choices=CLUSTER_TYPES)
    cluster_id = models.IntegerField()
    source_stock = models.ForeignKey('stocks.Stock', on_delete=models.CASCADE, related_name='similarity_sources')
    target_stock = models.ForeignKey('stocks.Stock', on_delete=models.CASCADE, related_name='similarity_targets')
    neighbor_rank = models.IntegerField()  # 유사도 순위 (1, 2, 3...)
    distance = models.FloatField()  # 유클리드 거리 (낮을수록 유사)
    similarity_score = models.FloatField(null=True, blank=True)  # 유사도 점수 (높을수록 유사)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['cluster_type', 'source_stock', 'target_stock']
        indexes = [
            models.Index(fields=['cluster_type', 'cluster_id']),
            models.Index(fields=['cluster_type', 'source_stock']),
            models.Index(fields=['distance']),
            models.Index(fields=['neighbor_rank']),
        ]
        ordering = ['cluster_type', 'cluster_id', 'source_stock', 'neighbor_rank']
    
    def __str__(self):
        return f"{self.source_stock.stock_name} → {self.target_stock.stock_name} (거리: {self.distance:.4f})"
    
    def save(self, *args, **kwargs):
        """저장 시 유사도 점수 자동 계산"""
        if self.distance is not None:
            # 거리를 0-1 범위의 유사도 점수로 변환 (거리가 낮을수록 유사도 높음)
            # 최대 거리 1.0으로 가정하여 1 - distance로 계산
            self.similarity_score = max(0, 1 - self.distance)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_most_similar_stocks(cls, stock, cluster_type='spectral', limit=5):
        """특정 종목과 가장 유사한 종목들 반환 (같은 클러스터 내에서만)"""
        # source_stock의 클러스터 정보를 통해 같은 cluster_id를 가진 종목만 조회
        try:
            if cluster_type == 'spectral':
                cluster_id = stock.spectral_cluster.cluster_id
            else:
                cluster_id = stock.agglomerative_cluster.cluster_id
        except (AttributeError, Exception):
            # 클러스터 정보가 없으면 빈 쿼리셋 반환
            return cls.objects.none()
        
        return cls.objects.filter(
            cluster_type=cluster_type,
            cluster_id=cluster_id,  # 같은 클러스터 내에서만
            source_stock=stock
        ).order_by('neighbor_rank')[:limit]
    
    @classmethod
    def get_similarity_network(cls, cluster_type, cluster_id, min_similarity=0.7):
        """클러스터 내 유사도 네트워크 데이터 반환"""
        similarities = cls.objects.filter(
            cluster_type=cluster_type,
            cluster_id=cluster_id,
            similarity_score__gte=min_similarity
        ).select_related('source_stock', 'target_stock')
        
        return similarities

class SharesVerification(models.Model):
    """발행주식수 검증 결과 모델"""
    STATUS_CHOICES = [
        ('MATCH', '일치'),
        ('MINOR_DIFF', '경미한 차이 (1% 미만)'),
        ('MAJOR_DIFF', '불일치 (1% 이상)'),
        ('DART_API_ERROR', 'DART API 오류'),
    ]
    
    stock = models.OneToOneField(Stock, on_delete=models.CASCADE, related_name='shares_verification')
    db_shares = models.BigIntegerField(null=True, blank=True, help_text='DB에 저장된 발행주식수')
    dart_shares = models.BigIntegerField(null=True, blank=True, help_text='DART API에서 가져온 발행주식수')
    match = models.BooleanField(default=False, help_text='DB와 DART 값이 일치하는지')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, help_text='검증 상태')
    diff_percent = models.FloatField(null=True, blank=True, help_text='차이율 (%)')
    dart_year = models.IntegerField(null=True, blank=True, help_text='DART API 조회 연도')
    dart_account_nm = models.CharField(max_length=200, blank=True, help_text='DART API 계정명')
    verified_at = models.DateTimeField(auto_now=True, help_text='검증 시각')
    
    class Meta:
        ordering = ['-verified_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['match']),
            models.Index(fields=['-verified_at']),
        ]
    
    def __str__(self):
        return f"{self.stock.stock_name} 발행주식수 검증 ({self.status})"
    
    @property
    def diff_amount(self):
        """차이량 (절대값)"""
        if self.db_shares and self.dart_shares:
            return abs(self.dart_shares - self.db_shares)
        return None
    