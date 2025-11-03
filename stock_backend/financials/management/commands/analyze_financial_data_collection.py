"""
재무 데이터 수집 및 검증 결과 분석 명령어

수집 및 검증이 완료된 후 실패한 종목들을 찾아서 이유를 분석합니다.
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from stocks.models import Stock
from financials.models import FinancialStatement
import os
import json
from datetime import datetime
from collections import defaultdict


class Command(BaseCommand):
    help = '재무 데이터 수집 및 검증 결과를 분석하여 실패한 종목들을 찾고 이유를 분석합니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            help='분석 결과를 JSON 파일로 저장할 경로',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv', 'both'],
            default='json',
            help='출력 형식 (기본값: json)',
        )

    def handle(self, *args, **options):
        output_path = options.get('output')
        format_type = options.get('format')

        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS('📊 재무 데이터 수집 및 검증 결과 분석'))
        self.stdout.write('=' * 60 + '\n')

        # 전체 통계
        total = FinancialStatement.objects.count()
        verified = FinancialStatement.objects.filter(is_verified=True).count()
        not_verified = FinancialStatement.objects.filter(is_verified=False).count()

        self.stdout.write('=== 전체 통계 ===')
        self.stdout.write(f'전체 재무 데이터: {total}개')
        self.stdout.write(
            self.style.SUCCESS(f'✅ 검증 완료: {verified}개 ({verified/total*100:.1f}%)')
        )
        self.stdout.write(
            self.style.WARNING(f'⚠️  미검증: {not_verified}개 ({not_verified/total*100:.1f}%)')
        )
        self.stdout.write('')

        # 검증 상태별 통계
        self.stdout.write('=== 검증 상태별 통계 ===')
        status_stats = FinancialStatement.objects.values('verification_status').annotate(
            count=Count('id')
        ).order_by('-count')

        for stat in status_stats:
            status = stat['verification_status']
            count = stat['count']
            if status == 'exact_match':
                style = self.style.SUCCESS
            elif status == 'not_verified':
                style = self.style.WARNING
            else:
                style = self.style.ERROR
            self.stdout.write(style(f'{status}: {count}개'))
        self.stdout.write('')

        # 종목별 분석
        self.stdout.write('=== 종목별 검증 상태 ===')
        stock_stats = Stock.objects.annotate(
            total_financials=Count('financials'),
            verified_financials=Count('financials', filter=Q(financials__is_verified=True)),
            not_verified_financials=Count('financials', filter=Q(financials__is_verified=False)),
            exact_match=Count('financials', filter=Q(financials__verification_status='exact_match')),
            difference=Count('financials', filter=Q(financials__verification_status='difference')),
            api_error=Count('financials', filter=Q(financials__verification_status='api_error')),
        ).filter(total_financials__gt=0).order_by('-not_verified_financials')

        # 완전히 검증된 종목
        fully_verified = [s for s in stock_stats if s.not_verified_financials == 0]
        self.stdout.write(
            self.style.SUCCESS(f'\n✅ 완전히 검증된 종목: {len(fully_verified)}개')
        )

        # 부분적으로 검증된 종목
        partially_verified = [
            s for s in stock_stats
            if s.verified_financials > 0 and s.not_verified_financials > 0
        ]
        self.stdout.write(
            self.style.WARNING(f'⚠️  부분 검증된 종목: {len(partially_verified)}개')
        )

        # 전혀 검증되지 않은 종목
        not_verified_stocks = [
            s for s in stock_stats if s.verified_financials == 0 and s.total_financials > 0
        ]
        self.stdout.write(
            self.style.ERROR(f'❌ 미검증 종목: {len(not_verified_stocks)}개\n')
        )

        # 미검증 종목 상세 분석
        not_verified_details = []
        if not_verified_stocks:
            self.stdout.write('=== 미검증 종목 상세 ===')
            
            for i, stock in enumerate(not_verified_stocks[:20], 1):
                financials = FinancialStatement.objects.filter(
                    stock=stock, is_verified=False
                ).order_by('-year')

                years = [f.year for f in financials]
                statuses = financials.values_list('verification_status', flat=True).distinct()

                detail = {
                    'stock_code': stock.stock_code,
                    'stock_name': stock.stock_name,
                    'total_count': stock.total_financials,
                    'not_verified_count': stock.not_verified_financials,
                    'years': sorted(years),
                    'statuses': list(statuses),
                }
                not_verified_details.append(detail)

                self.stdout.write(
                    f'{i}. {stock.stock_name} ({stock.stock_code}): '
                    f'{stock.not_verified_financials}개 - {sorted(years)}년'
                )
                if len(statuses) > 1:
                    self.stdout.write(f'   상태: {", ".join(statuses)}')

        # 검증 상태별 종목 그룹화
        by_status = defaultdict(list)
        for stock in stock_stats:
            if stock.not_verified_financials > 0:
                financials = FinancialStatement.objects.filter(
                    stock=stock, is_verified=False
                )
                for fs in financials:
                    by_status[fs.verification_status].append({
                        'stock_code': stock.stock_code,
                        'stock_name': stock.stock_name,
                        'year': fs.year,
                    })

        # 결과 데이터 구성
        analysis_result = {
            'analysis_date': datetime.now().isoformat(),
            'summary': {
                'total_financial_statements': total,
                'verified_count': verified,
                'not_verified_count': not_verified,
                'verification_rate': round(verified / total * 100, 2) if total > 0 else 0,
            },
            'status_breakdown': {
                stat['verification_status']: stat['count']
                for stat in status_stats
            },
            'stocks_summary': {
                'fully_verified': len(fully_verified),
                'partially_verified': len(partially_verified),
                'not_verified': len(not_verified_stocks),
            },
            'not_verified_details': not_verified_details[:50],  # 상위 50개만
            'failures_by_status': {
                status: len(stocks) for status, stocks in by_status.items()
            },
        }

        # 파일로 저장
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, ensure_ascii=False, indent=2)
            self.stdout.write(f'\n💾 분석 결과가 {output_path}에 저장되었습니다.')

        # 실패 원인 분석
        self.stdout.write('\n=== 실패 원인 분석 ===')
        
        # API 오류
        api_errors = FinancialStatement.objects.filter(verification_status='api_error')
        if api_errors.exists():
            self.stdout.write(
                self.style.ERROR(f'\n❌ API 오류: {api_errors.count()}개')
            )
            api_error_stocks = api_errors.values_list('stock__stock_code', 'stock__stock_name', 'year').distinct()
            self.stdout.write('   주요 종목:')
            for code, name, year in api_error_stocks[:10]:
                self.stdout.write(f'   - {name} ({code}) - {year}년')

        # 차이 발견
        differences = FinancialStatement.objects.filter(verification_status='difference')
        if differences.exists():
            self.stdout.write(
                self.style.ERROR(f'\n⚠️  차이 발견: {differences.count()}개')
            )

        # 미검증
        not_verified_fs = FinancialStatement.objects.filter(verification_status='not_verified')
        if not_verified_fs.exists():
            self.stdout.write(
                self.style.WARNING(f'\n⚠️  미검증: {not_verified_fs.count()}개')
            )
            # 미검증 데이터의 연도 분포
            years_dist = not_verified_fs.values('year').annotate(count=Count('id')).order_by('year')
            self.stdout.write('   연도별 분포:')
            for item in years_dist:
                self.stdout.write(f'   - {item["year"]}년: {item["count"]}개')

        # 권장사항
        self.stdout.write('\n=== 권장사항 ===')
        if not_verified_stocks:
            self.stdout.write(
                self.style.WARNING(
                    f'1. {len(not_verified_stocks)}개 종목의 재무 데이터가 미검증 상태입니다.'
                )
            )
            self.stdout.write('   다음 명령어로 특정 종목을 다시 수집하세요:')
            sample_codes = [s.stock_code for s in not_verified_stocks[:5]]
            self.stdout.write(
                f'   python manage.py collect_and_verify_financial_data '
                f'--stock-codes {" ".join(sample_codes)} --overwrite --verify'
            )

        if api_errors.exists():
            self.stdout.write(
                self.style.ERROR(
                    f'2. {api_errors.count()}개의 API 오류가 있습니다.'
                )
            )
            self.stdout.write('   - DART API 연결 상태 확인')
            self.stdout.write('   - API 키 유효성 확인')
            self.stdout.write('   - 해당 종목의 DART 고유번호 확인')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ 분석 완료'))
        self.stdout.write('=' * 60)

