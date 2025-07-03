# Flask 감정분석 앱을 위한 Dockerfile
# 🐍 Python 3.11 베이스 이미지 사용 (가벼운 slim 버전)
FROM python:3.11-slim

# 📝 이미지 메타데이터 추가
LABEL maintainer="kospi-project"
LABEL description="KOSPI 주식 감정분석 Flask 서버"

# 📁 작업 디렉토리 설정 (/app 폴더에서 작업)
WORKDIR /app

# 📦 시스템 패키지 업데이트 및 필요 패키지 설치
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 📋 requirements.txt를 먼저 복사 (Docker 레이어 캐싱 최적화)
COPY requirements.txt .

# 🛠️ Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 📁 애플리케이션 코드 복사
COPY . .

# 🌐 Flask 앱이 사용할 포트 노출
EXPOSE 5001

# 🚀 컨테이너 실행 시 Flask 앱 시작
CMD ["python", "app.py"] 