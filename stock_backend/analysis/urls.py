from django.urls import path
from .views import (
    SimilarStocksAPIView, stock_analysis_view, market_overview_view,
    WatchlistListCreateAPIView, WatchlistDetailAPIView, watchlist_stock_view,
    AlertListCreateAPIView, AlertDetailAPIView, check_alerts_view,
    cluster_overview_api, cluster_stocks_api, stock_cluster_info_api, similar_stocks_api,
    similarity_network_api, stock_similarity_detail_api
)

urlpatterns = [
    # 주식 분석 관련
    path('stocks/<str:stock_code>/', stock_analysis_view, name='stock-analysis'),
    path('similar/<str:stock_code>/', SimilarStocksAPIView.as_view(), name='similar-stocks'),
    path('cluster/<str:stock_code>/', stock_analysis_view, name='cluster-data'),  # 클러스터 데이터도 분석에 포함
    
    # 시장 개요
    path('market/overview/', market_overview_view, name='market-overview'),
    
    # 관심종목 (더 나은 구현이 있을 때까지 임시)
    path('watchlist/', WatchlistListCreateAPIView.as_view(), name='watchlist-list-create'),
    path('watchlist/<int:pk>/', WatchlistDetailAPIView.as_view(), name='watchlist-detail'),
    path('watchlist/<int:watchlist_id>/stocks/<str:stock_code>/', watchlist_stock_view, name='watchlist-stock'),
    
    # 알림
    path('alerts/', AlertListCreateAPIView.as_view(), name='alert-list-create'),
    path('alerts/<int:pk>/', AlertDetailAPIView.as_view(), name='alert-detail'),
    path('alerts/check/', check_alerts_view, name='check-alerts'),

    # 클러스터링 관련 API
    path('clusters/', cluster_overview_api, name='cluster-overview'),
    path('clusters/<str:cluster_type>/<int:cluster_id>/', cluster_stocks_api, name='cluster-stocks'),
    path('stocks/<str:stock_code>/cluster/', stock_cluster_info_api, name='stock-cluster-info'),
    path('stocks/<str:stock_code>/similar/', similar_stocks_api, name='similar-stocks'),
    
    # 유사도 네트워크 및 상세 정보 API
    path('clusters/<str:cluster_type>/<int:cluster_id>/network/', similarity_network_api, name='similarity-network'),
    path('stocks/<str:stock_code>/similarity/', stock_similarity_detail_api, name='stock-similarity-detail'),
]
