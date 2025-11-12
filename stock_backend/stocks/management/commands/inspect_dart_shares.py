"""
DART API에서 발행주식수 관련 항목을 정확히 확인하는 명령어

DART API 응답의 모든 계정명과 account_id를 확인하여
발행주식수에 해당하는 정확한 attribute를 찾습니다.
"""
from django.core.management.base import BaseCommand
from stocks.models import Stock
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
import json
import os
import time

class Command(BaseCommand):
    help = 'DART API에서 발행주식수 관련 항목을 정확히 확인합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-code',
            type=str,
            help='확인할 종목코드 (예: 005930)',
            default='005930',  # 삼성전자 기본값
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='DART API 키 (환경변수 DART_API_KEY 사용 가능)',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=2024,
            help='확인할 연도 (기본값: 2024)',
        )

    def get_corp_code(self, stock_code: str, api_key: str):
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
            self.stdout.write(self.style.ERROR(f"Failed to get corp_code: {e}"))
            return None

    def handle(self, *args, **options):
        stock_code = options.get('stock_code', '005930')
        api_key = options.get('api_key') or os.getenv('DART_API_KEY')
        year = options.get('year', 2024)
        
        if not api_key:
            self.stdout.write(
                self.style.ERROR('❌ DART API 키가 필요합니다. --api-key 옵션을 사용하거나 DART_API_KEY 환경변수를 설정해주세요.')
            )
            return
        
        try:
            stock = Stock.objects.get(stock_code=stock_code)
        except Stock.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ 종목 {stock_code}를 찾을 수 없습니다.'))
            return
        
        self.stdout.write(f'🔍 {stock.stock_name} ({stock_code})의 DART API 응답 구조 확인 중...\n')
        
        corp_code = self.get_corp_code(stock_code, api_key)
        if not corp_code:
            self.stdout.write(self.style.ERROR('❌ DART 고유번호를 찾을 수 없습니다.'))
            return
        
        self.stdout.write(f'📊 DART 고유번호: {corp_code}\n')
        
        # DART API 호출
        url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
        params = {
            'crtfc_key': api_key,
            'corp_code': corp_code,
            'bsns_year': str(year),
            'reprt_code': '11011',  # 사업보고서
            'fs_div': 'CFS'  # 연결재무제표
        }
        
        self.stdout.write(f'🌐 DART API 호출 중...')
        self.stdout.write(f'   URL: {url}')
        self.stdout.write(f'   파라미터: {params}\n')
        
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != '000':
                self.stdout.write(self.style.ERROR(f'❌ API 오류: {data.get("message")}'))
                return
            
            list_data = data.get('list', [])
            self.stdout.write(f'✅ 총 {len(list_data)}개 항목 발견\n')
            
            # 발행주식수 관련 항목 찾기
            self.stdout.write('='*80)
            self.stdout.write('📋 발행주식수 관련 항목 (계정명에 "주식" 포함)')
            self.stdout.write('='*80)
            
            shares_related = []
            for item in list_data:
                account_nm = item.get('account_nm', '').strip()
                if '주식' in account_nm or 'share' in item.get('account_id', '').lower():
                    shares_related.append(item)
            
            if not shares_related:
                self.stdout.write('⚠️  발행주식수 관련 항목을 찾을 수 없습니다.\n')
            else:
                for i, item in enumerate(shares_related, 1):
                    self.stdout.write(f'\n[{i}] {item.get("account_nm", "N/A")}')
                    self.stdout.write(f'    account_id: {item.get("account_id", "N/A")}')
                    self.stdout.write(f'    sj_nm: {item.get("sj_nm", "N/A")}')  # 재무제표 구분
                    self.stdout.write(f'    thstrm_amount: {item.get("thstrm_amount", "N/A")}')  # 당기금액
                    self.stdout.write(f'    frmtrm_amount: {item.get("frmtrm_amount", "N/A")}')  # 전기금액
                    self.stdout.write(f'    bfefrmtrm_amount: {item.get("bfefrmtrm_amount", "N/A")}')  # 전전기금액
                    
                    # 금액이 있는 경우 숫자로 변환 시도
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    if thstrm and thstrm != '-':
                        try:
                            amount = int(thstrm)
                            if 1_000_000 <= amount <= 10_000_000_000:  # 합리적인 범위
                                self.stdout.write(self.style.SUCCESS(f'    ✅ 후보 (범위 내): {amount:,}주'))
                            else:
                                self.stdout.write(f'    ⚠️  범위 외: {amount:,}')
                        except ValueError:
                            pass
            
            # 전체 항목 중 자본 관련 항목도 확인
            self.stdout.write('\n' + '='*80)
            self.stdout.write('📋 자본 관련 항목 (계정명에 "자본" 포함)')
            self.stdout.write('='*80)
            
            capital_related = []
            for item in list_data:
                account_nm = item.get('account_nm', '').strip()
                if '자본' in account_nm:
                    capital_related.append(item)
            
            if capital_related:
                for i, item in enumerate(capital_related[:10], 1):  # 최대 10개만 표시
                    self.stdout.write(f'\n[{i}] {item.get("account_nm", "N/A")}')
                    self.stdout.write(f'    account_id: {item.get("account_id", "N/A")}')
                    self.stdout.write(f'    thstrm_amount: {item.get("thstrm_amount", "N/A")}')
            
            # JSON 파일로 저장 (선택적)
            self.stdout.write('\n' + '='*80)
            self.stdout.write('💾 전체 응답 데이터 저장 옵션')
            self.stdout.write('='*80)
            self.stdout.write('전체 응답을 JSON 파일로 저장하려면 --save 옵션을 추가하세요.')
            
            # DB에 저장된 발행주식수와 비교
            if stock.shares_outstanding:
                self.stdout.write('\n' + '='*80)
                self.stdout.write('📊 DB 저장값과 비교')
                self.stdout.write('='*80)
                self.stdout.write(f'DB 발행주식수: {stock.shares_outstanding:,}주')
                
                # 가장 유사한 값 찾기
                for item in shares_related:
                    thstrm = item.get('thstrm_amount', '').replace(',', '').strip()
                    if thstrm and thstrm != '-':
                        try:
                            dart_shares = int(thstrm)
                            if 1_000_000 <= dart_shares <= 10_000_000_000:
                                diff = abs(dart_shares - stock.shares_outstanding)
                                diff_percent = (diff / max(dart_shares, stock.shares_outstanding)) * 100
                                
                                if diff == 0:
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f'\n✅ 일치: {item.get("account_nm")} = {dart_shares:,}주'
                                        )
                                    )
                                elif diff_percent < 1.0:
                                    self.stdout.write(
                                        self.style.WARNING(
                                            f'\n⚠️  경미한 차이: {item.get("account_nm")} = {dart_shares:,}주 (차이: {diff_percent:.2f}%)'
                                        )
                                    )
                                else:
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f'\n❌ 차이: {item.get("account_nm")} = {dart_shares:,}주 (차이: {diff_percent:.2f}%)'
                                        )
                                    )
                        except ValueError:
                            pass
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ 오류 발생: {e}'))
            import traceback
            self.stdout.write(traceback.format_exc())

