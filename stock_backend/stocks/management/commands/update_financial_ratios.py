from django.core.management.base import BaseCommand
from stocks.models import Stock
from django.db.models import Q

class Command(BaseCommand):
    help = 'Update all financial ratios (PER, PBR, ROE) and market cap for all stocks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stock-code',
            type=str,
            help='Update only specific stock by code',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output for each stock',
        )

    def handle(self, *args, **options):
        stock_code = options.get('stock_code')
        verbose = options.get('verbose', False)
        
        if stock_code:
            stocks = Stock.objects.filter(stock_code=stock_code)
            if not stocks.exists():
                self.stdout.write(
                    self.style.ERROR(f'Stock with code {stock_code} not found')
                )
                return
        else:
            stocks = Stock.objects.all()
        
        total_count = stocks.count()
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting update for {total_count} stocks...')
        )
        
        for idx, stock in enumerate(stocks, 1):
            try:
                # 최신 주가 확인
                current_price = stock.get_current_price()
                if not current_price:
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'[{idx}/{total_count}] {stock.stock_name} ({stock.stock_code}): No price data'
                            )
                        )
                    skipped_count += 1
                    continue
                
                # 최신 재무 데이터 확인
                latest_financial = stock.financials.first()
                if not latest_financial:
                    if verbose:
                        self.stdout.write(
                            self.style.WARNING(
                                f'[{idx}/{total_count}] {stock.stock_name} ({stock.stock_code}): No financial data'
                            )
                        )
                    skipped_count += 1
                    continue
                
                # update_financial_ratios() 메서드 호출
                # 이 메서드가 PER, PBR, ROE, 시가총액을 모두 계산하고 저장함
                stock.update_financial_ratios()
                
                if verbose:
                    per_str = f'{stock.per:.2f}' if stock.per else 'N/A'
                    pbr_str = f'{stock.pbr:.2f}' if stock.pbr else 'N/A'
                    roe_str = f'{stock.roe:.2f}' if stock.roe else 'N/A'
                    mcap_str = f'{stock.market_cap:,}' if stock.market_cap else 'N/A'
                    
                    self.stdout.write(
                        f'[{idx}/{total_count}] Updated {stock.stock_name} ({stock.stock_code}): '
                        f'PER={per_str}, PBR={pbr_str}, ROE={roe_str}%, Market Cap={mcap_str}'
                    )
                
                updated_count += 1
                
                # 진행 상황 표시 (10개마다)
                if not verbose and idx % 10 == 0:
                    self.stdout.write(f'Progress: {idx}/{total_count} stocks processed...')
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f'[{idx}/{total_count}] Error updating {stock.stock_name} ({stock.stock_code}): {str(e)}'
                    )
                )
                error_count += 1
        
        # 최종 결과 출력
        self.stdout.write('\n' + '='*70)
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Successfully updated: {updated_count} stocks'
            )
        )
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⊘ Skipped (no data): {skipped_count} stocks'
                )
            )
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(
                    f'✗ Errors: {error_count} stocks'
                )
            )
        self.stdout.write('='*70)

