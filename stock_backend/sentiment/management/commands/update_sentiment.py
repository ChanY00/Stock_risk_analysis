import json
import os
from datetime import datetime
from django.core.management.base import BaseCommand
from sentiment.models import SentimentAnalysis
from stocks.models import Stock

class Command(BaseCommand):
    help = 'Update sentiment analysis data from Stock_risk_analysis results'

    def add_arguments(self, parser):
        parser.add_argument(
            '--json-file',
            type=str,
            help='Path to the sentiment analysis JSON file',
            required=True
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        
        if not os.path.exists(json_file):
            self.stdout.write(self.style.ERROR(f'File not found: {json_file}'))
            return

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('Invalid JSON file'))
            return

        updated_count = 0
        for item in data:
            try:
                stock = Stock.objects.get(stock_code=item['stock_code'])
                
                # 업데이트 시간을 파싱
                updated_at = datetime.fromisoformat(item['updated_at'].replace('Z', '+00:00'))
                
                # SentimentAnalysis 객체 생성 또는 업데이트
                sentiment, created = SentimentAnalysis.objects.update_or_create(
                    stock=stock,
                    defaults={
                        'positive': item['positive'],
                        'negative': item['negative'],
                        'top_keywords': item['top_keywords'],
                        'updated_at': updated_at
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(
                        f'Created sentiment analysis for {stock.stock_name}'
                    ))
                else:
                    self.stdout.write(self.style.SUCCESS(
                        f'Updated sentiment analysis for {stock.stock_name}'
                    ))
                updated_count += 1

            except Stock.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f'Stock not found: {item["stock_code"]}'
                ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(
                    f'Error processing {item["stock_code"]}: {str(e)}'
                ))

        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed {updated_count} sentiment analysis results'
        )) 