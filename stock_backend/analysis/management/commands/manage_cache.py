from django.core.management.base import BaseCommand
from analysis.cache_utils import CacheManager, CacheStats
import json

class Command(BaseCommand):
    help = '캐시를 관리하는 명령어입니다'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='모든 캐시를 클리어합니다'
        )
        parser.add_argument(
            '--clear-stock',
            type=str,
            help='특정 주식의 캐시를 클리어합니다 (stock_id)'
        )
        parser.add_argument(
            '--clear-market',
            action='store_true',
            help='시장 관련 캐시를 클리어합니다'
        )
        parser.add_argument(
            '--info',
            action='store_true',
            help='캐시 정보를 확인합니다'
        )
        parser.add_argument(
            '--stats',
            action='store_true',
            help='캐시 통계를 확인합니다'
        )

    def handle(self, *args, **options):
        if options.get('clear'):
            self.clear_all_cache()
        elif options.get('clear_stock'):
            self.clear_stock_cache(options['clear_stock'])
        elif options.get('clear_market'):
            self.clear_market_cache()
        elif options.get('info'):
            self.show_cache_info()
        elif options.get('stats'):
            self.show_cache_stats()
        else:
            self.stdout.write("사용법: python manage.py manage_cache --help")

    def clear_all_cache(self):
        """모든 캐시 클리어"""
        self.stdout.write("모든 캐시를 클리어합니다...")
        
        try:
            CacheStats.clear_all_caches()
            self.stdout.write(
                self.style.SUCCESS("모든 캐시가 성공적으로 클리어되었습니다.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"캐시 클리어 중 오류 발생: {str(e)}")
            )

    def clear_stock_cache(self, stock_id):
        """특정 주식 캐시 클리어"""
        self.stdout.write(f"주식 ID {stock_id}의 캐시를 클리어합니다...")
        
        try:
            CacheManager.invalidate_stock_cache(int(stock_id))
            self.stdout.write(
                self.style.SUCCESS(f"주식 ID {stock_id}의 캐시가 클리어되었습니다.")
            )
        except ValueError:
            self.stdout.write(
                self.style.ERROR("잘못된 주식 ID입니다. 숫자를 입력하세요.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"캐시 클리어 중 오류 발생: {str(e)}")
            )

    def clear_market_cache(self):
        """시장 관련 캐시 클리어"""
        self.stdout.write("시장 관련 캐시를 클리어합니다...")
        
        try:
            CacheManager.invalidate_market_cache()
            self.stdout.write(
                self.style.SUCCESS("시장 관련 캐시가 클리어되었습니다.")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"캐시 클리어 중 오류 발생: {str(e)}")
            )

    def show_cache_info(self):
        """캐시 정보 표시"""
        self.stdout.write("=== 캐시 설정 정보 ===")
        
        try:
            cache_info = CacheStats.get_cache_info()
            
            for cache_name, info in cache_info.items():
                self.stdout.write(f"\n[{cache_name.upper()} 캐시]")
                self.stdout.write(f"  백엔드: {info['backend']}")
                self.stdout.write(f"  위치: {info['location']}")
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"캐시 정보 조회 중 오류 발생: {str(e)}")
            )

    def show_cache_stats(self):
        """캐시 통계 표시"""
        self.stdout.write("=== 캐시 키 정보 ===")
        
        # 캐시 키 상수들 표시
        cache_keys = {
            "주식 목록": CacheManager.STOCK_LIST_KEY,
            "주식 상세": CacheManager.STOCK_DETAIL_KEY,
            "시장 개요": CacheManager.MARKET_OVERVIEW_KEY,
            "주식 분석": CacheManager.STOCK_ANALYSIS_KEY,
            "섹터 성과": CacheManager.SECTOR_PERFORMANCE_KEY,
            "상위 주식": CacheManager.TOP_STOCKS_KEY,
        }
        
        for desc, key in cache_keys.items():
            self.stdout.write(f"{desc:10s}: {key}")
        
        self.stdout.write("\n=== 캐시 타임아웃 설정 ===")
        
        from django.conf import settings
        timeouts = {
            "주가 데이터": getattr(settings, 'STOCK_CACHE_TIMEOUT', 'N/A'),
            "시장 데이터": getattr(settings, 'MARKET_CACHE_TIMEOUT', 'N/A'),
            "분석 데이터": getattr(settings, 'ANALYSIS_CACHE_TIMEOUT', 'N/A'),
        }
        
        for desc, timeout in timeouts.items():
            self.stdout.write(f"{desc:10s}: {timeout}초") 