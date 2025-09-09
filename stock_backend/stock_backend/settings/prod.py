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

