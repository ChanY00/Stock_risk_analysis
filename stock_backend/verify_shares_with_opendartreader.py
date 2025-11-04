#!/usr/bin/env python
"""
OpenDartReader를 사용하여 발행주식수 검증
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')
django.setup()

from stocks.models import Stock
import OpenDartReader
import time

def get_corp_code_from_stock_code(dart, stock_code: str):
    """종목코드로 DART 고유번호 찾기"""
    try:
        # OpenDartReader의 corp_codes 속성 사용
        corp_list = dart.corp_codes
        
        # 종목코드로 검색
        matching = corp_list[corp_list['stock_code'] == stock_code]
        
        if not matching.empty:
            return matching.iloc[0]['corp_code']
        
        return None
    except Exception as e:
        print(f"  ⚠️  고유번호 조회 오류: {e}")
        return None

def get_shares_from_opendartreader(dart, corp_code: str, year: int = 2024):
    """
    OpenDartReader를 사용하여 발행주식수 조회
    
    여러 방법 시도:
    1. report() 메서드로 '주식총수현황' 조회
    2. company() 메서드로 기업 정보 조회
    3. finstate() 메서드로 재무제표에서 찾기
    """
    result = None
    
    # 방법 1: report() 메서드로 '주식총수' 조회
    try:
        print(f"  🔍 report() 메서드로 주식총수 조회 시도...")
        stock_tot_report = dart.report(corp_code, '주식총수', str(year))
        
        if stock_tot_report is not None and not stock_tot_report.empty:
            print(f"  ✅ report() 메서드 성공")
            print(f"  응답 형태: {type(stock_tot_report)}")
            print(f"  컬럼: {list(stock_tot_report.columns) if hasattr(stock_tot_report, 'columns') else 'N/A'}")
            
            # 발행주식수 관련 컬럼 찾기
            if hasattr(stock_tot_report, 'columns'):
                    # DataFrame인 경우
                    print(f"  DataFrame 컬럼: {list(stock_tot_report.columns)}")
                    
                    # 'se' 컬럼이 있으면 '보통주'만 필터링
                    if 'se' in stock_tot_report.columns:
                        common_stock = stock_tot_report[stock_tot_report['se'] == '보통주']
                        if not common_stock.empty:
                            print(f"  ✅ 보통주 데이터 발견: {len(common_stock)}개")
                            stock_tot_report = common_stock
                    
                    # 발행주식수 관련 컬럼 찾기
                    # 우선순위: 현재 발행주식수 > 발행주식 총수 > 유통주식수
                    possible_cols = ['now_to_isu_stock_totqy', 'isu_stock_totqy', 'distb_stock_co']
                    for col in possible_cols:
                        if col in stock_tot_report.columns:
                            shares = stock_tot_report[col].iloc[0]
                            if shares and shares != '-':
                                try:
                                    shares_int = int(str(shares).replace(',', ''))
                                    if 1_000_000 <= shares_int <= 100_000_000_000:
                                        result = {
                                            'shares': shares_int,
                                            'method': 'report',
                                            'source': f'주식총수/{col}',
                                            'year': year,
                                        }
                                        print(f"  ✅ 발행주식수 발견: {shares_int:,}주 (컬럼: {col})")
                                        break
                                except (ValueError, AttributeError):
                                    continue
                    
                    # 첫 번째 행의 모든 값 확인
                    if not result and len(stock_tot_report) > 0:
                        first_row = stock_tot_report.iloc[0]
                        print(f"  첫 번째 행 샘플:")
                        for key, value in first_row.items():
                            print(f"    {key}: {value}")
                            
                            # 숫자 값 중 발행주식수 범위에 맞는 것 찾기
                            if value and value != '-':
                                try:
                                    shares_int = int(str(value).replace(',', ''))
                                    if 1_000_000 <= shares_int <= 100_000_000_000:
                                        result = {
                                            'shares': shares_int,
                                            'method': 'report',
                                            'source': f'주식총수/{key}',
                                            'year': year,
                                        }
                                        print(f"  ✅ 발행주식수 후보 발견: {shares_int:,}주 (컬럼: {key})")
                                        break
                                except (ValueError, AttributeError):
                                    continue
    except Exception as e:
        print(f"  ⚠️  report() 메서드 오류: {e}")
    
    # 방법 2: company() 메서드로 기업 정보 조회
    if not result:
        try:
            print(f"  🔍 company() 메서드로 기업 정보 조회 시도...")
            company_info = dart.company(corp_code)
            
            if company_info is not None:
                print(f"  ✅ company() 메서드 성공")
                print(f"  응답 형태: {type(company_info)}")
                
                if isinstance(company_info, dict):
                    print(f"  응답 키: {list(company_info.keys())[:10]}")
                    
                    # 발행주식수 관련 키 찾기
                    stock_keys = [k for k in company_info.keys() if 'stock' in k.lower() or 'share' in k.lower() or '주식' in k]
                    if stock_keys:
                        print(f"  주식수 관련 키: {stock_keys}")
                        for key in stock_keys:
                            value = company_info[key]
                            print(f"    {key}: {value}")
                            
                            # 숫자로 변환 시도
                            if value and value != '-':
                                try:
                                    shares_int = int(str(value).replace(',', ''))
                                    if 1_000_000 <= shares_int <= 100_000_000_000:
                                        result = {
                                            'shares': shares_int,
                                            'method': 'company',
                                            'source': key,
                                            'year': year,
                                        }
                                        break
                                except (ValueError, AttributeError):
                                    continue
                elif hasattr(company_info, 'to_dict'):
                    # DataFrame인 경우
                    company_dict = company_info.to_dict()
                    print(f"  DataFrame을 dict로 변환: {company_dict}")
        except Exception as e:
            print(f"  ⚠️  company() 메서드 오류: {e}")
    
    # 방법 3: finstate() 메서드로 재무제표에서 찾기
    if not result:
        try:
            print(f"  🔍 finstate() 메서드로 재무제표 조회 시도...")
            # 최신 보고서 시도 (사업보고서)
            finstate = dart.finstate(corp_code, str(year), '11011')  # 사업보고서
            
            if finstate is not None and not finstate.empty:
                print(f"  ✅ finstate() 메서드 성공")
                print(f"  응답 형태: {type(finstate)}")
                print(f"  컬럼: {list(finstate.columns) if hasattr(finstate, 'columns') else 'N/A'}")
                
                # 재무상태표(sj_nm == '재무상태표')에서 '보통주식수' 또는 '발행주식수' 항목 찾기
                balance_sheet = finstate[finstate['sj_nm'] == '재무상태표']
                
                if not balance_sheet.empty:
                    print(f"  재무상태표 항목: {len(balance_sheet)}개")
                    
                    # '보통주식수' 또는 '발행주식수' 항목 찾기
                    target_accounts = ['보통주식수', '보통주 총수', '발행주식수', '주식수', '보통주']
                    
                    for account in target_accounts:
                        matching = balance_sheet[balance_sheet['account_nm'].str.contains(account, na=False)]
                        if not matching.empty:
                            # 가장 최신 항목 사용
                            thstrm_amount = matching.iloc[0]['thstrm_amount']
                            if thstrm_amount and thstrm_amount != '-':
                                try:
                                    shares_int = int(str(thstrm_amount).replace(',', ''))
                                    if 1_000_000 <= shares_int <= 100_000_000_000:
                                        result = {
                                            'shares': shares_int,
                                            'method': 'finstate',
                                            'source': f'{account} (재무상태표)',
                                            'year': year,
                                        }
                                        print(f"  ✅ 발행주식수 발견: {shares_int:,}주 (항목: {account})")
                                        break
                                except (ValueError, AttributeError):
                                    continue
                    
                    # account_nm에 '주식' 포함된 모든 항목 출력 (찾지 못한 경우)
                    if not result:
                        stock_related = balance_sheet[balance_sheet['account_nm'].str.contains('주식', na=False)]
                        if not stock_related.empty:
                            print(f"  주식 관련 항목 (재무상태표):")
                            for idx, row in stock_related.head(10).iterrows():
                                account_nm = row['account_nm']
                                thstrm = row.get('thstrm_amount', 'N/A')
                                print(f"    - {account_nm}: {thstrm}")
                                
                                # 숫자 값 중 발행주식수 범위에 맞는 것 찾기
                                if thstrm and thstrm != '-' and thstrm != 'N/A':
                                    try:
                                        shares_int = int(str(thstrm).replace(',', ''))
                                        if 1_000_000 <= shares_int <= 100_000_000_000:
                                            result = {
                                                'shares': shares_int,
                                                'method': 'finstate',
                                                'source': f'{account_nm} (재무상태표)',
                                                'year': year,
                                            }
                                            print(f"  ✅ 발행주식수 후보 발견: {shares_int:,}주 (항목: {account_nm})")
                                            break
                                    except (ValueError, AttributeError):
                                        continue
        except Exception as e:
            print(f"  ⚠️  finstate() 메서드 오류: {e}")
    
    return result

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # OpenDartReader 초기화
    print("🔍 OpenDartReader를 사용하여 발행주식수 검증\n")
    
    try:
        dart = OpenDartReader(api_key)
        print("✅ OpenDartReader 초기화 성공")
        print()
    except Exception as e:
        print(f"❌ OpenDartReader 초기화 실패: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 테스트할 종목들
    test_stocks = ['005930', '000660', '035420']  # 삼성전자, SK하이닉스, 네이버
    
    print("="*80)
    
    for stock_code in test_stocks:
        try:
            stock = Stock.objects.get(stock_code=stock_code)
            print(f"\n📊 {stock.stock_name} ({stock.stock_code})")
            print(f"DB 발행주식수: {stock.shares_outstanding:,}주" if stock.shares_outstanding else "DB 발행주식수: 없음")
            print()
            
            # DART 고유번호 찾기
            print("🔍 DART 고유번호 조회 중...")
            corp_code = get_corp_code_from_stock_code(dart, stock_code)
            
            if not corp_code:
                print("  ❌ DART 고유번호를 찾을 수 없습니다.")
                continue
            
            print(f"  ✅ DART 고유번호: {corp_code}")
            print()
            
            # 발행주식수 조회
            print("="*80)
            print("📋 OpenDartReader로 발행주식수 조회")
            print("="*80)
            
            result = get_shares_from_opendartreader(dart, corp_code, 2024)
            
            if result:
                dart_shares = result['shares']
                method = result['method']
                source = result['source']
                
                print()
                print(f"✅ 발행주식수 발견!")
                print(f"   방법: {method}")
                print(f"   출처: {source}")
                print(f"   발행주식수: {dart_shares:,}주")
                print()
                
                # DB 값과 비교
                if stock.shares_outstanding:
                    db_shares = stock.shares_outstanding
                    diff = abs(dart_shares - db_shares)
                    diff_percent = (diff / max(dart_shares, db_shares)) * 100 if max(dart_shares, db_shares) > 0 else 0
                    
                    print(f"📊 DB와 비교:")
                    print(f"   DB: {db_shares:,}주")
                    print(f"   DART: {dart_shares:,}주")
                    print(f"   차이: {diff:,}주 ({diff_percent:.2f}%)")
                    
                    if diff == 0:
                        print(f"   ✅ 완전 일치!")
                    elif diff_percent < 1.0:
                        print(f"   ⚠️  경미한 차이 (1% 미만)")
                    elif diff_percent < 5.0:
                        print(f"   ⚠️  차이 (1-5%)")
                    else:
                        print(f"   ❌ 불일치 (5% 이상)")
                    
                    print(f"\n🔍 웹 검증:")
                    print(f"   네이버: https://search.naver.com/search.naver?query={stock.stock_name}+발행주식수")
                    print(f"   구글: https://www.google.com/search?q={stock.stock_name}+발행주식수")
            else:
                print("\n❌ 발행주식수를 찾을 수 없습니다.")
            
            print()
            print("-"*80)
            time.sleep(0.3)  # API 호출 제한 방지
            
        except Stock.DoesNotExist:
            print(f"\n❌ 종목 {stock_code}를 찾을 수 없습니다.")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()

