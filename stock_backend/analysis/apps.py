from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class AnalysisConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'analysis'

    def ready(self):
        """앱 준비 완료시 호출"""
        try:
            # 시장 지수 실시간 업데이트 시작
            from .services import market_index_service
            
            # Django 서버 시작시 자동으로 시장 지수 업데이트 시작
            logger.info("🔄 시장 지수 실시간 업데이트 자동 시작...")
            market_index_service.start_real_time_updates()
            
        except Exception as e:
            logger.error(f"❌ 시장 지수 실시간 업데이트 자동 시작 실패: {e}")
            # 실패해도 앱 시작은 계속 진행
