"""
ASGI config for stock_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
# from channels.security.websocket import AllowedHostsOriginValidator  # 개발용으로 비활성화
import stocks.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')

# Django ASGI application for HTTP
django_asgi_app = get_asgi_application()

# Full ASGI application with WebSocket support (개발용으로 Origin 검증 비활성화)
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(
            stocks.routing.websocket_urlpatterns
        )
    ),
})
