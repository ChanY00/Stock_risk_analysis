from django.urls import path
from .views import (
    PortfolioListCreateAPIView, PortfolioDetailAPIView,
    PortfolioHoldingListCreateAPIView, PortfolioHoldingDetailAPIView,
    update_portfolio_weights
)

urlpatterns = [
    # 포트폴리오 CRUD
    path('', PortfolioListCreateAPIView.as_view(), name='portfolio-list-create'),
    path('<int:pk>/', PortfolioDetailAPIView.as_view(), name='portfolio-detail'),
    
    # 포트폴리오 보유종목 CRUD
    path('<int:portfolio_id>/holdings/', PortfolioHoldingListCreateAPIView.as_view(), name='portfolio-holdings'),
    path('<int:portfolio_id>/holdings/<int:id>/', PortfolioHoldingDetailAPIView.as_view(), name='portfolio-holding-detail'),
    
    # 유틸리티
    path('<int:portfolio_id>/update-weights/', update_portfolio_weights, name='update-portfolio-weights'),
] 