import os
import json
import logging
import requests
from datetime import datetime, UTC
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from sentiment_analysis.crawler import get_today_posts
from sentiment_analysis.gemini_sentiment import batch_sentiment_analysis
from sentiment_analysis.keywords import extract_top_keywords
from dotenv import load_dotenv
import time

# ===================== 환경 설정 =====================
load_dotenv()  # .env 파일 로드

# Docker 환경에서는 'backend' 서비스명 사용, 로컬에서는 'localhost' 사용
# 주의: DJANGO_ENDPOINT가 .env에 설정되어 있으면 그 값을 사용하지만,
# DJANGO_HOST와 DJANGO_PORT를 우선적으로 사용하여 동적으로 생성
DJANGO_HOST = os.getenv('DJANGO_HOST', 'backend')  # Docker 네트워크에서는 'backend', 로컬에서는 'localhost'
DJANGO_PORT = os.getenv('DJANGO_PORT', '8000')

# DJANGO_ENDPOINT 처리 로직
# Docker Compose에서 DJANGO_HOST=backend로 설정되어 있으면 Docker 환경
# .env 파일의 DJANGO_ENDPOINT가 localhost를 포함하면 Docker 환경에서는 backend로 교체
env_django_endpoint = os.getenv('DJANGO_ENDPOINT', None)
actual_django_host = os.getenv('DJANGO_HOST', 'backend')  # Docker Compose에서 설정된 값

if env_django_endpoint:
    # .env에 DJANGO_ENDPOINT가 설정된 경우
    # Docker 환경에서는 localhost를 backend로 교체
    if 'localhost' in env_django_endpoint and actual_django_host == 'backend':
        # Docker 환경에서 localhost를 backend로 교체
        DJANGO_ENDPOINT = env_django_endpoint.replace('localhost', 'backend')
    else:
        DJANGO_ENDPOINT = env_django_endpoint
else:
    # DJANGO_ENDPOINT가 설정되지 않은 경우 DJANGO_HOST와 DJANGO_PORT로 동적으로 생성
    DJANGO_ENDPOINT = f'http://{DJANGO_HOST}:{DJANGO_PORT}/api/sentiment/bulk/'
DJANGO_API_KEY = os.getenv('DJANGO_API_KEY', '')
KOSPI_CSV = os.getenv('KOSPI_CSV_PATH', 'kospi200.csv')
MAX_STOCKS = int(os.getenv('MAX_STOCKS', '0') or 0)  # 0이면 전체
RESULT_DIR = os.getenv('RESULT_DIR', 'result_json')
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '5'))  # 초 단위

# ===================== Flask 앱 초기화 =====================
app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 환경 변수 로깅 (Flask 초기화 후)
logger.info(f"Django 연결 설정: HOST={DJANGO_HOST}, PORT={DJANGO_PORT}, ENDPOINT={DJANGO_ENDPOINT}")
if 'localhost' in str(DJANGO_ENDPOINT):
    logger.warning(f"⚠️ DJANGO_ENDPOINT에 localhost가 포함되어 있습니다. Docker 환경에서는 'backend'를 사용해야 합니다.")

# ===================== Django 서버 헬스 체크 =====================
def check_django_health():
    """Django 서버가 실행 중인지 확인"""
    health_url = f'http://{DJANGO_HOST}:{DJANGO_PORT}/api/stocks/health/'
    try:
        resp = requests.get(health_url, timeout=5)
        resp.raise_for_status()
        logger.info(f"Django 서버 헬스 체크 성공: {health_url}")
        return True
    except requests.exceptions.RequestException as e:
        logger.warning(f"Django 서버 헬스 체크 실패: {health_url} - {e}")
        return False

