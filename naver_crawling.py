import os
import pandas as pd
import requests
import time
from tqdm import trange
from bs4 import BeautifulSoup as bs
from datetime import datetime
from pykrx import stock

# -------------------------------
# 네이버 금융 게시판 크롤링 함수들
# -------------------------------

headers = {"user-agent": "Mozilla/5.0"}


def get_url(item_code, page_no=1):
    return f"https://finance.naver.com/item/board.nhn?code={item_code}&page={page_no}"


def get_one_page(item_code, page_no):
    """한 페이지 수집: '날짜'와 '제목' 열이 있는 게시판 테이블을 찾아 오늘 날짜의 게시글만 반환"""
    url = get_url(item_code, page_no)
    response = requests.get(url, headers=headers)
    html = bs(response.text, "lxml")

    # pd.read_html로 추출한 모든 테이블 검색
    tables = pd.read_html(response.text)
    board_table = None
    for t in tables:
        # 테이블에 '날짜'와 '제목' 열이 있는지 확인
        if '날짜' in t.columns and '제목' in t.columns:
            board_table = t.copy()  # 원본과 분리하기 위해 copy() 사용
            break
    if board_table is None:
        raise ValueError("게시판 테이블을 찾을 수 없습니다.")

    # '날짜'와 '제목' 열만 선택
    table_filtered = board_table[['날짜', '제목']].copy()

    # 오늘 날짜 (형식: YYYY.MM.DD)
    today = datetime.today().strftime('%Y.%m.%d')

    # 날짜에 시간이 포함되어 있을 경우, 날짜 부분만 사용
    table_filtered.loc[:, '날짜'] = table_filtered['날짜'].astype(str).str.split().str[0]

    # 오늘 날짜와 일치하는 게시글만 필터링
    table_filtered_today = table_filtered[table_filtered['날짜'] == today]

    return table_filtered_today


def get_last_page(item_code):
    """게시판의 마지막 페이지 번호 추출"""
    url = get_url(item_code)
    response = requests.get(url, headers=headers)
    html = bs(response.text, "lxml")
    try:
        last_page = int(
            html.select_one(
                "#content > div.section.inner_sub > table > tbody > tr > td > table > tbody > tr > td.pgRR > a"
            )["href"].split('=')[-1]
        )
    except (TypeError, AttributeError):
        last_page = 1  # 페이지가 없으면 기본값 1로 설정
    return last_page


def get_all_pages(item_code):
    """1~10페이지에서 오늘 날짜의 게시글만 수집"""
    last = get_last_page(item_code)
    page_list = []

    # 1~10페이지까지만 수집 (실제 마지막 페이지와 비교하여 min(last, 10))
    for page_num in trange(1, min(last, 10) + 1, desc=f"{item_code} 수집중"):
        try:
            page = get_one_page(item_code, page_num)
            if not page.empty:
                page_list.append(page)
            time.sleep(0.1)
        except Exception as e:
            print(f"{item_code}의 {page_num}페이지 에러: {e}")
            continue

    if page_list:
        df_all_page = pd.concat(page_list, ignore_index=True)
        df_all_page = df_all_page.dropna(how="all")
        return df_all_page
    else:
        return pd.DataFrame(columns=['날짜', '제목'])


# -------------------------------
# pykrx를 이용한 상위 100 종목 코드 수집 함수들
# -------------------------------

def get_latest_trading_day():
    """
    간단히 오늘 날짜를 거래일로 사용.
    실제 거래일 확인 로직이 필요하다면 별도 구현 필요.
    """
    return datetime.today().strftime("%Y%m%d")


def get_top_100_tickers():
    """
    pykrx를 사용하여 KOSPI 시가총액 상위 100종목의 티커(종목코드)를 반환.
    """
    latest_day = get_latest_trading_day()
    df = stock.get_market_cap_by_ticker(latest_day, market="KOSPI")
    top100 = df.sort_values(by="시가총액", ascending=False).head(100)
    return top100.index.tolist()


# -------------------------------
# 상위 100 종목에 대해 데이터 수집 및 폴더 내 개별 Excel 파일 저장
# -------------------------------

def collect_top_100_data():
    # 저장 폴더 생성 (폴더가 존재하지 않으면 생성)
    save_folder = "stock_data"
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    tickers = get_top_100_tickers()

    for ticker in tickers:
        print(f"수집 중: {ticker}")
        df = get_all_pages(ticker)
        if not df.empty:
            filename = os.path.join(save_folder, f"{ticker}_stock_data_today.xlsx")
            df.to_excel(filename, index=False)
            print(f"{ticker}의 데이터를 {filename}로 저장했습니다.")
        else:
            print(f"{ticker}의 오늘 날짜 게시글이 없습니다.")

    print("모든 데이터 수집 완료.")


if __name__ == "__main__":
    collect_top_100_data()
