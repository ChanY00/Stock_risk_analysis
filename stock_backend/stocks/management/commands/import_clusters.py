import csv
import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from stocks.models import Stock
from analysis.models import SpectralCluster, AgglomerativeCluster, ClusterAnalysis
from collections import Counter

class Command(BaseCommand):
    help = 'Import clustering results from CSV files'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--spectral-file',
            type=str,
            help='Path to spectral clustering CSV file',
            default='spectral_clustered_company.csv'
        )
        parser.add_argument(
            '--agglomerative-file', 
            type=str,
            help='Path to agglomerative clustering CSV file',
            default='clustered_tickers_agglomerative.csv'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to the database'
        )

    def handle(self, *args, **options):
        spectral_file = options['spectral_file']
        agglomerative_file = options['agglomerative_file']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        # Import spectral clustering
        if os.path.exists(spectral_file):
            self.import_spectral_clusters(spectral_file, dry_run)
        else:
            self.stdout.write(self.style.ERROR(f'Spectral file not found: {spectral_file}'))
            
        # Import agglomerative clustering  
        if os.path.exists(agglomerative_file):
            self.import_agglomerative_clusters(agglomerative_file, dry_run)
        else:
            self.stdout.write(self.style.ERROR(f'Agglomerative file not found: {agglomerative_file}'))
    
    def import_spectral_clusters(self, file_path, dry_run=False):
        """Spectral clustering 결과 임포트"""
        self.stdout.write(f'Importing spectral clusters from: {file_path}')
        
        imported_count = 0
        skipped_count = 0
        cluster_stats = Counter()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            with transaction.atomic():
                if not dry_run:
                    # 기존 데이터 삭제
                    SpectralCluster.objects.all().delete()
                
                for row in reader:
                    ticker = row['ticker'].strip()
                    cluster_id = int(row['cluster'])
                    
                    # 6자리 ticker를 stock_code 형식으로 변환
                    if len(ticker) == 6:
                        stock_code = ticker
                    else:
                        self.stdout.write(self.style.WARNING(f'Invalid ticker format: {ticker}'))
                        skipped_count += 1
                        continue
                    
                    try:
                        stock = Stock.objects.get(stock_code=stock_code)
                        
                        if not dry_run:
                            spectral_cluster, created = SpectralCluster.objects.get_or_create(
                                stock=stock,
                                defaults={'cluster_id': cluster_id}
                            )
                            if not created:
                                spectral_cluster.cluster_id = cluster_id
                                spectral_cluster.save()
                        
                        cluster_stats[cluster_id] += 1
                        imported_count += 1
                        
                    except Stock.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'Stock not found: {stock_code}'))
                        skipped_count += 1
                        continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Spectral clustering: {imported_count} imported, {skipped_count} skipped'
        ))
        self.stdout.write(f'Cluster distribution: {dict(cluster_stats)}')
        
        # 클러스터 분석 정보 생성
        if not dry_run:
            self.generate_cluster_analysis('spectral', cluster_stats)
    
    def import_agglomerative_clusters(self, file_path, dry_run=False):
        """Agglomerative clustering 결과 임포트"""
        self.stdout.write(f'Importing agglomerative clusters from: {file_path}')
        
        imported_count = 0
        skipped_count = 0
        cluster_stats = Counter()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            with transaction.atomic():
                if not dry_run:
                    # 기존 데이터 삭제
                    AgglomerativeCluster.objects.all().delete()
                
                for row in reader:
                    ticker = row['Ticker'].strip()
                    cluster_id = int(row['Cluster'])
                    
                    # Yahoo Finance 형식 (.KS 제거)
                    if ticker.endswith('.KS'):
                        stock_code = ticker[:-3]
                    else:
                        stock_code = ticker
                    
                    try:
                        stock = Stock.objects.get(stock_code=stock_code)
                        
                        if not dry_run:
                            agg_cluster, created = AgglomerativeCluster.objects.get_or_create(
                                stock=stock,
                                defaults={'cluster_id': cluster_id}
                            )
                            if not created:
                                agg_cluster.cluster_id = cluster_id
                                agg_cluster.save()
                        
                        cluster_stats[cluster_id] += 1
                        imported_count += 1
                        
                    except Stock.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f'Stock not found: {stock_code}'))
                        skipped_count += 1
                        continue
        
        self.stdout.write(self.style.SUCCESS(
            f'Agglomerative clustering: {imported_count} imported, {skipped_count} skipped'
        ))
        self.stdout.write(f'Cluster distribution: {dict(cluster_stats)}')
        
        # 클러스터 분석 정보 생성
        if not dry_run:
            self.generate_cluster_analysis('agglomerative', cluster_stats)
    
    def generate_cluster_analysis(self, cluster_type, cluster_stats):
        """클러스터 분석 정보 생성"""
        self.stdout.write(f'Generating {cluster_type} cluster analysis...')
        
        # 기존 분석 정보 삭제
        ClusterAnalysis.objects.filter(cluster_type=cluster_type).delete()
        
        for cluster_id, stock_count in cluster_stats.items():
            # 해당 클러스터의 주식들 조회
            if cluster_type == 'spectral':
                cluster_stocks = Stock.objects.filter(spectral_cluster__cluster_id=cluster_id)
            else:
                cluster_stocks = Stock.objects.filter(agglomerative_cluster__cluster_id=cluster_id)
            
            # 섹터 분포 계산
            sector_counts = Counter()
            market_caps = []
            pers = []
            pbrs = []
            
            for stock in cluster_stocks:
                if stock.sector:
                    sector_counts[stock.sector] += 1
                if stock.market_cap:
                    market_caps.append(stock.market_cap)
                if stock.per:
                    pers.append(stock.per)
                if stock.pbr:
                    pbrs.append(stock.pbr)
            
            # 주요 섹터 (상위 3개)
            dominant_sectors = [sector for sector, count in sector_counts.most_common(3)]
            
            # 평균값 계산
            avg_market_cap = sum(market_caps) // len(market_caps) if market_caps else None
            avg_per = sum(pers) / len(pers) if pers else None
            avg_pbr = sum(pbrs) / len(pbrs) if pbrs else None
            
            # 클러스터 특성 결정
            cluster_name = self.determine_cluster_name(cluster_type, cluster_id, dominant_sectors, avg_market_cap)
            
            ClusterAnalysis.objects.create(
                cluster_type=cluster_type,
                cluster_id=cluster_id,
                cluster_name=cluster_name,
                description=f'{cluster_type} 클러스터 {cluster_id}',
                dominant_sectors=dominant_sectors,
                stock_count=stock_count,
                avg_market_cap=avg_market_cap,
                avg_per=avg_per,
                avg_pbr=avg_pbr,
                characteristics={
                    'sector_distribution': dict(sector_counts),
                    'market_cap_range': {
                        'min': min(market_caps) if market_caps else None,
                        'max': max(market_caps) if market_caps else None
                    }
                }
            )
        
        self.stdout.write(self.style.SUCCESS(f'{cluster_type} cluster analysis completed'))
    
    def determine_cluster_name(self, cluster_type, cluster_id, dominant_sectors, avg_market_cap):
        """클러스터 이름 결정"""
        # 간단한 네이밍 로직
        if avg_market_cap and avg_market_cap > 50_000_000_000_000:  # 50조 이상
            size_label = "대형주"
        elif avg_market_cap and avg_market_cap > 5_000_000_000_000:  # 5조 이상
            size_label = "중형주"
        else:
            size_label = "소형주"
        
        if dominant_sectors:
            main_sector = dominant_sectors[0]
            if main_sector == 'Technology':
                sector_label = "테크"
            elif main_sector == 'Financial Services':
                sector_label = "금융"
            elif main_sector == 'Industrials':
                sector_label = "산업재"
            elif main_sector == 'Consumer Cyclical':
                sector_label = "소비재"
            elif main_sector == 'Healthcare':
                sector_label = "헬스케어"
            else:
                sector_label = main_sector
                
            return f"{size_label} {sector_label} 그룹"
        else:
            return f"{size_label} 클러스터 {cluster_id}" 