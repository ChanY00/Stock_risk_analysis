from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.conf import settings
import logging
from .models import SentimentAnalysis
from .serializers import SentimentAnalysisSerializer, SentimentBulkItemSerializer
from stocks.models import Stock
from rest_framework import status

logger = logging.getLogger('sentiment')

class SentimentAnalysisAPIView(APIView):
    def get(self, request, stock_code):
        try:
            stock = Stock.objects.get(stock_code=stock_code)
        except Stock.DoesNotExist:
            raise NotFound("해당 종목이 존재하지 않습니다.")

        try:
            sentiment = SentimentAnalysis.objects.get(stock=stock)
        except SentimentAnalysis.DoesNotExist:
            raise NotFound("해당 종목의 감정 분석 데이터가 없습니다.")

        serializer = SentimentAnalysisSerializer(sentiment)
        data = {
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            **serializer.data
        }
        return Response(data)

class SentimentAnalysisListAPIView(APIView):
    def get(self, request):
        sentiments = SentimentAnalysis.objects.all().select_related('stock')
        results = []
        
        for sentiment in sentiments:
            serializer = SentimentAnalysisSerializer(sentiment)
            data = {
                "stock_code": sentiment.stock.stock_code,
                "stock_name": sentiment.stock.stock_name,
                **serializer.data
            }
            results.append(data)
        
        return Response(results)

class SentimentAnalysisBulkAPIView(APIView):
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    authentication_classes = []
    http_method_names = ['post', 'options']

    def post(self, request, *args, **kwargs):
        # 최소 로그만 남기고, 민감 헤더/본문은 기록하지 않음
        logger.info(f"Bulk sentiment ingest request at {request.path}")

        # 내부 토큰 게이트: SENTIMENT_BULK_TOKEN이 설정됐을 때만 검사
        ingest_token = getattr(settings, 'SENTIMENT_BULK_TOKEN', None) or None
        if ingest_token:
            provided = request.headers.get('X-Internal-Token') or request.headers.get('Authorization', '').replace('Bearer ', '')
            if not provided or provided != ingest_token:
                logger.warning("Unauthorized bulk ingest attempt (token mismatch)")
                return Response({'detail': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            data = request.data if isinstance(request.data, list) else [request.data]
            
            results = []
            errors = []
            success_count = 0
            error_count = 0
            
            for item in data:
                try:
                    # 1) 입력 검증
                    item_serializer = SentimentBulkItemSerializer(data=item)
                    item_serializer.is_valid(raise_exception=True)
                    validated = item_serializer.validated_data
                    stock_code = validated.get('stock_code')
                    
                    # 2) 주식 존재 확인
                    try:
                        stock = Stock.objects.get(stock_code=stock_code)
                    except Stock.DoesNotExist as e:
                        raise NotFound(f"Stock not found: {stock_code}")
                    
                    # 3) 저장/업서트
                    sentiment, created = SentimentAnalysis.objects.update_or_create(
                        stock=stock,
                        defaults={
                            'positive': validated.get('positive'),
                            'negative': validated.get('negative'),
                            'top_keywords': validated.get('top_keywords', ''),
                            'updated_at': validated.get('updated_at')
                        }
                    )
                    
                    results.append({
                        'stock_code': stock_code,
                        'status': 'success',
                        'created': created
                    })
                    success_count += 1
                    
                except Exception as e:
                    error_msg = f"Error processing stock {item.get('stock_code', 'UNKNOWN')}: {str(e)}"
                    logger.warning(error_msg)
                    errors.append({
                        'stock_code': item.get('stock_code', 'UNKNOWN'),
                        'error': error_msg
                    })
                    error_count += 1
            
            response_data = {
                'success': True,
                'message': 'Bulk update completed',
                'summary': {
                    'total': len(data),
                    'success': success_count,
                    'errors': error_count
                },
                'results': results,
                'errors': errors
            }
            
            logger.info(f"Bulk update completed. success={success_count} errors={error_count}")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_msg = f"Error in bulk update: {str(e)}"
            logger.warning(error_msg)
            return Response({
                'success': False,
                'error': error_msg
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SentimentTrendAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, stock_code):
        try:
            stock = Stock.objects.get(stock_code=stock_code)
        except Stock.DoesNotExist:
            raise NotFound("해당 종목이 존재하지 않습니다.")

        # days 파라미터 처리 (기본 14일)
        try:
            days = int(request.GET.get('days', 14))
        except ValueError:
            days = 14

        # 단일 최신 스냅샷만 저장되는 구조이므로, 프론트엔드가 요구하는 형식에 맞게
        # 최근 N일의 추이 데이터를 생성한다. 실제 일자 구분은 updated_at의 날짜를 사용하고,
        # 데이터가 하나뿐이면 동일 값을 N일에 복제하여 반환한다.
        try:
            sentiment = SentimentAnalysis.objects.get(stock=stock)
        except SentimentAnalysis.DoesNotExist:
            raise NotFound("해당 종목의 감정 분석 데이터가 없습니다.")

        base_date = timezone.localdate()
        positive = float(sentiment.positive)
        negative = float(sentiment.negative)
        neutral = max(0.0, 1.0 - (positive + negative))
        # sentiment_score를 -1~1 범위로 변환 (양수 우세일수록 1에 가까움)
        if positive + negative + neutral > 0:
            sentiment_score = (positive - negative)  # 이미 0~1 합을 가정
        else:
            sentiment_score = 0.0

        trend = []
        for i in range(days - 1, -1, -1):
            day = base_date - timezone.timedelta(days=i)
            trend.append({
                'date': day.isoformat(),
                'positive': round(positive, 4),
                'negative': round(negative, 4),
                'neutral': round(neutral, 4),
                'sentiment_score': round(sentiment_score, 4),
                'total_posts': None,
            })

        return Response(trend)
