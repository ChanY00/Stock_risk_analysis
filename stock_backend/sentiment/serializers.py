from rest_framework import serializers
from .models import SentimentAnalysis

class SentimentAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = SentimentAnalysis
        fields = ['updated_at', 'positive', 'negative', 'top_keywords']
