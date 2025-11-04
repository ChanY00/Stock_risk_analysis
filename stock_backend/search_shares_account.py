#!/usr/bin/env python
"""
DART API에서 발행주식수 계정명 정확히 찾기
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
        
        # 발행주식수 관련 키워드로 검색
        print("="*80)
        print("📋 발행주식수 관련 키워드 검색")
        print("="*80)
        
        keywords = [
            '보통주식수', '보통주 총수', '주식수', '발행주식수',
            '보통주', '상장주식수', '유통주식수', '보통주 발행주식수',
            'numberofshares', 'shares outstanding', 'common stock'
        ]
        
        candidates = []
        for item in list_data:
            account_nm = item.get('account_nm', '').strip()
            account_id = item.get('account_id', '').strip().lower()
            sj_nm = item.get('sj_nm', '').strip()
            
            # 키워드 매칭
            for keyword in keywords:
                if keyword.lower() in account_nm.lower() or keyword.lower() in account_id:
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    if not thstrm or thstrm == '-':
                        thstrm = item.get('frmtrm_amount', '').replace(',', '').strip()
                    
                    candidates.append({
                        'account_nm': account_nm,
                        'account_id': item.get('account_id', ''),
                        'sj_nm': sj_nm,
                        'thstrm_amount': thstrm,
                        'keyword': keyword
                    })
                    break
        
        if candidates:
            print(f"✅ {len(candidates)}개 후보 발견\n")
            for i, candidate in enumerate(candidates, 1):
                print(f"[{i}] {candidate['account_nm']}")
                print(f"    account_id: {candidate['account_id']}")
                print(f"    sj_nm: {candidate['sj_nm']}")
                print(f"    thstrm_amount: {candidate['thstrm_amount']}")
                print(f"    매칭 키워드: {candidate['keyword']}")
                
                # 숫자로 변환 시도
                if candidate['thstrm_amount'] and candidate['thstrm_amount'] != '-':
                    try:
                        amount = int(candidate['thstrm_amount'])
                        # 합리적인 범위 (100만~100억)
                        if 1_000_000 <= amount <= 100_000_000_000:
                            diff = abs(amount - stock.shares_outstanding)
                            diff_percent = (diff / max(amount, stock.shares_outstanding)) * 100 if max(amount, stock.shares_outstanding) > 0 else 100
                            print(f"    ✅ 후보! (DB와 {diff_percent:.2f}% 차이)")
                        elif amount > 100_000_000_000:
                            print(f"    ⚠️  금액으로 보임 (원 단위 가능성)")
                    except ValueError:
                        pass
                print()
        else:
            print("❌ 발행주식수 관련 항목을 찾을 수 없습니다.")
            print()
            print("재무상태표의 모든 항목 확인:")
            print("="*80)
            
            for item in list_data:
                if item.get('sj_nm', '').strip() == '재무상태표':
                    account_nm = item.get('account_nm', '').strip()
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    
                    # 숫자로 변환 시도
                    if thstrm and thstrm != '-':
                        try:
                            amount = int(thstrm)
                            # DB 값과 비교 (범위 체크)
                            if 1_000_000 <= amount <= 100_000_000_000:
                                diff = abs(amount - stock.shares_outstanding)
                                diff_percent = (diff / max(amount, stock.shares_outstanding)) * 100 if max(amount, stock.shares_outstanding) > 0 else 100
                                if diff_percent < 10.0:  # 10% 이내 차이
                                    print(f"✅ {account_nm}: {amount:,} (차이: {diff_percent:.2f}%)")
                        except ValueError:
                            pass

if __name__ == '__main__':
    main()

