#!/usr/bin/env python
"""
재무상태표의 모든 항목을 확인하여 발행주식수 찾기
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
    
    # 2024년 사업보고서 확인
    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': '2024',
        'reprt_code': '11011',  # 사업보고서
        'fs_div': 'CFS'  # 연결재무제표
    }
    
    print("🔍 DART API 호출 중...")
    response = requests.get(url, params=params, timeout=20)
    
    if response.status_code == 200:
        data = response.json()
        
        if data.get('status') != '000':
            print(f"❌ API 오류: {data.get('message')}")
            return
        
        list_data = data.get('list', [])
        print(f"✅ 총 {len(list_data)}개 항목 발견")
        print()
        
        # 재무상태표의 모든 항목 출력
        print("="*80)
        print("📋 재무상태표의 모든 항목 (자본 관련)")
        print("="*80)
        
        balance_sheet_items = []
        for item in list_data:
            sj_nm = item.get('sj_nm', '').strip()
            if sj_nm == '재무상태표':
                balance_sheet_items.append(item)
        
        print(f"✅ 재무상태표 항목: {len(balance_sheet_items)}개\n")
        
        # 자본 관련 키워드로 필터링
        capital_keywords = ['자본', '주식', '자기', '지분', '자본금', '주', 'share', 'capital', 'equity']
        
        capital_items = []
        for item in balance_sheet_items:
            account_nm = item.get('account_nm', '').strip()
            account_id = item.get('account_id', '').strip().lower()
            
            for keyword in capital_keywords:
                if keyword in account_nm.lower() or keyword in account_id:
                    capital_items.append(item)
                    break
        
        print(f"✅ 자본 관련 항목: {len(capital_items)}개\n")
        
        # DB 값과 비교 가능한 항목 찾기
        db_shares = stock.shares_outstanding
        
        for i, item in enumerate(capital_items, 1):
            account_nm = item.get('account_nm', '').strip()
            account_id = item.get('account_id', '').strip()
            thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
            
            print(f"[{i}] {account_nm}")
            print(f"    account_id: {account_id}")
            print(f"    thstrm_amount: {thstrm}")
            
            # 숫자로 변환 시도
            if thstrm and thstrm != '-':
                try:
                    amount = int(thstrm)
                    
                    # DB 값과 비교 (범위 체크)
                    if 1_000_000 <= amount <= 100_000_000_000:
                        diff = abs(amount - db_shares)
                        diff_percent = (diff / max(amount, db_shares)) * 100 if max(amount, db_shares) > 0 else 100
                        
                        if diff_percent < 10.0:  # 10% 이내 차이
                            print(f"    ✅ 후보! (DB와 {diff_percent:.2f}% 차이)")
                            if diff_percent < 1.0:
                                print(f"    🎯 매우 유사한 값!")
                        else:
                            print(f"    (DB와 {diff_percent:.2f}% 차이)")
                    elif amount > 100_000_000_000:
                        print(f"    ⚠️  금액으로 보임 (원 단위)")
                except ValueError:
                    pass
            print()

if __name__ == '__main__':
    main()

