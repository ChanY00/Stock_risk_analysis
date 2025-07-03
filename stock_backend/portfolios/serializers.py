from rest_framework import serializers
from .models import Portfolio, PortfolioHolding
from stocks.serializers import StockListSerializer

class PortfolioHoldingSerializer(serializers.ModelSerializer):
    stock_name = serializers.CharField(source='stock.stock_name', read_only=True)
    stock_code = serializers.CharField(source='stock.stock_code', read_only=True)
    sector = serializers.CharField(source='stock.sector', read_only=True)
    market = serializers.CharField(source='stock.market', read_only=True)
    current_price = serializers.ReadOnlyField()
    total_investment = serializers.ReadOnlyField()
    current_value = serializers.ReadOnlyField()
    profit_loss = serializers.ReadOnlyField()
    profit_loss_percent = serializers.ReadOnlyField()
    
    class Meta:
        model = PortfolioHolding
        fields = [
            'id', 'stock_code', 'stock_name', 'sector', 'market',
            'quantity', 'average_price', 'current_price', 'weight',
            'total_investment', 'current_value', 'profit_loss', 'profit_loss_percent',
            'created_at', 'updated_at'
        ]

class PortfolioSerializer(serializers.ModelSerializer):
    holdings = PortfolioHoldingSerializer(many=True, read_only=True)
    total_investment = serializers.ReadOnlyField()
    current_value = serializers.ReadOnlyField()
    total_profit_loss = serializers.ReadOnlyField()
    total_profit_loss_percent = serializers.ReadOnlyField()
    holdings_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Portfolio
        fields = [
            'id', 'name', 'description', 'holdings_count',
            'total_investment', 'current_value', 'total_profit_loss', 'total_profit_loss_percent',
            'holdings', 'created_at', 'updated_at'
        ]
    
    def get_holdings_count(self, obj):
        return obj.holdings.count()

class PortfolioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Portfolio
        fields = ['name', 'description']

class PortfolioHoldingCreateSerializer(serializers.ModelSerializer):
    stock_code = serializers.CharField(write_only=True)
    
    class Meta:
        model = PortfolioHolding
        fields = ['stock_code', 'quantity', 'average_price']
    
    def validate_stock_code(self, value):
        from stocks.models import Stock
        try:
            Stock.objects.get(stock_code=value)
            return value
        except Stock.DoesNotExist:
            raise serializers.ValidationError(f"종목코드 '{value}'를 찾을 수 없습니다.")
    
    def create(self, validated_data):
        from stocks.models import Stock
        stock_code = validated_data.pop('stock_code')
        stock = Stock.objects.get(stock_code=stock_code)
        validated_data['stock'] = stock
        return super().create(validated_data) 