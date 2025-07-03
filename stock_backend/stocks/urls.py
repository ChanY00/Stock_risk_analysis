# stocks/urls.py

from django.urls import path
from .views import (
    StockListAPIView, StockDetailAPIView, StockListAPIViewLegacy,
    stock_filter_view, stock_price_history_view, real_time_price,
    multiple_real_time_prices, kospi200_real_time_prices, daily_chart_data,
    orderbook_data, search_stocks_api, api_health_check, market_status,
    watchlist_api_v2
)
from financials.views import FinancialDataAPIView

urlpatterns = [
    # 시스템 API들을 먼저 배치 (구체적인 패턴)
    path('health/', api_health_check, name='api-health-check'),
    path('market-status/', market_status, name='market_status'),  # 시장 상태 API
    
    # Real-time API endpoints
    path('real-time/multiple/', multiple_real_time_prices, name='multiple_real_time_prices'),
    path('real-time/kospi200/', kospi200_real_time_prices, name='kospi200_real_time_prices'),
    path('real-time/<str:stock_code>/', real_time_price, name='real_time_price'),
    
    # 기타 구체적인 API들
    path('filter/', stock_filter_view, name='stock-filter'),
    path('search/', search_stocks_api, name='search_stocks_api'),
    path('chart/<str:stock_code>/', daily_chart_data, name='daily_chart_data'),
    path('orderbook/<str:stock_code>/', orderbook_data, name='orderbook_data'),
    
    # 관심종목 API (프론트엔드 호환)
    path('watchlist/', watchlist_api_v2, name='watchlist-api'),
    path('watchlist/<str:stock_code>/', watchlist_api_v2, name='watchlist-stock-api'),
    
    # Financial data endpoint
    path('<str:stock_code>/financials/', FinancialDataAPIView.as_view(), name='stock-financials'),
    
    # 기존 호환성을 위한 레거시 API
    path('legacy/', StockListAPIViewLegacy.as_view(), name='stock-list-legacy'),
    
    # 메인 API (가장 일반적인 패턴을 마지막에 배치)
    path('', StockListAPIView.as_view(), name='stock-list'),
    path('<str:stock_code>/', StockDetailAPIView.as_view(), name='stock-detail'),
    path('<str:stock_code>/price-history/', stock_price_history_view, name='stock-price-history'),
]
