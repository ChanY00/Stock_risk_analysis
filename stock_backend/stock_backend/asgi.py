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
from channels.security.websocket import AllowedHostsOriginValidator
import stocks.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')

# Django ASGI application for HTTP
django_asgi_app = get_asgi_application()

# Determine if we should enable origin validation
# In development, we can optionally disable it via environment variable
ENABLE_WS_ORIGIN_CHECK = os.getenv('ENABLE_WS_ORIGIN_CHECK', 'True').lower() == 'true'

# Full ASGI application with WebSocket support
if ENABLE_WS_ORIGIN_CHECK:
    # 프로덕션 및 보안 강화 모드: Origin 검증 활성화
    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(
                    stocks.routing.websocket_urlpatterns
                )
            )
        ),
    })
else:
    # 개발 모드: Origin 검증 비활성화 (편의성)
    application = ProtocolTypeRouter({
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                stocks.routing.websocket_urlpatterns
            )
        ),
    })
