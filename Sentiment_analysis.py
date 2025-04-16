import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
from collections import Counter
from konlpy.tag import Okt
import json
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

# 모델 로딩
finbert_tokenizer = AutoTokenizer.from_pretrained("snunlp/KR-FinBert-SC")
finbert_model = AutoModelForSequenceClassification.from_pretrained("snunlp/KR-FinBert-SC")
finbert_pipe = pipeline("text-classification", model=finbert_model, tokenizer=finbert_tokenizer, return_all_scores=True)

electra_tokenizer = AutoTokenizer.from_pretrained("beomi/KcELECTRA-base")
electra_model = AutoModelForSequenceClassification.from_pretrained("beomi/KcELECTRA-base", num_labels=3)

# 크롤링 관련
headers = {"User-Agent": "Mozilla/5.0"}


def get_url(item_code, page_no=1):
    return f"https://finance.naver.com/item/board.nhn?code={item_code}&page={page_no}"


def get_one_page(item_code, page_no):
    url = get_url(item_code, page_no)
    response = requests.get(url, headers=headers)
    html = BeautifulSoup(response.text, "lxml")

    tables = pd.read_html(response.text)
    board_table = next((t for t in tables if '날짜' in t.columns and '제목' in t.columns), None)
    if board_table is None:
        raise ValueError("게시판 테이블을 찾을 수 없습니다.")

    table_filtered = board_table[['날짜', '제목']].copy()
    today = datetime.today().strftime('%Y.%m.%d')
    table_filtered['날짜'] = table_filtered['날짜'].astype(str).str.split().str[0]
    return table_filtered[table_filtered['날짜'] == today]


def get_last_page(item_code):
    url = get_url(item_code)
    response = requests.get(url, headers=headers)
    html = BeautifulSoup(response.text, "lxml")
    try:
        last_page = int(
            html.select_one(
                "#content > div.section.inner_sub > table > tbody > tr > td > table > tbody > tr > td.pgRR > a"
            )["href"].split('=')[-1]
        )
    except (TypeError, AttributeError):
        last_page = 1
    return last_page


def get_all_pages(item_code):
    last = get_last_page(item_code)
    page_list = []

    for page_num in range(1, min(last, 10) + 1):
        try:
            page = get_one_page(item_code, page_num)
            if not page.empty:
                page_list.append(page)
        except Exception as e:
            print(f"{item_code}의 {page_num}페이지 에러: {e}")
            continue

    if page_list:
        df_all_page = pd.concat(page_list, ignore_index=True)
        return df_all_page.dropna(how="all")
    else:
        return pd.DataFrame(columns=['날짜', '제목'])


# 전처리
okt = Okt()


def clean_text(text):
    text = BeautifulSoup(text, "html.parser").get_text()
    text = re.sub(r"[^ㄱ-ㅎㅏ-ㅣ가-힣\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess_text(text):
    text = clean_text(text)
    tokens = [word for word in okt.morphs(text) if word not in ['의', '에', '이', '가', '은', '는', '를', '을', '도', '로']]
    return " ".join(tokens)


def convert_label(label):
    return {"positive": 1, "neutral": 0, "negative": -1}.get(label, None)


# 두 모델을 함께 사용하는 감성 분석;
def analyze_sentiments_with_dual_model(texts, threshold=0.6):
    finbert_preds = finbert_pipe(texts, truncation=True)

    electra_inputs = electra_tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        electra_outputs = electra_model(**electra_inputs)
    electra_logits = electra_outputs.logits
    electra_probs = torch.nn.functional.softmax(electra_logits, dim=-1)
    electra_labels = torch.argmax(electra_probs, dim=-1).tolist()

    final_results = []
    for i, pred in enumerate(finbert_preds):
        sorted_pred = sorted(pred, key=lambda x: x['score'], reverse=True)
        top_label = sorted_pred[0]['label']
        top_score = sorted_pred[0]['score']

        # FinBERT label 결정
        if top_label == "neutral" and top_score < threshold:
            finbert_label = sorted_pred[1]['label']
        else:
            finbert_label = top_label

        # Electra label 매핑 (0: 부정, 1: 중립, 2: 긍정)
        electra_label = electra_labels[i]
        electra_label_str = {0: "negative", 1: "neutral", 2: "positive"}[electra_label]

        # 결합 로직
        if ("positive" in [finbert_label, electra_label_str]) and not (
                "negative" in [finbert_label, electra_label_str]):
            final_results.append(1)
        elif ("negative" in [finbert_label, electra_label_str]) and not (
                "positive" in [finbert_label, electra_label_str]):
            final_results.append(-1)
        else:
            final_results.append(0)

    return final_results


def extract_top_keywords(texts, top_n=4):
    all_nouns = []
    for text in texts:
        nouns = okt.nouns(text)
        all_nouns.extend(nouns)
    counter = Counter(all_nouns)
    return [word for word, _ in counter.most_common(top_n)]


def show_sample_titles(df):
    print("\n=== 감성별 제목 예시 ===")
    for sentiment, label in zip(["긍정", "중립", "부정"], [1, 0, -1]):
        samples = df[df['감성'] == label]['제목'].sample(n=min(5, len(df[df['감성'] == label])), random_state=42).tolist()
        if samples:
            print(f"\n[{sentiment} 예제]")
            for title in samples:
                print(f"- {title}")
        else:
            print(f"\n[{sentiment} 예제] 해당 감성의 제목이 없습니다.")


# 메인 실행
def main():
    item_code = input("수집할 종목 코드를 입력하세요: ").strip()
    stock_name = input("종목명을 입력하세요 (예: 삼성전자): ").strip()

    print(f"{item_code} ({stock_name})의 게시글 데이터를 수집 중입니다...")
    df = get_all_pages(item_code)
    if df.empty:
        print(f"{item_code}의 오늘 날짜 게시글이 없습니다.")
        return

    print("데이터 전처리 및 감성 분석을 수행 중입니다...")
    df['전처리된 제목'] = df['제목'].apply(preprocess_text)
    df['감성'] = analyze_sentiments_with_dual_model(df['전처리된 제목'].tolist(), threshold=0.6)

    sentiment_distribution = df['감성'].value_counts(normalize=True)

    result = {
        "stock_code": item_code,
        "stock_name": stock_name,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "sentiment": {
            "positive": round(sentiment_distribution.get(1, 0.0), 2),
            "neutral": round(sentiment_distribution.get(0, 0.0), 2),
            "negative": round(sentiment_distribution.get(-1, 0.0), 2)
        },
        "top_keywords": extract_top_keywords(df['전처리된 제목'])
    }

    print("\n=== JSON 결과 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    show_sample_titles(df)

    # 🔽 CSV 저장 추가
    output_filename = f"sentiment_result_{item_code}_{datetime.today().strftime('%Y%m%d')}.csv"
    df.to_csv(output_filename, index=False, encoding='utf-8-sig')
    print(f"\nCSV 파일로 저장 완료: {output_filename}")

if __name__ == "__main__":
    main()
