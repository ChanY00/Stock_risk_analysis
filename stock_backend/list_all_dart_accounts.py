#!/usr/bin/env python
"""
DART API 응답의 모든 계정명 확인
발행주식수 관련 항목을 찾기 위해 모든 항목을 확인합니다
"""
import os
import sys
import django
import json

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
    
    # 2024년 연결재무제표 확인
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
        
        # 재무상태표(자본 관련) 항목만 필터링
        print("="*80)
        print("📋 재무상태표 - 자본 관련 항목")
        print("="*80)
        
        capital_items = []
        for item in list_data:
            sj_nm = item.get('sj_nm', '').strip()
            if sj_nm == '재무상태표':
                account_nm = item.get('account_nm', '').strip()
                # 자본 관련 키워드
                if any(keyword in account_nm for keyword in ['자본', '주식', '자기', '지분', '자본금']):
                    capital_items.append(item)
        
        print(f"✅ 자본 관련 항목: {len(capital_items)}개\n")
        
        for i, item in enumerate(capital_items[:20], 1):  # 상위 20개
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
                    # DB 값과 비교
                    if stock.shares_outstanding:
                        diff = abs(amount - stock.shares_outstanding)
                        diff_percent = (diff / max(amount, stock.shares_outstanding)) * 100 if max(amount, stock.shares_outstanding) > 0 else 100
                        
                        # 합리적인 범위 (100만~100억)이고 DB와 유사한 경우
                        if 1_000_000 <= amount <= 100_000_000_000 and diff_percent < 10.0:
                            print(f"    ✅ 후보! (DB와 {diff_percent:.2f}% 차이)")
                except ValueError:
                    pass
            print()
        
        # account_id에 "share" 또는 "number" 포함하는 모든 항목
        print()
        print("="*80)
        print("📋 account_id에 'share' 또는 'number' 포함 항목 (전체)")
        print("="*80)
        
        share_number_items = []
        for item in list_data:
            account_id = item.get('account_id', '').lower()
            if 'share' in account_id or 'number' in account_id:
                share_number_items.append(item)
        
        print(f"✅ 관련 항목: {len(share_number_items)}개\n")
        
        for i, item in enumerate(share_number_items[:15], 1):
            print(f"[{i}] {item.get('account_nm', 'N/A')}")
            print(f"    account_id: {item.get('account_id', 'N/A')}")
            print(f"    sj_nm: {item.get('sj_nm', 'N/A')}")
            print(f"    thstrm_amount: {item.get('thstrm_amount', 'N/A')}")
            print()

if __name__ == '__main__':
    main()

