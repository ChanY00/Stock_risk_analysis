#!/bin/bash

# KOSPI WebSocket 시스템 - Mock 모드 전환 스크립트
# 사용법: ./scripts/switch_to_mock.sh

echo "🔧 KOSPI WebSocket 시스템 Mock 모드 전환 시작..."

# 현재 디렉토리 확인
if [ ! -f "manage.py" ]; then
    echo "❌ 오류: stock_backend 디렉토리에서 실행해주세요."
    exit 1
fi

# Mock 모드 활성화
echo "🎭 Mock 모드 활성화 중..."
export KIS_USE_MOCK=True

# consumers.py 복원 또는 수정
echo "📝 consumers.py 수정 중..."

if [ -f "stocks/consumers.py.backup" ]; then
    echo "📋 백업 파일에서 복원 중..."
    cp stocks/consumers.py.backup stocks/consumers.py
    echo "✅ consumers.py 복원 완료"
else
    echo "📝 직접 수정 중..."
    # is_mock=None을 is_mock=True로 변경
    sed -i.bak 's/KISWebSocketClient(is_mock=None)/KISWebSocketClient(is_mock=True)/g' stocks/consumers.py
    echo "✅ consumers.py 수정 완료"
fi

echo ""
echo "🎭 Mock 모드 전환 완료!"
echo ""
echo "📋 확인사항:"
echo "  ✅ KIS_USE_MOCK=True"
echo "  ✅ consumers.py Mock 모드로 설정됨"
echo "  ✅ 개발 환경 최적화됨"
echo ""
echo "🚀 서버 재시작:"
echo "  pkill -f daphne"
echo "  daphne -b 0.0.0.0 -p 8000 stock_backend.asgi:application"
echo ""
echo "📊 Mock 데이터 확인:"
echo "  curl http://localhost:8000/api/stocks/market-status/ | jq"
echo "  WebSocket: ws://localhost:8000/ws/stocks/realtime/"
echo ""
echo "💡 Mock 모드의 장점:"
echo "  - 24/7 데이터 생성 (휴장일에도 동작)"
echo "  - API 호출 제한 없음"
echo "  - 개발/테스트에 최적화"
echo "  - 네트워크 연결 불필요" 