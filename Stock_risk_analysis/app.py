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

DJANGO_ENDPOINT = os.getenv(
    'DJANGO_ENDPOINT',
    'http://localhost:8000/api/sentiment/bulk/'  # 올바른 URL로 수정
)
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

# ===================== Django 서버 연동 함수 =====================
def send_to_django(data, retry_count=0):
    """Django 서버로 데이터를 전송하고 실패 시 재시도"""
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    if DJANGO_API_KEY:
        headers['Authorization'] = f"Token {DJANGO_API_KEY}"

    try:
        logger.debug(f"Sending data to Django: {json.dumps(data, ensure_ascii=False)}")
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
    except requests.exceptions.RequestException as e:
        if retry_count < MAX_RETRIES:
            logger.warning(f"Failed to send data (attempt {retry_count + 1}/{MAX_RETRIES}): {e}")
            if hasattr(e.response, 'text'):
                logger.warning(f"Error response: {e.response.text}")
            time.sleep(RETRY_DELAY)
            return send_to_django(data, retry_count + 1)
        else:
            logger.error(f"Failed to send data after {MAX_RETRIES} attempts: {e}")
            if hasattr(e.response, 'text'):
                logger.error(f"Error response: {e.response.text}")
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

            df_posts = get_today_posts(code)
            if df_posts.empty:
                logger.info(f"No posts for {code} - {name}. Skipping.")
                continue

            sentiments = batch_sentiment_analysis(df_posts['제목'].tolist())
            df_posts['감성'] = sentiments
            df_filtered = df_posts[df_posts['감성'].isin([1, -1])]
            
            if df_filtered.empty:
                logger.info(f"No positive/negative posts for {code} - {name}. Skipping.")
                continue

            dist = df_filtered['감성'].value_counts(normalize=True)
            result = {
                "stock_code": code,
                "stock_name": name,
                "updated_at": datetime.now(UTC).isoformat() + 'Z',
                "positive": round(dist.get(1, 0), 2),
                "negative": round(dist.get(-1, 0), 2),
                "top_keywords": ', '.join(extract_top_keywords(df_filtered['제목'].tolist()))
            }
            results.append(result)
            logger.info(f"Processed {code} - {name}: positive={result['positive']}, negative={result['negative']}")

        # 결과 저장 및 전송
        os.makedirs(RESULT_DIR, exist_ok=True)
        json_filename = f"{RESULT_DIR}/kospi200_sentiment_{today_str}.json"
        
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved results to {json_filename}")

        # Django 서버로 전송
        if send_to_django(results):
            logger.info("Successfully completed analysis and data transfer")
        else:
            logger.error("Analysis completed but failed to send data to Django")

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
