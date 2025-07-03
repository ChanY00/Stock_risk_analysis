from django.urls import path
from .views import (
    SentimentAnalysisAPIView,
    SentimentAnalysisListAPIView,
    SentimentAnalysisBulkAPIView
)

urlpatterns = [
    path('bulk/', SentimentAnalysisBulkAPIView.as_view(), name='stock-sentiment-bulk'),
    path('', SentimentAnalysisListAPIView.as_view(), name='stock-sentiment-list'),
    path('<str:stock_code>/', SentimentAnalysisAPIView.as_view(), name='stock-sentiment'),
]
