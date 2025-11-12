"""
총자본(total_equity) 데이터 수정 명령어

문제: DART API 파싱 시 "자본잉여금"이 "총자본"으로 잘못 저장됨
해결: "자본총계" 또는 "지배기업의 소유지분"을 올바르게 파싱하여 업데이트
"""
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone
from stocks.models import Stock
from financials.models import FinancialStatement
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, Optional
import time
import os


class DartAPIClient:
    """DART API 클라이언트"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://opendart.fss.or.kr/api"
        self.session = requests.Session()
        self._corp_mapping = None
        
    def get_corp_list(self) -> Dict[str, str]:
        """전체 기업 목록과 고유번호 매핑 조회"""
        if self._corp_mapping:
            return self._corp_mapping
        
        url = f"{self.base_url}/corpCode.xml"
        params = {"crtfc_key": self.api_key}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            # ZIP 파일 압축 해제
            zip_file = zipfile.ZipFile(io.BytesIO(response.content))
            xml_content = zip_file.read('CORPCODE.xml')
            
            # XML 파싱
            root = ET.fromstring(xml_content)
            
            mapping = {}
            for corp in root.findall('.//list'):
                stock_code = corp.findtext('stock_code', '').strip()
                corp_code = corp.findtext('corp_code', '').strip()
                if stock_code and corp_code:
                    mapping[stock_code] = corp_code
            
            self._corp_mapping = mapping
            return mapping
            
        except Exception as e:
            print(f"❌ 기업 목록 조회 실패: {e}")
            return {}
    
    def get_correct_total_equity(self, corp_code: str, year: int) -> Optional[int]:
        """DART API에서 올바른 총자본 조회"""
        url = f"{self.base_url}/fnlttSinglAcntAll.json"
        
        # CFS (연결재무제표) 시도
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",  # 사업보고서
            "fs_div": "CFS"
        }
        
        try:
            response = self.session.get(url, params=params, timeout=20)
            data = response.json()
            
            if data.get('status') != '000':
                # OFS (별도재무제표) 시도
                params['fs_div'] = 'OFS'
                response = self.session.get(url, params=params, timeout=20)
                data = response.json()
                
                if data.get('status') != '000':
                    return None
            
            raw_data = data.get('list', [])
            
            # 총자본 파싱 (올바른 우선순위)
            equity_candidates = []
            
            for item in raw_data:
                account_nm = item.get('account_nm', '').strip()
                account_id = item.get('account_id', '').strip()
                sj_div = item.get('sj_div', '').strip()
                thstrm_amount = item.get('thstrm_amount', '0').replace(',', '').strip()
                
                # 재무상태표(BS)만 확인
                if sj_div != 'BS':
                    continue
                
                # 자본잉여금, 자본금, 기타자본 등은 제외
                if any(keyword in account_nm for keyword in ['잉여금', '자본금', '기타자본', '기타포괄', '비지배']):
                    continue
                
                # 총자본 관련 항목 수집
                if '자본총계' in account_nm:
                    try:
                        amount = int(thstrm_amount)
                        equity_candidates.append({
                            'amount': amount,
                            'account_nm': account_nm,
                            'account_id': account_id,
                            'priority': 1,  # 최우선
                            'type': 'equity_total'
                        })
                    except (ValueError, TypeError):
                        pass
                
                elif '지배기업의 소유지분' in account_nm or 'EquityAttributableToOwnersOfParent' in account_id:
                    try:
                        amount = int(thstrm_amount)
                        equity_candidates.append({
                            'amount': amount,
                            'account_nm': account_nm,
                            'account_id': account_id,
                            'priority': 2,  # 2순위
                            'type': 'owners_equity'
                        })
                    except (ValueError, TypeError):
                        pass
            
            # 우선순위에 따라 선택
            if equity_candidates:
                equity_candidates.sort(key=lambda x: x['priority'])
                selected = equity_candidates[0]
                return selected['amount']
            
            return None
            
        except Exception as e:
            return None


class Command(BaseCommand):
    help = 'DART API에서 올바른 총자본 데이터를 조회하여 DB 업데이트'

    def add_arguments(self, parser):
        parser.add_argument(
            '--api_key',
            type=str,
            help='DART API 키 (환경변수 DART_API_KEY 사용 가능)'
        )
        parser.add_argument(
            '--stock_code',
            type=str,
            help='특정 종목만 수정 (생략 시 전체)'
        )
        parser.add_argument(
            '--year',
            type=int,
            help='특정 연도만 수정 (생략 시 전체)'
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            help='실제 저장하지 않고 시뮬레이션만 (테스트용)'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='처리할 최대 항목 수 (0=전체, 테스트용)'
        )

    def handle(self, *args, **options):
        # API 키 확인
        api_key = options.get('api_key') or os.getenv('DART_API_KEY')
        if not api_key:
            self.stdout.write(self.style.ERROR('❌ DART_API_KEY가 필요합니다.'))
            return

        dry_run = options.get('dry_run', False)
        limit = options.get('limit', 0)
        
        self.stdout.write('=' * 100)
        self.stdout.write(self.style.SUCCESS('총자본(total_equity) 데이터 수정'))
        self.stdout.write('=' * 100)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️  DRY RUN 모드: 실제 저장하지 않음\n'))
        
        # DART API 클라이언트 초기화
        dart_client = DartAPIClient(api_key)
        
        self.stdout.write('📡 DART API 기업 목록 조회 중...')
        corp_mapping = dart_client.get_corp_list()
        self.stdout.write(f'✅ {len(corp_mapping)}개 기업 매핑 완료\n')
        
        # 수정 대상 조회
        queryset = FinancialStatement.objects.filter(
            total_assets__isnull=False,
            total_liabilities__isnull=False,
            total_equity__isnull=False
        ).select_related('stock')
        
        # 필터 적용
        if options.get('stock_code'):
            queryset = queryset.filter(stock__stock_code=options['stock_code'])
        
        if options.get('year'):
            queryset = queryset.filter(year=options['year'])
        
        # 회계 등식 오류만 필터링
        error_items = []
        for fs in queryset:
            calculated = fs.total_assets - fs.total_liabilities
            diff_pct = abs(fs.total_equity - calculated) / calculated * 100 if calculated != 0 else 0
            
            if diff_pct > 1:  # 1% 이상 차이
                error_items.append(fs)
        
        total_count = len(error_items)
        
        if limit > 0:
            error_items = error_items[:limit]
            self.stdout.write(f'⚠️  테스트 모드: 상위 {limit}개만 처리\n')
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ 수정이 필요한 항목이 없습니다.'))
            return
        
        self.stdout.write(f'수정 대상: {total_count}개')
        self.stdout.write(f'처리 예정: {len(error_items)}개\n')
        
        # 진행 상황 카운터
        success_count = 0
        skip_count = 0
        fail_count = 0
        
        for i, fs in enumerate(error_items, 1):
            stock = fs.stock
            
            # 진행 상황 출력
            self.stdout.write(
                f'\n[{i}/{len(error_items)}] {stock.stock_name} ({stock.stock_code}) - {fs.year}년'
            )
            
            # 현재 값
            calculated_equity = fs.total_assets - fs.total_liabilities
            old_equity = fs.total_equity
            diff_pct = abs(old_equity - calculated_equity) / calculated_equity * 100
            
            self.stdout.write(
                f'  현재 DB 총자본: {old_equity/1e12:.2f}조원'
            )
            self.stdout.write(
                f'  계산된 총자본:  {calculated_equity/1e12:.2f}조원 (차이: {diff_pct:.1f}%)'
            )
            
            # DART 고유번호 확인
            corp_code = corp_mapping.get(stock.stock_code)
            if not corp_code:
                self.stdout.write(self.style.WARNING(f'  ⏭️  DART 고유번호를 찾을 수 없습니다.'))
                skip_count += 1
                continue
            
            # DART API에서 정확한 총자본 조회
            self.stdout.write(f'  📡 DART API 조회 중...')
            correct_equity = dart_client.get_correct_total_equity(corp_code, fs.year)
            
            if correct_equity is None:
                self.stdout.write(self.style.WARNING(f'  ⚠️  DART API에서 데이터를 가져올 수 없습니다.'))
                fail_count += 1
                time.sleep(0.3)  # API 요청 제한 고려
                continue
            
            self.stdout.write(
                f'  ✅ DART 총자본:  {correct_equity/1e12:.2f}조원'
            )
            
            # 검증: DART 값이 회계 등식과 일치하는지 확인
            verification_diff = abs(correct_equity - calculated_equity) / calculated_equity * 100
            
            if verification_diff > 1:
                self.stdout.write(
                    self.style.WARNING(
                        f'  ⚠️  DART 값도 회계 등식과 맞지 않음 (차이: {verification_diff:.1f}%)'
                    )
                )
                fail_count += 1
                time.sleep(0.3)
                continue
            
            # 업데이트
            if not dry_run:
                fs.total_equity = correct_equity
                fs.verification_note = (
                    f'총자본 수정: {old_equity:,} → {correct_equity:,} '
                    f'(fix_total_equity 명령어, {timezone.now().strftime("%Y-%m-%d")})'
                )
                fs.save(update_fields=['total_equity', 'verification_note'])
                self.stdout.write(self.style.SUCCESS(f'  💾 DB 업데이트 완료'))
            else:
                self.stdout.write(self.style.WARNING(f'  💾 DRY RUN: 저장 생략'))
            
            success_count += 1
            time.sleep(0.3)  # API 요청 제한 고려 (초당 3회)
        
        # 결과 요약
        self.stdout.write('\n' + '=' * 100)
        self.stdout.write(self.style.SUCCESS('작업 완료'))
        self.stdout.write('=' * 100)
        self.stdout.write(f'✅ 성공: {success_count}개')
        self.stdout.write(f'⏭️  건너뜀: {skip_count}개')
        self.stdout.write(f'❌ 실패: {fail_count}개')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  DRY RUN 모드였습니다. 실제로 저장하려면 --dry_run 옵션을 제거하세요.'))
        
        self.stdout.write('=' * 100)


