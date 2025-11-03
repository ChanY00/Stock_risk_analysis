"""
실패한 재무 데이터 수집 상세 디버깅 명령어

실패한 종목들을 재수집하면서 상세한 API 응답을 분석하여
데이터가 정말 없음(상장 전/상장 해제)인지, API 오류인지 확인합니다.
"""
from django.core.management.base import BaseCommand
from stocks.models import Stock
from financials.models import FinancialStatement
import requests
import io
import zipfile
import xml.etree.ElementTree as ET
import json
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '실패한 재무 데이터를 재수집하면서 상세 오류 정보를 분석합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-codes',
            nargs='+',
            help='특정 종목코드들만 분석 (없으면 모든 미검증 종목)',
        )
        parser.add_argument(
            '--years',
            nargs='+',
            type=int,
            help='특정 연도만 분석 (없으면 모든 미검증 연도)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='분석 결과를 JSON 파일로 저장할 경로',
        )
        parser.add_argument(
            '--retry',
            action='store_true',
            help='데이터가 존재하는 경우 재수집 실행',
        )

    def handle(self, *args, **options):
        api_key = os.getenv('DART_API_KEY')
        if not api_key:
            self.stdout.write(
                self.style.ERROR('❌ DART_API_KEY 환경변수가 필요합니다.')
            )
            return

        stock_codes = options.get('stock_codes')
        years = options.get('years')
        output_path = options.get('output')
        retry = options.get('retry', False)

        self.stdout.write('=' * 70)
        self.stdout.write(self.style.SUCCESS('🔍 재무 데이터 수집 실패 원인 상세 분석'))
        self.stdout.write('=' * 70 + '\n')

        # DART 기업 고유번호 매핑 조회
        self.stdout.write('📋 DART 기업 고유번호 매핑 조회 중...')
        corp_mapping = self._get_corp_mapping(api_key)
        if not corp_mapping:
            self.stdout.write(self.style.ERROR('❌ 기업 목록 조회 실패'))
            return
        self.stdout.write(f'✅ {len(corp_mapping)}개 기업 정보 조회 완료\n')

        # 분석 대상 추출
        if stock_codes:
            stocks = Stock.objects.filter(stock_code__in=stock_codes)
            analysis_targets = []
            for stock in stocks:
                stock_financials = FinancialStatement.objects.filter(
                    stock=stock, is_verified=False
                )
                if years:
                    stock_financials = stock_financials.filter(year__in=years)
                for fs in stock_financials:
                    analysis_targets.append({
                        'stock': stock,
                        'year': fs.year
                    })
        else:
            # 모든 미검증 데이터
            not_verified = FinancialStatement.objects.filter(is_verified=False).select_related('stock')
            if years:
                not_verified = not_verified.filter(year__in=years)
            
            analysis_targets = []
            seen = set()
            for fs in not_verified:
                key = (fs.stock.stock_code, fs.year)
                if key not in seen:
                    seen.add(key)
                    analysis_targets.append({
                        'stock': fs.stock,
                        'year': fs.year
                    })

        total = len(analysis_targets)
        self.stdout.write(f'📊 분석 대상: {total}개 항목\n')

        if total == 0:
            self.stdout.write(self.style.WARNING('⚠️  분석할 항목이 없습니다.'))
            return

        results = []
        success_count = 0
        no_data_count = 0
        api_error_count = 0
        other_error_count = 0

        for i, target in enumerate(analysis_targets, 1):
            stock = target['stock']
            year = target['year']

            self.stdout.write(f'\n[{i}/{total}] {stock.stock_name} ({stock.stock_code}) - {year}년 분석 중...')

            corp_code = corp_mapping.get(stock.stock_code)
            if not corp_code:
                result = {
                    'stock_code': stock.stock_code,
                    'stock_name': stock.stock_name,
                    'year': year,
                    'status': 'corp_code_not_found',
                    'message': 'DART 고유번호를 찾을 수 없습니다'
                }
                results.append(result)
                self.stdout.write(f"  ❌ DART 고유번호 없음")
                other_error_count += 1
                continue

            # DART API 조회
            analysis_result = self._analyze_dart_api_response(api_key, corp_code, year)
            
            result = {
                'stock_code': stock.stock_code,
                'stock_name': stock.stock_name,
                'corp_code': corp_code,
                'year': year,
                **analysis_result
            }
            results.append(result)

            # 결과 출력
            status = analysis_result['status']
            if status == 'success':
                self.stdout.write(f"  ✅ 데이터 존재 (재수집 가능)")
                if retry:
                    # 재수집 실행
                    self._retry_collect(stock, corp_code, year)
                success_count += 1
            elif status == 'no_data':
                self.stdout.write(f"  ⏭️  데이터 없음 (정상 - 상장 전/해제 또는 미제공)")
                self.stdout.write(f"      이유: {analysis_result.get('reason', 'N/A')}")
                no_data_count += 1
            elif status == 'api_error':
                self.stdout.write(f"  ❌ API 오류")
                self.stdout.write(f"      오류: {analysis_result.get('error_message', 'N/A')}")
                api_error_count += 1
            else:
                self.stdout.write(f"  ⚠️  기타 오류")
                self.stdout.write(f"      메시지: {analysis_result.get('message', 'N/A')}")
                other_error_count += 1

        # 결과 요약
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('📊 분석 결과 요약'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'✅ 데이터 존재 (재수집 가능): {success_count}개')
        self.stdout.write(f'⏭️  데이터 없음 (정상): {no_data_count}개')
        self.stdout.write(f'❌ API 오류: {api_error_count}개')
        self.stdout.write(f'⚠️  기타 오류: {other_error_count}개')
        self.stdout.write(f'📊 전체: {total}개\n')

        # 파일로 저장
        if output_path:
            report = {
                'analysis_date': datetime.now().isoformat(),
                'summary': {
                    'total': total,
                    'success': success_count,
                    'no_data': no_data_count,
                    'api_error': api_error_count,
                    'other_error': other_error_count
                },
                'details': results
            }
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            self.stdout.write(f'💾 상세 분석 결과가 {output_path}에 저장되었습니다.')

        # 권장사항
        self.stdout.write('\n=== 권장사항 ===')
        if success_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ {success_count}개 항목은 데이터가 존재합니다. --retry 옵션으로 재수집하세요.'
                )
            )
        if no_data_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⏭️  {no_data_count}개 항목은 데이터가 없습니다. 상장 전/해제 또는 미제공으로 정상입니다.'
                )
            )
        if api_error_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'❌ {api_error_count}개 항목은 API 오류입니다. 나중에 재시도하거나 DART API 상태를 확인하세요.'
                )
            )

    def _get_corp_mapping(self, api_key: str) -> Dict[str, str]:
        """DART 기업 고유번호 매핑 조회"""
        url = "https://opendart.fss.or.kr/api/corpCode.xml"
        params = {"crtfc_key": api_key}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                xml_content = zip_file.read('CORPCODE.xml')

            root = ET.fromstring(xml_content)
            corp_mapping = {}

            for item in root.findall('.//list'):
                corp_code = item.findtext('corp_code', '').strip()
                stock_code = item.findtext('stock_code', '').strip()

                if stock_code and corp_code:
                    corp_mapping[stock_code] = corp_code

            return corp_mapping

        except Exception as e:
            logger.error(f"기업 목록 조회 실패: {str(e)}")
            return {}

    def _analyze_dart_api_response(self, api_key: str, corp_code: str, year: int) -> Dict:
        """DART API 응답을 분석하여 상태를 판단"""
        base_url = "https://opendart.fss.or.kr/api"
        url = f"{base_url}/fnlttSinglAcntAll.json"

        result = {
            'status': 'unknown',
            'message': '',
            'cfs_response': None,
            'ofs_response': None,
            'error_message': None
        }

        # CFS (연결재무제표) 시도
        params_cfs = {
            "crtfc_key": api_key,
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",
            "fs_div": "CFS"
        }

        try:
            response = requests.get(url, params=params_cfs, timeout=20)
            response.raise_for_status()
            data_cfs = response.json()

            result['cfs_response'] = {
                'status': data_cfs.get('status'),
                'message': data_cfs.get('message', ''),
                'has_data': len(data_cfs.get('list', [])) > 0
            }

            if data_cfs.get('status') == '000':
                # CFS 성공
                list_data = data_cfs.get('list', [])
                if list_data:
                    result['status'] = 'success'
                    result['message'] = 'CFS로 데이터 조회 성공'
                    return result
                else:
                    result['status'] = 'no_data'
                    result['reason'] = 'CFS 조회 성공했지만 데이터 리스트가 비어있음'
                    return result

            # CFS 실패 - OFS 시도
            cfs_status = data_cfs.get('status')
            cfs_message = data_cfs.get('message', '')
            
            # 일반적인 "데이터 없음" 메시지 패턴
            no_data_messages = [
                '조회된 데이터가 없습니다',
                '등록된 데이터가 없습니다',
                '재무정보가 없습니다'
            ]
            
            if any(msg in cfs_message for msg in no_data_messages):
                # 데이터가 없음으로 판단
                result['status'] = 'no_data'
                result['reason'] = f'CFS: {cfs_message}'
                
                # OFS도 확인해봄
                params_ofs = params_cfs.copy()
                params_ofs['fs_div'] = 'OFS'
                response_ofs = requests.get(url, params=params_ofs, timeout=20)
                data_ofs = response_ofs.json()
                
                result['ofs_response'] = {
                    'status': data_ofs.get('status'),
                    'message': data_ofs.get('message', ''),
                    'has_data': len(data_ofs.get('list', [])) > 0
                }
                
                if data_ofs.get('status') == '000' and data_ofs.get('list'):
                    # OFS로 성공
                    result['status'] = 'success'
                    result['message'] = 'CFS 실패, OFS로 데이터 조회 성공'
                    return result
                elif data_ofs.get('status') != '000':
                    ofs_message = data_ofs.get('message', '')
                    if any(msg in ofs_message for msg in no_data_messages):
                        result['reason'] += f' / OFS: {ofs_message}'
                
                return result

            # CFS 실패 - OFS 시도 (일반 오류인 경우)
            params_ofs = params_cfs.copy()
            params_ofs['fs_div'] = 'OFS'
            response_ofs = requests.get(url, params=params_ofs, timeout=20)
            data_ofs = response_ofs.json()

            result['ofs_response'] = {
                'status': data_ofs.get('status'),
                'message': data_ofs.get('message', ''),
                'has_data': len(data_ofs.get('list', [])) > 0
            }

            if data_ofs.get('status') == '000':
                list_data = data_ofs.get('list', [])
                if list_data:
                    result['status'] = 'success'
                    result['message'] = 'CFS 실패, OFS로 데이터 조회 성공'
                    return result
                else:
                    result['status'] = 'no_data'
                    result['reason'] = 'OFS 조회 성공했지만 데이터 리스트가 비어있음'
                    return result

            # 모두 실패
            ofs_status = data_ofs.get('status')
            ofs_message = data_ofs.get('message', '')
            
            # 데이터 없음인지 API 오류인지 판단
            if any(msg in ofs_message for msg in no_data_messages):
                result['status'] = 'no_data'
                result['reason'] = f'CFS: {cfs_message} / OFS: {ofs_message}'
            else:
                result['status'] = 'api_error'
                result['error_message'] = f'CFS: {cfs_message} / OFS: {ofs_message}'

        except requests.exceptions.Timeout:
            result['status'] = 'api_error'
            result['error_message'] = 'API 요청 타임아웃'
        except requests.exceptions.RequestException as e:
            result['status'] = 'api_error'
            result['error_message'] = f'API 요청 오류: {str(e)}'
        except Exception as e:
            result['status'] = 'api_error'
            result['error_message'] = f'예상치 못한 오류: {str(e)}'

        return result

    def _retry_collect(self, stock, corp_code: str, year: int):
        """데이터가 존재하는 경우 재수집"""
        from financials.management.commands.collect_and_verify_financial_data import DartAPIClient
        import os
        
        api_key = os.getenv('DART_API_KEY')
        client = DartAPIClient(api_key)
        
        financial_data = client.fetch_financial_data(stock.stock_code, corp_code, year)
        if financial_data:
            FinancialStatement.objects.update_or_create(
                stock=stock,
                year=year,
                defaults={
                    **financial_data,
                    'is_verified': True,
                    'verification_status': 'exact_match'
                }
            )
            self.stdout.write(f"      ✅ {year}년 데이터 재수집 완료")
        else:
            self.stdout.write(f"      ⚠️  재수집 실패 (파싱 오류 가능)")

