import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime
import re
from collections import Counter
import json
import time
import os
from dotenv import load_dotenv

# ✅ 여기에 너의 Gemini API 키 입력
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 공통 헤더
headers = {"Content-Type": "application/json"}

# 네이버 금융 게시판 URL 생성
def get_url(item_code, page_no=1):
    return f"https://finance.naver.com/item/board.nhn?code={item_code}&page={page_no}"

# 한 페이지에서 오늘 날짜 게시글만 가져오기
def get_one_page(item_code, page_no):
    url = get_url(item_code, page_no)
    resp = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
    tables = pd.read_html(StringIO(resp.text))

    board = next((t for t in tables if '날짜' in t.columns and '제목' in t.columns), None)
    if board is None:
        raise ValueError("게시판 테이블을 찾을 수 없습니다.")

    df = board[['날짜','제목']].copy()
    today = datetime.today().strftime('%Y.%m.%d')
    df['날짜'] = df['날짜'].astype(str).str.split().str[0]
    return df[df['날짜'] == today]

# 마지막 페이지 번호 조회
def get_last_page(item_code):
    resp = requests.get(get_url(item_code), headers={"User-Agent":"Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, 'lxml')
    link = soup.select_one("#content .pgRR a")
    if link and 'href' in link.attrs:
        return int(link['href'].split('=')[-1])
    return 1

# 여러 페이지에서 오늘 게시글 수집
def get_all_pages(item_code, max_pages=10):
    last = get_last_page(item_code)
    dfs = []
    for page in range(1, min(last, max_pages) + 1):
        try:
            df = get_one_page(item_code, page)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            print(f"{item_code} 페이지 {page} 에러: {e}")
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=['날짜','제목'])

# 배치(batch) 감성 분석
def analyze_sentiments_batch(texts, batch_size=5, max_retries=3):
    """
    texts: 분석할 문장 리스트
    batch_size: 한 번에 묶어서 보낼 문장 개수
    """
    results = [0] * len(texts)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.0-flash:generateContent"
        f"?key={GEMINI_API_KEY}"
    )

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start+batch_size]

        # 1) 배치 프롬프트 구성
        prompt = "다음 문장들의 감성을 'positive', 'negative', 'neutral' 중 하나로 알려줘.\n"
        for idx, t in enumerate(batch, 1):
            prompt += f"{idx}. {t}\n"
        prompt += "형식: 번호. 감성\n"

        payload = {"contents":[{"parts":[{"text": prompt}]}]}

        # 2) 최대 max_retries회까지 재시도
        for attempt in range(1, max_retries+1):
            resp = requests.post(url, headers=headers, data=json.dumps(payload))
            if resp.status_code == 200:
                break
            elif resp.status_code == 429:
                # RetryInfo delay 처리
                try:
                    details = resp.json().get('error', {}).get('details', [])
                    delay = next(
                        (int(d['retryDelay'].rstrip('s'))
                         for d in details
                         if d.get('@type','').endswith('RetryInfo')),
                        60
                    )
                except:
                    delay = 60
                print(f"429: 쿼터 초과, {delay}s 대기({attempt}/{max_retries})")
                time.sleep(delay)
            else:
                resp.raise_for_status()
        else:
            # 모두 실패 시 해당 배치는 중립으로 채움
            continue

        # 3) 응답 파싱
        text = resp.json()['candidates'][0]['content']['parts'][0]['text']
        for line in text.splitlines():
            m = re.match(r"\s*(\d+)\.\s*(positive|negative|neutral)", line, re.IGNORECASE)
            if not m:
                continue
            idx = int(m.group(1)) - 1
            label = m.group(2).lower()
            val = 1 if label == 'positive' else -1 if label == 'negative' else 0
            results[start + idx] = val

        # 4) 너무 빠른 연속 호출 방지 (선택)
        time.sleep(1)

    return results

# 단순 단어 기반 키워드 추출
def extract_top_keywords(texts, top_n=4):
    words = []
    for t in texts:
        words.extend(re.findall(r"[가-힣]+", t))
    return [w for w,_ in Counter(words).most_common(top_n)]

# 샘플 제목 출력
def show_sample_titles(df):
    print("\n=== 감성별 제목 예시 ===")
    for label, name in [(1, "긍정"), (-1, "부정"), (0, "중립")]:
        samples = df[df['감성'] == label]['제목']
        print(f"\n[{name} 예제]")
        if not samples.empty:
            for title in samples.sample(n=min(5, len(samples)), random_state=42):
                print(f"- {title}")
        else:
            print("해당 감성의 제목이 없습니다.")

# 메인 실행
if __name__ == "__main__":
    code = input("수집할 종목 코드를 입력하세요: ").strip()
    print(f"{code} 게시글 수집 중...")

    df = get_all_pages(code)
    if df.empty:
        print("오늘 날짜 게시글이 없습니다.")
        exit()

    print("배치 감성 분석 중...")
    df['감성'] = analyze_sentiments_batch(df['제목'].tolist(), batch_size=5)

    # 결과 통계 및 JSON 생성
    dist = df['감성'].value_counts(normalize=True)
    result = {
        "stock_code": code,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "sentiment": {
            "positive": round(dist.get(1, 0), 2),
            "negative": round(dist.get(-1, 0), 2),
            "neutral": round(dist.get(0, 0), 2)
        },
        "top_keywords": extract_top_keywords(df['제목'].tolist())
    }

    print("\n=== JSON 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    show_sample_titles(df)

    # CSV 저장
    fname = f"sentiment_result_{code}_{datetime.today().strftime('%Y%m%d')}.csv"
    df.to_csv(fname, index=False, encoding='utf-8-sig')
    print(f"\nCSV 저장 완료: {fname}")
