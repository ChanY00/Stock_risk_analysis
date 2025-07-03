#!/bin/bash

# KOSPI WebSocket 시스템 - 프로덕션 전환 스크립트
# 사용법: ./scripts/switch_to_production.sh

echo "🚀 KOSPI WebSocket 시스템 프로덕션 전환 시작..."

# 현재 디렉토리 확인
if [ ! -f "manage.py" ]; then
    echo "❌ 오류: stock_backend 디렉토리에서 실행해주세요."
    exit 1
fi

# 환경변수 확인
echo "📋 환경변수 확인 중..."

if [ -z "$KIS_APP_KEY" ] || [ -z "$KIS_APP_SECRET" ]; then
    echo "❌ 오류: KIS API 키가 설정되지 않았습니다."
    echo "다음 환경변수를 설정해주세요:"
    echo "export KIS_APP_KEY=your_app_key"
    echo "export KIS_APP_SECRET=your_app_secret"
    exit 1
fi

# Mock 모드 비활성화
echo "🔧 Mock 모드 비활성화 중..."
export KIS_USE_MOCK=False

# consumers.py 백업 및 수정
echo "📝 consumers.py 수정 중..."
cp stocks/consumers.py stocks/consumers.py.backup

# is_mock=True를 is_mock=None으로 변경
sed -i.bak 's/KISWebSocketClient(is_mock=True)/KISWebSocketClient(is_mock=None)/g' stocks/consumers.py

echo "✅ consumers.py 수정 완료 (백업: consumers.py.backup)"

# 시장 상태 확인
echo "📊 현재 시장 상태 확인 중..."
python -c "
from kis_api.market_hours import get_market_status
status = get_market_status()
print(f'시장 상태: {status[\"status\"]}')
print(f'현재 시간: {status[\"current_time_str\"]}')
if not status['is_open']:
    print('⚠️  주의: 현재 시장이 닫혀있습니다.')
    print('실제 API는 시장 운영시간에만 데이터를 제공합니다.')
"

echo ""
echo "🎯 프로덕션 전환 완료!"
echo ""
echo "📋 확인사항:"
echo "  ✅ KIS_USE_MOCK=False"
echo "  ✅ consumers.py 수정됨"
echo "  ✅ 환경변수 설정됨"
echo ""
echo "🚀 서버 재시작:"
echo "  pkill -f daphne"
echo "  daphne -b 0.0.0.0 -p 8000 stock_backend.asgi:application"
echo ""
echo "📊 시장 상태 모니터링:"
echo "  curl http://localhost:8000/api/stocks/market-status/ | jq"
echo ""
echo "🔄 Mock 모드로 되돌리기:"
echo "  ./scripts/switch_to_mock.sh" 