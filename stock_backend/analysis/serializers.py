from rest_framework import serializers
from .models import ClusteringCriterion, ClusteringResult, SpectralCluster, AgglomerativeCluster, ClusterAnalysis, StockSimilarity
from stocks.models import Stock
from .models import TechnicalIndicator, MarketIndex, Watchlist, Alert
from stocks.serializers import StockListSerializer

class StockSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Stock
        fields = ['stock_code', 'stock_name']

class ClusteringResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusteringResult
        fields = '__all__'

class TechnicalIndicatorSerializer(serializers.ModelSerializer):
    stock_name = serializers.CharField(source='stock.stock_name', read_only=True)
    stock_code = serializers.CharField(source='stock.stock_code', read_only=True)
    
    class Meta:
        model = TechnicalIndicator
        fields = [
            'stock_code', 'stock_name', 'ma5', 'ma20', 'ma60',
            'rsi', 'macd', 'macd_signal', 'macd_histogram',
            'bollinger_upper', 'bollinger_middle', 'bollinger_lower',
            'stochastic_k', 'stochastic_d', 'updated_at'
        ]

class MarketIndexSerializer(serializers.ModelSerializer):
    class Meta:
        model = MarketIndex
        fields = [
            'name', 'current_value', 'change', 'change_percent',
            'volume', 'trade_value', 'high', 'low', 'updated_at'
        ]

class WatchlistSerializer(serializers.ModelSerializer):
    stocks = serializers.SerializerMethodField()
    stocks_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Watchlist
        fields = ['id', 'name', 'stocks', 'stocks_count', 'created_at', 'updated_at']
    
    def get_stocks(self, obj):
        return StockListSerializer(obj.stocks.all(), many=True).data
    
    def get_stocks_count(self, obj):
        return obj.stocks.count()

class WatchlistCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Watchlist
        fields = ['name']

class AlertSerializer(serializers.ModelSerializer):
    stock_name = serializers.CharField(source='stock.stock_name', read_only=True)
    is_triggered = serializers.SerializerMethodField()
    
    class Meta:
        model = Alert
        fields = [
            'id', 'stock', 'stock_name', 'condition', 'target_price',
            'is_active', 'message', 'is_triggered', 'created_at', 'triggered_at'
        ]
    
    def get_is_triggered(self, obj):
        return obj.triggered_at is not None

class AlertCreateSerializer(serializers.ModelSerializer):
    stock_code = serializers.CharField(write_only=True)
    message = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Alert
        fields = ['stock_code', 'condition', 'target_price', 'message']
    
    def validate_stock_code(self, value):
        """stock_code 유효성 검사"""
        try:
            Stock.objects.get(stock_code=value)
            return value
        except Stock.DoesNotExist:
            raise serializers.ValidationError(f"종목 코드 '{value}'를 찾을 수 없습니다.")
    
    def create(self, validated_data):
        """stock_code를 stock 객체로 변환하여 생성"""
        stock_code = validated_data.pop('stock_code')
        stock = Stock.objects.get(stock_code=stock_code)
        validated_data['stock'] = stock
        return super().create(validated_data)

class StockAnalysisSerializer(serializers.Serializer):
    """주식 분석 API 응답 시리얼라이저"""
    stock_code = serializers.CharField()
    stock_name = serializers.CharField()
    technical_indicators = TechnicalIndicatorSerializer()
    fundamental_analysis = serializers.DictField()
    
class MarketOverviewSerializer(serializers.Serializer):
    """시장 개요 API 응답 시리얼라이저"""
    market_summary = serializers.DictField()
    sector_performance = serializers.ListField()

class SpectralClusterSerializer(serializers.ModelSerializer):
    stock = StockListSerializer(read_only=True)
    
    class Meta:
        model = SpectralCluster
        fields = ['stock', 'cluster_id', 'cluster_label', 'created_at']

class AgglomerativeClusterSerializer(serializers.ModelSerializer):
    stock = StockListSerializer(read_only=True)
    
    class Meta:
        model = AgglomerativeCluster
        fields = ['stock', 'cluster_id', 'cluster_label', 'created_at']

class ClusterAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClusterAnalysis
        fields = [
            'cluster_type', 'cluster_id', 'cluster_name', 'description',
            'dominant_sectors', 'stock_count', 'avg_market_cap', 
            'avg_per', 'avg_pbr', 'characteristics'
        ]

class ClusterStockListSerializer(serializers.Serializer):
    """클러스터별 주식 목록"""
    cluster_analysis = ClusterAnalysisSerializer()
    stocks = StockListSerializer(many=True)
    similar_clusters = ClusterAnalysisSerializer(many=True, required=False)

class StockSimilaritySerializer(serializers.ModelSerializer):
    """종목 유사도 시리얼라이저"""
    source_stock = StockListSerializer(read_only=True)
    target_stock = StockListSerializer(read_only=True)
    
    class Meta:
        model = StockSimilarity
        fields = [
            'cluster_type', 'cluster_id', 'source_stock', 'target_stock',
            'neighbor_rank', 'distance', 'similarity_score'
        ]

class SimilarStockSerializer(serializers.ModelSerializer):
    """유사한 종목 정보 (간단한 버전)"""
    stock_code = serializers.CharField(source='target_stock.stock_code')
    stock_name = serializers.CharField(source='target_stock.stock_name')
    sector = serializers.CharField(source='target_stock.sector')
    current_price = serializers.IntegerField(source='target_stock.current_price')
    market_cap = serializers.IntegerField(source='target_stock.market_cap')
    per = serializers.FloatField(source='target_stock.per')
    pbr = serializers.FloatField(source='target_stock.pbr')
    
    class Meta:
        model = StockSimilarity
        fields = [
            'stock_code', 'stock_name', 'sector', 'current_price',
            'market_cap', 'per', 'pbr', 'neighbor_rank', 'distance', 'similarity_score'
        ]

class SimilarStocksResponseSerializer(serializers.Serializer):
    """유사 종목 API 응답"""
    base_stock = serializers.DictField()
    cluster_type = serializers.CharField()
    similar_stocks = SimilarStockSerializer(many=True)
    total_count = serializers.IntegerField()

class SimilarityNetworkSerializer(serializers.Serializer):
    """유사도 네트워크 데이터"""
    nodes = serializers.ListField()
    edges = serializers.ListField()
    cluster_info = serializers.DictField()
