from .base import *
import os

# Production overrides
DEBUG = False

# Hosts and security
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()]

# CORS tightened; define explicit origins via env
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [h.strip() for h in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if h.strip()]

# Channels via Redis
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(REDIS_HOST, REDIS_PORT)],
            'capacity': 1500,
            'expiry': 60,
        },
    },
}

# Logging: be quiet in production (only warnings/errors by default)
try:
    LOGGING['root']['level'] = 'WARNING'
    # Reduce chatter from websocket/kis modules unless explicitly overridden by env
    LOGGING['loggers'].update({
        'stocks.consumers': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'kis_api.real_websocket_client': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'kis_api.market_index_client': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    })
except Exception:
    pass

