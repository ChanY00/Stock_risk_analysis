from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from stocks.models import Stock
from .models import Portfolio, PortfolioHolding
from .serializers import (
    PortfolioSerializer, PortfolioCreateSerializer,
    PortfolioHoldingSerializer, PortfolioHoldingCreateSerializer
)

class PortfolioListCreateAPIView(generics.ListCreateAPIView):
    """포트폴리오 목록 조회 및 생성"""
    queryset = Portfolio.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PortfolioCreateSerializer
        return PortfolioSerializer
    
    def perform_create(self, serializer):
        # 현재는 사용자 인증을 사용하지 않으므로 user=None으로 설정
        serializer.save()

class PortfolioDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """포트폴리오 상세 조회, 수정, 삭제"""
    queryset = Portfolio.objects.all()
    serializer_class = PortfolioSerializer

class PortfolioHoldingListCreateAPIView(generics.ListCreateAPIView):
    """포트폴리오 보유종목 목록 조회 및 추가"""
    serializer_class = PortfolioHoldingSerializer
    
    def get_queryset(self):
        portfolio_id = self.kwargs['portfolio_id']
        return PortfolioHolding.objects.filter(portfolio_id=portfolio_id)
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return PortfolioHoldingCreateSerializer
        return PortfolioHoldingSerializer
    
    def perform_create(self, serializer):
        portfolio_id = self.kwargs['portfolio_id']
        portfolio = get_object_or_404(Portfolio, id=portfolio_id)
        holding = serializer.save(portfolio=portfolio)
        
        # 비중 재계산
        portfolio.calculate_weights()
        
        return holding

class PortfolioHoldingDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """포트폴리오 보유종목 상세 조회, 수정, 삭제"""
    serializer_class = PortfolioHoldingSerializer
    lookup_field = 'id'
    
    def get_queryset(self):
        portfolio_id = self.kwargs['portfolio_id']
        return PortfolioHolding.objects.filter(portfolio_id=portfolio_id)
    
    def perform_update(self, serializer):
        holding = serializer.save()
        # 비중 재계산
        holding.portfolio.calculate_weights()
    
    def perform_destroy(self, instance):
        portfolio = instance.portfolio
        super().perform_destroy(instance)
        # 비중 재계산
        portfolio.calculate_weights()

@api_view(['POST'])
def update_portfolio_weights(request, portfolio_id):
    """포트폴리오 비중 재계산"""
    portfolio = get_object_or_404(Portfolio, id=portfolio_id)
    portfolio.calculate_weights()
    
    serializer = PortfolioSerializer(portfolio)
    return Response({
        'message': '포트폴리오 비중이 재계산되었습니다.',
        'portfolio': serializer.data
    }) 