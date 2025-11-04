#!/usr/bin/env python
"""
OpenDartReader를 사용하여 유통주식수 검증 및 업데이트
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
        corp_list = dart.corp_codes
        matching = corp_list[corp_list['stock_code'] == stock_code]
        if not matching.empty:
            return matching.iloc[0]['corp_code']
        return None
    except Exception as e:
        print(f"  ⚠️  고유번호 조회 오류: {e}")
        return None

def get_distb_stock_from_opendartreader(dart, corp_code: str, year: int = 2024):
    """
    OpenDartReader를 사용하여 유통주식수 조회
    
    Returns:
        dict: {
            'distb_stock': 유통주식수,
            'isu_stock_totqy': 발행주식 총수,
            'now_to_isu_stock_totqy': 현재 발행주식 총수,
            'year': 연도,
            'stlm_dt': 기준일
        }
    """
    result = None
    
    try:
        print(f"  🔍 report() 메서드로 주식총수 조회 시도...")
        stock_tot_report = dart.report(corp_code, '주식총수', str(year))
        
        if stock_tot_report is not None and not stock_tot_report.empty:
            print(f"  ✅ report() 메서드 성공")
            
            # 'se' 컬럼이 있으면 '보통주'만 필터링
            if 'se' in stock_tot_report.columns:
                common_stock = stock_tot_report[stock_tot_report['se'] == '보통주']
                if not common_stock.empty:
                    print(f"  ✅ 보통주 데이터 발견: {len(common_stock)}개")
                    stock_tot_report = common_stock
            
            if len(stock_tot_report) > 0:
                first_row = stock_tot_report.iloc[0]
                
                # 유통주식수 (distb_stock_co) 찾기
                distb_stock = first_row.get('distb_stock_co')
                isu_stock_totqy = first_row.get('isu_stock_totqy')
                now_to_isu_stock_totqy = first_row.get('now_to_isu_stock_totqy')
                stlm_dt = first_row.get('stlm_dt', '')
                
                if distb_stock and distb_stock != '-':
                    try:
                        distb_stock_int = int(str(distb_stock).replace(',', ''))
                        if 1_000_000 <= distb_stock_int <= 100_000_000_000:
                            result = {
                                'distb_stock': distb_stock_int,
                                'isu_stock_totqy': int(str(isu_stock_totqy).replace(',', '')) if isu_stock_totqy and isu_stock_totqy != '-' else None,
                                'now_to_isu_stock_totqy': int(str(now_to_isu_stock_totqy).replace(',', '')) if now_to_isu_stock_totqy and now_to_isu_stock_totqy != '-' else None,
                                'year': year,
                                'stlm_dt': stlm_dt,
                            }
                    except (ValueError, AttributeError) as e:
                        print(f"  ⚠️  숫자 변환 오류: {e}")
    except Exception as e:
        print(f"  ⚠️  report() 메서드 오류: {e}")
    
    return result

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # OpenDartReader 초기화
    print("🔍 OpenDartReader를 사용하여 유통주식수 검증\n")
    
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
    test_stocks = ['005930', '000660']  # 삼성전자, SK하이닉스
    
    print("="*80)
    
    results = []
    
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
            
            # 유통주식수 조회
            print("="*80)
            print("📋 OpenDartReader로 유통주식수 조회")
            print("="*80)
            
            result = get_distb_stock_from_opendartreader(dart, corp_code, 2024)
            
            if result:
                distb_stock = result['distb_stock']
                isu_stock_totqy = result.get('isu_stock_totqy')
                now_to_isu_stock_totqy = result.get('now_to_isu_stock_totqy')
                stlm_dt = result.get('stlm_dt', '')
                
                print()
                print(f"✅ 유통주식수 발견!")
                print(f"   유통주식수 (distb_stock_co): {distb_stock:,}주")
                if isu_stock_totqy:
                    print(f"   발행주식 총수 (isu_stock_totqy): {isu_stock_totqy:,}주")
                if now_to_isu_stock_totqy:
                    print(f"   현재 발행주식 총수 (now_to_isu_stock_totqy): {now_to_isu_stock_totqy:,}주")
                if stlm_dt:
                    print(f"   기준일: {stlm_dt}")
                print()
                
                # DB 값과 비교
                if stock.shares_outstanding:
                    db_shares = stock.shares_outstanding
                    diff = abs(distb_stock - db_shares)
                    diff_percent = (diff / max(distb_stock, db_shares)) * 100 if max(distb_stock, db_shares) > 0 else 0
                    
                    print(f"📊 DB와 비교:")
                    print(f"   DB 발행주식수: {db_shares:,}주")
                    print(f"   DART 유통주식수: {distb_stock:,}주")
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
                print(f"   네이버: https://search.naver.com/search.naver?query={stock.stock_name}+유통주식수")
                print(f"   구글: https://www.google.com/search?q={stock.stock_name}+유통주식수")
                print(f"   네이버 금융: https://finance.naver.com/item/main.naver?code={stock_code}")
                
                # 결과 저장
                results.append({
                    'stock_code': stock_code,
                    'stock_name': stock.stock_name,
                    'corp_code': corp_code,
                    'db_shares': stock.shares_outstanding,
                    'dart_distb_stock': distb_stock,
                    'dart_isu_stock_totqy': isu_stock_totqy,
                    'dart_now_to_isu_stock_totqy': now_to_isu_stock_totqy,
                    'stlm_dt': stlm_dt,
                })
            else:
                print("\n❌ 유통주식수를 찾을 수 없습니다.")
            
            print()
            print("-"*80)
            time.sleep(0.3)  # API 호출 제한 방지
            
        except Stock.DoesNotExist:
            print(f"\n❌ 종목 {stock_code}를 찾을 수 없습니다.")
        except Exception as e:
            print(f"\n❌ 오류 발생: {e}")
            import traceback
            traceback.print_exc()
    
    # 검증 결과 요약
    if results:
        print("\n" + "="*80)
        print("📋 검증 결과 요약")
        print("="*80)
        print()
        print("다음 종목들의 유통주식수를 확인했습니다:")
        print()
        for r in results:
            print(f"  {r['stock_name']} ({r['stock_code']}):")
            print(f"    DART 유통주식수: {r['dart_distb_stock']:,}주")
            if r['db_shares']:
                diff = abs(r['dart_distb_stock'] - r['db_shares'])
                diff_percent = (diff / max(r['dart_distb_stock'], r['db_shares'])) * 100 if max(r['dart_distb_stock'], r['db_shares']) > 0 else 0
                print(f"    DB 발행주식수: {r['db_shares']:,}주 (차이: {diff:,}주, {diff_percent:.2f}%)")
            print()
        
        print("="*80)
        print("💡 다음 단계:")
        print("="*80)
        print("1. 위의 웹 검증 링크를 통해 실제 유통주식수를 확인하세요.")
        print("2. 검증이 완료되면 다음 명령어로 DB를 업데이트할 수 있습니다:")
        print()
        print("   python manage.py update_shares_outstanding_from_dart \\")
        print("     --stock-codes 005930 000660 \\")
        print("     --use-distb-stock \\")
        print("     --confirm")
        print()

if __name__ == '__main__':
    main()

