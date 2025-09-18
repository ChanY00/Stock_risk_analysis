from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Avg, Count
from stocks.models import Stock
from .models import ClusteringCriterion, ClusteringResult, TechnicalIndicator, MarketIndex, Watchlist, Alert, SpectralCluster, AgglomerativeCluster, ClusterAnalysis, StockSimilarity
from .serializers import (
    ClusteringResultSerializer, TechnicalIndicatorSerializer, MarketIndexSerializer,
    WatchlistSerializer, WatchlistCreateSerializer, AlertSerializer, AlertCreateSerializer,
    StockAnalysisSerializer, MarketOverviewSerializer, StockSummarySerializer,
    ClusterAnalysisSerializer, ClusterStockListSerializer,
    SpectralClusterSerializer, AgglomerativeClusterSerializer, SimilarStockSerializer, StockSimilaritySerializer
)
from sentiment.models import SentimentAnalysis
from stocks.serializers import StockListSerializer
from .cache_utils import CacheManager

class SimilarStocksAPIView(generics.ListAPIView):
    serializer_class = StockSummarySerializer

    def get_queryset(self):
        stock_code = self.kwargs['stock_code']
        
        try:
            target_stock = Stock.objects.get(stock_code=stock_code)
        except Stock.DoesNotExist:
            return Stock.objects.none()

        # 클러스터링 결과를 기반으로 유사한 주식 찾기
        clustering_results = ClusteringResult.objects.filter(stock=target_stock)
        
        similar_stocks = Stock.objects.none()
        for result in clustering_results:
            cluster_stocks = ClusteringResult.objects.filter(
                criterion=result.criterion,
                cluster_id=result.cluster_id
            ).exclude(stock=target_stock)
            
            for cluster_stock in cluster_stocks:
                similar_stocks = similar_stocks.union(Stock.objects.filter(id=cluster_stock.stock.id))
        
        return similar_stocks.distinct()[:10]  # 최대 10개

@api_view(['GET'])
def stock_analysis_view(request, stock_code):
    """주식 분석 API (캐시 적용)"""
    try:
        stock = Stock.objects.get(stock_code=stock_code)
    except Stock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # 캐시에서 먼저 확인
    cached_data = CacheManager.get_stock_analysis(stock.id)
    if cached_data:
        return Response(cached_data)
    
    # 기술적 지표
    try:
        technical = stock.technical
        technical_data = TechnicalIndicatorSerializer(technical).data
    except TechnicalIndicator.DoesNotExist:
        technical_data = None
    
    # 기본적 분석 (순위 계산)
    total_stocks = Stock.objects.exclude(per__isnull=True).count()
    
    fundamental_analysis = {}
    if stock.per:
        per_rank = Stock.objects.filter(per__lt=stock.per, per__isnull=False).count() + 1
        fundamental_analysis['per_rank'] = per_rank
    
    if stock.pbr:
        pbr_rank = Stock.objects.filter(pbr__lt=stock.pbr, pbr__isnull=False).count() + 1
        fundamental_analysis['pbr_rank'] = pbr_rank
    
    if stock.roe:
        roe_rank = Stock.objects.filter(roe__gt=stock.roe, roe__isnull=False).count() + 1
        fundamental_analysis['roe_rank'] = roe_rank
    
    if stock.dividend_yield:
        dividend_rank = Stock.objects.filter(
            dividend_yield__gt=stock.dividend_yield, 
            dividend_yield__isnull=False
        ).count() + 1
        fundamental_analysis['dividend_yield_rank'] = dividend_rank
    
    # 종합 순위 (간단한 평균 방식)
    ranks = [fundamental_analysis.get(key) for key in ['per_rank', 'pbr_rank', 'roe_rank', 'dividend_yield_rank'] if fundamental_analysis.get(key)]
    if ranks:
        fundamental_analysis['overall_rank'] = int(sum(ranks) / len(ranks))
    
    response_data = {
        'stock_code': stock_code,
        'stock_name': stock.stock_name,
        'technical_indicators': technical_data,
        'fundamental_analysis': fundamental_analysis
    }
    
    # 캐시에 저장
    CacheManager.set_stock_analysis(stock.id, response_data)
    
    return Response(response_data)

