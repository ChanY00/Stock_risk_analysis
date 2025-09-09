import time
import logging
from typing import List, Dict

from django.core.management.base import BaseCommand
from django.conf import settings

from kis_api.websocket_client import KISWebSocketClient


class Command(BaseCommand):
    help = "KIS WebSocket 통합 테스트: 지정한 종목코드 실시간 수신 여부를 짧게 검증합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--codes",
            type=str,
            default="005930,000660",
            help="콤마로 구분된 종목코드 목록 (예: 005930,000660)",
        )
        parser.add_argument(
            "--duration",
            type=int,
            default=20,
            help="테스트 실행 시간(초). 기본 20초",
        )
        parser.add_argument(
            "--mock",
            type=str,
            default=None,
            help="모의 모드 강제(True/False). 미지정 시 settings.KIS_USE_MOCK를 따름",
        )

    def handle(self, *args, **options):
        logger = logging.getLogger("kis_ws_test")
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

        # 인자 파싱
        raw_codes: str = options["codes"] or ""
        duration: int = options["duration"] or 20
        mock_opt = options["mock"]

        stock_codes: List[str] = [c.strip() for c in raw_codes.split(",") if c.strip()]
        if not stock_codes:
            stock_codes = ["005930"]

        if mock_opt is None:
            is_mock = getattr(settings, "KIS_USE_MOCK", True)
        else:
            is_mock = str(mock_opt).lower() in ["1", "true", "yes", "y"]

        logger.info("================= KIS WebSocket 통합 테스트 시작 =================")
        logger.info(f"모드: {'MOCK' if is_mock else 'REAL'} | 기간: {duration}s | 종목: {stock_codes}")

        # 클라이언트 생성 및 연결
        try:
            client = KISWebSocketClient(is_mock=is_mock)
        except Exception as e:
            logger.error(f"클라이언트 생성 실패: {e}")
            return

        connected = client.connect()
        if not connected:
            logger.error("WebSocket 연결 실패. 설정/네트워크/시장시간을 확인하세요.")
            return

        received_counts: Dict[str, int] = {code: 0 for code in stock_codes}

        def make_callback(code: str):
            def _cb(data: Dict):
                try:
                    received_counts[code] += 1
                    if received_counts[code] <= 3:
                        price = data.get("current_price")
                        chg = data.get("change_amount")
                        ts = data.get("timestamp")
                        logger.info(f"[{code}] 수신 #{received_counts[code]} price={price} chg={chg} ts={ts}")
                except Exception as cb_err:
                    logger.warning(f"콜백 처리 오류({code}): {cb_err}")
            return _cb

        # 구독 등록
        success_codes: List[str] = []
        for code in stock_codes:
            try:
                ok = client.subscribe_stock(code, make_callback(code))
                if ok:
                    success_codes.append(code)
                    logger.info(f"구독 성공: {code}")
                else:
                    logger.warning(f"구독 실패: {code}")
            except Exception as sub_err:
                logger.error(f"구독 중 오류({code}): {sub_err}")

        if not success_codes:
            logger.error("어떤 종목도 구독되지 않았습니다. 종료합니다.")
            try:
                client.close()
            finally:
                return

        # 지정된 기간 동안 수신 대기
        start = time.time()
        while time.time() - start < duration:
            time.sleep(1)

        # 정리 및 요약 출력
        try:
            client.close()
        except Exception:
            pass

        total_msgs = sum(received_counts.values())
        logger.info("================= KIS WebSocket 테스트 요약 =================")
        for code in stock_codes:
            logger.info(f"{code}: {received_counts.get(code, 0)}건 수신")
        logger.info(f"총 수신: {total_msgs}건 | 모드: {'MOCK' if is_mock else 'REAL'} | 기간: {duration}s")
        logger.info("=============================================================")





