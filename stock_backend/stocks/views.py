# stocks/views.py

from rest_framework import generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db.models import Q
from .models import Stock
from .serializers import (
    StockSerializer, StockDetailSerializer, StockListSerializer, StockFilterSerializer
)
from analysis.cache_utils import CacheManager
from .services import StockPriceService, StockSearchService
from django.utils import timezone
import logging
import random
import os

# 시장 시간 체크 모듈 import
from kis_api.market_hours import get_market_status, log_market_status

logger = logging.getLogger(__name__)

class StockListAPIView(generics.ListAPIView):
    """주식 목록 API - 확장된 필드 포함 (캐시 적용)"""
    serializer_class = StockListSerializer

    def get(self, request, *args, **kwargs):
        # 쿼리 파라미터로 캐시 키 생성
        filters = {
            'search': request.query_params.get('search'),
            'market': request.query_params.get('market'),
            'sector': request.query_params.get('sector'),
        }
        
        # 빈 값 제거
        filters = {k: v for k, v in filters.items() if v}
        
        # 캐시에서 먼저 확인
        cached_data = CacheManager.get_stock_list(filters)
        if cached_data:
            return Response(cached_data)
        
        # 기존 로직 실행
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        response_data = {
            'count': queryset.count(),
            'results': serializer.data
        }
        
        # 캐시에 저장
        CacheManager.set_stock_list(response_data, filters)
        
        return Response(response_data)

    def get_queryset(self):
        queryset = Stock.objects.select_related().prefetch_related('prices')
        
        # 검색 기능
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(stock_name__icontains=search) | Q(stock_code__icontains=search)
            )
        
        # 시장 필터
        market = self.request.query_params.get('market', None)
        if market:
            queryset = queryset.filter(market=market)
            
        # 섹터 필터
        sector = self.request.query_params.get('sector', None)
        if sector:
            queryset = queryset.filter(sector__icontains=sector)
            
        return queryset

class StockDetailAPIView(generics.RetrieveAPIView):
    """주식 상세 정보 API - 모든 관련 데이터 포함 (캐시 적용)"""
    serializer_class = StockDetailSerializer
    lookup_field = 'stock_code'
    
    def get(self, request, *args, **kwargs):
        stock_code = kwargs.get('stock_code')
        
        try:
            stock = self.get_object()
        except Stock.DoesNotExist:
            return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # 캐시에서 먼저 확인
        cached_data = CacheManager.get_stock_detail(stock.id)
        if cached_data:
            return Response(cached_data)
        
        # 기존 로직 실행
        serializer = self.get_serializer(stock)
        response_data = serializer.data
        
        # 캐시에 저장
        CacheManager.set_stock_detail(stock.id, response_data)
        
        return Response(response_data)
    
    def get_queryset(self):
        return Stock.objects.select_related().prefetch_related(
            'prices', 'financials', 'technical'
        )

@api_view(['GET'])
def stock_filter_view(request):
    """주식 필터링 API"""
    serializer = StockFilterSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    queryset = Stock.objects.all()
    
    # 시장 필터
    if 'market' in filters:
        queryset = queryset.filter(market=filters['market'])
    
    # 섹터 필터
    if 'sector' in filters:
        queryset = queryset.filter(sector__icontains=filters['sector'])
    
    # PER 필터
    if 'min_per' in filters:
        queryset = queryset.filter(per__gte=filters['min_per'])
    if 'max_per' in filters:
        queryset = queryset.filter(per__lte=filters['max_per'])
    
    # PBR 필터
    if 'min_pbr' in filters:
        queryset = queryset.filter(pbr__gte=filters['min_pbr'])
    if 'max_pbr' in filters:
        queryset = queryset.filter(pbr__lte=filters['max_pbr'])
    
    # ROE 필터
    if 'min_roe' in filters:
        queryset = queryset.filter(roe__gte=filters['min_roe'])
    if 'max_roe' in filters:
        queryset = queryset.filter(roe__lte=filters['max_roe'])
    
    # 배당수익률 필터
    if 'min_dividend_yield' in filters:
        queryset = queryset.filter(dividend_yield__gte=filters['min_dividend_yield'])
    if 'max_dividend_yield' in filters:
        queryset = queryset.filter(dividend_yield__lte=filters['max_dividend_yield'])
    
    # Null 값 제외
    queryset = queryset.exclude(per__isnull=True, pbr__isnull=True, roe__isnull=True)
    
    # 결과 시리얼라이즈
    serializer = StockListSerializer(queryset, many=True)
    return Response({
        'count': queryset.count(),
        'stocks': serializer.data
    })

