import pandas as pd
import json
from datetime import datetime
from crawler import get_today_posts
from gemini_sentiment import batch_sentiment_analysis
from keywords import extract_top_keywords
import os

def main(file_path="kospi200.csv", max_stocks=None):
    kospi_df = pd.read_csv(file_path, dtype={"종목코드": str})
    if max_stocks:
        kospi_df = kospi_df.head(max_stocks)

    results = []
    today_str = datetime.today().strftime('%Y%m%d')

    for _, row in kospi_df.iterrows():
        code = row['종목코드']
        name = row['종목명']
        print(f"\n🔍 [{code} | {name}] 게시글 수집 중...")

        df = get_today_posts(code)
        if df.empty:
            print("  📭 게시글 없음 — 건너뜀")
            continue

        original_count = len(df)
        df['감성'] = batch_sentiment_analysis(df['제목'].tolist())

        # 중립 제외
        df = df[df['감성'].isin([1, -1])]
        remaining_count = len(df)

        print(f"  📊 원본: {original_count}개 | 최종: {remaining_count}개")
        if df.empty:
            print("  ⚪ 남은 데이터 없음 — 건너뜀")
            continue

        dist = df['감성'].value_counts(normalize=True)
        sentiment_result = {
            "stock_code": code,
            "stock_name": name,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "positive": round(dist.get(1, 0), 2),
            "negative": round(dist.get(-1, 0), 2),
            "top_keywords": ', '.join(extract_top_keywords(df['제목'].tolist()))
        }
        results.append(sentiment_result)

    # JSON 저장
    os.makedirs("result_json", exist_ok=True)
    json_filename = f"result_json/kospi200_sentiment_{today_str}.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 전체 종목 분석 완료. JSON 저장 완료: {json_filename}")

if __name__ == "__main__":
    main(max_stocks=3)  # 테스트 시 원하는 종목 수 조절
