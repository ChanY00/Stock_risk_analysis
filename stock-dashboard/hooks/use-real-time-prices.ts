import { useState, useEffect, useCallback, useRef } from 'react'
import { RealTimeApiClient, type RealTimePrice } from '@/lib/real-time-api'

export interface RealTimePriceData {
  [stockCode: string]: RealTimePrice
}

export interface UseRealTimePricesOptions {
  stockCodes: string[]
  refreshInterval?: number // milliseconds
  enabled?: boolean
}

export interface UseRealTimePricesReturn {
  data: RealTimePriceData
  loading: boolean
  error: string | null
  lastUpdated: Date | null
  refetch: () => Promise<void>
}

export function useRealTimePrices({
  stockCodes,
  refreshInterval = 60000, // 60초마다 갱신 (토큰 제한 고려)
  enabled = true
}: UseRealTimePricesOptions): UseRealTimePricesReturn {
  const [data, setData] = useState<RealTimePriceData>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  
  const apiClient = useRef(new RealTimeApiClient())
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchPrices = useCallback(async () => {
    if (!enabled || stockCodes.length === 0) return

    try {
      setLoading(true)
      setError(null)

      let pricesData: RealTimePriceData = {}

      if (stockCodes.length === 1) {
        // 단일 종목 조회
        const price = await apiClient.current.getRealTimePrice(stockCodes[0])
        if (price) {
          pricesData[stockCodes[0]] = price
        }
      } else {
        // 여러 종목 조회 (최대 10개씩 처리하여 API 부하 감소)
        const batchSize = 10
        for (let i = 0; i < stockCodes.length; i += batchSize) {
          const batch = stockCodes.slice(i, i + batchSize)
          
          try {
            const batchPrices = await apiClient.current.getMultipleRealTimePrices(batch)
            pricesData = { ...pricesData, ...batchPrices }
            
            // 배치 간 1초 대기 (API 부하 방지)
            if (i + batchSize < stockCodes.length) {
              await new Promise(resolve => setTimeout(resolve, 1000))
            }
          } catch (batchError) {
            console.warn(`배치 ${i}-${i + batchSize} 처리 실패:`, batchError)
            // 한 배치 실패해도 계속 진행
          }
        }
      }

      setData(pricesData)
      setLastUpdated(new Date())
      
      console.log(`✅ 실시간 주가 업데이트 완료: ${Object.keys(pricesData).length}개 종목`)
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '실시간 주가 조회 중 오류가 발생했습니다'
      setError(errorMessage)
      console.error('실시간 주가 조회 실패:', err)
      
      // Rate limit 에러인 경우 특별 처리
      if (errorMessage.includes('API_RATE_LIMIT')) {
        console.warn('⏱️ API Rate Limited - 다음 요청을 2분 후로 연기')
        setError('API 요청 제한 초과 - 잠시 후 다시 시도해주세요 (1분당 1회 제한)')
        
        // interval 중지하고 2분 후 재시작
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        
        // 2분 후 자동 재시작
        setTimeout(() => {
          if (enabled && stockCodes.length > 0) {
            fetchPrices()
          }
        }, 120000) // 2분 대기
        
        return
      }
      
      // 일반 에러의 경우 다음 주기적 갱신을 기다림
    } finally {
      setLoading(false)
    }
  }, [stockCodes, enabled])

  // 수동 refetch 함수
  const refetch = useCallback(async () => {
    await fetchPrices()
  }, [fetchPrices])

  // 초기 데이터 로드
  useEffect(() => {
    if (enabled && stockCodes.length > 0) {
      fetchPrices()
    }
  }, [fetchPrices, enabled, stockCodes])

  // 주기적 갱신 설정
  useEffect(() => {
    if (!enabled || !refreshInterval || stockCodes.length === 0) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      return
    }

    // 이전 interval 클리어
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
    }

    // 새 interval 설정
    intervalRef.current = setInterval(() => {
      fetchPrices()
    }, refreshInterval)

    // cleanup 함수
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [fetchPrices, refreshInterval, enabled, stockCodes])

  // 컴포넌트 언마운트 시 cleanup
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [])

  return {
    data,
    loading,
    error,
    lastUpdated,
    refetch
  }
}

// KOSPI 200 주요 종목 실시간 데이터를 위한 특별한 Hook
export function useKospi200RealTimePrices(refreshInterval?: number) {
  const [data, setData] = useState<RealTimePriceData>({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  
  const apiClient = useRef(new RealTimeApiClient())
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchKospi200Prices = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)

      const response = await apiClient.current.getKospi200RealTimePrices()
      
      if (response.data) {
        setData(response.data)
        setLastUpdated(new Date())
        console.log(`✅ KOSPI 200 실시간 주가 업데이트: ${Object.keys(response.data).length}개 종목`)
      }
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'KOSPI 200 실시간 주가 조회 중 오류가 발생했습니다'
      setError(errorMessage)
      console.error('KOSPI 200 실시간 주가 조회 실패:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  // 초기 데이터 로드
  useEffect(() => {
    fetchKospi200Prices()
  }, [fetchKospi200Prices])

  // 주기적 갱신
  useEffect(() => {
    if (!refreshInterval) return

    intervalRef.current = setInterval(fetchKospi200Prices, refreshInterval)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetchKospi200Prices, refreshInterval])

  return {
    data,
    loading,
    error,
    lastUpdated,
    refetch: fetchKospi200Prices
  }
} 