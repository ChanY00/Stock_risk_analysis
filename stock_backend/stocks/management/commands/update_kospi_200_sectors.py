from django.core.management.base import BaseCommand
from stocks.models import Stock
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update KOSPI 200 stocks with real sector classification based on GICS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # KOSPI 200 종목들의 실제 GICS 섹터 분류
        # 2024년 기준 KOSPI 200 구성종목의 실제 섹터 정보
        kospi_200_sectors = {
            # IT (Information Technology)
            '005930': 'IT',  # 삼성전자
            '000660': 'IT',  # SK하이닉스
            '066570': 'IT',  # LG전자
            '009150': 'IT',  # 삼성전기
            '006400': 'IT',  # 삼성SDI
            '034220': 'IT',  # LG디스플레이
            '011070': 'IT',  # LG이노텍
            '018260': 'IT',  # 삼성SDS
            '035420': 'Communication Services',  # 네이버
            '035720': 'Communication Services',  # 카카오
            '017670': 'Communication Services',  # SK텔레콤
            '030200': 'Communication Services',  # KT
            '032640': 'Communication Services',  # LG유플러스
            
            # Financials
            '105560': 'Financials',  # KB금융
            '055550': 'Financials',  # 신한지주
            '086790': 'Financials',  # 하나금융지주
            '316140': 'Financials',  # 우리금융지주
            '029780': 'Financials',  # 삼성카드
            '000810': 'Financials',  # 삼성화재
            '032830': 'Financials',  # 삼성생명
            '088350': 'Financials',  # 한화생명
            '005830': 'Financials',  # DB손해보험
            '001450': 'Financials',  # 현대해상
            '323410': 'Financials',  # 카카오뱅크
            '039490': 'Financials',  # 키움증권
            '006800': 'Financials',  # 미래에셋증권
            
            # Consumer Discretionary
            '005380': 'Consumer Discretionary',  # 현대차
            '000270': 'Consumer Discretionary',  # 기아
            '012330': 'Consumer Discretionary',  # 현대모비스
            '018880': 'Consumer Discretionary',  # 한온시스템
            '011210': 'Consumer Discretionary',  # 현대위아
            '204320': 'Consumer Discretionary',  # HL만도
            '021240': 'Consumer Discretionary',  # 코웨이
            '161390': 'Consumer Discretionary',  # 한국타이어앤테크놀로지
            '008770': 'Consumer Discretionary',  # 호텔신라
            '069960': 'Consumer Discretionary',  # 현대백화점
            '004170': 'Consumer Discretionary',  # 신세계
            '035250': 'Consumer Discretionary',  # 강원랜드
            '023530': 'Consumer Discretionary',  # 롯데쇼핑
            
            # Health Care
            '068270': 'Health Care',  # 셀트리온
            '207940': 'Health Care',  # 삼성바이오로직스
            '128940': 'Health Care',  # 한미약품
            '000100': 'Health Care',  # 유한양행
            '185750': 'Health Care',  # 종근당
            '006280': 'Health Care',  # 녹십자
            '326030': 'Health Care',  # SK바이오팜
            '302440': 'Health Care',  # SK바이오사이언스
            '069620': 'Health Care',  # 대웅제약
            '009420': 'Health Care',  # 한올바이오파마
            
            # Consumer Staples
            '051900': 'Consumer Staples',  # LG생활건강
            '090430': 'Consumer Staples',  # 아모레퍼시픽
            '004370': 'Consumer Staples',  # 농심
            '000080': 'Consumer Staples',  # 하이트진로
            '007310': 'Consumer Staples',  # 오뚜기
            '280360': 'Consumer Staples',  # 롯데웰푸드
            '271560': 'Consumer Staples',  # 오리온
            '005300': 'Consumer Staples',  # 롯데칠성
            '033780': 'Consumer Staples',  # KT&G
            '097950': 'Consumer Staples',  # CJ제일제당
            '139480': 'Consumer Staples',  # 이마트
            '015760': 'Utilities',  # 한국전력
            '036460': 'Utilities',  # 한국가스공사
            
            # Materials (Steels & Materials)
            '005490': 'Materials',  # POSCO홀딩스
            '004020': 'Materials',  # 현대제철
            '010130': 'Materials',  # 고려아연
            '010140': 'Materials',  # 삼성중공업
            '003670': 'Materials',  # 포스코퓨처엠
            '001430': 'Materials',  # 세아베스틸홀딩스
            '003030': 'Materials',  # 세아제강지주
            '103140': 'Materials',  # 풍산
            
            # Energy & Chemicals
            '051910': 'Energy',  # LG화학
            '009830': 'Energy',  # 한화솔루션
            '096770': 'Energy',  # SK이노베이션
            '010950': 'Energy',  # S-Oil
            '011170': 'Energy',  # 롯데케미칼
            '000880': 'Energy',  # 한화
            '285130': 'Energy',  # SK케미칼
            '011780': 'Energy',  # 금호석유화학
            '002380': 'Energy',  # KCC
            '120110': 'Energy',  # 코오롱인더
            '006650': 'Energy',  # 대한화섬
            '456040': 'Energy',  # OCI
            '010060': 'Energy',  # OCI홀딩스
            
            # Industrials
            '373220': 'Industrials',  # LG에너지솔루션
            '047810': 'Industrials',  # 한국항공우주
            '012450': 'Industrials',  # 한화에어로스페이스
            '272210': 'Industrials',  # 한화시스템
            '003490': 'Industrials',  # 대한항공
            '086280': 'Industrials',  # 현대글로비스
            '047050': 'Industrials',  # 포스코인터내셔널
            '000120': 'Industrials',  # CJ대한통운
            '028670': 'Industrials',  # 팬오션
            '011200': 'Industrials',  # HMM
            '006260': 'Industrials',  # LS
            '010120': 'Industrials',  # LS ELECTRIC
            '051600': 'Industrials',  # 한전KPS
            '079550': 'Industrials',  # LIG넥스원
            
            # Heavy Industries
            '034020': 'Heavy Industries',  # 두산에너빌리티
            '042670': 'Heavy Industries',  # HD현대인프라코어
            '009540': 'Heavy Industries',  # HD한국조선해양
            '010620': 'Heavy Industries',  # HD현대미포
            '329180': 'Heavy Industries',  # HD현대중공업
            '267260': 'Heavy Industries',  # HD현대일렉트릭
            '000150': 'Heavy Industries',  # 두산
            '064350': 'Heavy Industries',  # 현대로템
            '241560': 'Heavy Industries',  # 두산밥캣
            '017800': 'Heavy Industries',  # 현대엘리베이터
            '042660': 'Heavy Industries',  # 한화오션
            '298040': 'Heavy Industries',  # 효성중공업
            '112610': 'Heavy Industries',  # 씨에스윈드
            
            # Constructions
            '000720': 'Constructions',  # 현대건설
            '028260': 'Constructions',  # 삼성물산
            '006360': 'Constructions',  # GS건설
            '047040': 'Constructions',  # 대우건설
            '375500': 'Constructions',  # DL이앤씨
            '052690': 'Constructions',  # 한전기술
            '028050': 'Constructions',  # 삼성엔지니어링
            '300720': 'Constructions',  # 한일시멘트
        }
        
        # 실제 GICS 기반 섹터 매핑
        gics_sector_mapping = {
            'IT': 'Information Technology',
            'Communication Services': 'Communication Services', 
            'Financials': 'Financials',
            'Consumer Discretionary': 'Consumer Discretionary',
            'Health Care': 'Health Care',
            'Consumer Staples': 'Consumer Staples',
            'Utilities': 'Utilities',
            'Materials': 'Materials', 
            'Energy': 'Energy',
            'Industrials': 'Industrials',
            'Heavy Industries': 'Industrials',  # Heavy Industries는 Industrials의 하위 분류
            'Constructions': 'Industrials',      # Constructions도 Industrials의 하위 분류
        }
        
        updated_count = 0
        total_stocks = Stock.objects.count()
        
        self.stdout.write(f"총 {total_stocks}개 종목을 처리합니다...")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN 모드: 실제 변경 없이 시뮬레이션만 실행합니다.")
            )
        
        for stock in Stock.objects.all():
            old_sector = stock.sector
            new_sector = None
            
            # KOSPI 200 종목인 경우 실제 데이터로 업데이트
            if stock.stock_code in kospi_200_sectors:
                sector_key = kospi_200_sectors[stock.stock_code]
                new_sector = gics_sector_mapping.get(sector_key, sector_key)
            else:
                # KOSPI 200에 포함되지 않은 종목은 기존 분류를 GICS 형태로 매핑
                sector_mappings = {
                    '전기전자': 'Information Technology',
                    '화학': 'Energy', 
                    '자동차': 'Consumer Discretionary',
                    '금융업': 'Financials',
                    '건설업': 'Industrials',
                    '통신업': 'Communication Services',
                    '유통업': 'Consumer Discretionary',
                    '의료정밀': 'Health Care',
                    '운수창고': 'Industrials', 
                    '기계': 'Industrials',
                    '철강금속': 'Materials',
                    '에너지': 'Energy',
                    '음식료': 'Consumer Staples',
                    '섬유의복': 'Consumer Discretionary',
                    '종이목재': 'Materials',
                    '비금속광물': 'Materials',
                    '의약품': 'Health Care',
                    '게임': 'Communication Services',
                    '바이오': 'Health Care',
                    '항공우주': 'Industrials'
                }
                new_sector = sector_mappings.get(old_sector, old_sector)
            
            # 섹터가 변경되는 경우
            if new_sector and new_sector != old_sector:
                if not dry_run:
                    stock.sector = new_sector
                    stock.save()
                
                self.stdout.write(
                    f"[{stock.stock_code}] {stock.stock_name}: {old_sector} → {new_sector}"
                )
                updated_count += 1
            
            if updated_count % 50 == 0 and updated_count > 0:
                self.stdout.write(f"진행률: {updated_count}개 업데이트 완료")
        
        # 업데이트된 섹터 목록 출력
        if not dry_run:
            sectors = Stock.objects.values_list('sector', flat=True).distinct().order_by('sector')
            sectors = [s for s in sectors if s]
            
            self.stdout.write("\n업데이트된 섹터 목록:")
            for sector in sectors:
                count = Stock.objects.filter(sector=sector).count()
                self.stdout.write(f"- {sector}: {count}개 종목")
        
        result_msg = f"총 {updated_count}개 종목의 섹터를 업데이트했습니다."
        if dry_run:
            result_msg += " (DRY RUN)"
            
        self.stdout.write(
            self.style.SUCCESS(result_msg)
        ) 