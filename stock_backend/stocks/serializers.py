from rest_framework import serializers
from .models import Stock
from datetime import datetime, timedelta

class StockListSerializer(serializers.ModelSerializer):
    """주식 목록 API용 시리얼라이저 - 기본 정보 + 새로운 필드들"""
    current_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Stock
        fields = [
            'stock_code', 'stock_name', 'market', 'sector', 
            'current_price', 'market_cap', 'per', 'pbr', 'roe', 'dividend_yield'
        ]
    
    def get_current_price(self, obj):
        """최신 주가 반환"""
        return obj.get_current_price()

class StockSerializer(serializers.ModelSerializer):
    """기존 호환성을 위한 기본 시리얼라이저"""
    class Meta:
        model = Stock
        fields = ['stock_code', 'stock_name']

class StockDetailSerializer(serializers.ModelSerializer):
    """주식 상세 정보 API용 시리얼라이저 - 모든 정보 포함"""
    price_data = serializers.SerializerMethodField()
    financial_data = serializers.SerializerMethodField()
    price_history = serializers.SerializerMethodField()
    technical_indicators = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            'stock_code', 'stock_name', 'market', 'sector',
            'current_price', 'market_cap', 'per', 'pbr', 'roe', 'dividend_yield',
            'shares_outstanding',  # 발행주식수 추가 (프론트엔드에서 시가총액 실시간 계산용)
            'price_data', 'financial_data', 'price_history', 'technical_indicators'
        ]

    def get_current_price(self, obj):
        """현재 주가"""
        return obj.get_current_price()

    def get_price_data(self, obj):
        """최신 주가 데이터"""
        latest = obj.prices.order_by('-date').first()
        if not latest:
            return None
        return {
            "date": latest.date,
            "open_price": latest.open_price,
            "high_price": latest.high_price,
            "low_price": latest.low_price,
            "close_price": latest.close_price,
            "volume": latest.volume
        }

    def get_financial_data(self, obj):
        """최신 재무 데이터"""
        latest_financial = obj.financials.order_by('-year').first()
        if not latest_financial:
            return None
        return {
            "year": latest_financial.year,
            "revenue": latest_financial.revenue,
            "operating_income": latest_financial.operating_income,
            "net_income": latest_financial.net_income,
            "eps": latest_financial.eps,
            "total_assets": latest_financial.total_assets,
            "total_liabilities": latest_financial.total_liabilities,
            "total_equity": latest_financial.total_equity
        }

    def get_price_history(self, obj):
        """주가 히스토리 (기본 90일, 요청 파라미터로 조정 가능)"""
        request = self.context.get('request')
        if request:
            # 요청 파라미터에서 days 추출
            days = int(request.query_params.get('days', 90))
        else:
            days = 90
        
        # 지정된 일수만큼 과거 데이터 조회
        start_date = datetime.now().date() - timedelta(days=days)
        prices = obj.prices.filter(date__gte=start_date).order_by('date')
        
        price_data = []
        close_prices = []
        
        for price in prices:
            close_prices.append(price.close_price)
            price_data.append({
                "date": price.date,
                "open": price.open_price,
                "high": price.high_price,
                "low": price.low_price,
                "close": price.close_price,
                "volume": price.volume
            })
        
        # 이동평균선 계산 (각 시점에서)
        if len(close_prices) > 0:
            for i, data in enumerate(price_data):
                # MA5 계산
                if i >= 4:  # 5일 이상 데이터가 있을 때
                    ma5 = sum(close_prices[i-4:i+1]) / 5
                    data['ma5'] = round(ma5, 2)
                else:
                    data['ma5'] = None
                
                # MA20 계산  
                if i >= 19:  # 20일 이상 데이터가 있을 때
                    ma20 = sum(close_prices[i-19:i+1]) / 20
                    data['ma20'] = round(ma20, 2)
                else:
                    data['ma20'] = None
                
                # MA60 계산
                if i >= 59:  # 60일 이상 데이터가 있을 때
                    ma60 = sum(close_prices[i-59:i+1]) / 60
                    data['ma60'] = round(ma60, 2)
                else:
                    data['ma60'] = None
        
        return price_data

    def get_technical_indicators(self, obj):
        """기술적 지표"""
        try:
            technical = getattr(obj, 'technical', None)
            if not technical:
                return None
                
            return {
                "ma5": getattr(technical, 'ma5', None),
                "ma20": getattr(technical, 'ma20', None),
                "ma60": getattr(technical, 'ma60', None),
                "rsi": getattr(technical, 'rsi', None),
                "macd": getattr(technical, 'macd', None),
                "macd_signal": getattr(technical, 'macd_signal', None),
                "macd_histogram": getattr(technical, 'macd_histogram', None),
                "bollinger_upper": getattr(technical, 'bollinger_upper', None),
                "bollinger_middle": getattr(technical, 'bollinger_middle', None),
                "bollinger_lower": getattr(technical, 'bollinger_lower', None),
                "stochastic_k": getattr(technical, 'stochastic_k', None),
                "stochastic_d": getattr(technical, 'stochastic_d', None)
            }
        except Exception as e:
            print(f"Error in get_technical_indicators: {e}")
            return None

class StockFilterSerializer(serializers.Serializer):
    """주식 필터링용 시리얼라이저"""
    market = serializers.CharField(required=False)
    sector = serializers.CharField(required=False)
    min_per = serializers.FloatField(required=False)
    max_per = serializers.FloatField(required=False)
    min_pbr = serializers.FloatField(required=False)
    max_pbr = serializers.FloatField(required=False)
    min_roe = serializers.FloatField(required=False)
    max_roe = serializers.FloatField(required=False)
    min_dividend_yield = serializers.FloatField(required=False)
    max_dividend_yield = serializers.FloatField(required=False)
