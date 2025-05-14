import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime, timedelta

USER_AGENT = "Mozilla/5.0"

def get_url(item_code: str, page_no: int = 1) -> str:
    return f"https://finance.naver.com/item/board.nhn?code={item_code}&page={page_no}"

def fetch_page(item_code: str, page_no: int) -> pd.DataFrame:
    resp = requests.get(get_url(item_code, page_no), headers={"User-Agent": USER_AGENT})
    tables = pd.read_html(StringIO(resp.text))
    board = next((t for t in tables if '날짜' in t.columns and '제목' in t.columns), None)
    if board is None:
        return pd.DataFrame()
    df = board[['날짜', '제목']].copy()
    df['날짜'] = df['날짜'].str.split().str[0]
    return df

def get_today_posts(item_code: str, max_pages: int = 25, max_rows: int = 500) -> pd.DataFrame:
    today = datetime.today()
    yesterday = today - timedelta(days=1)
    valid_dates = {today.strftime('%Y.%m.%d'), yesterday.strftime('%Y.%m.%d')}

    collected = []
    total = 0

    for page in range(1, max_pages + 1):
        try:
            df = fetch_page(item_code, page)
        except Exception as e:
            print(f"[오류] {e}")
            continue

        df = df[df['날짜'].isin(valid_dates)]
        if df.empty:
            break

        for _, row in df.iterrows():
            if total >= max_rows:
                break
            collected.append(row)
            total += 1

        if total >= max_rows:
            break

    return pd.DataFrame(collected)
