from .base import *
import os

# Development overrides
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Permissive CORS for local dev
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = []

# Channel layer: default InMemory, optional Redis when USE_REDIS_CHANNELS=true
if os.getenv('USE_REDIS_CHANNELS', 'false').lower() == 'true' or \
   os.getenv('CHANNELS_BACKEND', '').lower() == 'redis':
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
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        }
    }
