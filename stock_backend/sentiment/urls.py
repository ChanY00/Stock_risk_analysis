from django.urls import path
from .views import (
    SentimentAnalysisAPIView,
    SentimentAnalysisListAPIView,
    SentimentAnalysisBulkAPIView,
    SentimentTrendAPIView
)

urlpatterns = [
    path('bulk/', SentimentAnalysisBulkAPIView.as_view(), name='stock-sentiment-bulk'),
    path('', SentimentAnalysisListAPIView.as_view(), name='stock-sentiment-list'),
    path('<str:stock_code>/trend/', SentimentTrendAPIView.as_view(), name='stock-sentiment-trend'),
    path('<str:stock_code>/', SentimentAnalysisAPIView.as_view(), name='stock-sentiment'),
]