# ===================== Django 서버 연동 함수 =====================
def send_to_django(data, retry_count=0):
    """Django 서버로 데이터를 전송하고 실패 시 재시도"""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    if DJANGO_API_KEY:
        headers['X-Internal-Token'] = DJANGO_API_KEY

    try:
        logger.info(f"Sending data to Django endpoint: {DJANGO_ENDPOINT} (attempt {retry_count + 1}/{MAX_RETRIES + 1})")
        logger.info(f"Sending {len(data)} items to Django")
        # 전송 데이터 샘플 로깅 (첫 번째 아이템만)
        if data:
            logger.debug(f"Data sample (first item): {json.dumps(data[0] if isinstance(data, list) else data, ensure_ascii=False)}")
        resp = requests.post(
            DJANGO_ENDPOINT,
            headers=headers,
            json=data,  # requests가 자동으로 JSON 직렬화
            timeout=30  # 30초 타임아웃
        )
        resp.raise_for_status()
        logger.info(f"Successfully sent data to Django: {resp.status_code}")
        logger.debug(f"Django response: {resp.text}")
        return True
    except requests.exceptions.ConnectionError as e:
        # 연결 실패는 재시도 가능 (Django 서버가 일시적으로 다운되었을 수 있음)
        if retry_count < MAX_RETRIES:
            logger.warning(f"Django 서버 연결 실패 (attempt {retry_count + 1}/{MAX_RETRIES}): {DJANGO_ENDPOINT} - {e}")
            logger.warning(f"Docker 네트워크 확인 필요: 서비스명 '{DJANGO_HOST}'가 실행 중인지 확인")
            time.sleep(RETRY_DELAY)
            return send_to_django(data, retry_count + 1)
        else:
            logger.error(f"Django 서버 연결 실패 (최종 시도): {DJANGO_ENDPOINT}")
            logger.error(f"Docker 네트워크 확인 필요: 서비스명 '{DJANGO_HOST}'가 실행 중인지 확인")
            logger.error(f"연결 오류 상세: {e}")
            return False
    except requests.exceptions.Timeout as e:
        # 타임아웃도 재시도 가능
        if retry_count < MAX_RETRIES:
            logger.warning(f"Django 서버 타임아웃 (attempt {retry_count + 1}/{MAX_RETRIES}): {e}")
            time.sleep(RETRY_DELAY)
            return send_to_django(data, retry_count + 1)
        else:
            logger.error(f"Django 서버 타임아웃 (최종 시도): {e}")
            return False
    except requests.exceptions.HTTPError as e:
        # HTTP 오류 (4xx, 5xx) - 상세 에러 메시지 로깅
        if hasattr(e, 'response') and e.response is not None:
            error_text = e.response.text
            error_status = e.response.status_code
            logger.error(f"HTTP {error_status} Error: {e}")
            logger.error(f"Response headers: {dict(e.response.headers)}")
            logger.error(f"Response body: {error_text[:500]}")  # 처음 500자만
            
            # 400 에러인 경우 데이터 형식 문제일 가능성
            if error_status == 400:
                logger.error("⚠️ 400 Bad Request - 데이터 형식이 Django Serializer 요구사항과 일치하지 않습니다.")
                logger.error("확인 사항:")
                logger.error("  - stock_name 필드가 포함되어 있는지 (제거해야 함)")
                logger.error("  - positive/negative가 소수점 4자리인지 (DecimalField(max_digits=5, decimal_places=4))")
                logger.error("  - updated_at이 올바른 ISO 형식인지")
                if data:
                    logger.error(f"전송 데이터 샘플: {json.dumps(data[0] if isinstance(data, list) else data, ensure_ascii=False, indent=2)}")
        
        if retry_count < MAX_RETRIES:
            logger.warning(f"HTTP 에러 발생 (attempt {retry_count + 1}/{MAX_RETRIES}), 재시도...")
            time.sleep(RETRY_DELAY)
            return send_to_django(data, retry_count + 1)
        else:
            return False
    except requests.exceptions.RequestException as e:
        # 기타 네트워크 오류
        if retry_count < MAX_RETRIES:
            logger.warning(f"Failed to send data (attempt {retry_count + 1}/{MAX_RETRIES}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.warning(f"Error response: {e.response.status_code} - {e.response.text[:200]}")
            time.sleep(RETRY_DELAY)
            return send_to_django(data, retry_count + 1)
        else:
            logger.error(f"Failed to send data after {MAX_RETRIES} attempts: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Error response: {e.response.status_code} - {e.response.text[:200]}")
            return False

# ===================== 메인 작업 함수 =====================
def run_analysis():
    from pandas import read_csv
    try:
        kospi_df = read_csv(KOSPI_CSV, dtype={"종목코드": str})
        if MAX_STOCKS:
            kospi_df = kospi_df.head(MAX_STOCKS)

        results = []
        today_str = datetime.today().strftime('%Y%m%d')

        for _, row in kospi_df.iterrows():
            code, name = row['종목코드'], row['종목명']
            logger.info(f"Processing {code} - {name}")
            logger.info(f"크롤링 시작: {code} - {name}")

            df_posts = get_today_posts(code)
            if df_posts.empty:
                logger.warning(f"No posts for {code} - {name}. Skipping. (크롤링 실패 또는 해당 날짜 게시글 없음)")
                logger.debug(f"크롤링 상세 로그는 DEBUG 레벨에서 확인 가능")
                continue

            sentiments = batch_sentiment_analysis(df_posts['제목'].tolist())
            df_posts['감성'] = sentiments
            df_filtered = df_posts[df_posts['감성'].isin([1, -1])]
            
            if df_filtered.empty:
                logger.info(f"No positive/negative posts for {code} - {name}. Skipping.")
                continue

            dist = df_filtered['감성'].value_counts(normalize=True)
            # Django Serializer 요구사항에 맞춰 데이터 형식 조정
            # - stock_name 제거 (serializer에 없음)
            # - positive/negative: DecimalField(max_digits=5, decimal_places=4) 요구
            # - updated_at: ISO 형식 문자열 (Django가 자동 파싱)
            # updated_at 형식: Django DateTimeField는 Z 또는 +00:00 중 하나만 허용
            # isoformat()은 +00:00 형식을 생성하므로, 이를 Z로 변환
            updated_at_str = datetime.now(UTC).isoformat().replace('+00:00', 'Z')
            
            result = {
                "stock_code": code,
                # "stock_name": name,  # Django Serializer에 없으므로 제거
                "updated_at": updated_at_str,
                "positive": round(float(dist.get(1, 0)), 4),  # 소수점 4자리로 변경 (serializer 요구사항)
                "negative": round(float(dist.get(-1, 0)), 4),  # 소수점 4자리로 변경 (serializer 요구사항)
                "top_keywords": ', '.join(extract_top_keywords(df_filtered['제목'].tolist()))
            }
            results.append(result)
            logger.info(f"Processed {code} - {name}: positive={result['positive']}, negative={result['negative']}")

        # 결과 저장 및 전송
        os.makedirs(RESULT_DIR, exist_ok=True)
        json_filename = f"{RESULT_DIR}/kospi200_sentiment_{today_str}.json"
        
        try:
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved results to {json_filename} (총 {len(results)}개 종목)")
            
            # 파일이 실제로 저장되었는지 확인
            if os.path.exists(json_filename):
                file_size = os.path.getsize(json_filename)
                logger.info(f"파일 저장 확인: {json_filename} ({file_size} bytes)")
            else:
                logger.error(f"파일 저장 실패: {json_filename}가 존재하지 않음")
        except Exception as e:
            logger.error(f"파일 저장 중 오류 발생: {e}", exc_info=True)

        # Django 서버로 전송
        if results:
            # Django 서버 헬스 체크 (선택적)
            if not check_django_health():
                logger.warning("Django 서버 헬스 체크 실패, 전송 시도는 계속 진행")
            
            if send_to_django(results):
                logger.info(f"Successfully completed analysis and data transfer ({len(results)} items)")
            else:
                logger.error(f"Analysis completed but failed to send data to Django ({len(results)} items)")
                logger.error("JSON 파일은 저장되었으므로 수동으로 전송 가능")
        else:
            logger.warning("분석 결과가 없어 Django로 전송하지 않음")

    except Exception as e:
        logger.error(f"Error in run_analysis: {e}", exc_info=True)

# ===================== 스케줄러 설정 =====================
scheduler = BackgroundScheduler()
scheduler.add_job(
    run_analysis,
    'interval',
    hours=2,
    next_run_time=datetime.now()
)
scheduler.start()

# ===================== 헬스 체크 엔드포인트 =====================
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'time': datetime.now(UTC).isoformat() + 'Z',
        'next_run': scheduler.get_jobs()[0].next_run_time.isoformat() if scheduler.get_jobs() else None
    })

# ===================== 애플리케이션 진입점 =====================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))  # 기본 포트를 5001로 변경
    app.run(host='0.0.0.0', port=port)
