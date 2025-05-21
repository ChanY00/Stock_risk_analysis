import json
import re
import time
import os
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# ===================== 환경 설정 =====================
load_dotenv()
API_KEY = os.getenv('GEMINI_API_KEY')
HEADERS = {"Content-Type": "application/json"}
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.0-flash:generateContent"
    f"?key={API_KEY}"
)

# ===================== 병렬 처리 메인 함수 =====================
def batch_sentiment_analysis(texts, batch_size=5, max_retries=3, max_workers=5):
    results = [None] * len(texts)
    batches = [(i, texts[i:i + batch_size]) for i in range(0, len(texts), batch_size)]

    def process_batch(start, batch):
        prompt = build_prompt(batch)
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        response = _request_with_retries(API_URL, payload, max_retries)
        if response:
            return (start, parse_sentiments(response.json(), len(batch)))
        else:
            return (start, [None] * len(batch))  # 실패 시 제외

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_batch, start, batch) for start, batch in batches]
        for future in futures:
            start, batch_result = future.result()
            results[start:start + len(batch_result)] = batch_result

    return results

# ===================== 프롬프트 구성 =====================
def build_prompt(batch):
    prompt = (
        "다음 문장은 댓글입니다. 감성을 'positive' 또는 'negative' 중 하나로 알려주세요.\n"
        "중립적인 문장은 제외해줘.\n"
    )
    prompt += ''.join([f"{i+1}. {text}\n" for i, text in enumerate(batch)])
    prompt += "형식: 번호. 감성"
    return prompt

# ===================== 요청 처리 및 재시도 =====================
def _request_with_retries(url, payload, max_retries):
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, headers=HEADERS, json=payload)
            if resp.status_code == 200:
                return resp
            if resp.status_code == 429:
                delay = _extract_retry_delay(resp)
                print(f"[429] 대기 {delay}s 후 재시도 ({attempt+1}/{max_retries})")
                time.sleep(delay)
            else:
                print(f"[오류] 상태 코드: {resp.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"[예외] 요청 실패: {e}")
            time.sleep(3)
    return None

# ===================== 재시도 대기 시간 추출 =====================
def _extract_retry_delay(resp):
    try:
        details = resp.json().get('error', {}).get('details', [])
        for d in details:
            if d.get('@type', '').endswith('RetryInfo'):
                return int(d['retryDelay'].rstrip('s'))
    except:
        pass
    return 60  # 기본 대기 시간

# ===================== 감성 파싱 함수 =====================
def parse_sentiments(resp_json, batch_length):
    results = [None] * batch_length
    try:
        text = resp_json['candidates'][0]['content']['parts'][0]['text']
        for line in text.splitlines():
            m = re.match(r"\s*(\d+)\.\s*(positive|negative|neutral)", line, re.IGNORECASE)
            if m:
                idx, label = int(m.group(1)) - 1, m.group(2).lower()
                if 0 <= idx < batch_length:
                    if label == 'positive':
                        results[idx] = 1
                    elif label == 'negative':
                        results[idx] = -1
                    else:
                        results[idx] = None  # neutral 제외
    except Exception as e:
        print(f"[파싱 오류] {e}")
    return results
