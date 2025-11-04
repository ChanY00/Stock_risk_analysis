#!/usr/bin/env python
"""
여러 종목으로 DART API에서 발행주식수 찾기
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
        return None

def search_shares_in_dart(corp_code: str, api_key: str, year: int = 2024):
    """DART API에서 발행주식수 찾기"""
    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': '11011',
        'fs_div': 'CFS'
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == '000':
                list_data = data.get('list', [])
                
                # 모든 항목에서 DB 값과 유사한 숫자 찾기
                candidates = []
                for item in list_data:
                    account_nm = item.get('account_nm', '').strip()
                    account_id = item.get('account_id', '').strip()
                    sj_nm = item.get('sj_nm', '').strip()
                    
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    if not thstrm or thstrm == '-':
                        thstrm = item.get('frmtrm_amount', '').replace(',', '').strip()
                    
                    if thstrm and thstrm != '-':
                        try:
                            amount = int(thstrm)
                            candidates.append({
                                'account_nm': account_nm,
                                'account_id': account_id,
                                'sj_nm': sj_nm,
                                'amount': amount
                            })
                        except ValueError:
                            pass
                
                return list_data, candidates
    except Exception as e:
        pass
    
    return None, []

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # 여러 종목 테스트
    test_stocks = ['005930', '000660', '035420']  # 삼성전자, SK하이닉스, 네이버
    
    print("🔍 여러 종목으로 DART API 발행주식수 검색\n")
    
    for stock_code in test_stocks:
        try:
            stock = Stock.objects.get(stock_code=stock_code)
            print(f"\n{'='*80}")
            print(f"📊 {stock.stock_name} ({stock.stock_code})")
            print(f"DB 발행주식수: {stock.shares_outstanding:,}주")
            print(f"{'='*80}")
            
            corp_code = get_corp_code(stock_code, api_key)
            if not corp_code:
                print("  ❌ DART 고유번호를 찾을 수 없습니다.")
                continue
            
            print(f"  ✅ DART 고유번호: {corp_code}")
            
            list_data, candidates = search_shares_in_dart(corp_code, api_key, 2024)
            
            if not list_data:
                print("  ❌ DART API 호출 실패")
                continue
            
            print(f"  ✅ 총 {len(list_data)}개 항목 발견")
            
            # DB 값과 유사한 범위의 숫자 찾기
            db_shares = stock.shares_outstanding
            matches = []
            
            for candidate in candidates:
                amount = candidate['amount']
                # 합리적인 범위 (100만~100억)
                if 1_000_000 <= amount <= 100_000_000_000:
                    diff = abs(amount - db_shares)
                    diff_percent = (diff / max(amount, db_shares)) * 100 if max(amount, db_shares) > 0 else 100
                    if diff_percent < 10.0:  # 10% 이내 차이
                        matches.append({
                            **candidate,
                            'diff': diff,
                            'diff_percent': diff_percent
                        })
            
            if matches:
                # 가장 가까운 순으로 정렬
                matches.sort(key=lambda x: x['diff_percent'])
                
                print(f"  ✅ {len(matches)}개 후보 발견\n")
                
                for i, match in enumerate(matches[:5], 1):  # 상위 5개
                    print(f"  [{i}] {match['account_nm']}")
                    print(f"      account_id: {match['account_id']}")
                    print(f"      sj_nm: {match['sj_nm']}")
                    print(f"      금액: {match['amount']:,}")
                    print(f"      DB와 차이: {match['diff_percent']:.2f}%")
                    
                    if match['diff_percent'] < 1.0:
                        print(f"      ✅ 매우 유사!")
                    print()
            else:
                print(f"  ⚠️  DB 값과 유사한 항목을 찾을 수 없습니다.")
                print(f"  💡 DART API 응답에 발행주식수(주 단위)가 없을 수 있습니다.")
                print(f"  💡 다른 보고서 형식이나 다른 엔드포인트를 확인해야 할 수 있습니다.")
            
            time.sleep(0.2)  # API 호출 제한 방지
            
        except Stock.DoesNotExist:
            print(f"\n❌ 종목 {stock_code}를 찾을 수 없습니다.")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()

