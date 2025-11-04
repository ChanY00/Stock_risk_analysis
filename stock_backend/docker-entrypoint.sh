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
    
    # 최대 재시도 횟수 설정 (기본 60회 = 5분)
    MAX_RETRIES=${DB_MAX_RETRIES:-60}
    RETRY_COUNT=0
    
    # 데이터베이스 연결 정보 확인
    DB_HOST=${DB_HOST:-postgres}
    DB_PORT=${DB_PORT:-5432}
    DB_NAME=${DB_NAME:-}
    DB_USER=${DB_USER:-}
    
    echo -e "${BLUE}📊 데이터베이스 연결 정보:${NC}"
    echo -e "  Host: ${DB_HOST}"
    echo -e "  Port: ${DB_PORT}"
    echo -e "  Database: ${DB_NAME:-'(설정되지 않음)'}"
    echo -e "  User: ${DB_USER:-'(설정되지 않음)'}"
    
    # Step 1: PostgreSQL 서버가 준비되었는지 확인 (pg_isready 사용)
    echo -e "${YELLOW}🔍 Step 1: PostgreSQL 서버 준비 상태 확인 중...${NC}"
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if PGPASSWORD="${DB_PASSWORD}" pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ PostgreSQL 서버 준비 완료!${NC}"
            break
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -e "${YELLOW}💤 PostgreSQL 서버 대기 중... (${RETRY_COUNT}/${MAX_RETRIES}, 5초 후 재시도)${NC}"
        sleep 5
    done
    
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo -e "${RED}❌ PostgreSQL 서버 준비 실패: 최대 재시도 횟수(${MAX_RETRIES}) 초과${NC}"
        exit 1
    fi
    
    # Step 2: Django를 통한 데이터베이스 연결 확인
    echo -e "${YELLOW}🔍 Step 2: Django 데이터베이스 연결 확인 중...${NC}"
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # Python 스크립트를 사용하여 Django 데이터베이스 연결 확인
        DB_CHECK_OUTPUT=$(python << 'PYTHON_EOF'
import os
import sys
import django

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')
    django.setup()
    
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        cursor.fetchone()
    print("SUCCESS", file=sys.stdout)
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
        2>&1)
        
        DB_CHECK_EXIT_CODE=$?
        
        if [ $DB_CHECK_EXIT_CODE -eq 0 ] && echo "$DB_CHECK_OUTPUT" | grep -q "SUCCESS"; then
            echo -e "${GREEN}✅ Django 데이터베이스 연결 성공!${NC}"
            return 0
        else
            # 첫 번째 시도가 아니면 에러 메시지를 출력하지 않음 (너무 많은 로그 방지)
            if [ $RETRY_COUNT -eq 0 ]; then
                echo -e "${YELLOW}⚠️  연결 시도 실패: $(echo "$DB_CHECK_OUTPUT" | grep "ERROR:" || echo "알 수 없는 오류")${NC}"
            fi
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo -e "${YELLOW}💤 Django 데이터베이스 연결 대기 중... (${RETRY_COUNT}/${MAX_RETRIES}, 5초 후 재시도)${NC}"
        sleep 5
    done
    
    echo -e "${RED}❌ Django 데이터베이스 연결 실패: 최대 재시도 횟수(${MAX_RETRIES}) 초과${NC}"
    echo -e "${YELLOW}💡 디버깅 팁:${NC}"
    echo -e "  1. PostgreSQL 서비스가 실행 중인지 확인: docker-compose ps postgres"
    echo -e "  2. 환경 변수가 올바르게 설정되었는지 확인"
    echo -e "  3. 네트워크 연결 확인: docker-compose exec backend ping -c 3 postgres"
    exit 1
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