from django.core.management.base import BaseCommand
from stocks.models import Stock
from financials.models import FinancialStatement

class Command(BaseCommand):
    help = 'Update ROE for all stocks based on financial data'

    def handle(self, *args, **options):
        stocks = Stock.objects.all()
        updated_count = 0
        
        for stock in stocks:
            try:
                # 최신 재무 데이터 가져오기
                financial = stock.financials.first()
                
                if financial and financial.total_equity and financial.total_equity > 0:
                    # ROE 계산: (순이익 / 총자본) * 100
                    calculated_roe = (financial.net_income / financial.total_equity) * 100
                    
                    # ROE 업데이트
                    stock.roe = calculated_roe
                    stock.save()
                    
                    self.stdout.write(
                        f"Updated {stock.stock_name} ({stock.stock_code}): ROE = {calculated_roe:.2f}%"
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"No financial data or zero equity for {stock.stock_name} ({stock.stock_code})"
                        )
                    )
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error updating {stock.stock_name} ({stock.stock_code}): {str(e)}"
                    )
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated ROE for {updated_count} stocks'
            )
        ) 