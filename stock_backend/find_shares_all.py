#!/usr/bin/env python
"""
DART API 응답에서 발행주식수 찾기 (모든 방법 시도)
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

def search_shares_in_dart(corp_code: str, api_key: str, year: int, fs_div: str = 'CFS'):
    """DART API에서 발행주식수 찾기"""
    url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
    params = {
        'crtfc_key': api_key,
        'corp_code': corp_code,
        'bsns_year': str(year),
        'reprt_code': '11011',  # 사업보고서
        'fs_div': fs_div
    }
    
    try:
        response = requests.get(url, params=params, timeout=20)
        if response.status_code == 200:
            data = response.json()
            
            if data.get('status') != '000':
                return None, []
            
            list_data = data.get('list', [])
            
            # 발행주식수 후보 찾기
            candidates = []
            
            # 키워드 패턴
            keywords = ['주식수', '보통주', '발행', '주식', 'number', 'share', 'stock']
            
            for item in list_data:
                account_nm = item.get('account_nm', '').strip()
                account_id = item.get('account_id', '').strip().lower()
                sj_nm = item.get('sj_nm', '').strip()
                
                # 키워드 매칭
                matches_keyword = False
                for keyword in keywords:
                    if keyword in account_nm.lower() or keyword in account_id:
                        matches_keyword = True
                        break
                
                if matches_keyword:
                    # 금액 확인
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    if not thstrm or thstrm == '-':
                        thstrm = item.get('frmtrm_amount', '').replace(',', '').strip()
                    
                    if thstrm and thstrm != '-':
                        try:
                            amount = int(thstrm)
                            # 합리적인 범위 (100만~100억)
                            if 1_000_000 <= amount <= 100_000_000_000:
                                candidates.append({
                                    'account_nm': account_nm,
                                    'account_id': item.get('account_id', ''),
                                    'sj_nm': sj_nm,
                                    'amount': amount,
                                    'year': year,
                                    'fs_div': fs_div,
                                })
                        except ValueError:
                            pass
            
            return len(list_data), candidates
    except Exception as e:
        print(f"  ❌ 오류: {e}")
        return None, []
    
    return None, []

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
    
    all_candidates = []
    
    # 다양한 조합 시도
    print("🔍 DART API 응답 확인 중...")
    print()
    
    for year in [2024, 2023]:
        for fs_div in ['CFS', 'OFS']:  # 연결재무제표, 별도재무제표
            print(f"  {year}년 {fs_div} 확인 중...", end=' ')
            total, candidates = search_shares_in_dart(corp_code, api_key, year, fs_div)
            
            if total:
                print(f"✅ {total}개 항목, 후보 {len(candidates)}개")
                all_candidates.extend(candidates)
            else:
                print("❌ 실패")
            
            time.sleep(0.1)  # API 호출 제한 방지
    
    print()
    print("="*80)
    print("📋 발행주식수 후보 (정리)")
    print("="*80)
    
    if not all_candidates:
        print("❌ 발행주식수 후보를 찾을 수 없습니다.")
        return
    
    # 중복 제거 및 정렬
    unique_candidates = {}
    for candidate in all_candidates:
        key = f"{candidate['account_nm']}_{candidate['account_id']}"
        if key not in unique_candidates:
            unique_candidates[key] = candidate
    
    # DB 값과 비교하여 정렬
    db_shares = stock.shares_outstanding
    sorted_candidates = sorted(
        unique_candidates.values(),
        key=lambda x: abs(x['amount'] - db_shares)
    )
    
    print(f"✅ 총 {len(sorted_candidates)}개 고유 후보 발견\n")
    
    for i, candidate in enumerate(sorted_candidates[:15], 1):  # 상위 15개
        diff = abs(candidate['amount'] - db_shares)
        diff_percent = (diff / max(candidate['amount'], db_shares)) * 100 if max(candidate['amount'], db_shares) > 0 else 100
        
        print(f"[{i}] {candidate['account_nm']}")
        print(f"    account_id: {candidate['account_id']}")
        print(f"    재무제표: {candidate['sj_nm']} ({candidate['fs_div']})")
        print(f"    연도: {candidate['year']}")
        print(f"    금액: {candidate['amount']:,}주")
        print(f"    DB와 차이: {diff:,}주 ({diff_percent:.2f}%)")
        
        if diff_percent < 1.0:
            print(f"    ✅ 매우 유사!")
        elif diff_percent < 5.0:
            print(f"    ⚠️  유사 (확인 필요)")
        print()

if __name__ == '__main__':
    main()

