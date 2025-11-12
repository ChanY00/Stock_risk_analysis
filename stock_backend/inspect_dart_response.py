#!/usr/bin/env python
"""
DART API 응답 구조 확인 스크립트
발행주식수 관련 항목을 찾습니다
"""
import os
import sys
import django
import json

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
    
    # DART API 호출
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
        
        # 발행주식수 관련 항목 찾기
        print("="*80)
        print("📋 발행주식수 관련 항목 (계정명에 '주식' 포함)")
        print("="*80)
        
        shares_related = []
        for item in list_data:
            account_nm = item.get('account_nm', '').strip()
            if '주식' in account_nm:
                shares_related.append(item)
        
        if not shares_related:
            print("⚠️  발행주식수 관련 항목을 찾을 수 없습니다.")
            print()
            print("전체 항목 중 자본 관련 항목 확인:")
            capital_related = [item for item in list_data if '자본' in item.get('account_nm', '')]
            for item in capital_related[:10]:
                print(f"  - {item.get('account_nm')}: {item.get('thstrm_amount', 'N/A')}")
        else:
            for i, item in enumerate(shares_related, 1):
                print(f"\n[{i}] {item.get('account_nm', 'N/A')}")
                print(f"    account_id: {item.get('account_id', 'N/A')}")
                print(f"    sj_nm: {item.get('sj_nm', 'N/A')}")
                print(f"    thstrm_amount: {item.get('thstrm_amount', 'N/A')}")
                print(f"    frmtrm_amount: {item.get('frmtrm_amount', 'N/A')}")
                
                # 숫자로 변환 시도
                thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                if thstrm and thstrm != '-':
                    try:
                        amount = int(thstrm)
                        if 1_000_000 <= amount <= 10_000_000_000:
                            print(f"    ✅ 후보 (범위 내): {amount:,}주")
                            
                            # DB 값과 비교
                            if stock.shares_outstanding:
                                diff = abs(amount - stock.shares_outstanding)
                                diff_percent = (diff / max(amount, stock.shares_outstanding)) * 100
                                if diff == 0:
                                    print(f"    ✅ DB와 일치!")
                                else:
                                    print(f"    ⚠️  DB와 차이: {diff:,}주 ({diff_percent:.2f}%)")
                    except ValueError:
                        pass
        
        # 전체 항목 중 'number' 또는 'share' 포함 항목 확인
        print()
        print("="*80)
        print("📋 account_id에 'number' 또는 'share' 포함 항목")
        print("="*80)
        
        number_related = []
        for item in list_data:
            account_id = item.get('account_id', '').lower()
            if 'number' in account_id or 'share' in account_id:
                number_related.append(item)
        
        if number_related:
            for i, item in enumerate(number_related[:5], 1):
                print(f"\n[{i}] {item.get('account_nm', 'N/A')}")
                print(f"    account_id: {item.get('account_id', 'N/A')}")
                print(f"    thstrm_amount: {item.get('thstrm_amount', 'N/A')}")
        else:
            print("⚠️  관련 항목을 찾을 수 없습니다.")
        
    else:
        print(f"❌ API 호출 실패: HTTP {response.status_code}")

if __name__ == '__main__':
    main()

