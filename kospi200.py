import pandas as pd
from pykrx import stock
from datetime import datetime

def save_kospi200_csv(filename="kospi200.csv"):
    # 오늘 날짜 기준 KOSPI200 구성종목 불러오기
    today = datetime.today().strftime("%Y%m%d")
    kospi200 = stock.get_index_portfolio_deposit_file("1028", today)  # '1028' = KOSPI200

    # 각 종목의 이름도 함께 가져오기
    data = []
    for code in kospi200:
        name = stock.get_market_ticker_name(code)
        data.append({"종목코드": code, "종목명": name})

    df = pd.DataFrame(data)
    df.to_csv(filename, index=False, encoding='utf-8-sig')
    print(f"✅ {filename} 저장 완료 ({len(df)}개 종목)")

# 실행 예시
if __name__ == "__main__":
    save_kospi200_csv()
