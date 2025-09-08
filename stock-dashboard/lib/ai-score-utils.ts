// AI 점수 계산 유틸리티 함수들

export interface StockForAiScore {
  sentiment: number
  changePercent: number
  technicalIndicators?: {
    sma_5?: number
    sma_20?: number
    sma_60?: number
    rsi?: number
    macd?: number
    macd_signal?: number
    bollinger_upper?: number
    bollinger_lower?: number
    bollinger_middle?: number
    current_price?: number
  }
}

/**
 * 기술분석 지표 기반 점수 계산
 * 이동평균, RSI, MACD, 볼린저밴드 등을 종합하여 0-1 점수 생성
 */
const calculateTechnicalScore = (indicators: StockForAiScore['technicalIndicators'], changePercent: number): number => {
  if (!indicators) {
    // 기술지표가 없으면 변동률 기반 간단 계산
    return Math.max(0, Math.min(1, 0.5 + Math.tanh(changePercent / 10) * 0.5))
  }

  let score = 0
  let factors = 0

  // 1. 이동평균 분석 (30% 가중치)
  if (indicators.sma_5 && indicators.sma_20 && indicators.current_price) {
    const price = indicators.current_price
    const sma5 = indicators.sma_5
    const sma20 = indicators.sma_20
    
    // 단기 > 장기 이동평균이면 상승 추세
    const maScore = sma5 > sma20 ? 0.7 : 0.3
    // 현재가가 단기 이동평균 위에 있으면 추가 점수
    const priceScore = price > sma5 ? 0.8 : 0.4
    
    score += (maScore + priceScore) / 2 * 0.3
    factors += 0.3
  }

  // 2. RSI 분석 (20% 가중치)
  if (indicators.rsi) {
    const rsi = indicators.rsi
    let rsiScore = 0.5 // 중립
    
    if (rsi < 30) rsiScore = 0.8 // 과매도 -> 반등 기대
    else if (rsi > 70) rsiScore = 0.2 // 과매수 -> 하락 위험
    else if (rsi > 50) rsiScore = 0.6 // 상승 모멘텀
    else rsiScore = 0.4 // 하락 모멘텀
    
    score += rsiScore * 0.2
    factors += 0.2
  }

  // 3. MACD 분석 (20% 가중치)
  if (indicators.macd && indicators.macd_signal) {
    const macd = indicators.macd
    const signal = indicators.macd_signal
    const macdScore = macd > signal ? 0.7 : 0.3
    
    score += macdScore * 0.2
    factors += 0.2
  }

  // 4. 볼린저밴드 분석 (20% 가중치)
  if (indicators.bollinger_upper && indicators.bollinger_lower && indicators.current_price) {
    const price = indicators.current_price
    const upper = indicators.bollinger_upper
    const lower = indicators.bollinger_lower
    const middle = indicators.bollinger_middle || (upper + lower) / 2
    
    let bbScore = 0.5 // 중립
    
    if (price > upper) bbScore = 0.2 // 상단 터치 -> 하락 위험
    else if (price < lower) bbScore = 0.8 // 하단 터치 -> 반등 기대
    else if (price > middle) bbScore = 0.6 // 상단 밴드 근처
    else bbScore = 0.4 // 하단 밴드 근처
    
    score += bbScore * 0.2
    factors += 0.2
  }

  // 5. 모멘텀 분석 (10% 가중치)
  const momentumScore = Math.max(0, Math.min(1, 0.5 + Math.tanh(changePercent / 10) * 0.5))
  score += momentumScore * 0.1
  factors += 0.1

  // 가중치 정규화
  return factors > 0 ? score / factors : 0.5
}

/**
 * AI 점수 계산 함수
 * 공식: (0.7 * 기술분석점수 + 0.3 * 감정점수) * 100
 * 
 * @param stock - AI 점수 계산에 필요한 주식 데이터
 * @returns 0-100 사이의 AI 점수
 */
export const computeAiScore = (stock: StockForAiScore): number => {
  const clamp = (n: number, min: number, max: number) => Math.max(min, Math.min(max, n))
  const sentiment = clamp(stock.sentiment, 0, 1)
  
  // 기술분석 지표 기반 점수 계산
  const technicalScore = calculateTechnicalScore(stock.technicalIndicators, stock.changePercent || 0)
  
  return Math.round((0.7 * technicalScore + 0.3 * sentiment) * 100)
}

/**
 * AI 점수에 따른 등급 반환
 * @param score - AI 점수 (0-100)
 * @returns 등급 정보
 */
export const getAiScoreGrade = (score: number) => {
  if (score >= 70) return { grade: "우수", variant: "default" as const, color: "text-green-600" }
  if (score >= 50) return { grade: "보통", variant: "secondary" as const, color: "text-yellow-600" }
  return { grade: "주의", variant: "destructive" as const, color: "text-red-600" }
}
