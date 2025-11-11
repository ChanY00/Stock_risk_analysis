#!/usr/bin/env python
"""
KIS API 시장 지수 코드 테스트 스크립트

목적: 실제 KOSPI/KOSDAQ 종합지수를 조회하는 정확한 코드 조합을 찾기
"""
import os
import sys
import django
import requests
from typing import Optional, Dict, List, Tuple
import time

# Django 설정 로드
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stock_backend.settings.dev')
django.setup()

from django.conf import settings
from kis_api.client import KISApiClient


class MarketIndexTester:
    """시장 지수 코드 테스트"""
    
    def __init__(self):
        self.app_key = getattr(settings, 'KIS_APP_KEY', os.getenv('KIS_APP_KEY'))
        self.app_secret = getattr(settings, 'KIS_APP_SECRET', os.getenv('KIS_APP_SECRET'))
        self.base_url = getattr(settings, 'KIS_BASE_URL', 'https://openapi.koreainvestment.com:9443')
        self.is_paper_trading = getattr(settings, 'KIS_IS_PAPER_TRADING', True)
        
        # 토큰 관리를 위한 KISApiClient 사용
        self._client = KISApiClient(is_mock=self.is_paper_trading)
        
        # 테스트할 지수 코드 조합
        self.test_combinations = [
            # KOSPI 관련
            ('0001', 'J', 'KOSPI (J)'),
            ('0001', 'U', 'KOSPI (U)'),
            ('0001', 'Q', 'KOSPI (Q)'),
            
            # KOSDAQ 관련 - 일반 지수
            ('1001', 'J', 'KOSDAQ (J)'),
            ('1001', 'U', 'KOSDAQ (U)'),
            ('1001', 'Q', 'KOSDAQ (Q)'),
            
            # KOSDAQ 관련 - 업종지수
            ('2001', 'J', 'KOSDAQ 업종 (J)'),
            ('2001', 'U', 'KOSDAQ 업종 (U)'),
            ('2001', 'Q', 'KOSDAQ 업종 (Q)'),
            
            # 기타 지수 코드
            ('1028', 'U', 'KOSDAQ 150 (U)'),
            ('1028', 'Q', 'KOSDAQ 150 (Q)'),
            ('2203', 'U', 'KOSDAQ IT (U)'),
            ('2203', 'Q', 'KOSDAQ IT (Q)'),
        ]
    
    def _ensure_token(self) -> bool:
        """토큰 확보"""
        try:
            return self._client.ensure_token()
        except Exception as e:
            print(f"❌ 토큰 확보 오류: {e}")
            return False
    
    def test_index_code(self, code: str, market_div: str, description: str) -> Optional[Dict]:
        """특정 지수 코드 조합 테스트"""
        try:
            if not self._ensure_token():
                return None
            
            url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-index-price"
            tr_id = os.getenv('KIS_INDEX_TR_ID', 'FHPUP02100000')
            
            headers = {
                'Content-Type': 'application/json',
                'authorization': f'Bearer {self._client.token_manager.access_token}',
                'appkey': self.app_key,
                'appsecret': self.app_secret,
                'tr_id': tr_id,
                'custtype': 'P'
            }
            
            params = {
                'FID_COND_MRKT_DIV_CODE': market_div,
                'FID_INPUT_ISCD': code
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=10)
            
            # 응답 분석
            if response.status_code == 200:
                result = response.json()
                
                if result.get('rt_cd') == '0' and result.get('output'):
                    output = result['output']
                    
                    # 주요 필드 추출
                    return {
                        'code': code,
                        'market_div': market_div,
                        'description': description,
                        'success': True,
                        'index_name': output.get('hts_kor_isnm', 'N/A'),  # 한글명
                        'current_value': float(output.get('bstp_nmix_prpr', 0)),  # 현재가
                        'change': float(output.get('bstp_nmix_prdy_vrss', 0)),  # 전일대비
                        'change_percent': float(output.get('prdy_ctrt', 0)),  # 등락률
                        'volume': int(output.get('acml_vol', 0)),  # 거래량
                        'high': float(output.get('bstp_nmix_hgpr', 0)),  # 최고가
                        'low': float(output.get('bstp_nmix_lwpr', 0)),  # 최저가
                        'response': result
                    }
                else:
                    return {
                        'code': code,
                        'market_div': market_div,
                        'description': description,
                        'success': False,
                        'error': f"rt_cd={result.get('rt_cd')} msg={result.get('msg1')}"
                    }
            else:
                return {
                    'code': code,
                    'market_div': market_div,
                    'description': description,
                    'success': False,
                    'error': f"HTTP {response.status_code}"
                }
        
        except Exception as e:
            return {
                'code': code,
                'market_div': market_div,
                'description': description,
                'success': False,
                'error': str(e)
            }
    
    def run_tests(self):
        """모든 조합 테스트 실행"""
        print("\n" + "="*80)
        print("🔍 KIS API 시장 지수 코드 테스트")
        print("="*80)
        print(f"📍 API URL: {self.base_url}")
        print(f"📍 모드: {'모의투자 (VTS)' if self.is_paper_trading else '실계좌'}")
        print("="*80 + "\n")
        
        successful_results = []
        failed_results = []
        
        for idx, (code, market_div, description) in enumerate(self.test_combinations, 1):
            print(f"\n[{idx}/{len(self.test_combinations)}] 테스트 중: {description}")
            print(f"   코드: {code}, 시장구분: {market_div}")
            
            result = self.test_index_code(code, market_div, description)
            
            if result:
                if result['success']:
                    print(f"   ✅ 성공!")
                    print(f"      지수명: {result.get('index_name', 'N/A')}")
                    print(f"      현재값: {result.get('current_value', 0):,.2f}")
                    print(f"      전일대비: {result.get('change', 0):+,.2f} ({result.get('change_percent', 0):+.2f}%)")
                    print(f"      거래량: {result.get('volume', 0):,}")
                    successful_results.append(result)
                else:
                    print(f"   ❌ 실패: {result.get('error', 'Unknown error')}")
                    failed_results.append(result)
            else:
                print(f"   ❌ 응답 없음")
            
            # API 호출 간격 (Rate limit 방지)
            if idx < len(self.test_combinations):
                time.sleep(0.5)
        
        # 결과 요약
        self._print_summary(successful_results, failed_results)
    
    def _print_summary(self, successful: List[Dict], failed: List[Dict]):
        """결과 요약 출력"""
        print("\n" + "="*80)
        print("📊 테스트 결과 요약")
        print("="*80)
        
        print(f"\n✅ 성공: {len(successful)}개")
        print(f"❌ 실패: {len(failed)}개")
        
        if successful:
            print("\n" + "-"*80)
            print("🎯 성공한 조합 (추천 설정)")
            print("-"*80)
            
            # KOSPI 관련
            kospi_results = [r for r in successful if r['code'] == '0001']
            if kospi_results:
                print("\n📈 KOSPI 지수:")
                for r in kospi_results:
                    print(f"   • ({r['code']}, {r['market_div']}): {r['index_name']} = {r['current_value']:,.2f}")
            
            # KOSDAQ 관련
            kosdaq_results = [r for r in successful if r['code'] in ('1001', '2001', '1028', '2203')]
            if kosdaq_results:
                print("\n📈 KOSDAQ 관련 지수:")
                for r in kosdaq_results:
                    print(f"   • ({r['code']}, {r['market_div']}): {r['index_name']} = {r['current_value']:,.2f}")
            
            # 추천 설정
            print("\n" + "="*80)
            print("💡 추천 환경 변수 설정")
            print("="*80)
            
            # KOSPI 추천
            if kospi_results:
                best_kospi = kospi_results[0]
                print(f"\n# KOSPI")
                print(f"KIS_KOSPI_CODE={best_kospi['code']}")
                print(f"KIS_KOSPI_DIV={best_kospi['market_div']}")
                print(f"# → {best_kospi['index_name']}")
            
            # KOSDAQ 추천 (1001 우선, 없으면 2001)
            kosdaq_1001 = [r for r in kosdaq_results if r['code'] == '1001']
            kosdaq_2001 = [r for r in kosdaq_results if r['code'] == '2001']
            
            if kosdaq_1001:
                best_kosdaq = kosdaq_1001[0]
                print(f"\n# KOSDAQ (추천: 종합지수)")
                print(f"KIS_KOSDAQ_CODE={best_kosdaq['code']}")
                print(f"KIS_KOSDAQ_DIV={best_kosdaq['market_div']}")
                print(f"# → {best_kosdaq['index_name']}")
            elif kosdaq_2001:
                best_kosdaq = kosdaq_2001[0]
                print(f"\n# KOSDAQ (대체: 업종지수)")
                print(f"KIS_KOSDAQ_CODE={best_kosdaq['code']}")
                print(f"KIS_KOSDAQ_DIV={best_kosdaq['market_div']}")
                print(f"# → {best_kosdaq['index_name']}")
        
        print("\n" + "="*80)
        print("✨ 테스트 완료!")
        print("="*80 + "\n")


def main():
    """메인 실행"""
    try:
        tester = MarketIndexTester()
        tester.run_tests()
    except KeyboardInterrupt:
        print("\n\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

