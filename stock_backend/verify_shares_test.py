#!/usr/bin/env python
"""
발행주식수 검증 테스트 스크립트
DART API와 DB 값을 비교
"""
import os
import sys
import django

# Django 설정
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')
django.setup()

from stocks.models import Stock
import requests
import io
import zipfile
import xml.etree.ElementTree as ET

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

def get_shares_from_dart(corp_code: str, api_key: str, year: int = 2024):
    """DART API에서 발행주식수 가져오기"""
    try:
        url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        params = {
            'crtfc_key': api_key,
            'corp_code': corp_code,
            'bsns_year': str(year),
            'reprt_code': '11011',  # 사업보고서
            'fs_div': 'CFS'  # 연결재무제표
        }
        
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '000':
                list_data = data.get('list', [])
                
                # 발행주식수 관련 항목 찾기
                target_accounts = [
                    '보통주식수',
                    '보통주 총수',
                    '주식수',
                    '발행주식수',
                    '보통주',
                    '보통주 발행주식수',
                ]
                
                for item in list_data:
                    account_nm = item.get('account_nm', '').strip()
                    account_id = item.get('account_id', '').strip()
                    
                    # 주식수 관련 항목 찾기
                    is_shares_account = False
                    for target in target_accounts:
                        if target in account_nm:
                            is_shares_account = True
                            break
                    
                    if not is_shares_account:
                        if 'share' in account_id.lower() or 'number' in account_id.lower():
                            is_shares_account = True
                    
                    if is_shares_account:
                        # 당기금액(thstrm_amount) 사용
                        thstrm_amount = item.get('thstrm_amount', '').replace(',', '').strip()
                        if not thstrm_amount or thstrm_amount == '-' or thstrm_amount == '':
                            # 전기금액(frmtrm_amount) 시도
                            thstrm_amount = item.get('frmtrm_amount', '').replace(',', '').strip()
                        
                        if thstrm_amount and thstrm_amount != '-' and thstrm_amount != '':
                            try:
                                shares = int(thstrm_amount)
                                # 합리적인 범위 확인 (100만~100억주)
                                if 1_000_000 <= shares <= 10_000_000_000:
                                    return {
                                        'shares': shares,
                                        'account_nm': account_nm,
                                        'account_id': account_id,
                                    }
                            except ValueError:
                                continue
        
        return None
    except Exception as e:
        print(f"❌ DART API 호출 실패: {e}")
        return None

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # 삼성전자로 테스트
    stock_code = '005930'
    try:
        stock = Stock.objects.get(stock_code=stock_code)
        print(f"📊 {stock.stock_name} ({stock.stock_code}) 검증 시작")
        print(f"DB 발행주식수: {stock.shares_outstanding:,}주")
        print()
        
        # DART 고유번호 조회
        print("🔍 DART 고유번호 조회 중...")
        corp_code = get_corp_code(stock_code, api_key)
        if not corp_code:
            print("❌ DART 고유번호를 찾을 수 없습니다.")
            return
        
        print(f"✅ DART 고유번호: {corp_code}")
        print()
        
        # DART API에서 발행주식수 가져오기
        print("🔍 DART API에서 발행주식수 조회 중...")
        dart_result = get_shares_from_dart(corp_code, api_key, 2024)
        
        if not dart_result:
            print("❌ DART API에서 발행주식수를 가져올 수 없습니다.")
            return
        
        dart_shares = dart_result['shares']
        print(f"✅ DART 발행주식수: {dart_shares:,}주")
        print(f"   계정명: {dart_result['account_nm']}")
        print(f"   account_id: {dart_result['account_id']}")
        print()
        
        # 비교
        print("="*60)
        print("📊 검증 결과")
        print("="*60)
        
        db_shares = stock.shares_outstanding
        if db_shares == dart_shares:
            print(f"✅ 일치: DB={db_shares:,}주, DART={dart_shares:,}주")
        else:
            diff = abs(dart_shares - db_shares)
            diff_percent = (diff / max(db_shares, dart_shares)) * 100
            print(f"❌ 불일치:")
            print(f"   DB: {db_shares:,}주")
            print(f"   DART: {dart_shares:,}주")
            print(f"   차이: {diff:,}주 ({diff_percent:.2f}%)")
            print()
            print(f"🔍 웹 검증:")
            print(f"   네이버: https://search.naver.com/search.naver?query={stock.stock_name}+발행주식수")
            print(f"   구글: https://www.google.com/search?q={stock.stock_name}+발행주식수")
        
    except Stock.DoesNotExist:
        print(f"❌ 종목 {stock_code}를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

