import os                         # ① 운영체제 환경변수 읽기/파일 경로 조작을 위해 os 모듈을 불러옴
import json                       # ② Python 객체와 JSON 간 직렬화/역직렬화를 위해 json 모듈 사용
import logging                    # ③ 로깅을 통한 정보·오류 기록을 위해 logging 모듈 사용
import requests                   # ④ HTTP 요청을 보내 Django 서버에 결과 전송을 위해 requests 사용
from datetime import datetime    # ⑤ 현재 시각을 얻고 포맷팅하기 위해 datetime 클래스 임포트
from flask import Flask, jsonify  # ⑥ Flask 앱과 JSON 응답 기능을 사용하기 위해 Flask, jsonify 임포트
from apscheduler.schedulers.background import BackgroundScheduler
                                  # ⑦ APScheduler의 백그라운드 스케줄러를 사용하기 위해 임포트
from crawler import get_today_posts             # ⑧ 기존 crawler.py에서 오늘/어제 게시글 수집 함수 가져오기
from gemini_sentiment import batch_sentiment_analysis
                                  # ⑨ gemini_sentiment.py에서 병렬 감성 분석 함수 가져오기
from keywords import extract_top_keywords       # ⑩ keywords.py에서 키워드 추출 함수 가져오기

# ===================== 환경 설정 =====================
DJANGO_ENDPOINT = os.getenv(
    'DJANGO_ENDPOINT',
    'https://your-django-server/api/receive-sentiment/'
)                                 # ⑪ Django에 보낼 POST 엔드포인트, 환경변수 우선 사용
DJANGO_API_KEY = os.getenv('DJANGO_API_KEY', '')
                                  # ⑫ (선택) 인증 토큰을 위한 API 키, 없으면 빈 문자열
KOSPI_CSV = os.getenv('KOSPI_CSV_PATH', 'kospi200.csv')
                                  # ⑬ 종목 리스트 CSV 경로, 환경변수 지정 가능
MAX_STOCKS = int(os.getenv('MAX_STOCKS', None))
                                  # ⑭ 분석할 최대 종목 수, None이면 전체
RESULT_DIR = os.getenv('RESULT_DIR', 'result_json')
                                  # ⑮ (Optional) 로컬 백업용 결과 폴더 경로

# ===================== Flask 앱 초기화 =====================
app = Flask(__name__)             # ⑯ Flask 애플리케이션 객체 생성
logging.basicConfig(level=logging.INFO)
                                  # ⑰ 로깅 레벨을 INFO로 설정(디버그·정보·경고·오류 기록)

# ===================== 메인 작업 함수 =====================
def run_analysis():
    from pandas import read_csv   # ⑱ pandas는 무겁기에 함수 내에서 동적 임포트
    kospi_df = read_csv(         # ⑲ CSV 파일을 DataFrame으로 읽되,
        KOSPI_CSV,
        dtype={"종목코드": str}   #     종목코드는 문자열로 읽어 앞자리 0 보존
    )
    if MAX_STOCKS:               # ⑳ MAX_STOCKS가 설정돼 있으면 상위 N개만 선택
        kospi_df = kospi_df.head(MAX_STOCKS)

    results = []                 # ㉑ 최종 JSON 결과를 담을 리스트 초기화
    today_str = datetime.today().strftime('%Y%m%d')
                                 # ㉒ 오늘 날짜 문자열 포맷 (파일명·로그 등에 사용 가능)

    for _, row in kospi_df.iterrows():
        code, name = row['종목코드'], row['종목명']
                                 # ㉓ 각 종목의 코드·이름을 변수에 할당
        logging.info(f"Processing {code} - {name}")
                                 # ㉔ 어느 종목을 처리 중인지 로그에 기록

        df_posts = get_today_posts(code)
                                 # ㉕ 오늘·어제 게시글 수집
        if df_posts.empty:        # ㉖ 게시글이 없으면 다음 종목으로 건너뜀
            logging.info("No posts for today/yesterday. Skipping.")
            continue

        sentiments = batch_sentiment_analysis(
            df_posts['제목'].tolist()
        )                          # ㉗ 제목 리스트를 Gemini API로 병렬 감성 분석
        df_posts['감성'] = sentiments
                                 # ㉘ 분석 결과(1, -1, None)를 DataFrame에 추가
        df_filtered = df_posts[
            df_posts['감성'].isin([1, -1])
        ]                          # ㉙ 중립(None)을 제외한 긍정/부정 포스트만 필터링
        if df_filtered.empty:      # ㉚ 남은 데이터가 없으면 건너뜀
            logging.info("No positive/negative posts. Skipping.")
            continue

        dist = df_filtered['감성'].value_counts(normalize=True)
                                 # ㉛ 긍정·부정 비율 계산(normalize=True)
        results.append({          # ㉜ 결과 딕셔너리 생성 후 리스트에 추가
            "stock_code": code,
            "stock_name": name,
            "updated_at": datetime.utcnow().isoformat() + 'Z',
            "positive": round(dist.get(1, 0), 2),
            "negative": round(dist.get(-1, 0), 2),
            "top_keywords": extract_top_keywords(
                df_filtered['제목'].tolist()
            )
        })

    # ===================== Django 서버로 전송 =====================
    headers = {'Content-Type': 'application/json'}
                                 # ㉝ JSON 형식 헤더
    if DJANGO_API_KEY:            # ㉞ API 키가 있으면 인증 헤더 추가
        headers['Authorization'] = f"Token {DJANGO_API_KEY}"
    try:
        resp = requests.post(     # ㉟ Django 엔드포인트에 POST 요청
            DJANGO_ENDPOINT,
            headers=headers,
            data=json.dumps(results)
        )
        resp.raise_for_status()   # ㊱ 200 OK가 아니면 예외 발생
        logging.info(f"Successfully sent data to Django: {resp.status_code}")
    except Exception as e:
        logging.error(f"Failed to send data to Django: {e}")

# ===================== 스케줄러 설정 =====================
scheduler = BackgroundScheduler()
                                 # ㊲ 백그라운드 스케줄러 인스턴스 생성
scheduler.add_job(                # ㊳ 스케줄러에 작업 추가
    run_analysis,                 #     실행할 함수
    'interval',                   #     interval 트리거 사용
    hours=2,                      #     2시간마다 반복
    next_run_time=datetime.now()  #     앱 실행 직후 한 번 바로 실행
)
scheduler.start()                # ㊴ 스케줄러 시작

# ===================== 헬스 체크 엔드포인트 =====================
@app.route('/health', methods=['GET'])
def health_check():
    # ㊵ 서비스 상태와 현재 UTC 시각을 JSON으로 반환
    return jsonify({'status': 'ok', 'time': datetime.utcnow().isoformat() + 'Z'})

# ===================== 애플리케이션 진입점 =====================
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    # ㊶ 환경변수 PORT가 있으면 그 값, 없으면 5000번 포트 사용
    app.run(host='0.0.0.0', port=port)
    # ㊷ 외부 요청 허용(0.0.0.0) 및 지정 포트로 Flask 서버 구동