@api_view(['GET'])
def market_overview_view(request):
    """시장 개요 API (캐시 적용)"""
    # 캐시에서 먼저 확인
    cached_data = CacheManager.get_market_overview()
    if cached_data:
        return Response(cached_data)
    
    # 시장 지수 데이터
    market_indices = MarketIndex.objects.all()
    market_summary = {}
    
    for index in market_indices:
        market_summary[index.name.lower()] = {
            'current': index.current_value,
            'change': index.change,
            'change_percent': index.change_percent,
            'volume': index.volume,
            'high': index.high,
            'low': index.low,
            'trade_value': index.trade_value
        }
    
    # 섹터별 성과 (간단한 구현)
    sectors = Stock.objects.exclude(sector__isnull=True).values('sector').annotate(
        count=Count('sector')
    ).order_by('-count')[:10]
    
    sector_performance = []
    for sector_data in sectors:
        sector_stocks = Stock.objects.filter(sector=sector_data['sector'])
        # 최고 성과 종목 찾기 (ROE 기준)
        top_performer = sector_stocks.exclude(roe__isnull=True).order_by('-roe').first()
        
        if top_performer:
            sector_performance.append({
                'sector': sector_data['sector'],
                'change_percent': top_performer.roe,  # 임시로 ROE를 사용
                'top_performer': {
                    'name': top_performer.stock_name,
                    'code': top_performer.stock_code,
                    'change_percent': top_performer.roe or 0
                }
            })
    
    response_data = {
        'market_summary': market_summary,
        'sector_performance': sector_performance
    }
    
    # 캐시에 저장 (30초)
    CacheManager.set_market_overview(response_data)
    
    return Response(response_data)

# Watchlist API Views
class WatchlistListCreateAPIView(generics.ListCreateAPIView):
    queryset = Watchlist.objects.all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return WatchlistCreateSerializer
        return WatchlistSerializer

class WatchlistDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Watchlist.objects.all()
    serializer_class = WatchlistSerializer

@api_view(['POST', 'DELETE'])
def watchlist_stock_view(request, watchlist_id, stock_code):
    """관심종목 리스트에 주식 추가/제거"""
    watchlist = get_object_or_404(Watchlist, id=watchlist_id)
    stock = get_object_or_404(Stock, stock_code=stock_code)
    
    if request.method == 'POST':
        watchlist.stocks.add(stock)
        return Response({'message': f'{stock.stock_name} added to {watchlist.name}'})
    
    elif request.method == 'DELETE':
        watchlist.stocks.remove(stock)
        return Response({'message': f'{stock.stock_name} removed from {watchlist.name}'})

