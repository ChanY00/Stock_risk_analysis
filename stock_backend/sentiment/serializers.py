from rest_framework import serializers
from .models import SentimentAnalysis

class SentimentAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentimentAnalysis
        fields = ['updated_at', 'positive', 'negative', 'top_keywords']


class SentimentBulkItemSerializer(serializers.Serializer):
    """입력 검증용 벌크 아이템 직렬화기"""
    stock_code = serializers.CharField(max_length=12)
    positive = serializers.DecimalField(max_digits=5, decimal_places=4)
    negative = serializers.DecimalField(max_digits=5, decimal_places=4)
    top_keywords = serializers.CharField(allow_blank=True, max_length=1024)
    updated_at = serializers.DateTimeField()

    def validate(self, attrs):
        pos = float(attrs['positive'])
        neg = float(attrs['negative'])
        if not (0.0 <= pos <= 1.0):
            raise serializers.ValidationError({'positive': 'must be between 0 and 1'})
        if not (0.0 <= neg <= 1.0):
            raise serializers.ValidationError({'negative': 'must be between 0 and 1'})
        return attrs
