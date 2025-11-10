import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0"

def normalize_date(date_str: str) -> str:
    """
    네이버 파이낸스 게시판의 다양한 날짜 형식을 표준 형식('YYYY.MM.DD')으로 정규화
    
    예시:
    - "2025.11.04" -> "2025.11.04"
    - "2025-11-04" -> "2025.11.04"
    - "23.11.04" -> "2023.11.04" (연도 축약 시 현재 연도 기반 추정)
    - "11.04" -> 현재 연도.11.04
    - "2025. 11. 04" -> "2025.11.04" (공백 제거)
    - "2025-11-04 12:34" -> "2025.11.04" (시간 제거)
    - "2025/11/04" -> "2025.11.04" (슬래시 지원)
    """
    if pd.isna(date_str) or not date_str:
        return ""
    
    original = str(date_str).strip()
    date_str = original
    
    # 시간 제거 (예: "2025.11.04 12:34" -> "2025.11.04")
    if ' ' in date_str:
        date_str = date_str.split()[0]
    
    # 공백 제거 (전체 공백, 탭, 특수 공백 문자)
    date_str = re.sub(r'[\s　]+', '', date_str)
    
    # 슬래시를 점으로 변환
    date_str = date_str.replace('/', '.').replace('-', '.')
    
    # YYYY.MM.DD 형식 (표준)
    match = re.match(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', date_str)
    if match:
        year, month, day = match.groups()
        normalized = f"{year}.{month.zfill(2)}.{day.zfill(2)}"
        return normalized
    
    # YY.MM.DD 형식 (연도 축약)
    match = re.match(r'(\d{2})\.(\d{1,2})\.(\d{1,2})', date_str)
    if match:
        year_short, month, day = match.groups()
        # 연도 추정: 00-30은 2000년대, 31-99는 1900년대로 가정
        year_full = f"20{year_short}" if int(year_short) <= 30 else f"19{year_short}"
        normalized = f"{year_full}.{month.zfill(2)}.{day.zfill(2)}"
        return normalized
    
    # MM.DD 형식 (연도 없음 - 현재 연도 사용)
    match = re.match(r'(\d{1,2})\.(\d{1,2})(?:\.\d{1,2})?', date_str)
    if match:
        month, day = match.groups()[:2]
        current_year = datetime.today().strftime('%Y')
        normalized = f"{current_year}.{month.zfill(2)}.{day.zfill(2)}"
        return normalized
    
    # YYYYMMDD 형식 (연속된 숫자)
    match = re.match(r'(\d{4})(\d{2})(\d{2})', date_str)
    if match:
        year, month, day = match.groups()
        normalized = f"{year}.{month}.{day}"
        return normalized
    
    # 정규화 실패 시 원본 반환 (디버깅용)
    # logger.warning(f"날짜 정규화 실패: '{original}' -> 원본 반환")
    return original

def get_url(item_code: str, page_no: int = 1) -> str:
    return f"https://finance.naver.com/item/board.nhn?code={item_code}&page={page_no}"

def fetch_page(item_code: str, page_no: int) -> pd.DataFrame:
    try:
        url = get_url(item_code, page_no)
        # logger.debug(f"[{item_code}] 페이지 {page_no} 요청 시작: {url}")
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
        resp.raise_for_status()
        # logger.debug(f"[{item_code}] 페이지 {page_no} 응답 받음: {resp.status_code}")
        tables = pd.read_html(StringIO(resp.text))
        board = next((t for t in tables if '날짜' in t.columns and '제목' in t.columns), None)
        if board is None:
            # logger.warning(f"[{item_code}] 페이지 {page_no}: 게시판 테이블을 찾을 수 없음")
            return pd.DataFrame()
        df = board[['날짜', '제목']].copy()
        
        # 원본 날짜 저장 (디버깅용)
        if len(df) > 0:
            original_dates = df['날짜'].head(3).tolist()
            # logger.debug(f"[{item_code}] 페이지 {page_no}: 원본 날짜 샘플 - {original_dates}")
        
        # 날짜 파싱: 공백으로 분리 후 첫 번째 부분만 사용 (예: "2025.11.04 12:34" -> "2025.11.04")
        df['날짜_원본'] = df['날짜'].copy()
        df['날짜'] = df['날짜'].astype(str).str.split().str[0]
        
        # 날짜 정규화: 다양한 형식을 표준 형식으로 변환
        df['날짜'] = df['날짜'].apply(normalize_date)
        
        # 정규화 결과 확인
        if len(df) > 0:
            normalized_dates = df['날짜'].head(3).tolist()
            # logger.debug(f"[{item_code}] 페이지 {page_no}: 정규화 후 날짜 샘플 - {normalized_dates}")
        
        # logger.debug(f"[{item_code}] 페이지 {page_no} 파싱 완료: {len(df)}개 게시글")
        return df
    except requests.exceptions.Timeout as e:
        # logger.error(f"[{item_code}] 페이지 {page_no} 요청 타임아웃 (10초 초과): {e}")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        # logger.error(f"[{item_code}] 페이지 {page_no} 요청 실패: {e}")
        return pd.DataFrame()
    except Exception as e:
        # logger.error(f"[{item_code}] 페이지 {page_no} 파싱 오류: {e}", exc_info=True)
        return pd.DataFrame()

# 최대 500개 수집
def get_today_posts(item_code: str, max_pages: int = 25, max_rows: int = 500) -> pd.DataFrame:
    today = datetime.today()
    yesterday = today - timedelta(days=1)
    valid_dates = {today.strftime('%Y.%m.%d'), yesterday.strftime('%Y.%m.%d')}
    
    # logger.info(f"[{item_code}] 크롤링 시작 - 검색 날짜: {valid_dates}")

    collected = []
    total = 0
    pages_fetched = 0
    total_posts_before_filter = 0

    for page in range(1, max_pages + 1):
        try:
            # logger.debug(f"[{item_code}] 페이지 {page} 크롤링 시작...")
            df = fetch_page(item_code, page)
            if df.empty:
                # logger.info(f"[{item_code}] 페이지 {page}: 빈 결과 - 크롤링 종료")
                break
            
            pages_fetched += 1
            total_posts_before_filter += len(df)
            
            # 날짜 필터링 전 원본 데이터 확인
            # logger.info(f"[{item_code}] 페이지 {page}: 필터링 전 {len(df)}개 게시글 수집")
            
            # 날짜 샘플 확인 (중요: 날짜 형식 불일치 문제 진단)
            if len(df) > 0:
                date_samples = df['날짜'].head(5).tolist()
                unique_dates = sorted(df['날짜'].unique()[:15].tolist())
                original_samples = df['날짜_원본'].head(5).tolist() if '날짜_원본' in df.columns else []
                
                # logger.info(f"[{item_code}] 페이지 {page}: 원본 날짜 샘플 (상위 5개) - {original_samples}")
                # logger.info(f"[{item_code}] 페이지 {page}: 정규화 후 날짜 샘플 (상위 5개) - {date_samples}")
                # logger.info(f"[{item_code}] 페이지 {page}: 고유 날짜 형식 (상위 15개) - {unique_dates}")
                # logger.info(f"[{item_code}] 페이지 {page}: 검색 날짜 형식 - {valid_dates}")
                
                # 필터링 전 매칭 확인
                matching_dates = [d for d in unique_dates if d in valid_dates]
                # if matching_dates:
                #     logger.info(f"[{item_code}] 페이지 {page}: 매칭되는 날짜 - {matching_dates}")
                # else:
                #     logger.warning(f"[{item_code}] 페이지 {page}: 검색 날짜와 매칭되는 날짜 없음!")
            
            # 필터링 전 데이터 백업 (디버깅용)
            df_before_filter = df.copy() if len(df) > 0 else df
            
            # 필터링 전 상세 정보 로깅 (중요: 디버깅용)
            if len(df_before_filter) > 0:
                all_dates_in_page = df_before_filter['날짜'].tolist()
                # logger.info(f"[{item_code}] 페이지 {page}: 필터링 전 모든 날짜 ({len(all_dates_in_page)}개) - {all_dates_in_page[:10]}")
                # logger.info(f"[{item_code}] 페이지 {page}: 검색 날짜 집합 - {valid_dates}")
                
                # 매칭 테스트
                matches = []
                for date_val in all_dates_in_page:
                    if date_val in valid_dates:
                        matches.append(date_val)
                # logger.info(f"[{item_code}] 페이지 {page}: 매칭되는 게시글 수 - {len(matches)}개")
                # if matches:
                #     logger.info(f"[{item_code}] 페이지 {page}: 매칭되는 날짜 값들 - {set(matches)}")
            
            df = df[df['날짜'].isin(valid_dates)]
            
            if df.empty:
                # logger.warning(f"[{item_code}] 페이지 {page}: 날짜 필터링 후 게시글 없음")
                if len(df_before_filter) > 0:
                    pass  # 날짜 필터링 실패 원인 분석 코드는 주석 처리됨
                    # logger.error(f"[{item_code}] ⚠️ 날짜 필터링 실패 원인 분석:")
                    # logger.error(f"[{item_code}]   - 필터링 전 게시글 수: {len(df_before_filter)}개")
                    # logger.error(f"[{item_code}]   - 검색 날짜: {valid_dates}")
                    # logger.error(f"[{item_code}]   - 정규화 후 날짜 샘플: {date_samples if 'date_samples' in locals() else 'N/A'}")
                    # logger.error(f"[{item_code}]   - 고유 날짜 형식: {unique_dates if 'unique_dates' in locals() else 'N/A'}")
                    
                    # 날짜 형식 비교 분석
                    # if 'unique_dates' in locals():
                    #     logger.error(f"[{item_code}]   - 검색 날짜와 실제 날짜 비교:")
                    #     for search_date in valid_dates:
                    #         if search_date in unique_dates:
                    #             logger.error(f"[{item_code}]     ✅ '{search_date}' 매칭됨")
                    #         else:
                    #             logger.error(f"[{item_code}]     ❌ '{search_date}' 매칭 안됨")
                    #             # 가장 유사한 날짜 찾기
                    #             similar = [d for d in unique_dates if search_date.split('.')[-2:] == d.split('.')[-2:]]
                    #             if similar:
                    #                 logger.error(f"[{item_code}]       유사한 날짜: {similar}")
                # 더 이상 유효한 날짜의 게시글이 없을 수 있으므로 break는 하지 않음
                # 하지만 연속으로 빈 페이지가 나오면 break
                if page > 1:  # 최소 1페이지는 확인
                    # logger.info(f"[{item_code}] 날짜 필터링 결과가 없어 크롤링 종료")
                    break
            # else:
            #     logger.info(f"[{item_code}] 페이지 {page}: 필터링 후 {len(df)}개 게시글 수집")

            for _, row in df.iterrows():
                if total >= max_rows:
                    break
                collected.append(row)
                total += 1

            if total >= max_rows:
                break
        except Exception as e:
            # logger.error(f"[{item_code}] 페이지 {page} 처리 중 오류: {e}", exc_info=True)
            # 페이지 처리 실패 시에도 계속 진행 (다음 페이지 시도)
            continue

    result_df = pd.DataFrame(collected)
    # logger.info(f"[{item_code}] 수집 완료: {pages_fetched}페이지 확인, 전체 {total_posts_before_filter}개 게시글 중 {len(result_df)}개 수집")
    
    if result_df.empty and total_posts_before_filter > 0:
        # logger.error(f"[{item_code}] ⚠️ 게시글은 있으나 날짜 필터링에서 제외됨")
        # logger.error(f"[{item_code}] 상세 분석:")
        # logger.error(f"[{item_code}]   - 전체 수집 게시글: {total_posts_before_filter}개")
        # logger.error(f"[{item_code}]   - 필터링 후 게시글: {len(result_df)}개")
        # logger.error(f"[{item_code}]   - 검색 날짜: {valid_dates}")
        # logger.error(f"[{item_code}]   - 원인: 날짜 정규화 실패 또는 실제 게시글 날짜가 검색 날짜와 다름")
        # logger.error(f"[{item_code}]   - 해결: 로그에서 '원본 날짜 샘플'과 '정규화 후 날짜 샘플' 확인 필요")
        pass
    
    return result_df
