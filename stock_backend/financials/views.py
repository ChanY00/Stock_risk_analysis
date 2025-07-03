from rest_framework.views import APIView
from rest_framework.response import Response
from stocks.models import Stock
from .models import FinancialStatement
from .serializers import FinancialStatementSerializer
from rest_framework.exceptions import NotFound

class FinancialDataAPIView(APIView):
    def get(self, request, stock_code):
        try:
            stock = Stock.objects.get(stock_code=stock_code)
        except Stock.DoesNotExist:
            raise NotFound("종목이 존재하지 않습니다.")

        financials = FinancialStatement.objects.filter(stock=stock)
        serializer = FinancialStatementSerializer(financials, many=True)

        # 연도별로 딕셔너리 정리
        financial_data = {
            str(entry['year']): {
                'revenue': entry['revenue'],
                'operating_income': entry['operating_income'],
                'net_income': entry['net_income'],
                'eps': entry['eps'],
                'total_assets': entry['total_assets'],
                'total_liabilities': entry['total_liabilities'],
                'total_equity': entry['total_equity']
            }
            for entry in serializer.data
        }

        return Response({
            "stock_code": stock.stock_code,
            "stock_name": stock.stock_name,
            "financials": financial_data
        })
