#!/bin/bash

# KOSPI 프로젝트 DB 초기화 스크립트
# 팀원들이 동일한 DB 상태로 시작할 수 있도록 도와주는 스크립트

set -e  # 에러 발생시 스크립트 중단

echo "🚀 KOSPI 프로젝트 DB 초기화를 시작합니다..."

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 현재 디렉토리가 프로젝트 루트인지 확인
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}❌ docker-compose.yml이 없습니다. 프로젝트 루트 디렉토리에서 실행해주세요.${NC}"
    exit 1
fi

# db_init 디렉토리 확인
if [ ! -d "db_init" ]; then
    echo -e "${RED}❌ db_init 디렉토리가 없습니다.${NC}"
    exit 1
fi

# 덤프 파일 확인
if [ ! -f "db_init/kospi_db_dump.sql" ]; then
    echo -e "${RED}❌ DB 덤프 파일이 없습니다.${NC}"
    exit 1
fi

echo -e "${BLUE}📊 DB 덤프 파일 정보:${NC}"
ls -lh db_init/kospi_db_dump.sql

# PostgreSQL 컨테이너 상태 확인
echo -e "${BLUE}🔍 PostgreSQL 컨테이너 상태 확인 중...${NC}"
if ! docker ps | grep -q "kospi-postgres"; then
    echo -e "${YELLOW}⚠️  PostgreSQL 컨테이너가 실행되지 않았습니다. 시작합니다...${NC}"
    docker-compose up postgres -d
    
    echo -e "${BLUE}⏳ PostgreSQL이 준비될 때까지 대기 중...${NC}"
    sleep 10
    
    # 헬스체크 대기
    for i in {1..30}; do
        if docker exec kospi-postgres pg_isready -U heehyeok -d kospi_db > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PostgreSQL이 준비되었습니다.${NC}"
            break
        fi
        echo -ne "${YELLOW}⏳ PostgreSQL 준비 대기 중... (${i}/30)\r${NC}"
        sleep 2
    done
    
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ PostgreSQL 시작 시간이 초과되었습니다.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ PostgreSQL 컨테이너가 이미 실행 중입니다.${NC}"
fi

# 기존 연결 종료 (선택사항)
echo -e "${BLUE}🔄 기존 DB 연결 정리 중...${NC}"
docker exec kospi-postgres psql -U heehyeok -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'kospi_db' AND pid <> pg_backend_pid();" > /dev/null 2>&1 || true

# DB 덤프 복원
echo -e "${BLUE}📦 DB 덤프 복원 중...${NC}"
if docker exec -i kospi-postgres psql -U heehyeok -d postgres < db_init/kospi_db_dump.sql; then
    echo -e "${GREEN}✅ DB 덤프 복원이 완료되었습니다!${NC}"
else
    echo -e "${RED}❌ DB 덤프 복원에 실패했습니다.${NC}"
    exit 1
fi

# 복원 확인
echo -e "${BLUE}🔍 복원 결과 확인 중...${NC}"
STOCK_COUNT=$(docker exec kospi-postgres psql -U heehyeok -d kospi_db -t -c "SELECT COUNT(*) FROM stocks_stock;" | tr -d ' ')
echo -e "${GREEN}📊 stocks_stock 테이블: ${STOCK_COUNT}개 레코드${NC}"

SENTIMENT_COUNT=$(docker exec kospi-postgres psql -U heehyeok -d kospi_db -t -c "SELECT COUNT(*) FROM sentiment_sentimentanalysis;" | tr -d ' ')
echo -e "${GREEN}💭 sentiment_sentimentanalysis 테이블: ${SENTIMENT_COUNT}개 레코드${NC}"

FINANCIAL_COUNT=$(docker exec kospi-postgres psql -U heehyeok -d kospi_db -t -c "SELECT COUNT(*) FROM financials_financialstatement;" | tr -d ' ')
echo -e "${GREEN}💰 financials_financialstatement 테이블: ${FINANCIAL_COUNT}개 레코드${NC}"

echo ""
echo -e "${GREEN}🎉 KOSPI 프로젝트 DB 초기화가 완료되었습니다!${NC}"
echo ""
echo -e "${BLUE}📋 다음 단계:${NC}"
echo -e "   1. ${YELLOW}docker-compose up backend -d${NC} - 백엔드 서비스 시작"
echo -e "   2. ${YELLOW}docker-compose up frontend -d${NC} - 프론트엔드 서비스 시작"
echo -e "   3. ${YELLOW}docker-compose up -d${NC} - 전체 서비스 시작"
echo ""
echo -e "${BLUE}🌐 접속 정보:${NC}"
echo -e "   - 프론트엔드: ${YELLOW}http://localhost:3000${NC}"
echo -e "   - 백엔드 API: ${YELLOW}http://localhost:8000${NC}"
echo -e "   - DB 접속: ${YELLOW}localhost:5432 (kospi_db)${NC}"
echo "" 