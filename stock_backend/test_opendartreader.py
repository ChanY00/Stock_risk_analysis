#!/usr/bin/env python
"""
OpenDartReader 라이브러리 테스트
발행주식수 조회 방법 확인
"""
import os
import sys
import django

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings')
django.setup()

from stocks.models import Stock
import OpenDartReader

def main():
    api_key = os.getenv('DART_API_KEY')
    if not api_key:
        print("❌ DART_API_KEY 환경변수가 설정되지 않았습니다.")
        return
    
    # OpenDartReader 초기화
    print("🔍 OpenDartReader 라이브러리 테스트\n")
    
    try:
        dart = OpenDartReader(api_key)
        print("✅ OpenDartReader 초기화 성공")
        print()
    except Exception as e:
        print(f"❌ OpenDartReader 초기화 실패: {e}")
        return
    
    # 테스트할 종목
    stock_code = '005930'  # 삼성전자
    stock = Stock.objects.get(stock_code=stock_code)
    
    print(f"📊 {stock.stock_name} ({stock.stock_code})")
    print(f"DB 발행주식수: {stock.shares_outstanding:,}주")
    print()
    
    # OpenDartReader의 사용 가능한 메서드 확인
    print("="*80)
    print("📋 OpenDartReader 사용 가능한 메서드 확인")
    print("="*80)
    
    methods = [method for method in dir(dart) if not method.startswith('_') and callable(getattr(dart, method))]
    print(f"✅ 총 {len(methods)}개 메서드 발견\n")
    
    # 주식수 관련 메서드 찾기
    stock_related_methods = [m for m in methods if 'stock' in m.lower() or 'share' in m.lower() or 'tot' in m.lower() or 'cnt' in m.lower()]
    
    if stock_related_methods:
        print("📋 주식수 관련 메서드:")
        for method in stock_related_methods:
            print(f"  - {method}")
        print()
    
    # company() 메서드 시도
    print("="*80)
    print("📋 company() 메서드로 기업 정보 조회")
    print("="*80)
    
    try:
        # 종목코드로 corp_code 찾기 (OpenDartReader가 자동으로 변환할 수도 있음)
        # 또는 직접 corp_code를 찾아서 사용
        from stocks.management.commands.update_shares_and_dividend import Command as UpdateCommand
        update_cmd = UpdateCommand()
        corp_code = update_cmd.get_corp_code(stock_code, api_key)
        
        if not corp_code:
            print("❌ DART 고유번호를 찾을 수 없습니다.")
            return
        
        print(f"✅ DART 고유번호: {corp_code}")
        print()
        
        # company() 메서드 시도
        print("🔍 company() 메서드 호출 중...")
        try:
            company_info = dart.company(corp_code)
            print(f"✅ company() 메서드 성공")
            print(f"응답 타입: {type(company_info)}")
            
            if isinstance(company_info, dict):
                print(f"응답 키: {list(company_info.keys())[:10]}")  # 처음 10개만
                # 발행주식수 관련 키 찾기
                stock_keys = [k for k in company_info.keys() if 'stock' in k.lower() or 'share' in k.lower() or '주식' in k]
                if stock_keys:
                    print(f"\n주식수 관련 키:")
                    for key in stock_keys:
                        print(f"  - {key}: {company_info[key]}")
        except Exception as e:
            print(f"❌ company() 메서드 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # get_stock_tot_cnt() 메서드 시도 (있다면)
        print()
        print("="*80)
        print("📋 get_stock_tot_cnt() 메서드 시도")
        print("="*80)
        
        if hasattr(dart, 'get_stock_tot_cnt'):
            print("🔍 get_stock_tot_cnt() 메서드 호출 중...")
            try:
                # 2024년 3분기 시도
                stock_tot = dart.get_stock_tot_cnt(corp_code, '2024', '11014')
                print(f"✅ get_stock_tot_cnt() 메서드 성공")
                print(f"응답 타입: {type(stock_tot)}")
                
                if isinstance(stock_tot, (dict, list)):
                    print(f"응답 내용:")
                    print(stock_tot)
            except Exception as e:
                print(f"❌ get_stock_tot_cnt() 메서드 오류: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("⚠️  get_stock_tot_cnt() 메서드를 찾을 수 없습니다.")
        
        # 다른 가능한 메서드들 시도
        print()
        print("="*80)
        print("📋 다른 가능한 메서드들 시도")
        print("="*80)
        
        # 주식수 관련 메서드들
        possible_methods = [
            'list_stock',
            'stock_tot',
            'stock_total',
            'shares',
            'stock_count',
        ]
        
        for method_name in possible_methods:
            if hasattr(dart, method_name):
                print(f"🔍 {method_name}() 메서드 발견!")
                try:
                    method = getattr(dart, method_name)
                    # 메서드 시그니처 확인
                    import inspect
                    sig = inspect.signature(method)
                    print(f"  시그니처: {sig}")
                except Exception as e:
                    print(f"  확인 오류: {e}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()

