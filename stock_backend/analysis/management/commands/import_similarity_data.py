import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from stocks.models import Stock
from analysis.models import StockSimilarity


class Command(BaseCommand):
    help = 'Import stock similarity data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-file',
            type=str,
            default='nearest_neighbors_within_cluster.csv',
            help='CSV file path (default: nearest_neighbors_within_cluster.csv)'
        )
        parser.add_argument(
            '--cluster-type',
            type=str,
            default='spectral',
            choices=['spectral', 'agglomerative'],
            help='Cluster type (default: spectral)'
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing similarity data before import'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        cluster_type = options['cluster_type']
        clear_existing = options['clear_existing']

        # CSV 파일 존재 확인
        if not os.path.exists(csv_file):
            self.stdout.write(
                self.style.ERROR(f'CSV 파일을 찾을 수 없습니다: {csv_file}')
            )
            return

        # 기존 데이터 삭제 (옵션)
        if clear_existing:
            deleted_count = StockSimilarity.objects.filter(cluster_type=cluster_type).count()
            StockSimilarity.objects.filter(cluster_type=cluster_type).delete()
            self.stdout.write(
                self.style.WARNING(f'기존 {cluster_type} 유사도 데이터 {deleted_count}개 삭제됨')
            )

        # 종목 코드 매핑 생성 (성능 최적화)
        stock_mapping = {stock.stock_code: stock for stock in Stock.objects.all()}
        
        imported_count = 0
        skipped_count = 0
        error_count = 0

        try:
            with open(csv_file, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                with transaction.atomic():
                    for row in reader:
                        try:
                            cluster_id = int(row['cluster'])
                            source_ticker = row['source_ticker']
                            neighbor_ticker = row['neighbor_ticker']
                            neighbor_rank = int(row['neighbor_rank'])
                            distance = float(row['distance'])

                            # 종목 조회
                            source_stock = stock_mapping.get(source_ticker)
                            target_stock = stock_mapping.get(neighbor_ticker)

                            if not source_stock:
                                self.stdout.write(
                                    self.style.WARNING(f'종목을 찾을 수 없음: {source_ticker}')
                                )
                                skipped_count += 1
                                continue

                            if not target_stock:
                                self.stdout.write(
                                    self.style.WARNING(f'종목을 찾을 수 없음: {neighbor_ticker}')
                                )
                                skipped_count += 1
                                continue

                            # StockSimilarity 객체 생성 또는 업데이트
                            similarity, created = StockSimilarity.objects.update_or_create(
                                cluster_type=cluster_type,
                                source_stock=source_stock,
                                target_stock=target_stock,
                                defaults={
                                    'cluster_id': cluster_id,
                                    'neighbor_rank': neighbor_rank,
                                    'distance': distance,
                                }
                            )

                            if created:
                                imported_count += 1
                            else:
                                imported_count += 1  # 업데이트도 카운트

                            # 진행 상황 출력 (100개마다)
                            if imported_count % 100 == 0:
                                self.stdout.write(f'처리된 데이터: {imported_count}개')

                        except (ValueError, KeyError) as e:
                            self.stdout.write(
                                self.style.ERROR(f'데이터 처리 오류: {row} - {str(e)}')
                            )
                            error_count += 1
                            continue

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(f'파일을 읽을 수 없습니다: {csv_file}')
            )
            return
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'예상치 못한 오류: {str(e)}')
            )
            return

        # 결과 출력
        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== {cluster_type.upper()} 클러스터 유사도 데이터 임포트 완료 ==='
            )
        )
        self.stdout.write(f'✅ 성공적으로 임포트된 데이터: {imported_count}개')
        self.stdout.write(f'⚠️  건너뛴 데이터: {skipped_count}개')
        self.stdout.write(f'❌ 오류 발생 데이터: {error_count}개')

        # 클러스터별 통계 출력
        cluster_stats = {}
        for similarity in StockSimilarity.objects.filter(cluster_type=cluster_type):
            cluster_id = similarity.cluster_id
            if cluster_id not in cluster_stats:
                cluster_stats[cluster_id] = 0
            cluster_stats[cluster_id] += 1

        self.stdout.write('\n=== 클러스터별 유사도 데이터 통계 ===')
        for cluster_id, count in sorted(cluster_stats.items()):
            self.stdout.write(f'클러스터 {cluster_id}: {count}개 관계')

        # 추천 사용법 출력
        self.stdout.write(
            self.style.SUCCESS(
                f'\n💡 사용 예시:'
                f'\n   - 특정 종목의 유사 종목: StockSimilarity.get_most_similar_stocks(stock)'
                f'\n   - 네트워크 분석: StockSimilarity.get_similarity_network("{cluster_type}", cluster_id)'
            )
        ) 