# Alert API Views
class AlertListCreateAPIView(generics.ListCreateAPIView):
    queryset = Alert.objects.all()
    permission_classes = [IsAuthenticated]  # 인증 필수
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AlertCreateSerializer
        return AlertSerializer
    
    def create(self, request, *args, **kwargs):
        # 로그인 체크 - 알람 생성은 로그인 필수
        if not request.user.is_authenticated:
            return Response(
                {'error': '알람 생성은 로그인이 필요합니다.'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class AlertDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Alert.objects.all()
    serializer_class = AlertSerializer

@api_view(['POST'])
def check_alerts_view(request):
    """활성 알림들 확인"""
    active_alerts = Alert.objects.filter(is_active=True, triggered_at__isnull=True)
    triggered_alerts = []
    
    for alert in active_alerts:
        if alert.check_condition():
            from django.utils import timezone
            alert.triggered_at = timezone.now()
            alert.is_active = False
            alert.save()
            triggered_alerts.append(AlertSerializer(alert).data)
    
    return Response({
        'triggered_count': len(triggered_alerts),
        'triggered_alerts': triggered_alerts
    })

@api_view(['GET'])
def cluster_overview_api(request):
    """클러스터링 개요 API"""
    cluster_type = request.query_params.get('type', 'spectral')  # spectral or agglomerative
    
    if cluster_type not in ['spectral', 'agglomerative']:
        return Response({'error': 'Invalid cluster type'}, status=status.HTTP_400_BAD_REQUEST)
    
    # 클러스터 분석 정보 조회
    cluster_analyses = ClusterAnalysis.objects.filter(cluster_type=cluster_type).order_by('cluster_id')
    
    response_data = {
        'cluster_type': cluster_type,
        'total_clusters': cluster_analyses.count(),
        'clusters': ClusterAnalysisSerializer(cluster_analyses, many=True).data
    }
    
    return Response(response_data)

@api_view(['GET'])
def cluster_stocks_api(request, cluster_type, cluster_id):
    """특정 클러스터의 주식 목록 API"""
    if cluster_type not in ['spectral', 'agglomerative']:
        return Response({'error': 'Invalid cluster type'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # 클러스터 분석 정보 조회
        cluster_analysis = ClusterAnalysis.objects.get(
            cluster_type=cluster_type, 
            cluster_id=cluster_id
        )
        
        # 해당 클러스터의 주식들 조회
        if cluster_type == 'spectral':
            cluster_stocks = Stock.objects.filter(
                spectral_cluster__cluster_id=cluster_id
            ).select_related('spectral_cluster')
        else:
            cluster_stocks = Stock.objects.filter(
                agglomerative_cluster__cluster_id=cluster_id
            ).select_related('agglomerative_cluster')
        
        # 유사한 클러스터 찾기 (같은 주요 섹터를 가진 다른 클러스터)
        similar_clusters = ClusterAnalysis.objects.filter(
            cluster_type=cluster_type,
            dominant_sectors__overlap=cluster_analysis.dominant_sectors
        ).exclude(cluster_id=cluster_id)[:3]
        
        response_data = {
            'cluster_analysis': ClusterAnalysisSerializer(cluster_analysis).data,
            'stocks': StockListSerializer(cluster_stocks, many=True).data,
            'similar_clusters': ClusterAnalysisSerializer(similar_clusters, many=True).data
        }
        
        return Response(response_data)
        
    except ClusterAnalysis.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def stock_cluster_info_api(request, stock_code):
    """특정 주식의 클러스터 정보 API"""
    try:
        stock = Stock.objects.get(stock_code=stock_code)
        
        response_data = {
            'stock_code': stock_code,
            'stock_name': stock.stock_name,
            'clusters': {}
        }
        
        # Spectral 클러스터 정보
        try:
            spectral_cluster = stock.spectral_cluster
            spectral_analysis = ClusterAnalysis.objects.get(
                cluster_type='spectral',
                cluster_id=spectral_cluster.cluster_id
            )
            response_data['clusters']['spectral'] = {
                'cluster_id': spectral_cluster.cluster_id,
                'cluster_name': spectral_analysis.cluster_name,
                'cluster_analysis': ClusterAnalysisSerializer(spectral_analysis).data
            }
        except (SpectralCluster.DoesNotExist, ClusterAnalysis.DoesNotExist):
            response_data['clusters']['spectral'] = None
        
        # Agglomerative 클러스터 정보
        try:
            agg_cluster = stock.agglomerative_cluster
            agg_analysis = ClusterAnalysis.objects.get(
                cluster_type='agglomerative',
                cluster_id=agg_cluster.cluster_id
            )
            response_data['clusters']['agglomerative'] = {
                'cluster_id': agg_cluster.cluster_id,
                'cluster_name': agg_analysis.cluster_name,
                'cluster_analysis': ClusterAnalysisSerializer(agg_analysis).data
            }
        except (AgglomerativeCluster.DoesNotExist, ClusterAnalysis.DoesNotExist):
            response_data['clusters']['agglomerative'] = None
        
        return Response(response_data)
        
    except Stock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_report_view(request, stock_code):
    """AI 기반 종합 리포트 생성 API"""
    # from .gemini_utils import generate_stock_report # 실제로는 gemini_utils.py 파일에 구현

    try:
        # Gemini API 호출을 모킹하는 함수입니다. 실제 구현 시에는 이 부분을 Gemini API 호출 코드로 대체해야 합니다.
        def generate_stock_report(data):
            opinion = "관망"
            tech_data = data.get('technical', {})
            senti_data = data.get('sentiment', {})

            if tech_data and senti_data and tech_data.get('rsi', 50) > 70 and senti_data.get('sentiment_score', 0.5) < 0.4:
                opinion = "매도 타이밍"
            elif tech_data and senti_data and tech_data.get('rsi', 50) < 30 and senti_data.get('sentiment_score', 0.5) > 0.6:
                opinion = "매수 타이밍"

            recommendation_stock = "추천 종목 없음"
            recommendation_reason = "유사 그룹 내 추천할 만한 종목을 찾지 못했습니다."
            recommendations = []
            if data.get('similar_stocks'):
                # 상위 3개 추천 생성
                for sim in data['similar_stocks'][:3]:
                    name = sim.get('stock_name', '추천 종목')
                    reasons = []
                    if sim.get('per') is not None:
                        reasons.append("밸류에이션이 안정적")
                    if sim.get('pbr') is not None:
                        reasons.append("자산가치 대비 합리적")
                    if sim.get('market_cap'):
                        reasons.append("시가총액 규모 적정")
                    reason_text = ", ".join(reasons) if reasons else "재무적으로 안정적인 모습"
                    recommendations.append({
                        'stock_name': name,
                        'reason': f"{name}은(는) {reason_text}을 보이고 있습니다."
                    })
                if recommendations:
                    recommendation_stock = recommendations[0]['stock_name']
                    recommendation_reason = recommendations[0]['reason']

            return {
                "investment_opinion": opinion,
                "financial_analysis": f"{data['stock_name']}의 재무 상태는 안정적으로 보입니다.",
                "technical_analysis": "기술적 지표상 현재 주가는 과매수/과매도 구간에 있습니다.",
                "sentiment_analysis": "시장의 감정은 현재 긍정적/부정적입니다.",
                "recommendation": {
                    "stock_name": recommendation_stock,
                    "reason": recommendation_reason
                },
                # 다건 추천 (옵션)
                "recommendations": recommendations,
                "excluded_sections": data.get('excluded_sections', [])
            }

        try:
            stock = Stock.objects.select_related('technical', 'sentiment').get(stock_code=stock_code)
        except Stock.DoesNotExist:
            return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)

        excluded_sections = []
        stock_data = {
            'stock_code': stock.stock_code, 'stock_name': stock.stock_name, 'sector': stock.sector,
            'current_price': stock.current_price, 'market_cap': stock.market_cap, 'per': stock.per,
            'pbr': stock.pbr, 'roe': stock.roe, 'dividend_yield': stock.dividend_yield,
        }

        try:
            financials = stock.financials.latest('year')
            stock_data['financials'] = {'revenue': financials.revenue, 'operating_income': financials.operating_income, 'net_income': financials.net_income}
        except Exception:
            excluded_sections.append('재무 분석')
            stock_data['financials'] = None

        try:
            stock_data['technical'] = TechnicalIndicatorSerializer(stock.technical).data
        except TechnicalIndicator.DoesNotExist:
            excluded_sections.append('기술적 분석')
            stock_data['technical'] = None
        
        try:
            # sentiment 앱의 모델은 Stock에 related_name='sentiment'로 연결
            stock_data['sentiment'] = {
                'sentiment_score': float(stock.sentiment.positive) - float(stock.sentiment.negative) if getattr(stock, 'sentiment', None) else None,
                'positive_ratio': float(stock.sentiment.positive) if getattr(stock, 'sentiment', None) else None,
                'negative_ratio': float(stock.sentiment.negative) if getattr(stock, 'sentiment', None) else None,
                'top_keywords': stock.sentiment.top_keywords if getattr(stock, 'sentiment', None) else ''
            }
        except (SentimentAnalysis.DoesNotExist, AttributeError, ValueError, TypeError) as e:
            excluded_sections.append('감정 분석')
            stock_data['sentiment'] = None

        similar_stocks = StockSimilarity.get_most_similar_stocks(stock=stock, limit=5)
        if similar_stocks.exists():
            stock_data['similar_stocks'] = SimilarStockSerializer(similar_stocks, many=True).data
        else:
            excluded_sections.append('유사 그룹 내 주식 추천')
            stock_data['similar_stocks'] = None
            
        stock_data['excluded_sections'] = excluded_sections

        report_content = generate_stock_report(stock_data)
        return Response(report_content)
    except Exception as e:
        # 어떤 예외도 JSON으로 반환하여 프론트에서 메시지 확인 가능하게 함
        return Response({'error': f'AI 리포트 생성 중 서버 오류: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def similar_stocks_api(request, stock_code):
    """유사한 주식 추천 API (클러스터 기반 + 유사도 정보)"""
    try:
        stock = Stock.objects.get(stock_code=stock_code)
        cluster_type = request.query_params.get('type', 'spectral')
        limit = int(request.query_params.get('limit', 10))
        
        if cluster_type not in ['spectral', 'agglomerative']:
            return Response({'error': 'Invalid cluster type'}, status=status.HTTP_400_BAD_REQUEST)
        
        # StockSimilarity 모델을 사용한 개선된 유사 종목 추천
        similar_stocks_data = StockSimilarity.get_most_similar_stocks(
            stock=stock, 
            cluster_type=cluster_type, 
            limit=limit
        )
        
        if similar_stocks_data.exists():
            # 유사도 데이터가 있는 경우
            similar_stocks_serializer = SimilarStockSerializer(similar_stocks_data, many=True)
            total_count = similar_stocks_data.count()
        else:
            # 유사도 데이터가 없는 경우 기존 클러스터 기반 로직 사용
            similar_stocks = []
            
            if cluster_type == 'spectral':
                try:
                    cluster_id = stock.spectral_cluster.cluster_id
                    similar_stocks = Stock.objects.filter(
                        spectral_cluster__cluster_id=cluster_id
                    ).exclude(stock_code=stock_code)[:limit]
                except SpectralCluster.DoesNotExist:
                    pass
            else:
                try:
                    cluster_id = stock.agglomerative_cluster.cluster_id
                    similar_stocks = Stock.objects.filter(
                        agglomerative_cluster__cluster_id=cluster_id
                    ).exclude(stock_code=stock_code)[:limit]
                except AgglomerativeCluster.DoesNotExist:
                    pass
            
            # 기본 형태로 변환 (유사도 점수 없이)
            similar_stocks_data = []
            for idx, sim_stock in enumerate(similar_stocks):
                similar_stocks_data.append({
                    'stock_code': sim_stock.stock_code,
                    'stock_name': sim_stock.stock_name,
                    'sector': sim_stock.sector,
                    'current_price': sim_stock.current_price,
                    'market_cap': sim_stock.market_cap,
                    'per': sim_stock.per,
                    'pbr': sim_stock.pbr,
                    'neighbor_rank': idx + 1,
                    'distance': None,
                    'similarity_score': None
                })
            
            similar_stocks_serializer = similar_stocks_data
            total_count = len(similar_stocks_data)
        
        response_data = {
            'base_stock': {
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'sector': stock.sector
            },
            'cluster_type': cluster_type,
            'similar_stocks': similar_stocks_serializer.data if hasattr(similar_stocks_serializer, 'data') else similar_stocks_serializer,
            'total_count': total_count
        }
        
        return Response(response_data)
        
    except Stock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
def similarity_network_api(request, cluster_type, cluster_id):
    """클러스터 내 유사도 네트워크 데이터 API"""
    if cluster_type not in ['spectral', 'agglomerative']:
        return Response({'error': 'Invalid cluster type'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        min_similarity = float(request.query_params.get('min_similarity', 0.5))
        
        # 클러스터 분석 정보
        cluster_analysis = ClusterAnalysis.objects.get(
            cluster_type=cluster_type,
            cluster_id=cluster_id
        )
        
        # 유사도 네트워크 데이터
        similarities = StockSimilarity.get_similarity_network(
            cluster_type=cluster_type,
            cluster_id=cluster_id,
            min_similarity=min_similarity
        )
        
        # 노드 데이터 생성 (클러스터 내 모든 종목)
        if cluster_type == 'spectral':
            cluster_stocks = Stock.objects.filter(spectral_cluster__cluster_id=cluster_id)
        else:
            cluster_stocks = Stock.objects.filter(agglomerative_cluster__cluster_id=cluster_id)
        
        nodes = []
        for stock in cluster_stocks:
            nodes.append({
                'id': stock.stock_code,
                'name': stock.stock_name,
                'sector': stock.sector,
                'market_cap': stock.market_cap,
                'current_price': stock.current_price,
                'per': stock.per,
                'pbr': stock.pbr
            })
        
        # 엣지 데이터 생성 (유사도 관계)
        edges = []
        for similarity in similarities:
            edges.append({
                'source': similarity.source_stock.stock_code,
                'target': similarity.target_stock.stock_code,
                'distance': similarity.distance,
                'similarity_score': similarity.similarity_score,
                'rank': similarity.neighbor_rank
            })
        
        response_data = {
            'nodes': nodes,
            'edges': edges,
            'cluster_info': {
                'cluster_type': cluster_type,
                'cluster_id': cluster_id,
                'cluster_name': cluster_analysis.cluster_name,
                'description': cluster_analysis.description,
                'stock_count': len(nodes),
                'similarity_count': len(edges)
            }
        }
        
        return Response(response_data)
        
    except ClusterAnalysis.DoesNotExist:
        return Response({'error': 'Cluster not found'}, status=status.HTTP_404_NOT_FOUND)
    except ValueError:
        return Response({'error': 'Invalid min_similarity parameter'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def stock_similarity_detail_api(request, stock_code):
    """특정 종목의 상세 유사도 정보 API"""
    try:
        stock = Stock.objects.get(stock_code=stock_code)
        cluster_type = request.query_params.get('type', 'spectral')
        
        if cluster_type not in ['spectral', 'agglomerative']:
            return Response({'error': 'Invalid cluster type'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 해당 종목의 모든 유사도 관계 조회
        similarities = StockSimilarity.objects.filter(
            cluster_type=cluster_type,
            source_stock=stock
        ).select_related('target_stock').order_by('neighbor_rank')
        
        response_data = {
            'stock_code': stock.stock_code,
            'stock_name': stock.stock_name,
            'cluster_type': cluster_type,
            'similarities': StockSimilaritySerializer(similarities, many=True).data,
            'total_similarities': similarities.count()
        }
        
        return Response(response_data)
        
    except Stock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)