@api_view(['GET'])
def stock_price_history_view(request, stock_code):
    """주가 히스토리 API (개선된 파라미터 처리)"""
    try:
        stock = Stock.objects.get(stock_code=stock_code)
    except Stock.DoesNotExist:
        return Response({'error': 'Stock not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # 파라미터 처리
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    days = request.query_params.get('days')
    interval = request.query_params.get('interval', 'daily')  # daily, weekly, monthly
    
    prices = stock.prices.all()
    
    # days 파라미터 처리 (새로 추가)
    if days:
        try:
            days_int = int(days)
            from datetime import datetime, timedelta
            start_date = (datetime.now().date() - timedelta(days=days_int)).strftime('%Y-%m-%d')
        except ValueError:
            pass
    
    # 날짜 필터링
    if start_date:
        prices = prices.filter(date__gte=start_date)
    if end_date:
        prices = prices.filter(date__lte=end_date)
    
    prices = prices.order_by('date')
    
    # 간격 처리 (간단한 구현 - 나중에 고도화 가능)
    if interval == 'weekly':
        # 주간 데이터는 매주 금요일 데이터만
        prices = prices.filter(date__week_day=6)
    elif interval == 'monthly':
        # 월간 데이터는 매월 마지막 거래일 (간단히 월말 근처)
        prices = prices.filter(date__day__gte=25)
    
    # 이동평균선을 포함한 가격 데이터 생성
    price_list = list(prices)
    close_prices = [p.close_price for p in price_list]
    price_data = []
    
    for i, price in enumerate(price_list):
        data = {
            "date": price.date,
            "open": price.open_price,
            "high": price.high_price,
            "low": price.low_price,
            "close": price.close_price,
            "volume": price.volume
        }
        
        # 이동평균선 계산
        if i >= 4:  # MA5
            ma5 = sum(close_prices[i-4:i+1]) / 5
            data['ma5'] = round(ma5, 2)
        else:
            data['ma5'] = None
            
        if i >= 19:  # MA20
            ma20 = sum(close_prices[i-19:i+1]) / 20
            data['ma20'] = round(ma20, 2)
        else:
            data['ma20'] = None
            
        if i >= 59:  # MA60
            ma60 = sum(close_prices[i-59:i+1]) / 60
            data['ma60'] = round(ma60, 2)
        else:
            data['ma60'] = None
        
        price_data.append(data)
    
    return Response({
        'stock_code': stock_code,
        'stock_name': stock.stock_name,
        'interval': interval,
        'total_records': len(price_data),
        'date_range': {
            'start': price_data[0]['date'] if price_data else None,
            'end': price_data[-1]['date'] if price_data else None
        },
        'price_history': price_data
    })

# 기존 호환성을 위한 뷰 (deprecated)
class StockListAPIViewLegacy(generics.ListAPIView):
    """기존 API 호환성을 위한 레거시 뷰"""
    serializer_class = StockSerializer

    def get_queryset(self):
        queryset = Stock.objects.all()
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(stock_name__icontains=search) | Q(stock_code__icontains=search)
            )
        return queryset

@api_view(['GET'])
def real_time_price(request, stock_code):
    """실시간 주가 조회 (개선된 에러 처리)"""
    try:
        service = StockPriceService()
        price_data = service.get_real_time_price(stock_code)
        
        if price_data:
            return Response(price_data)
        else:
            # 실패 시 DB에서 기본 정보라도 제공
            try:
                stock = Stock.objects.get(stock_code=stock_code)
                return Response({
                    'code': stock_code,
                    'name': stock.stock_name,
                    'current_price': stock.current_price or 0,
                    'change_amount': 0,
                    'change_percent': 0.0,
                    'volume': 0,
                    'trading_value': 0,
                    'market_cap': stock.market_cap or 0,
                    'high_price': 0,
                    'low_price': 0,
                    'open_price': 0,
                    'prev_close': 0,
                    'timestamp': '',
                    'fallback': True,
                    'message': '실시간 데이터를 가져올 수 없어 DB 데이터를 사용합니다.'
                })
            except Stock.DoesNotExist:
                return Response(
                    {"error": "Stock not found"}, 
                    status=404
                )
    except Exception as e:
        error_msg = str(e)
        
        # 토큰 관련 오류 체크
        if '토큰' in error_msg or 'token' in error_msg.lower() or '1분당' in error_msg:
            return Response({
                "error": "API_RATE_LIMIT",
                "message": "API 토큰 발급 제한으로 잠시 후 다시 시도해주세요. (1분당 1회 제한)",
                "retry_after": 60
            }, status=429)
        
        return Response({
            "error": str(e),
            "message": "실시간 데이터 조회 중 오류가 발생했습니다."
        }, status=500)

@api_view(['GET'])
def multiple_real_time_prices(request):
    """여러 종목 실시간 주가 조회 (개선된 안정성)"""
    try:
        codes_param = request.GET.get('codes', '')
        
        if not codes_param:
            return Response({
                'error': '종목 코드가 필요합니다. ?codes=005930,000660 형식으로 입력하세요.'
            }, status=400)
        
        stock_codes = [code.strip() for code in codes_param.split(',') if code.strip()]
        
        if len(stock_codes) > 20:  # 제한 추가
            return Response({
                'error': '한 번에 최대 20개 종목까지만 조회 가능합니다.'
            }, status=400)
        
        service = StockPriceService()
        
        # API 시도
        api_results = service.get_multiple_prices(stock_codes)
        
        # 실패한 종목들을 위한 폴백 데이터
        failed_codes = [code for code in stock_codes if code not in api_results]
        fallback_data = {}
        
        if failed_codes:
            logger.warning(f"API failed for codes: {failed_codes}, trying fallback...")
            fallback_data = service.get_db_fallback_data(failed_codes)
        
        # 결과 병합
        all_results = {**api_results, **fallback_data}
        
        total_requested = len(stock_codes)
        successful = len(all_results)
        api_successful = len(api_results)
        fallback_successful = len(fallback_data)
        
        return Response({
            'data': all_results,
            'summary': {
                'total_requested': total_requested,
                'successful': successful,
                'api_successful': api_successful,
                'fallback_successful': fallback_successful,
                'failed': total_requested - successful,
                'failed_codes': [code for code in stock_codes if code not in all_results],
                'success_rate': round((successful / total_requested) * 100, 1) if total_requested > 0 else 0
            },
            'message': f'{successful}/{total_requested} 종목 조회 완료 (API: {api_successful}, DB: {fallback_successful})'
        })
    
    except Exception as e:
        logger.error(f"Multiple real-time prices error: {e}")
        return Response({
            'error': '서버 오류가 발생했습니다.',
            'detail': str(e)
        }, status=500)

@api_view(['GET'])
def kospi200_real_time_prices(request):
    """KOSPI 200 종목 실시간 주가 조회 (제한적)"""
    try:
        limit = int(request.GET.get('limit', 20))  # 기본 20개로 제한
        
        if limit > 50:
            return Response({
                'error': '한 번에 최대 50개 종목까지만 조회 가능합니다.'
            }, status=400)
        
        service = StockPriceService()
        
        # DB에서 KOSPI 종목 제한적으로 조회
        kospi_stocks = Stock.objects.filter(
            market='KOSPI'
        ).values_list('stock_code', flat=True)[:limit]
        
        if not kospi_stocks:
            return Response({
                'error': 'KOSPI 종목을 찾을 수 없습니다.'
            }, status=404)
        
        stock_codes = list(kospi_stocks)
        
        # API 시도
        api_results = service.get_multiple_prices(stock_codes)
        
        # 실패한 종목들을 위한 폴백 데이터
        failed_codes = [code for code in stock_codes if code not in api_results]
        fallback_data = {}
        
        if failed_codes and len(failed_codes) < len(stock_codes) * 0.7:  # 70% 이상 실패하지 않았으면 폴백 시도
            fallback_data = service.get_db_fallback_data(failed_codes)
        
        # 결과 병합
        all_results = {**api_results, **fallback_data}
        
        total_requested = len(stock_codes)
        successful = len(all_results)
        
        return Response({
            'data': all_results,
            'summary': {
                'total_requested': total_requested,
                'successful': successful,
                'api_successful': len(api_results),
                'fallback_successful': len(fallback_data),
                'failed': total_requested - successful,
                'success_rate': round((successful / total_requested) * 100, 1) if total_requested > 0 else 0
            },
            'message': f'KOSPI {successful}/{total_requested} 종목 조회 완료'
        })
    
    except Exception as e:
        logger.error(f"KOSPI 200 real-time prices error: {e}")
        return Response({
            'error': '서버 오류가 발생했습니다.',
            'detail': str(e)
        }, status=500)

@api_view(['GET'])  
def daily_chart_data(request, stock_code):
    """일봉 차트 데이터 조회 (폴백 포함)"""
    try:
        period = request.GET.get('period', 'D')
        service = StockPriceService()
        
        # API 시도
        chart_data = service.get_daily_chart_data(stock_code, period)
        
        if chart_data:
            return Response({
                'data': chart_data,
                'source': 'api',
                'message': f'{stock_code} 차트 데이터 조회 성공'
            })
        else:
            # 폴백: DB에서 최근 30일 데이터 조회
            try:
                stock = Stock.objects.get(stock_code=stock_code)
                recent_prices = stock.prices.all()[:30]  # 최근 30일
                
                fallback_data = []
                for price in recent_prices:
                    fallback_data.append({
                        'date': price.date.strftime('%Y%m%d'),
                        'open': price.open_price,
                        'high': price.high_price,
                        'low': price.low_price,
                        'close': price.close_price,
                        'volume': price.volume
                    })
                
                if fallback_data:
                    return Response({
                        'data': fallback_data,
                        'source': 'database',
                        'message': f'{stock_code} DB 차트 데이터 (최근 30일)'
                    })
                
            except Stock.DoesNotExist:
                pass
            
            return Response({
                'error': f'{stock_code} 차트 데이터를 찾을 수 없습니다.'
            }, status=404)
    
    except Exception as e:
        logger.error(f"Daily chart data error for {stock_code}: {e}")
        return Response({
            'error': '차트 데이터 조회 중 오류가 발생했습니다.',
            'detail': str(e)
        }, status=500)

@api_view(['GET'])
def orderbook_data(request, stock_code):
    """호가 정보 조회 (에러 처리 개선)"""
    try:
        service = StockPriceService()
        orderbook = service.get_orderbook_data(stock_code)
        
        if orderbook:
            return Response({
                'data': orderbook,
                'message': f'{stock_code} 호가 정보 조회 성공'
            })
        else:
            return Response({
                'error': f'{stock_code} 호가 정보를 조회할 수 없습니다.',
                'message': '모의투자 계정에서는 호가 정보가 제한될 수 있습니다.'
            }, status=503)  # Service Unavailable
    
    except Exception as e:
        logger.error(f"Orderbook data error for {stock_code}: {e}")
        return Response({
            'error': '호가 정보 조회 중 오류가 발생했습니다.',
            'detail': str(e),
            'message': '모의투자 계정에서는 호가 정보가 제한될 수 있습니다.'
        }, status=500)

@api_view(['GET'])
def search_stocks_api(request):
    """종목 검색 API"""
    try:
        keyword = request.GET.get('q', '').strip()
        
        if not keyword:
            return Response({"error": "검색어가 필요합니다."}, status=400)
        
        # DB에서 검색 (실시간 API 실패 시 대안)
        stocks = Stock.objects.filter(
            Q(name__icontains=keyword) | 
            Q(code__icontains=keyword)
        )[:10]
        
        results = []
        for stock in stocks:
            results.append({
                'code': stock.code,
                'name': stock.name,
                'market': stock.market,
                'sector': stock.sector,
                'current_price': 0,  # 실시간 가격은 별도 API로 조회
                'change_percent': 0.0
            })
        
        return Response(results)
        
    except Exception as e:
        return Response({
            "error": str(e),
            "message": "종목 검색 중 오류가 발생했습니다."
        }, status=500)

@api_view(['GET'])
def api_health_check(request):
    """KIS API 상태 체크"""
    try:
        service = StockPriceService()
        
        # 단일 종목으로 API 상태 테스트 (삼성전자)
        test_result = service.get_real_time_price('005930')
        
        if test_result:
            return Response({
                'status': 'healthy',
                'message': 'KIS API 연결 정상',
                'api_working': True,
                'test_stock': '005930',
                'test_price': test_result.get('current_price', 0),
                'timestamp': timezone.now().isoformat()
            })
        else:
            return Response({
                'status': 'degraded',
                'message': 'KIS API 일부 제한',
                'api_working': False,
                'fallback_available': True,
                'timestamp': timezone.now().isoformat()
            }, status=503)
    
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'message': 'KIS API 연결 실패',
            'error': str(e),
            'api_working': False,
            'fallback_available': True,
            'timestamp': timezone.now().isoformat()
        }, status=503)

