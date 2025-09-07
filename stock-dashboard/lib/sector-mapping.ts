// GICS 섹터 영어-한국어 매핑
export const SECTOR_MAPPING: Record<string, string> = {
  'Communication Services': '커뮤니케이션 서비스',
  'Consumer Discretionary': '소비재',
  'Consumer Staples': '필수소비재',
  'Energy': '에너지',
  'Financials': '금융',
  'Health Care': '헬스케어',
  'Industrials': '산업재',
  'Information Technology': 'IT',
  'Materials': '소재',
  'Utilities': '유틸리티'
};

// 테이블 표시용 짧은 섹터명
export const SECTOR_SHORT_MAPPING: Record<string, string> = {
  'Communication Services': '커뮤니케이션',
  'Consumer Discretionary': '소비재',
  'Consumer Staples': '필수소비재',
  'Energy': '에너지',
  'Financials': '금융',
  'Health Care': '헬스케어',
  'Industrials': '산업재',
  'Information Technology': 'IT',
  'Materials': '소재',
  'Utilities': '유틸리티'
};

// 역매핑 (한국어 -> 영어)
export const SECTOR_REVERSE_MAPPING: Record<string, string> = Object.fromEntries(
  Object.entries(SECTOR_MAPPING).map(([en, ko]) => [ko, en])
);

// 영어 섹터명을 한국어로 변환
export function translateSectorToKorean(englishSector: string): string {
  return SECTOR_MAPPING[englishSector] || englishSector;
}

// 영어 섹터명을 짧은 한국어로 변환 (테이블용)
export function translateSectorToKoreanShort(englishSector: string): string {
  return SECTOR_SHORT_MAPPING[englishSector] || englishSector;
}

// 한국어 섹터명을 영어로 변환
export function translateSectorToEnglish(koreanSector: string): string {
  return SECTOR_REVERSE_MAPPING[koreanSector] || koreanSector;
}

// 모든 섹터 목록 (한국어)
export const KOREAN_SECTORS = Object.values(SECTOR_MAPPING).sort();

// 모든 섹터 목록 (영어)
export const ENGLISH_SECTORS = Object.keys(SECTOR_MAPPING).sort();

// 섹터 색상 매핑 (시각적 구분을 위한)
export const SECTOR_COLORS: Record<string, string> = {
  'Communication Services': '#8B5CF6', // 보라색
  'Consumer Discretionary': '#EF4444', // 빨간색
  'Consumer Staples': '#F59E0B', // 주황색
  'Energy': '#10B981', // 초록색
  'Financials': '#3B82F6', // 파란색
  'Health Care': '#EC4899', // 분홍색
  'Industrials': '#6B7280', // 회색
  'Information Technology': '#06B6D4', // 청록색
  'Materials': '#84CC16', // 라임색
  'Utilities': '#F97316' // 주황색
};

// 한국어 섹터명으로 색상 가져오기
export function getSectorColor(sector: string): string {
  const englishSector = translateSectorToEnglish(sector);
  return SECTOR_COLORS[englishSector] || '#6B7280';
} 