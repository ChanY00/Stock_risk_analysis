from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/stocks/realtime/$', consumers.StockPriceConsumer.as_asgi()),
] 