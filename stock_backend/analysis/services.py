import logging
from django.utils import timezone
from .models import MarketIndex
from kis_api.market_index_client import market_index_client
from channels.layers import get_channel_layer
import asyncio

logger = logging.getLogger(__name__)

class MarketIndexService:
    """시장 지수 실시간 업데이트 서비스"""
    
    def __init__(self):
        self.is_running = False
        
    def start_real_time_updates(self):
        """실시간 시장 지수 업데이트 시작"""
        if self.is_running:
            logger.warning("⚠️ 시장 지수 실시간 업데이트가 이미 실행 중입니다")
            return
            
        logger.info("🚀 시장 지수 실시간 업데이트 서비스 시작")
        
        # KIS 클라이언트에 콜백 등록
        success = market_index_client.start_real_time_updates(self._update_market_indices)
        
        if success:
            self.is_running = True
            logger.info("✅ 시장 지수 실시간 업데이트 시작 완료")
        else:
            logger.error("❌ 시장 지수 실시간 업데이트 시작 실패")
    
    def _update_market_indices(self, indices_data: dict):
        """시장 지수 데이터 업데이트 콜백"""
        try:
            logger.info(f"📊 시장 지수 업데이트 수신: {list(indices_data.keys())}")
            
            for index_name, data in indices_data.items():
                # 데이터베이스에서 MarketIndex 객체 가져오기 또는 생성
                market_index, created = MarketIndex.objects.get_or_create(
                    name=index_name.upper(),
                    defaults={
                        'current_value': 0,
                        'change': 0,
                        'change_percent': 0,
                        'volume': 0
                    }
                )
                
                # 데이터 업데이트
                market_index.current_value = data.get('current', 0)
                market_index.change = data.get('change', 0)
                market_index.change_percent = data.get('change_percent', 0)
                market_index.volume = data.get('volume', 0)
                market_index.trade_value = data.get('trade_value', 0)
                market_index.high = data.get('high', 0)
                market_index.low = data.get('low', 0)
                market_index.updated_at = timezone.now()
                
                market_index.save()
                
                action = "생성" if created else "업데이트"
                logger.info(f"✅ {market_index.name} 지수 {action}: {market_index.current_value:,.2f} ({market_index.change:+.2f}, {market_index.change_percent:+.2f}%)")
            
            # WS 브로드캐스트는 비활성화 (REST 폴링만 유지)
                
        except Exception as e:
            logger.error(f"❌ 시장 지수 업데이트 오류: {e}")

    async def _async_broadcast_indices(self, group_name: str, market_summary: dict):
        return
    
    def stop(self):
        """실시간 업데이트 중지"""
        if self.is_running:
            market_index_client.stop()
            self.is_running = False
            logger.info("🛑 시장 지수 실시간 업데이트 중지")

# 전역 인스턴스
market_index_service = MarketIndexService() 