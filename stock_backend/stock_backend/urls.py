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
from analysis.views import market_overview_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include([
        # 인증 API
        path('auth/', include('authentication.urls')),
        # 시장 개요 (분산 캐시 포함 실제 서비스)
        path('market-overview/', market_overview_view, name='market-overview'),
        
        # 올바른 API 구조
        path('stocks/', include('stocks.urls')),
        path('sentiment/', include('sentiment.urls')),
        path('financials/', include('financials.urls')),
        path('analysis/', include('analysis.urls')),
        path('portfolios/', include('portfolios.urls')),
    ])),
]
