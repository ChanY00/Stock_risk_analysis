"""
발행주식수 검증 명령어

DB에 저장된 발행주식수와 DART API에서 가져온 발행주식수를 비교하여 검증합니다.
검증 결과는 별도 모델에 저장하여 웹에서 확인할 수 있도록 합니다.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from stocks.models import Stock
from analysis.models import SharesVerification
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Optional, List
import time
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'DB 발행주식수와 DART API 발행주식수를 비교하여 검증합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='검증할 종목코드 리스트 (예: 005930 000660)',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=10,
            help='검증할 종목 수 제한 (기본값: 10)',
        )
        parser.add_argument(
            '--api-key',
            type=str,
            help='DART API 키 (환경변수 DART_API_KEY 사용 가능)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='실제 업데이트 없이 검증만 수행',
        )
        parser.add_argument(
            '--auto-update',
            action='store_true',
            help='검증 후 DART 값이 다르면 자동으로 DB 업데이트',
        )
        parser.add_argument(
            '--update-threshold',
            type=float,
            default=1.0,
            help='자동 업데이트 기준 차이율 (기본값: 1.0%%)',
        )

    def get_corp_code(self, stock_code: str, api_key: str) -> Optional[str]:
        """DART 고유번호 조회"""
        try:
            url = 'https://opendart.fss.or.kr/api/corpCode.xml'
            params = {'crtfc_key': api_key}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # ZIP 파일로 압축되어 있음
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
            logger.error(f"Failed to get corp_code for {stock_code}: {e}")
            return None

    def get_shares_from_dart(self, stock: Stock, api_key: str) -> Optional[Dict]:
        """
        DART API에서 발행주식수 가져오기
        Returns: {'shares': int, 'source': str, 'year': int, 'account_nm': str}
        """
        try:
            corp_code = self.get_corp_code(stock.stock_code, api_key)
            if not corp_code:
                return None
            
            # 최근 연도 (2024, 2023) 순서로 시도
            for year in [2024, 2023]:
                url = f"https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"
                params = {
                    'crtfc_key': api_key,
                    'corp_code': corp_code,
                    'bsns_year': str(year),
                    'reprt_code': '11011',  # 사업보고서
                    'fs_div': 'CFS'  # 연결재무제표
                }
                
                response = requests.get(url, params=params, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == '000':
                        list_data = data.get('list', [])
                        
                        # 발행주식수 관련 항목 찾기
                        # "보통주식수", "주식수", "발행주식수" 등
                        target_accounts = [
                            '보통주식수',
                            '보통주 총수',
                            '주식수',
                            '발행주식수',
                            '보통주',
                            '보통주 발행주식수',
                        ]
                        
                        for item in list_data:
                            account_nm = item.get('account_nm', '').strip()
                            account_id = item.get('account_id', '').strip()
                            
                            # 주식수 관련 항목 찾기
                            is_shares_account = False
                            for target in target_accounts:
                                if target in account_nm:
                                    is_shares_account = True
                                    break
                            
                            # account_id에 'shares' 또는 'number' 포함하는 경우
                            if not is_shares_account:
                                if 'share' in account_id.lower() or 'number' in account_id.lower():
                                    is_shares_account = True
                            
                            if is_shares_account:
                                # 당기금액(thstrm_amount) 사용
                                thstrm_amount = item.get('thstrm_amount', '').replace(',', '').strip()
                                if not thstrm_amount or thstrm_amount == '-' or thstrm_amount == '':
                                    # 전기금액(frmtrm_amount) 시도
                                    thstrm_amount = item.get('frmtrm_amount', '').replace(',', '').strip()
                                
                                if thstrm_amount and thstrm_amount != '-' and thstrm_amount != '':
                                    try:
                                        shares = int(thstrm_amount)
                                        # 합리적인 범위 확인 (100만~100억주)
                                        if 1_000_000 <= shares <= 10_000_000_000:
                                            return {
                                                'shares': shares,
                                                'source': 'DART_API',
                                                'year': year,
                                                'account_nm': account_nm,
                                                'account_id': account_id,
                                            }
                                    except ValueError:
                                        continue
                        
                        time.sleep(0.1)  # API 호출 제한 방지
                
        except Exception as e:
            logger.debug(f"Failed to get shares from DART for {stock.stock_code}: {e}")
        
        return None

    def handle(self, *args, **options):
        api_key = options.get('api_key') or os.getenv('DART_API_KEY')
        
        if not api_key:
            self.stdout.write(
                self.style.ERROR('❌ DART API 키가 필요합니다. --api-key 옵션을 사용하거나 DART_API_KEY 환경변수를 설정해주세요.')
            )
            return
        
        stock_codes = options.get('stock_codes')
        limit = options.get('limit', 10)
        dry_run = options.get('dry_run', False)
        auto_update = options.get('auto_update', False)
        update_threshold = options.get('update_threshold', 1.0)
        
        self.stdout.write('🔍 발행주식수 검증 시작...\n')
        
        # 검증할 종목 선택
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
        else:
            # 발행주식수가 있는 종목 중 랜덤 샘플링
            stocks = Stock.objects.filter(
                shares_outstanding__isnull=False
            ).exclude(
                shares_outstanding=0
            )[:limit]
        
        if not stocks.exists():
            self.stdout.write(self.style.ERROR('❌ 검증할 종목이 없습니다.'))
            return
        
        self.stdout.write(f'📊 검증 대상: {stocks.count()}개 종목\n')
        
        verification_results = []
        
        for i, stock in enumerate(stocks, 1):
            self.stdout.write(f'[{i}/{stocks.count()}] {stock.stock_name} ({stock.stock_code}) 검증 중...')
            
            db_shares = stock.shares_outstanding
            
            # DART API에서 발행주식수 가져오기
            dart_result = self.get_shares_from_dart(stock, api_key)
            
            if not dart_result:
                self.stdout.write(f'  ⚠️  DART API에서 발행주식수를 가져올 수 없습니다.')
                verification_results.append({
                    'stock': stock,
                    'db_shares': db_shares,
                    'dart_shares': None,
                    'match': False,
                    'status': 'DART_API_ERROR',
                    'diff_percent': None,
                })
                time.sleep(0.2)  # API 호출 제한 방지
                continue
            
            dart_shares = dart_result['shares']
            
            # 비교
            # 웹 검색 링크 생성 (네이버/다음에서 발행주식수 확인)
            search_query = f"{stock.stock_name} 발행주식수"
            naver_search_url = f"https://search.naver.com/search.naver?query={search_query.replace(' ', '+')}"
            google_search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            
            if db_shares == dart_shares:
                match = True
                status = 'MATCH'
                diff_percent = 0.0
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ 일치: DB={db_shares:,}주, DART={dart_shares:,}주')
                )
                self.stdout.write(f'  🔍 웹 검증: {naver_search_url}')
            else:
                match = False
                diff = abs(dart_shares - db_shares)
                diff_percent = (diff / max(db_shares, dart_shares)) * 100 if max(db_shares, dart_shares) > 0 else 0
                
                if diff_percent < 1.0:  # 1% 미만 차이면 경미한 차이
                    status = 'MINOR_DIFF'
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️  경미한 차이: DB={db_shares:,}주, DART={dart_shares:,}주 (차이: {diff_percent:.2f}%)'
                        )
                    )
                else:
                    status = 'MAJOR_DIFF'
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ 불일치: DB={db_shares:,}주, DART={dart_shares:,}주 (차이: {diff_percent:.2f}%)'
                        )
                    )
                
                self.stdout.write(f'  🔍 웹 검증 필요:')
                self.stdout.write(f'     - 네이버: {naver_search_url}')
                self.stdout.write(f'     - 구글: {google_search_url}')
            
            # 웹 검색 링크 생성
            search_query = f"{stock.stock_name} 발행주식수"
            naver_search_url = f"https://search.naver.com/search.naver?query={search_query.replace(' ', '+')}"
            google_search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            
            verification_results.append({
                'stock': stock,
                'db_shares': db_shares,
                'dart_shares': dart_shares,
                'match': match,
                'status': status,
                'diff_percent': diff_percent,
                'dart_source': dart_result.get('source'),
                'dart_year': dart_result.get('year'),
                'dart_account_nm': dart_result.get('account_nm'),
                'naver_search_url': naver_search_url,
                'google_search_url': google_search_url,
            })
            
            # 검증 결과 저장 및 자동 업데이트 (dry-run이 아닌 경우)
            if not dry_run:
                # 검증 결과 저장
                verification, created = SharesVerification.objects.update_or_create(
                    stock=stock,
                    defaults={
                        'db_shares': db_shares,
                        'dart_shares': dart_shares,
                        'match': match,
                        'status': status,
                        'diff_percent': diff_percent,
                        'dart_year': dart_result.get('year'),
                        'dart_account_nm': dart_result.get('account_nm', ''),
                        'verified_at': timezone.now(),
                    }
                )
                
                # 자동 업데이트 옵션이 활성화되어 있고, 차이가 threshold 이상인 경우
                updated = False
                if auto_update and not match and diff_percent >= update_threshold:
                    old_shares = stock.shares_outstanding
                    stock.shares_outstanding = dart_shares
                    
                    # 시가총액도 재계산
                    current_price = stock.get_current_price()
                    if current_price:
                        stock.market_cap = current_price * dart_shares
                    
                    stock.save()
                    updated = True
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✅ DB 업데이트: {old_shares:,}주 → {dart_shares:,}주'
                        )
                    )
                
                # verification_results에 updated 플래그 추가
                verification_results[-1]['updated'] = updated
            
            time.sleep(0.2)  # API 호출 제한 방지
        
        # 결과 요약
        self.stdout.write('\n' + '='*60)
        self.stdout.write('📊 검증 결과 요약')
        self.stdout.write('='*60)
        
        total = len(verification_results)
        matches = sum(1 for r in verification_results if r['match'])
        minor_diffs = sum(1 for r in verification_results if r['status'] == 'MINOR_DIFF')
        major_diffs = sum(1 for r in verification_results if r['status'] == 'MAJOR_DIFF')
        errors = sum(1 for r in verification_results if r['status'] == 'DART_API_ERROR')
        
        self.stdout.write(f'  총 검증: {total}개')
        self.stdout.write(self.style.SUCCESS(f'  ✅ 일치: {matches}개'))
        self.stdout.write(self.style.WARNING(f'  ⚠️  경미한 차이: {minor_diffs}개'))
        self.stdout.write(self.style.ERROR(f'  ❌ 불일치: {major_diffs}개'))
        self.stdout.write(f'  ⚠️  API 오류: {errors}개')
        
        if not dry_run:
            updated_count = sum(1 for r in verification_results if r.get('updated', False))
            
            self.stdout.write(f'\n✅ 검증 결과가 DB에 저장되었습니다.')
            if auto_update:
                self.stdout.write(self.style.SUCCESS(f'✅ {updated_count}개 종목의 발행주식수가 DART 값으로 업데이트되었습니다.'))
            self.stdout.write(f'웹에서 확인: /api/analysis/shares-verification/')
            
            # 불일치 항목이 있으면 웹 검증 필요 안내
            if major_diffs > 0:
                self.stdout.write(f'\n⚠️  {major_diffs}개 종목에서 불일치가 발견되었습니다.')
                if not auto_update:
                    self.stdout.write(f'웹 검색을 통해 실제 발행주식수를 확인해주세요.')
                    self.stdout.write(f'자동 업데이트: --auto-update 옵션 사용')
                self.stdout.write(f'\n웹 검증이 필요한 종목:')
                for result in verification_results:
                    if result['status'] == 'MAJOR_DIFF' and not result.get('updated', False):
                        self.stdout.write(f'  - {result["stock"].stock_name} ({result["stock"].stock_code})')
                        self.stdout.write(f'    네이버: {result["naver_search_url"]}')
        else:
            self.stdout.write(f'\n🔍 DRY-RUN 모드: 실제 업데이트 없이 검증만 수행했습니다.')

