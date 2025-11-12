"""
Base settings for stock_backend project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load environment variables
# 1. Django 프로젝트의 .env 파일 (stock_backend/.env)
load_dotenv()
# 2. 프로젝트 루트의 .env 파일 (프로젝트 루트/.env)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent.parent / '.env', override=False)
# 3. Stock_risk_analysis/.env 파일 (Gemini API 키 등)
load_dotenv(BASE_DIR.parent.parent / 'Stock_risk_analysis' / '.env', override=False)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# Gemini API Key
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

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
    'corsheaders.middleware.CorsMiddleware',  # Must be before CommonMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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

# ===== Auth security controls =====
# 로그인 실패 시도 제한 및 잠금(환경변수로 조절 가능)
AUTH_MAX_LOGIN_ATTEMPTS = int(os.getenv('AUTH_MAX_LOGIN_ATTEMPTS', '5'))
AUTH_LOCKOUT_SECONDS = int(os.getenv('AUTH_LOCKOUT_SECONDS', '300'))  # 5분
AUTH_ATTEMPT_WINDOW_SECONDS = int(os.getenv('AUTH_ATTEMPT_WINDOW_SECONDS', '600'))  # 10분

# ===== Cookie / Session security (env-driven) =====
# NOTE: For cross-site cookies, set SameSite=None AND Secure=True in production (HTTPS)
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
CSRF_COOKIE_SECURE = os.getenv('CSRF_COOKIE_SECURE', 'false').lower() == 'true'

SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')  # 'Lax' | 'Strict' | 'None'
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')

# Cookie age/domain (optional overrides)
SESSION_COOKIE_AGE = int(os.getenv('SESSION_COOKIE_AGE', '1209600'))  # 2 weeks default
SESSION_COOKIE_DOMAIN = os.getenv('SESSION_COOKIE_DOMAIN') or None
CSRF_COOKIE_DOMAIN = os.getenv('CSRF_COOKIE_DOMAIN') or None

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Seoul'  # 한국 시간대 사용
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = os.getenv('STATIC_ROOT', '/app/staticfiles')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===== Celery Configuration =====
# Redis를 Celery 브로커로 사용 (기본값은 dev/prod에서 오버라이드)
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

CELERY_BROKER_URL = os.getenv(
    'CELERY_BROKER_URL',
    f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
)
CELERY_RESULT_BACKEND = os.getenv(
    'CELERY_RESULT_BACKEND',
    f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB + 1}'  # 결과는 별도 DB 사용
)

# Celery 설정
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Seoul'  # 한국 시간대
CELERY_ENABLE_UTC = True

# Celery Beat 스케줄 설정
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'update-daily-stock-prices': {
        'task': 'stocks.update_daily_prices',
        # cron 표현식: 분 시 일 월 요일
        # KST 15:30 = UTC 06:30 (KST는 UTC+9)
        # crontab 객체를 사용하여 스케줄 정의 (UTC 기준)
        # CELERY_TIMEZONE 설정이 있지만, crontab은 UTC 기준으로 동작
        'schedule': crontab(minute='30', hour='6', day_of_week='1-5'),  # 월~금요일 UTC 06:30 (= KST 15:30)
    },
}

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
        'detailed': {
            'format': '[{asctime}] {levelname} {name}:{lineno} {funcName}() - {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'detailed'},
    },
    'root': {'handlers': ['console'], 'level': 'DEBUG'},  # INFO → DEBUG로 변경
    'loggers': {
        'stocks.consumers': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'kis_api.mock_websocket_client': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},
        'kis_api.real_websocket_client': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},  # 추가!
        'kis_api.websocket_client': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},  # 추가!
        'kis_api.market_index_client': {'handlers': ['console'], 'level': 'DEBUG', 'propagate': False},  # 추가!
        'django.channels': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},  # Channels 로그
        'daphne': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},  # Daphne 로그
    },
}

# CORS (base is strict; dev loosens)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ['DELETE', 'GET', 'OPTIONS', 'PATCH', 'POST', 'PUT']
CORS_ALLOW_HEADERS = [
    'accept', 'accept-encoding', 'authorization', 'content-type', 'dnt', 'origin',
    'user-agent', 'x-csrftoken', 'x-requested-with', 'x-internal-token'  # Sentiment 서비스용 인증 토큰
]
CORS_ALLOWED_ORIGINS = _split_csv('CORS_ALLOWED_ORIGINS')

# CSRF
CSRF_TRUSTED_ORIGINS = _split_csv('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')

# Email settings (override via env in dev/prod)
# Defaults to console backend for local development
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'true').lower() == 'true'
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'false').lower() == 'true'

if os.getenv('EMAIL_BACKEND'):
    EMAIL_BACKEND = os.getenv('EMAIL_BACKEND')
else:
    EMAIL_BACKEND = (
        'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST else 'django.core.mail.backends.console.EmailBackend'
    )

DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'no-reply@example.com')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', DEFAULT_FROM_EMAIL)
PASSWORD_RESET_FRONTEND_URL = os.getenv('PASSWORD_RESET_FRONTEND_URL', 'http://localhost:3000/password-reset/confirm')
EMAIL_VERIFICATION_FRONTEND_URL = os.getenv('EMAIL_VERIFICATION_FRONTEND_URL', 'http://localhost:3000/verify-email')
REQUIRE_EMAIL_VERIFICATION = os.getenv('REQUIRE_EMAIL_VERIFICATION', 'False').lower() == 'true'
EMAIL_VERIFICATION_TOKEN_TTL_MINUTES = int(os.getenv('EMAIL_VERIFICATION_TOKEN_TTL_MINUTES', '60'))

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

# ===== Internal ingestion token (optional gate) =====
SENTIMENT_BULK_TOKEN = os.getenv('SENTIMENT_BULK_TOKEN')
