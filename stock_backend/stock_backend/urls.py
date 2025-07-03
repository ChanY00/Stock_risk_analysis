"""
URL configuration for stock_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json

# 임시 API 뷰들 (비회원 지원)
@csrf_exempt
@require_http_methods(["GET", "POST", "DELETE"])
def watchlist_api(request, stock_code=None):
    """임시 관심종목 API - 비회원은 빈 응답 반환"""
    if request.method == 'GET':
        return JsonResponse({"success": True, "data": []})
    elif request.method == 'POST':
        return JsonResponse({"success": False, "message": "로그인이 필요합니다."})
    elif request.method == 'DELETE':
        return JsonResponse({"success": False, "message": "로그인이 필요합니다."})

def market_overview_api(request):
    """임시 시장 개요 API"""
    mock_data = {
        "market_summary": {
            "KOSPI": {
                "current": 2650.5,
                "change": 15.2,
                "change_percent": 0.58,
                "volume": 450000000,
                "high": 2660.8,
                "low": 2635.1,
                "trade_value": 8500000000000
            }
        },
        "sector_performance": [
            {
                "sector": "Technology",
                "change_percent": 1.2,
                "top_performer": {
                    "name": "삼성전자",
                    "code": "005930",
                    "change_percent": 2.1
                }
            }
        ]
    }
    return JsonResponse(mock_data)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        # 인증 API
        path('auth/', include('authentication.urls')),
        
        # 임시 누락된 API들
        path('watchlist/', watchlist_api, name='watchlist-list'),
        path('watchlist/<str:stock_code>/', watchlist_api, name='watchlist-detail'),
        path('market-overview/', market_overview_api, name='market-overview'),
        
        # 올바른 API 구조
        path('stocks/', include('stocks.urls')),
        path('sentiment/', include('sentiment.urls')),
        path('financials/', include('financials.urls')),
        path('analysis/', include('analysis.urls')),
        path('portfolios/', include('portfolios.urls')),
    ])),
]
