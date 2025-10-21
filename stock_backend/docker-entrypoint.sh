#!/bin/bash
# Django 컨테이너 엔트리포인트 스크립트

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🐳 Django 컨테이너 시작 중...${NC}"

# 환경 변수 기본값 설정
export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-stock_backend.settings}
export DEBUG=${DEBUG:-True}

# 실행 모드 확인
MODE=${1:-development}
echo -e "${YELLOW}📋 실행 모드: ${MODE}${NC}"

# 데이터베이스 연결 대기 함수
wait_for_db() {
    echo -e "${YELLOW}⏳ 데이터베이스 연결 대기 중...${NC}"
    
    while ! python manage.py dbshell --command="SELECT 1;" >/dev/null 2>&1; do
        echo -e "${YELLOW}💤 데이터베이스 대기 중... (5초 후 재시도)${NC}"
        sleep 5
    done
     
    echo -e "${GREEN}✅ 데이터베이스 연결 성공!${NC}"
}

# 개발 환경 설정
setup_development() {
    echo -e "${BLUE}🔧 개발 환경 설정 중...${NC}"
    
    # 데이터베이스 대기
    wait_for_db
    
    # 마이그레이션 실행
    echo -e "${YELLOW}📊 데이터베이스 마이그레이션 실행 중...${NC}"
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput
    
    # 정적 파일 수집 (개발 환경에서는 선택적)
    if [ "$COLLECT_STATIC" = "True" ]; then
        echo -e "${YELLOW}📁 정적 파일 수집 중...${NC}"
        python manage.py collectstatic --noinput
    fi
    
    # 개발 서버 실행
    echo -e "${GREEN}🚀 Django 개발 서버 시작 (포트 8000)${NC}"
    exec python manage.py runserver 0.0.0.0:8000
}

# 프로덕션 환경 설정
setup_production() {
    echo -e "${BLUE}🏭 프로덕션 환경 설정 중...${NC}"
    
    # 데이터베이스 대기
    wait_for_db
    
    # 마이그레이션 실행
    echo -e "${YELLOW}📊 데이터베이스 마이그레이션 실행 중...${NC}"
    python manage.py migrate --noinput
    
    # 정적 파일 수집 (환경변수로 제어 가능)
    if [ "$SKIP_COLLECTSTATIC" != "True" ]; then
        echo -e "${YELLOW}📁 정적 파일 수집 중...${NC}"
        python manage.py collectstatic --noinput
    else
        echo -e "${YELLOW}⏭️ 정적 파일 수집 건너뛰기 (SKIP_COLLECTSTATIC=True)${NC}"
    fi
    
    # ASGI 서버 실행 (WebSocket 지원)
    echo -e "${GREEN}🚀 ASGI 서버 시작 (Daphne, 포트 8000)${NC}"
    exec daphne -b 0.0.0.0 -p 8000 stock_backend.asgi:application
}

# ASGI 환경 설정 (WebSocket 전용)
setup_asgi() {
    echo -e "${BLUE}🔌 ASGI 서버 설정 중...${NC}"
    
    # 데이터베이스 대기
    wait_for_db
    
    # 마이그레이션 실행 (중요!)
    echo -e "${YELLOW}📊 데이터베이스 마이그레이션 실행 중...${NC}"
    python manage.py makemigrations --noinput
    python manage.py migrate --noinput
    
    # WebSocket 전용 ASGI 서버 실행
    echo -e "${GREEN}🌐 ASGI WebSocket 서버 시작${NC}"
    exec daphne -b 0.0.0.0 -p 8000 stock_backend.asgi:application
}

# 커스텀 명령어 실행
run_command() {
    echo -e "${BLUE}⚙️ 커스텀 명령어 실행: $@${NC}"
    exec "$@"
}

# 헬스체크 함수
health_check() {
    echo -e "${YELLOW}🏥 헬스체크 실행 중...${NC}"
    python manage.py check
    echo -e "${GREEN}✅ Django 애플리케이션 정상${NC}"
}

# 실행 모드에 따른 분기
case "$MODE" in
    "development"|"dev")
        setup_development
        ;;
    "production"|"prod")
        setup_production
        ;;
    "asgi"|"websocket")
        setup_asgi
        ;;
    "health"|"check")
        health_check
        ;;
    *)
        echo -e "${RED}❌ 알 수 없는 모드: $MODE${NC}"
        echo -e "${YELLOW}사용 가능한 모드: development, production, asgi, health${NC}"
        echo -e "${YELLOW}또는 커스텀 명령어를 직접 실행하세요.${NC}"
        run_command "$@"
        ;;
esac 