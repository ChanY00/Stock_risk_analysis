# Django KOSPI 백엔드를 위한 Dockerfile
# 🐍 Python 3.11 베이스 이미지 사용
FROM python:3.11-slim as base

# 📝 메타데이터
LABEL maintainer="kospi-project"
LABEL description="KOSPI Django Backend with WebSocket support"

# 🔧 시스템 패키지 설치 및 업데이트
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 📁 작업 디렉토리 설정
WORKDIR /app

# 👤 비루트 사용자 생성 (보안 강화)
RUN groupadd -r django && useradd -r -g django django

# 📋 requirements.txt 먼저 복사 (캐싱 최적화)
COPY requirements.txt .

# 🛠️ Python 의존성 설치
RUN pip install --no-cache-dir -r requirements.txt

# 📁 애플리케이션 코드 복사
COPY . .

# 📁 정적 파일 및 미디어 디렉토리 생성
RUN mkdir -p /app/staticfiles /app/media

# 📜 엔트리포인트 스크립트 실행 권한 (USER 전환 전에 실행)
RUN chmod +x /app/docker-entrypoint.sh

# 🔐 권한 설정
RUN chown -R django:django /app
USER django

# 🌐 포트 노출 (Django: 8000)
EXPOSE 8000

# 🚀 개발 환경 (기본)
FROM base as development
ENV DJANGO_SETTINGS_MODULE=stock_backend.settings
CMD ["./docker-entrypoint.sh", "development"]

# 🏭 프로덕션 환경
FROM base as production
ENV DJANGO_SETTINGS_MODULE=stock_backend.settings
ENV DEBUG=False
CMD ["./docker-entrypoint.sh", "production"] 