// 전역 감정 분석 데이터 스토어 (메인 페이지와 상세보기 페이지 공유)

interface SentimentData {
  positive: number;
  negative: number;
  neutral?: number;
  timestamp: number;
}

class SentimentStore {
  private cache = new Map<string, SentimentData>();
  private readonly CACHE_DURATION = 5 * 60 * 1000; // 5분

  // 감정 데이터 가져오기
  getSentiment(stockCode: string): { positive: number; negative: number; neutral?: number } | null {
    const cached = this.cache.get(stockCode);
    if (cached && Date.now() - cached.timestamp < this.CACHE_DURATION) {
      return { 
        positive: cached.positive, 
        negative: cached.negative, 
        neutral: cached.neutral 
      };
    }
    return null;
  }

  // 감정 데이터 저장
  setSentiment(stockCode: string, positive: number, negative: number, neutral: number = 0): void {
    this.cache.set(stockCode, {
      positive,
      negative,
      neutral,
      timestamp: Date.now()
    });
  }

  // 캐시 클리어
  clearCache(): void {
    this.cache.clear();
  }

  // 특정 종목 캐시 제거
  removeSentiment(stockCode: string): void {
    this.cache.delete(stockCode);
  }

  // 캐시 상태 확인
  getCacheInfo(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys())
    };
  }
}

// 싱글톤 인스턴스
export const sentimentStore = new SentimentStore();

// 감정 점수 계산 유틸리티
export const calculateSentimentScore = (positive: number, negative: number, neutral: number = 0): number => {
  const total = positive + negative + neutral;
  if (total === 0) return 0.5; // 데이터가 없으면 중립
  
  // 긍정 비율을 0-1로 정규화
  return positive / total;
};
