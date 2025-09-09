from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.utils import timezone
from django.db.models.functions import TruncDate
from django.db.models import Avg, Count, F
import logging
from .models import SentimentAnalysis
from .serializers import SentimentAnalysisSerializer
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
        logger.info(f"Received request at {request.path}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Request headers: {request.headers}")
        
        try:
            data = request.data if isinstance(request.data, list) else [request.data]
            logger.info(f"Received data: {data}")
            
            results = []
            errors = []
            success_count = 0
            error_count = 0
            
            for item in data:
                try:
                    stock_code = item.get('stock_code')
                    logger.info(f"Processing stock: {stock_code}")
                    
                    try:
                        stock = Stock.objects.get(stock_code=stock_code)
                        logger.info(f"Found stock: {stock.stock_name}")
                    except Stock.DoesNotExist as e:
                        logger.error(f"Stock not found: {stock_code}")
                        raise e
                    
                    try:
                        # 날짜 문자열 파싱
                        date_str = item['updated_at']
                        if date_str.endswith('Z'):
                            date_str = date_str[:-1]  # Z 제거
                        updated_at = timezone.datetime.fromisoformat(date_str)
                        logger.info(f"Parsed updated_at: {updated_at}")
                    except Exception as e:
                        logger.error(f"Error parsing updated_at: {str(e)}")
                        raise e
                    
                    try:
                        logger.info(f"Attempting to save sentiment data for {stock_code}")
                        sentiment, created = SentimentAnalysis.objects.update_or_create(
                            stock=stock,
                            defaults={
                                'positive': item.get('positive', 0.0),
                                'negative': item.get('negative', 0.0),
                                'top_keywords': item.get('top_keywords', ''),
                                'updated_at': updated_at
                            }
                        )
                        logger.info(f"Successfully saved sentiment data for {stock_code}. Created: {created}")
                    except Exception as e:
                        logger.error(f"Database error while saving sentiment data: {str(e)}")
                        raise e
                    
                    results.append({
                        'stock_code': stock_code,
                        'status': 'success',
                        'created': created
                    })
                    success_count += 1
                    logger.info(f"Successfully processed stock: {stock_code}")
                    
                except Stock.DoesNotExist:
                    error_msg = f"Stock not found: {stock_code}"
                    logger.warning(error_msg)
                    errors.append({
                        'stock_code': stock_code,
                        'error': error_msg
                    })
                    error_count += 1
                except Exception as e:
                    error_msg = f"Error processing stock {stock_code}: {str(e)}"
                    logger.error(error_msg)
                    errors.append({
                        'stock_code': stock_code,
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
            
            logger.info(f"Bulk update completed. Success: {success_count}, Errors: {error_count}")
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            error_msg = f"Error in bulk update: {str(e)}"
            logger.error(error_msg)
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
