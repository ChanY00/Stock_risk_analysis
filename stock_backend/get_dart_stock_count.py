#!/usr/bin/env python
"""
DART API getStockTotCnt를 사용하여 발행주식수 확인
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')
django.setup()

from stocks.models import Stock
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
import time

def get_corp_code(stock_code: str, api_key: str):
    """DART 고유번호 조회"""
    try:
        url = 'https://opendart.fss.or.kr/api/corpCode.xml'
        params = {'crtfc_key': api_key}
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            with zip_file.open('CORPCODE.xml') as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                
                for corp in root.findall('.//list'):
                    stock_cd = corp.find('stock_code')
                    corp_code_elem = corp.find('corp_code')
                    
                    if stock_cd is not None and corp_code_elem is not None:
                        if stock_cd.text == stock_code:
                            return corp_code_elem.text
        
        return None
    except Exception as e:
        print(f"❌ DART 고유번호 조회 실패: {e}")
        return None

def get_stock_tot_cnt(corp_code: str, api_key: str, year: int = 2024, reprt_code: str = '11014'):
    """
    DART API getStockTotCnt로 발행주식수 조회
    
    Args:
        corp_code: DART 고유번호
        api_key: DART API 키
        year: 사업연도
        reprt_code: 보고서 코드
            - 11013: 1분기보고서
            - 11012: 반기보고서
            - 11014: 3분기보고서
            - 11011: 사업보고서
    
    Returns:
        dict: {
            'isu_stock_tot_cnt': 발행주식 총수,
            'ordn_stk_cnt': 보통주식수,
            'prfr_stk_cnt': 우선주식수,
            'outcl_stock_cnt': 유통주식수,
            'year': 연도,
            'reprt_code': 보고서 코드
        }
    """
    # 재무제표 API에서 보통주식수 찾기
    # fnlttSinglAcntAll.json을 사용하여 재무상태표에서 보통주식수 찾기
    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': reprt_code,
        'fs_div': 'CFS'  # 연결재무제표
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') != '000':
                return None
            
            list_data = data.get('list', [])
            if not list_data:
                return None
            
            # 보통주식수 관련 항목 찾기
            # 정확한 계정명: "보통주식수", "보통주 총수", "주식수" 등
            target_accounts = [
                '보통주식수',
                '보통주 총수',
                '보통주 발행주식수',
                '주식수',
                '발행주식수',
            ]
            
            result = None
            
            for item in list_data:
                account_nm = item.get('account_nm', '').strip()
                account_id = item.get('account_id', '').strip()
                sj_nm = item.get('sj_nm', '').strip()
                
                # 재무상태표의 자본 관련 항목만 확인
                if sj_nm != '재무상태표':
                    continue
                
                # 계정명 매칭
                is_shares_account = False
                for target in target_accounts:
                    if target in account_nm:
                        is_shares_account = True
                        break
                
                # account_id로도 확인
                if not is_shares_account:
                    account_id_lower = account_id.lower()
                    if 'numberofshares' in account_id_lower or 'sharesoutstanding' in account_id_lower:
                        is_shares_account = True
                
                if is_shares_account:
                    # 당기금액 사용
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    if not thstrm or thstrm == '-':
                        thstrm = item.get('frmtrm_amount', '').replace(',', '').strip()
                    
                    if thstrm and thstrm != '-':
                        try:
                            shares = int(thstrm)
                            # 합리적인 범위 확인 (100만~100억주)
                            if 1_000_000 <= shares <= 100_000_000_000:
                                result = {
                                    'ordn_stk_cnt': shares,  # 보통주식수
                                    'account_nm': account_nm,
                                    'account_id': account_id,
                                    'year': year,
                                    'reprt_code': reprt_code,
                                }
                                break  # 찾았으면 중단
                        except ValueError:
                            continue
            
            return result
        
        return None
    except Exception as e:
        return None

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # 테스트할 종목들
    test_stocks = ['005930', '000660', '035420']  # 삼성전자, SK하이닉스, 네이버
    
    print("🔍 DART API getStockTotCnt로 발행주식수 확인\n")
    print("="*80)
    
    for stock_code in test_stocks:
        try:
            stock = Stock.objects.get(stock_code=stock_code)
            print(f"\n📊 {stock.stock_name} ({stock.stock_code})")
            print(f"DB 발행주식수: {stock.shares_outstanding:,}주" if stock.shares_outstanding else "DB 발행주식수: 없음")
            print()
            
            # DART 고유번호 조회
            corp_code = get_corp_code(stock_code, api_key)
            if not corp_code:
                print("  ❌ DART 고유번호를 찾을 수 없습니다.")
                continue
            
            print(f"  ✅ DART 고유번호: {corp_code}")
            
            # 최신 보고서 순서로 시도 (3분기 -> 반기 -> 1분기 -> 사업보고서)
            # 최신 연도부터 역순으로
            for year in [2024, 2023]:
                for reprt_code, reprt_name in [('11014', '3분기'), ('11012', '반기'), ('11013', '1분기'), ('11011', '사업보고서')]:
                    print(f"  🔍 {year}년 {reprt_name} 확인 중...")
                    
                    result = get_stock_tot_cnt(corp_code, api_key, year, reprt_code)
                    
                    if result and result.get('ordn_stk_cnt'):
                        ordn = result['ordn_stk_cnt']
                        account_nm = result.get('account_nm', '')
                        account_id = result.get('account_id', '')
                        
                        print(f"✅ 발견!")
                        print(f"     보통주식수: {ordn:,}주")
                        print(f"     계정명: {account_nm}")
                        print(f"     account_id: {account_id}")
                        print(f"     연도: {year}, 보고서: {reprt_name}")
                        
                        # DB 값과 비교
                        if stock.shares_outstanding:
                            db_shares = stock.shares_outstanding
                            
                            diff = abs(ordn - db_shares)
                            diff_percent = (diff / max(ordn, db_shares)) * 100 if max(ordn, db_shares) > 0 else 0
                            
                            print()
                            print(f"  📊 DB와 비교:")
                            print(f"     DB: {db_shares:,}주")
                            print(f"     DART: {ordn:,}주")
                            print(f"     차이: {diff:,}주 ({diff_percent:.2f}%)")
                            
                            if diff == 0:
                                print(f"     ✅ 완전 일치!")
                            elif diff_percent < 1.0:
                                print(f"     ⚠️  경미한 차이 (1% 미만)")
                            elif diff_percent < 5.0:
                                print(f"     ⚠️  차이 (1-5%)")
                            else:
                                print(f"     ❌ 불일치 (5% 이상)")
                            
                            print(f"  🔍 웹 검증:")
                            print(f"     네이버: https://search.naver.com/search.naver?query={stock.stock_name}+발행주식수")
                            print(f"     구글: https://www.google.com/search?q={stock.stock_name}+발행주식수")
                        
                        break  # 찾았으면 다음 종목으로
                    else:
                        print("❌")
                    
                    time.sleep(0.1)  # API 호출 제한 방지
                
                if result and result.get('isu_stock_tot_cnt'):
                    break  # 찾았으면 다음 종목으로
            
            if not result or not result.get('isu_stock_tot_cnt'):
                print("  ⚠️  발행주식수 정보를 찾을 수 없습니다.")
            
            print()
            print("-"*80)
            time.sleep(0.2)  # API 호출 제한 방지
            
        except Stock.DoesNotExist:
            print(f"\n❌ 종목 {stock_code}를 찾을 수 없습니다.")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()

