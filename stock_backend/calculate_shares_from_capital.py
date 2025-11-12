#!/usr/bin/env python
"""
재무제표에서 자본금과 액면가로 발행주식수 계산
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

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # 테스트할 종목들
    test_stocks = ['005930', '000660', '035420']  # 삼성전자, SK하이닉스, 네이버
    
    print("🔍 재무제표에서 자본금과 액면가로 발행주식수 계산\n")
    print("="*80)
    
    for stock_code in test_stocks:
        try:
            stock = Stock.objects.get(stock_code=stock_code)
            print(f"\n📊 {stock.stock_name} ({stock.stock_code})")
            print(f"DB 발행주식수: {stock.shares_outstanding:,}주" if stock.shares_outstanding else "DB 발행주식수: 없음")
            print()
            
            corp_code = get_corp_code(stock_code, api_key)
            if not corp_code:
                print("  ❌ DART 고유번호를 찾을 수 없습니다.")
                continue
            
            print(f"  ✅ DART 고유번호: {corp_code}")
            
            # 2024년 사업보고서 확인
            url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
            params = {
                'crtfc_key': api_key,
                'corp_code': corp_code,
                'bsns_year': '2024',
                'reprt_code': '11011',  # 사업보고서
                'fs_div': 'CFS'  # 연결재무제표
            }
            
            print("  🔍 DART API 호출 중...")
            response = requests.get(url, params=params, timeout=20)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('status') != '000':
                    print(f"  ❌ API 오류: {data.get('message')}")
                    continue
                
                list_data = data.get('list', [])
                print(f"  ✅ 총 {len(list_data)}개 항목 발견")
                print()
                
                # 자본금과 액면가 찾기
                common_stock_capital = None  # 보통주자본금
                par_value = None  # 주당 액면가
                
                print("  🔍 재무상태표에서 자본 관련 항목 찾기...")
                
                for item in list_data:
                    account_nm = item.get('account_nm', '').strip()
                    account_id = item.get('account_id', '').strip()
                    sj_nm = item.get('sj_nm', '').strip()
                    
                    if sj_nm != '재무상태표':
                        continue
                    
                    # 보통주자본금 찾기
                    if '보통주자본금' in account_nm or 'dart_IssuedCapitalOfCommonStock' in account_id:
                        thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                        if thstrm and thstrm != '-':
                            try:
                                common_stock_capital = int(thstrm)
                                print(f"  ✅ 보통주자본금: {common_stock_capital:,}원")
                            except ValueError:
                                pass
                    
                    # 주당 액면가 찾기 (재무상태표에 없을 수도 있음)
                    # 보통 500원 또는 100원
                    if '액면가' in account_nm or 'par' in account_id.lower():
                        thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                        if thstrm and thstrm != '-':
                            try:
                                par_value = int(thstrm)
                                print(f"  ✅ 주당 액면가: {par_value:,}원")
                            except ValueError:
                                pass
                
                # 액면가가 없으면 일반적인 값 사용 (500원 또는 100원)
                if not par_value:
                    print("  ⚠️  주당 액면가를 찾을 수 없습니다.")
                    print("  💡 일반적인 액면가로 시도: 500원, 100원")
                    
                    for test_par in [500, 100]:
                        if common_stock_capital:
                            calculated = common_stock_capital // test_par
                            print(f"\n  액면가 {test_par}원 가정:")
                            print(f"    계산된 발행주식수: {calculated:,}주")
                            
                            if stock.shares_outstanding:
                                db_shares = stock.shares_outstanding
                                diff = abs(calculated - db_shares)
                                diff_percent = (diff / max(calculated, db_shares)) * 100 if max(calculated, db_shares) > 0 else 0
                                
                                print(f"    DB: {db_shares:,}주")
                                print(f"    차이: {diff:,}주 ({diff_percent:.2f}%)")
                                
                                if diff_percent < 1.0:
                                    print(f"    ✅ 매우 유사! (액면가 {test_par}원일 가능성)")
                                    par_value = test_par
                                    break
                else:
                    # 액면가가 있으면 계산
                    if common_stock_capital and par_value > 0:
                        calculated_shares = common_stock_capital // par_value
                        print(f"\n  ✅ 계산된 발행주식수: {calculated_shares:,}주")
                        print(f"     계산식: 자본금({common_stock_capital:,}원) ÷ 액면가({par_value:,}원)")
                        
                        # DB 값과 비교
                        if stock.shares_outstanding:
                            db_shares = stock.shares_outstanding
                            diff = abs(calculated_shares - db_shares)
                            diff_percent = (diff / max(calculated_shares, db_shares)) * 100 if max(calculated_shares, db_shares) > 0 else 0
                            
                            print(f"\n  📊 DB와 비교:")
                            print(f"     DB: {db_shares:,}주")
                            print(f"     계산값: {calculated_shares:,}주")
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
                    else:
                        print("  ⚠️  보통주자본금을 찾을 수 없습니다.")
            
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

