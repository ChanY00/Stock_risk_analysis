"""
Celery tasks for stock price updates
"""
import logging
from celery import shared_task
from django.core.management import call_command
from kis_api.market_utils import KoreanMarketUtils
from datetime import datetime

logger = logging.getLogger(__name__)


@shared_task(name='stocks.update_daily_prices')
def update_daily_prices_task():
    """
    매일 장 마감 후(15:30) 주가 데이터를 업데이트하는 Celery 태스크
    
    거래일인 경우에만 실행되며, update_stock_prices_gap 명령어를 호출합니다.
    """
    kst_now = KoreanMarketUtils.get_current_kst_time()
    
    # 거래일 확인
    if not KoreanMarketUtils.is_market_day(kst_now):
        logger.info(f"⏭️  {kst_now.strftime('%Y-%m-%d')}는 거래일이 아닙니다. 주가 업데이트를 건너뜁니다.")
        return {
            'status': 'skipped',
            'reason': 'not_trading_day',
            'date': kst_now.strftime('%Y-%m-%d'),
            'weekday': kst_now.strftime('%A')
        }
    
    # 장 마감 시간 확인 (15:30 이후인지 확인)
    current_time = kst_now.time()
    market_close = KoreanMarketUtils.MARKET_CLOSE_TIME
    
    if current_time < market_close:
        logger.info(f"⏭️  아직 장 마감 전입니다. 현재 시간: {current_time.strftime('%H:%M')}, 마감 시간: {market_close.strftime('%H:%M')}")
        return {
            'status': 'skipped',
            'reason': 'before_market_close',
            'current_time': current_time.strftime('%H:%M'),
            'market_close': market_close.strftime('%H:%M')
        }
    
    # 주가 업데이트 실행
    try:
        logger.info(f"📊 주가 데이터 업데이트 시작: {kst_now.strftime('%Y-%m-%d %H:%M:%S KST')}")
        
        # update_stock_prices_gap 명령어 실행
        call_command('update_stock_prices_gap', '--batch-size', '10', verbosity=1)
        
        logger.info(f"✅ 주가 데이터 업데이트 완료: {kst_now.strftime('%Y-%m-%d %H:%M:%S KST')}")
        
        return {
            'status': 'success',
            'date': kst_now.strftime('%Y-%m-%d'),
            'time': kst_now.strftime('%H:%M:%S'),
            'timezone': 'KST'
        }
        
    except Exception as e:
        logger.error(f"❌ 주가 데이터 업데이트 실패: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e),
            'date': kst_now.strftime('%Y-%m-%d'),
            'time': kst_now.strftime('%H:%M:%S')
        }

