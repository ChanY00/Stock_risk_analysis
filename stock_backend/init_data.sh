#!/bin/bash

# =============================================
# 🗄️ Django 초기 데이터 로딩 스크립트
# =============================================
#
# 사용법: 
# - Docker 내부: docker-compose exec backend ./init_data.sh
# - 로컬: ./init_data.sh
#
# 이 스크립트는 팀원들이 동일한 기본 데이터를 가질 수 있도록
# KOSPI 200 주식 목록과 기본 정보를 자동으로 로딩합니다.

set -e  # 에러 발생 시 스크립트 종료

# 색상 설정
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 헤더
echo -e "${BLUE}"
echo "================================================="
echo "🗄️ KOSPI 200 대시보드 - 초기 데이터 로딩"
echo "================================================="
echo -e "${NC}"

# 1. 데이터베이스 마이그레이션 확인
log_info "데이터베이스 마이그레이션 적용 중..."
python manage.py migrate
log_success "마이그레이션 완료"

# 2. 기존 데이터 확인
STOCK_COUNT=$(python manage.py shell -c "from stocks.models import Stock; print(Stock.objects.count())")
if [ "$STOCK_COUNT" -gt 0 ]; then
    log_warning "이미 $STOCK_COUNT 개의 주식 데이터가 존재합니다."
    echo "기존 데이터를 삭제하고 새로 로딩하시겠습니까? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        log_info "기존 데이터 삭제 중..."
        python manage.py shell -c "
from stocks.models import Stock
from financials.models import FinancialStatement
from analysis.models import TechnicalIndicator

# 관련 데이터 삭제 (외래키 제약 때문에 순서 중요)
TechnicalIndicator.objects.all().delete()
FinancialStatement.objects.all().delete()
Stock.objects.all().delete()
print('기존 데이터 삭제 완료')
"
        log_success "기존 데이터 삭제 완료"
    else
        log_info "기존 데이터를 유지합니다."
        exit 0
    fi
fi

# 3. KOSPI 200 주식 목록 가져오기
log_info "KOSPI 200 주식 목록 다운로드 중..."
python manage.py fetch_kospi200_stocks
log_success "KOSPI 200 주식 목록 로딩 완료"

# 4. 기본 주식 정보 채우기
log_info "주식 기본 정보 및 섹터 데이터 생성 중..."
python manage.py populate_stock_data
log_success "주식 기본 정보 생성 완료"

# 5. 주가 데이터 가져오기 (샘플)
log_info "주요 종목 주가 데이터 가져오기 중..."
python manage.py fetch_stock_prices
log_success "주가 데이터 로딩 완료"

# 6. KOSPI 200 섹터 정보 업데이트
log_info "KOSPI 200 섹터 정보 업데이트 중..."
python manage.py update_kospi_200_sectors
log_success "섹터 정보 업데이트 완료"

# 7. 클러스터 분석 데이터 로딩 (있는 경우)
if [ -f "../project_archive/data_files/spectral_clustered_company.csv" ]; then
    log_info "클러스터 분석 데이터 로딩 중..."
    python manage.py import_clusters
    log_success "클러스터 분석 데이터 로딩 완료"
else
    log_warning "클러스터 분석 데이터 파일을 찾을 수 없습니다. 스킵합니다."
fi

# 8. 관리자 계정 생성 (선택사항)
log_info "Django 관리자 계정을 생성하시겠습니까? (y/N)"
read -r admin_response
if [[ "$admin_response" =~ ^[Yy]$ ]]; then
    log_info "관리자 계정 생성 중..."
    python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('관리자 계정 생성: admin / admin123')
else:
    print('관리자 계정이 이미 존재합니다.')
"
    log_success "관리자 계정 설정 완료"
fi

# 9. 최종 결과 확인
FINAL_STOCK_COUNT=$(python manage.py shell -c "from stocks.models import Stock; print(Stock.objects.count())")
FINANCIAL_COUNT=$(python manage.py shell -c "from financials.models import FinancialStatement; print(FinancialStatement.objects.count())")

echo -e "${GREEN}"
echo "================================================="
echo "🎉 초기 데이터 로딩 완료!"
echo "================================================="
echo -e "${NC}"

echo "📊 로딩된 데이터:"
echo "   - 주식 종목: $FINAL_STOCK_COUNT 개"
echo "   - 재무 데이터: $FINANCIAL_COUNT 개"
echo ""
echo "🌐 접속 정보:"
echo "   - 프론트엔드: http://localhost:3000"
echo "   - Django Admin: http://localhost:8000/admin"
echo "   - API: http://localhost:8000/api/stocks/"
echo ""
if [[ "$admin_response" =~ ^[Yy]$ ]]; then
    echo "🔑 관리자 계정: admin / admin123"
    echo ""
fi
echo -e "${BLUE}💡 이제 팀원들과 동일한 데이터를 사용할 수 있습니다!${NC}" 