from django.urls import path
from .views import (
    stock_analysis_view, market_overview_view,
    cluster_overview_api, cluster_stocks_api, stock_cluster_info_api,
    similar_stocks_api, similarity_network_api, stock_similarity_detail_api,
    generate_report_view
)

urlpatterns = [
    # 분석 관련 API
    path('stock/<str:stock_code>/', stock_analysis_view, name='stock-analysis'),
    path('market-overview/', market_overview_view, name='market-overview'),

    # 클러스터링 관련 API
    path('cluster/overview/', cluster_overview_api, name='cluster-overview'),
    path('cluster/stocks/<str:cluster_type>/<int:cluster_id>/', cluster_stocks_api, name='cluster-stocks'),
    path('cluster/info/<str:stock_code>/', stock_cluster_info_api, name='stock-cluster-info'),
    # 유사도 기반 추천 API
    path('similar-stocks/<str:stock_code>/', similar_stocks_api, name='similar-stocks-api'),
    path('similarity-network/<str:cluster_type>/<int:cluster_id>/', similarity_network_api, name='similarity-network-api'),
    path('stock-similarity/<str:stock_code>/', stock_similarity_detail_api, name='stock-similarity-detail-api'),
    # AI 리포트 생성 API
    path('report/<str:stock_code>/', generate_report_view, name='generate-report'),
]
