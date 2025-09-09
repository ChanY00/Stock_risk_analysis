"""
Base settings for stock_backend project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# Defaults are conservative here; dev/prod override as needed
DEBUG = False

def _split_csv(env_key: str, default: str = ""):
    return [h.strip() for h in os.getenv(env_key, default).split(',') if h.strip()]

ALLOWED_HOSTS = _split_csv('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'stocks',
    'financials',
    'analysis',
    'sentiment',
    'authentication',
    'portfolios',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'corsheaders.middleware.CorsMiddleware',
]

ROOT_URLCONF = 'stock_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'stock_backend.wsgi.application'
ASGI_APPLICATION = 'stock_backend.asgi.application'

# Channels layer (default in-memory; prod may override to Redis)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'kospi-cache',
        'TIMEOUT': 300,
        'OPTIONS': {'MAX_ENTRIES': 1000}
    },
    'stock_data': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'stock-data-cache',
        'TIMEOUT': 60,
        'OPTIONS': {'MAX_ENTRIES': 500}
    },
    'market_data': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'market-data-cache',
        'TIMEOUT': 30,
        'OPTIONS': {'MAX_ENTRIES': 100}
    }
}

CACHE_KEY_PREFIX = 'kospi_'
STOCK_CACHE_TIMEOUT = 60
MARKET_CACHE_TIMEOUT = 30
ANALYSIS_CACHE_TIMEOUT = 300

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.getenv('STATIC_ROOT', '/app/staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'stocks.consumers': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'kis_api.mock_websocket_client': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
    },
}

# CORS (base is strict; dev loosens)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type', 'dnt', 'origin',
    'user-agent', 'x-csrftoken', 'x-requested-with'
]
CORS_ALLOWED_ORIGINS = _split_csv('CORS_ALLOWED_ORIGINS')

# CSRF
CSRF_TRUSTED_ORIGINS = _split_csv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')

# ===== KIS API 설정 =====
KIS_USE_MOCK = os.getenv('KIS_USE_MOCK', 'False').lower() == 'true'
KIS_IS_PAPER_TRADING = os.getenv('KIS_IS_PAPER_TRADING', 'True').lower() == 'true'
KIS_APP_KEY = os.getenv('KIS_APP_KEY')
KIS_APP_SECRET = os.getenv('KIS_APP_SECRET')

if KIS_IS_PAPER_TRADING:
    # strip()으로 환경변수에 섞여 들어온 보이지 않는 공백/개행/제로폭 문자 제거
    KIS_BASE_URL = os.getenv('KIS_BASE_URL', 'https://openapivts.koreainvestment.com:29443').strip()
    KIS_WEBSOCKET_URL = os.getenv('KIS_WEBSOCKET_URL', 'ws://ops.koreainvestment.com:31000').strip()
else:
    KIS_BASE_URL = os.getenv('KIS_BASE_URL', 'https://openapi.koreainvestment.com:9443').strip()
    KIS_WEBSOCKET_URL = os.getenv('KIS_WEBSOCKET_URL', 'ws://ops.koreainvestment.com:21000').strip()

KIS_WEBSOCKET_TIMEOUT = int(os.getenv('KIS_WEBSOCKET_TIMEOUT', '30'))
KIS_RECONNECT_ATTEMPTS = int(os.getenv('KIS_RECONNECT_ATTEMPTS', '3'))
KIS_PING_INTERVAL = int(os.getenv('KIS_PING_INTERVAL', '30'))

logger = logging.getLogger(__name__)
logger.info("🔧 KIS API 설정 로드 완료:")
logger.info(f"   - USE_MOCK: {KIS_USE_MOCK}")
logger.info(f"   - IS_PAPER_TRADING: {KIS_IS_PAPER_TRADING}")
logger.info(f"   - BASE_URL: {KIS_BASE_URL}")
logger.info(f"   - APP_KEY: {'설정됨' if KIS_APP_KEY else '없음'}")
logger.info(f"   - APP_SECRET: {'설정됨' if KIS_APP_SECRET else '없음'}")

if KIS_USE_MOCK:
    logger.info("🎭 Mock 모드 활성화 - 가상 데이터 제공")
else:
    if not KIS_APP_KEY or not KIS_APP_SECRET:
        logger.warning("⚠️ KIS API 키가 설정되지 않았습니다!")
        logger.warning("환경변수 KIS_APP_KEY와 KIS_APP_SECRET를 설정하거나 Mock 모드를 사용하세요.")
        logger.warning("Mock 모드 사용: export KIS_USE_MOCK=true")
    else:
        logger.info("🚀 실제 KIS API 모드 활성화")

# ===== WebSocket 보강/캐시 설정 =====
# 거래량 보강 기능 토글(기본 비활성화)
WS_ENABLE_VOLUME_ENHANCEMENT = os.getenv('WS_ENABLE_VOLUME_ENHANCEMENT', 'False').lower() == 'true'
WS_VOLUME_REFRESH_INTERVAL_SEC = int(os.getenv('WS_VOLUME_REFRESH_INTERVAL_SEC', '5'))
WS_VOLUME_CACHE_TTL_SEC = int(os.getenv('WS_VOLUME_CACHE_TTL_SEC', '10'))
