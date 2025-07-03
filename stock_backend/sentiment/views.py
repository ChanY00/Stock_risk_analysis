from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from django.utils import timezone
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