@api_view(['GET'])
def market_status(request):
    """시장 운영 상태 확인 API"""
    try:
        status_info = get_market_status()
        
        # 추가 정보
        additional_info = {
            'api_mode': 'mock' if os.getenv('KIS_USE_MOCK', 'True').lower() == 'true' else 'real',
            'market_hours': '09:00 ~ 15:30 (KST)',
            'trading_days': '평일 (월~금)',
            'holidays_note': '한국 법정공휴일 및 임시휴장일 제외'
        }
        
        response_data = {
            **status_info,
            **additional_info
        }
        
        # 로그로도 출력
        log_market_status()
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Market status check error: {e}")
        return Response({
            'error': 'Failed to check market status',
            'detail': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST', 'DELETE'])
def watchlist_api_v2(request, stock_code=None):
    """프론트엔드 호환 관심종목 API"""
    from analysis.models import Watchlist
    
    # 기본 관심종목 리스트 가져오기 (첫 번째 리스트 사용)
    watchlist, created = Watchlist.objects.get_or_create(
        name="My Watchlist",
        defaults={'name': "My Watchlist"}
    )
    
    if request.method == 'GET':
        # 관심종목 목록 반환
        stocks_data = []
        for stock in watchlist.stocks.all():
            stocks_data.append({
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'current_price': stock.current_price or 0,
                'change_percent': 0.0,  # TODO: 실시간 데이터 연동
                'market': stock.market,
                'sector': stock.sector
            })
        
        return Response({
            'success': True,
            'data': stocks_data
        })
    
    elif request.method == 'POST':
        # 관심종목 추가
        if not stock_code:
            return Response({
                'success': False,
                'message': '종목코드가 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            stock = Stock.objects.get(stock_code=stock_code)
            watchlist.stocks.add(stock)
            return Response({
                'success': True,
                'message': f'{stock.stock_name}이(가) 관심종목에 추가되었습니다.'
            })
        except Stock.DoesNotExist:
            return Response({
                'success': False,
                'message': f'종목코드 {stock_code}를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)
    
    elif request.method == 'DELETE':
        # 관심종목 삭제
        if not stock_code:
            return Response({
                'success': False,
                'message': '종목코드가 필요합니다.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            stock = Stock.objects.get(stock_code=stock_code)
            watchlist.stocks.remove(stock)
            return Response({
                'success': True,
                'message': f'{stock.stock_name}이(가) 관심종목에서 제거되었습니다.'
            })
        except Stock.DoesNotExist:
            return Response({
                'success': False,
                'message': f'종목코드 {stock_code}를 찾을 수 없습니다.'
            }, status=status.HTTP_404_NOT_FOUND)