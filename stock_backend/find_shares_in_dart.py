#!/usr/bin/env python
"""
DART API 응답에서 발행주식수 찾기
모든 항목을 확인하여 발행주식수 후보를 찾습니다
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

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    stock_code = '005930'  # 삼성전자
    stock = Stock.objects.get(stock_code=stock_code)
    
    print(f"📊 {stock.stock_name} ({stock.stock_code})")
    print(f"DB 발행주식수: {stock.shares_outstanding:,}주")
    print()
    
    corp_code = get_corp_code(stock_code, api_key)
    if not corp_code:
        print("❌ DART 고유번호를 찾을 수 없습니다.")
        return
    
    print(f"✅ DART 고유번호: {corp_code}")
    print()
    
    # 여러 연도 시도
    for year in [2024, 2023]:
        print(f"🔍 {year}년 데이터 확인 중...")
        
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
            
            if data.get('status') != '000':
                print(f"  ⚠️  API 오류: {data.get('message')}")
                continue
            
            list_data = data.get('list', [])
            print(f"  ✅ 총 {len(list_data)}개 항목 발견")
            
            # DB 값과 유사한 범위의 숫자 찾기 (100만~100억 사이)
            db_shares = stock.shares_outstanding
            candidates = []
            
            for item in list_data:
                account_nm = item.get('account_nm', '').strip()
                account_id = item.get('account_id', '').strip()
                sj_nm = item.get('sj_nm', '').strip()
                
                # 당기금액 확인
                thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                if thstrm and thstrm != '-':
                    try:
                        amount = int(thstrm)
                        # 합리적인 범위 (100만~100억)
                        if 1_000_000 <= amount <= 100_000_000_000:
                            # DB 값과 비교 (10% 이내 차이)
                            diff_percent = abs(amount - db_shares) / max(amount, db_shares) * 100 if max(amount, db_shares) > 0 else 100
                            if diff_percent < 10.0:  # 10% 이내 차이
                                candidates.append({
                                    'account_nm': account_nm,
                                    'account_id': account_id,
                                    'sj_nm': sj_nm,
                                    'amount': amount,
                                    'diff_percent': diff_percent,
                                })
                    except ValueError:
                        pass
            
            if candidates:
                print(f"  ✅ 후보 발견: {len(candidates)}개")
                print()
                print("="*80)
                print(f"📋 발행주식수 후보 (DB 값과 10% 이내 차이)")
                print("="*80)
                
                # DB 값과 가장 가까운 순으로 정렬
                candidates.sort(key=lambda x: x['diff_percent'])
                
                for i, candidate in enumerate(candidates[:10], 1):  # 상위 10개만
                    print(f"\n[{i}] {candidate['account_nm']}")
                    print(f"    account_id: {candidate['account_id']}")
                    print(f"    sj_nm: {candidate['sj_nm']}")
                    print(f"    금액: {candidate['amount']:,}주")
                    print(f"    DB와 차이: {candidate['diff_percent']:.2f}%")
                    
                    if candidate['diff_percent'] < 1.0:
                        print(f"    ✅ 매우 유사한 값!")
                    elif candidate['diff_percent'] < 5.0:
                        print(f"    ⚠️  유사한 값 (확인 필요)")
                
                break  # 찾았으면 중단
        
        import time
        time.sleep(0.2)  # API 호출 제한 방지

if __name__ == '__main__':
    main()

