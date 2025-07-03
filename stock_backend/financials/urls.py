from django.urls import path
from .views import FinancialDataAPIView

urlpatterns = [
    path('<str:stock_code>/', FinancialDataAPIView.as_view(), name='stock-financials'),
]
