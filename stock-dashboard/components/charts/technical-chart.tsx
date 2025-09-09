"use client"

import { useState, useEffect, useMemo, useCallback, memo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, ComposedChart, Bar, Cell, RadialBarChart, RadialBar, Legend, ReferenceLine, BarChart } from 'recharts'
import { TechnicalIndicators, PriceData, stocksApi } from '@/lib/api'

interface TechnicalChartProps {
  indicators: TechnicalIndicators
  priceData?: PriceData[]
  title?: string
  stockCode?: string
}

// memo로 감싸서 불필요한 리렌더링 방지
export const TechnicalChart = memo(function TechnicalChart({ indicators, priceData = [], title = "기술적 지표", stockCode }: TechnicalChartProps) {
  const [selectedTab, setSelectedTab] = useState<'overview' | 'ma' | 'oscillators' | 'macd' | 'bollinger'>('overview')
  const [extendedPriceData, setExtendedPriceData] = useState<PriceData[]>(priceData)
  const [loading, setLoading] = useState(false)

  // 기술적 분석을 위해 충분한 데이터 확보 (90일 이상)
  useEffect(() => {
    if (stockCode && priceData.length < 90) {
      const loadExtendedData = async () => {
        setLoading(true)
        try {
          console.log(`🔄 기술적 분석을 위한 확장 데이터 로딩: ${stockCode}`)
          const response = await stocksApi.getPriceHistory(stockCode, { days: 180 }) // 6개월 데이터
          
          let newData: PriceData[] = []
          if (Array.isArray(response)) {
            newData = response
          } else if (response && typeof response === 'object' && 'price_history' in response) {
            newData = (response as any).price_history || []
          }
          
          console.log(`✅ 기술적 분석용 데이터 로드 완료: ${newData.length}개`)
          setExtendedPriceData(newData)
        } catch (error) {
          console.error('기술적 분석용 데이터 로딩 실패:', error)
          setExtendedPriceData(priceData) // 실패시 기존 데이터 사용
        } finally {
          setLoading(false)
        }
      }
      
      loadExtendedData()
    } else {
      setExtendedPriceData(priceData)
    }
  }, [stockCode, priceData])

  // 실제 이동평균 계산 함수 (개선) - useCallback으로 메모이제이션
  const calculateMovingAverage = useCallback((prices: number[], period: number) => {
    const result: (number | null)[] = []
    
    for (let i = 0; i < prices.length; i++) {
      if (i < period - 1) {
        result.push(null)
      } else {
        const sum = prices.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0)
        result.push(sum / period)
      }
    }
    
    return result
  }, [])

  // 주가 데이터를 차트용으로 변환 (이동평균 계산 포함) - useMemo로 메모이제이션
  const candlestickData = useMemo(() => {
    if (extendedPriceData.length === 0) return []
    
    const minDataPoints = Math.max(70, extendedPriceData.length)
    const recentData = extendedPriceData.slice(-minDataPoints)
    const closePrices = recentData.map(p => p.close)
    
    const ma5Array = calculateMovingAverage(closePrices, 5)
    const ma20Array = calculateMovingAverage(closePrices, 20)
    const ma60Array = calculateMovingAverage(closePrices, 60)
    
    // 볼린저 밴드 계산 (20일 기준, 표준편차 2배)
    const calculateBollingerBands = (prices: number[], period: number = 20, stdDev: number = 2) => {
      const result: { upper: number | null, middle: number | null, lower: number | null }[] = []
      
      for (let i = 0; i < prices.length; i++) {
        if (i < period - 1) {
          result.push({ upper: null, middle: null, lower: null })
        } else {
          const slice = prices.slice(i - period + 1, i + 1)
          const ma = slice.reduce((a, b) => a + b, 0) / period
          const variance = slice.reduce((acc, val) => acc + Math.pow(val - ma, 2), 0) / period
          const std = Math.sqrt(variance)
          
          result.push({
            middle: ma,
            upper: ma + (std * stdDev),
            lower: ma - (std * stdDev)
          })
        }
      }
      
      return result
    }
    
    const bollingerArray = calculateBollingerBands(closePrices, 20, 2)
    
    return recentData.slice(-30).map((price, index) => {
      const actualIndex = Math.max(0, recentData.length - 30 + index)
      const date = new Date(price.date).toLocaleDateString('ko-KR', { 
        month: 'short', 
        day: 'numeric' 
      })
      
      const bollinger = bollingerArray[actualIndex] || { upper: null, middle: null, lower: null }
      
      return {
        date,
        open: price.open,
        high: price.high,
        low: price.low,
        close: price.close,
        volume: price.volume,
        ma5: ma5Array[actualIndex],
        ma20: ma20Array[actualIndex],
        ma60: ma60Array[actualIndex],
        bb_upper: bollinger.upper,
        bb_middle: bollinger.middle,
        bb_lower: bollinger.lower,
      }
    })
  }, [extendedPriceData, calculateMovingAverage])

  // RSI 게이지 데이터 - useMemo로 메모이제이션
  const rsiData = useMemo(() => [
    {
      name: 'RSI',
      value: indicators?.rsi || 0,
      fill: indicators?.rsi ? (
        indicators.rsi > 70 ? '#ef4444' : 
        indicators.rsi < 30 ? '#3b82f6' : 
        '#22c55e'
      ) : '#d1d5db'
    }
  ], [indicators?.rsi])

  // Stochastic 데이터 - useMemo로 메모이제이션
  const stochasticData = useMemo(() => [
    { name: '%K', value: indicators?.stochastic_k || 0 },
    { name: '%D', value: indicators?.stochastic_d || 0 }
  ], [indicators?.stochastic_k, indicators?.stochastic_d])

  // MACD 데이터 - useMemo로 메모이제이션
  const macdData = useMemo(() => [
    { 
      name: 'MACD', 
      macd: indicators?.macd || 0,
      signal: indicators?.macd_signal || 0,
      histogram: indicators?.macd_histogram || 0
    }
  ], [indicators?.macd, indicators?.macd_signal, indicators?.macd_histogram])

  const CustomTooltip = useCallback(({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
          <p className="font-medium text-gray-900 dark:text-white">{label}</p>
          <div className="mt-2">
            {payload.map((entry: any, index: number) => (
              <p key={index} className="text-sm">
                <span className="text-gray-600 dark:text-gray-400">{entry.name || entry.dataKey}: </span>
                <span className="font-mono" style={{ color: entry.color }}>
                  {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
                </span>
              </p>
            ))}
          </div>
        </div>
      )
    }
    return null
  }, [])

  // 주가 차트 컴포넌트 - useCallback으로 메모이제이션
  const PriceAreaChart = useCallback(({ data }: { data: any[] }) => (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis 
          dataKey="date" 
          tick={{ fontSize: 12 }}
          stroke="#666"
        />
        <YAxis 
          domain={(() => {
            const values = data.map(d => d.close).filter(v => v > 0)
            if (values.length === 0) return ['dataMin - 1%', 'dataMax + 1%']
            
            const sortedValues = values.sort((a, b) => a - b)
            const removeOutliers = 0.1
            const lowerIndex = Math.floor(sortedValues.length * removeOutliers)
            const upperIndex = Math.floor(sortedValues.length * (1 - removeOutliers))
            const filteredValues = sortedValues.slice(lowerIndex, upperIndex)
            
            if (filteredValues.length === 0) return ['dataMin - 1%', 'dataMax + 1%']
            
            const median = filteredValues[Math.floor(filteredValues.length / 2)]
            const p5 = filteredValues[Math.floor(filteredValues.length * 0.05)]
            const p95 = filteredValues[Math.floor(filteredValues.length * 0.95)]
            
            const range = Math.max(p95 - median, median - p5)
            const centeredMin = Math.max(median - range * 1.3, p5)
            const centeredMax = Math.min(median + range * 1.3, p95)
            
            return [centeredMin, centeredMax]
          })()}
          tick={{ fontSize: 12 }}
          stroke="#666"
        />
        <Tooltip content={CustomTooltip} />
        <Area 
          type="monotone" 
          dataKey="close" 
          stroke="#2563eb" 
          fill="#3b82f6" 
          fillOpacity={0.1}
          strokeWidth={2}
          name="종가"
        />
        <Area 
          type="monotone" 
          dataKey="high" 
          stroke="#10b981" 
          fill="transparent"
          strokeWidth={1}
          strokeDasharray="2 2"
          name="고가"
        />
        <Area 
          type="monotone" 
          dataKey="low" 
          stroke="#f59e0b" 
          fill="transparent"
          strokeWidth={1}
          strokeDasharray="2 2"
          name="저가"
        />
      </AreaChart>
    </ResponsiveContainer>
  ), [CustomTooltip])

  // 탭 목록 - useMemo로 메모이제이션
  const tabs = useMemo(() => [
    { id: 'overview', label: '전체 개요' },
    { id: 'ma', label: '이동평균' },
    { id: 'oscillators', label: '오실레이터' },
    { id: 'macd', label: 'MACD' },
    { id: 'bollinger', label: '볼린저밴드' }
  ], [])

  // 조건부 렌더링을 JSX에서 처리 - 모든 hooks가 실행된 후
  if (!indicators) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
        기술적 지표 데이터가 없습니다.
      </div>
    )
  }

  if (loading) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
        기술적 분석을 위한 데이터를 로딩 중입니다...
      </div>
    )
  }

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
        
        {/* 탭 선택 */}
        <div className="flex space-x-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setSelectedTab(tab.id as any)}
              className={`px-3 py-1 text-sm rounded-md transition-colors ${
                selectedTab === tab.id
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* 전체 개요 */}
      {selectedTab === 'overview' && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* RSI 게이지 */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-800 dark:text-white mb-3">RSI</h4>
            <div className="h-32">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart cx="50%" cy="50%" innerRadius="60%" outerRadius="90%" data={rsiData}>
                  <RadialBar dataKey="value" cornerRadius={10} fill={rsiData[0]?.fill} />
                  <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle" className="text-lg font-bold">
                    {indicators.rsi?.toFixed(1) || 'N/A'}
                  </text>
                </RadialBarChart>
              </ResponsiveContainer>
            </div>
            <div className="text-center text-xs">
              <span className={`font-medium ${
                !indicators.rsi ? 'text-gray-400' :
                indicators.rsi > 70 ? 'text-red-600' : 
                indicators.rsi < 30 ? 'text-blue-600' : 
                'text-green-600'
              }`}>
                {!indicators.rsi ? '데이터 없음' :
                 indicators.rsi > 70 ? '과매수' : 
                 indicators.rsi < 30 ? '과매도' : '중립'}
              </span>
            </div>
          </div>

          {/* MACD 요약 */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-800 dark:text-white mb-3">MACD</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">MACD:</span>
                <span className="font-mono">{indicators.macd ? Math.round(indicators.macd).toLocaleString() : 'N/A'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">Signal:</span>
                <span className="font-mono">{indicators.macd_signal ? Math.round(indicators.macd_signal).toLocaleString() : 'N/A'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">Histogram:</span>
                <span className={`font-mono ${(indicators.macd_histogram || 0) > 0 ? 'text-red-600' : 'text-blue-600'}`}>
                  {indicators.macd_histogram ? Math.round(indicators.macd_histogram).toLocaleString() : 'N/A'}
                </span>
              </div>
            </div>
            <div className="mt-3 text-center text-xs">
              <span className={`font-medium ${
                !indicators.macd || !indicators.macd_signal ? 'text-gray-400' :
                indicators.macd > indicators.macd_signal ? 'text-red-600' : 'text-blue-600'
              }`}>
                {!indicators.macd || !indicators.macd_signal ? '데이터 없음' :
                 indicators.macd > indicators.macd_signal ? '매수 신호' : '매도 신호'}
              </span>
            </div>
          </div>

          {/* 이동평균 요약 */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-800 dark:text-white mb-3">이동평균</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-red-500">MA5:</span>
                <span className="font-mono">{indicators.ma5?.toLocaleString() || 'N/A'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-blue-500">MA20:</span>
                <span className="font-mono">{indicators.ma20?.toLocaleString() || 'N/A'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-green-500">MA60:</span>
                <span className="font-mono">{indicators.ma60?.toLocaleString() || 'N/A'}</span>
              </div>
            </div>
          </div>

          {/* 볼린저밴드 요약 */}
          <div className="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-sm font-medium text-gray-800 dark:text-white mb-3">볼린저밴드</h4>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">상단:</span>
                <span className="font-mono">
                  {(() => {
                    const latestData = candlestickData[candlestickData.length - 1]
                    return latestData?.bb_upper ? Math.round(latestData.bb_upper).toLocaleString() : 'N/A'
                  })()}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">중앙:</span>
                <span className="font-mono">
                  {(() => {
                    const latestData = candlestickData[candlestickData.length - 1]
                    return latestData?.bb_middle ? Math.round(latestData.bb_middle).toLocaleString() : 'N/A'
                  })()}
                </span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-gray-600 dark:text-gray-400">하단:</span>
                <span className="font-mono">
                  {(() => {
                    const latestData = candlestickData[candlestickData.length - 1]
                    return latestData?.bb_lower ? Math.round(latestData.bb_lower).toLocaleString() : 'N/A'
                  })()}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 이동평균 + 주가 차트 */}
      {selectedTab === 'ma' && (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">주가 + 이동평균선</h4>
          {candlestickData.length > 0 ? (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={candlestickData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fontSize: 12 }}
                    stroke="#666"
                  />
                  <YAxis 
                    domain={(() => {
                      const values = candlestickData.map(d => d.close).filter(v => v > 0)
                      if (values.length === 0) return ['dataMin - 2%', 'dataMax + 2%']
                      
                      const sortedValues = values.sort((a, b) => a - b)
                      const removeOutliers = 0.1
                      const lowerIndex = Math.floor(sortedValues.length * removeOutliers)
                      const upperIndex = Math.floor(sortedValues.length * (1 - removeOutliers))
                      const filteredValues = sortedValues.slice(lowerIndex, upperIndex)
                      
                      if (filteredValues.length === 0) return ['dataMin - 2%', 'dataMax + 2%']
                      
                      const median = filteredValues[Math.floor(filteredValues.length / 2)]
                      const p5 = filteredValues[Math.floor(filteredValues.length * 0.05)]
                      const p95 = filteredValues[Math.floor(filteredValues.length * 0.95)]
                      
                      const range = Math.max(p95 - median, median - p5)
                      const centeredMin = Math.max(median - range * 1.3, p5)
                      const centeredMax = Math.min(median + range * 1.3, p95)
                      
                      return [centeredMin, centeredMax]
                    })()}
                    tick={{ fontSize: 12 }}
                    stroke="#666"
                  />
                  <Tooltip content={CustomTooltip} />
                  
                  <Line
                    type="monotone"
                    dataKey="close" 
                    stroke="#1e293b"
                    strokeWidth={3}
                    dot={false}
                    name="종가"
                  />
                  
                  <Line
                    type="monotone"
                    dataKey="ma5" 
                    stroke="#dc2626"
                    strokeWidth={2}
                    strokeDasharray="5 0"
                    dot={false}
                    name="MA5"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="ma20" 
                    stroke="#2563eb" 
                    strokeWidth={2.5}
                    strokeDasharray="8 2"
                    dot={false}
                    name="MA20"
                  />
                  <Line
                    type="monotone"
                    dataKey="ma60" 
                    stroke="#059669"
                    strokeWidth={2}
                    strokeDasharray="12 4"
                    dot={false}
                    name="MA60"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              주가 데이터가 없어 이동평균 차트를 표시할 수 없습니다.
            </div>
          )}
          
          {/* 이동평균 정보 */}
          <div className="mt-4 grid grid-cols-4 gap-4">
            <div className="text-center p-3 bg-gray-50 rounded-lg">
              <div className="text-sm text-gray-800 font-medium flex items-center justify-center">
                <div className="w-4 h-0.5 bg-slate-800 mr-2"></div>
                주가
              </div>
              <div className="text-lg font-mono text-gray-700">현재가</div>
            </div>
            <div className="text-center p-3 bg-red-50 dark:bg-red-900/20 rounded-lg">
              <div className="text-sm text-red-600 dark:text-red-400 font-medium flex items-center justify-center">
                <div className="w-4 h-0.5 bg-red-600 dark:bg-red-400 mr-2"></div>
                MA5
              </div>
              <div className="text-lg font-mono text-red-700 dark:text-red-300">{indicators.ma5?.toLocaleString() || 'N/A'}</div>
            </div>
            <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <div className="text-sm text-blue-600 dark:text-blue-400 font-medium flex items-center justify-center">
                <div className="w-4 h-0.5 bg-blue-600 dark:bg-blue-400 mr-2 border-dashed"></div>
                MA20
              </div>
              <div className="text-lg font-mono text-blue-700 dark:text-blue-300">{indicators.ma20?.toLocaleString() || 'N/A'}</div>
            </div>
            <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <div className="text-sm text-green-600 dark:text-green-400 font-medium flex items-center justify-center">
                <div className="w-4 h-0.5 bg-green-600 dark:bg-green-400 mr-2 border-dotted"></div>
                MA60
              </div>
              <div className="text-lg font-mono text-green-700 dark:text-green-300">{indicators.ma60?.toLocaleString() || 'N/A'}</div>
            </div>
          </div>
        </div>
      )}

      {/* 오실레이터 (RSI + Stochastic) + 주가 차트 */}
      {selectedTab === 'oscillators' && (
        <div className="space-y-6">
          {/* 상단: 주가 차트 */}
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">주가 차트</h4>
            {candlestickData.length > 0 ? (
              <div className="h-60">
                <PriceAreaChart data={candlestickData} />
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">주가 데이터 없음</div>
            )}
          </div>

          {/* 하단: RSI + Stochastic */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* RSI */}
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
              <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">RSI (Relative Strength Index)</h4>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[{name: 'RSI', value: indicators.rsi || 0}]}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    
                    <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="5 5" label="과매수" />
                    <ReferenceLine y={50} stroke="#666" strokeDasharray="2 2" label="중립" />
                    <ReferenceLine y={30} stroke="#3b82f6" strokeDasharray="5 5" label="과매도" />
                    
                    <Bar dataKey="value" fill={
                      !indicators.rsi ? '#d1d5db' :
                      indicators.rsi > 70 ? '#ef4444' : 
                      indicators.rsi < 30 ? '#3b82f6' : 
                      '#22c55e'
                    } />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="text-center mt-2">
                <span className="text-2xl font-bold text-gray-900 dark:text-white">{indicators.rsi?.toFixed(1) || 'N/A'}</span>
                <div className={`text-sm font-medium ${
                  !indicators.rsi ? 'text-gray-400 dark:text-gray-500' :
                  indicators.rsi > 70 ? 'text-red-600 dark:text-red-400' : 
                  indicators.rsi < 30 ? 'text-blue-600 dark:text-blue-400' : 
                  'text-green-600 dark:text-green-400'
                }`}>
                  {!indicators.rsi ? '데이터 없음' :
                   indicators.rsi > 70 ? '과매수 구간' : 
                   indicators.rsi < 30 ? '과매도 구간' : '중립 구간'}
                </div>
              </div>
            </div>

            {/* Stochastic */}
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
              <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">Stochastic (%K, %D)</h4>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stochasticData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    
                    <ReferenceLine y={80} stroke="#ef4444" strokeDasharray="5 5" label="과매수" />
                    <ReferenceLine y={20} stroke="#3b82f6" strokeDasharray="5 5" label="과매도" />
                    
                    <Bar dataKey="value" fill="#8884d8" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="text-center mt-2 space-y-1">
                <div>
                  <span className="text-sm text-gray-600">%K: </span>
                  <span className="font-mono font-bold">{indicators.stochastic_k ? Math.round(indicators.stochastic_k * 10) / 10 : 'N/A'}</span>
                </div>
                <div>
                  <span className="text-sm text-gray-600">%D: </span>
                  <span className="font-mono font-bold">{indicators.stochastic_d ? Math.round(indicators.stochastic_d * 10) / 10 : 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MACD + 주가 차트 */}
      {selectedTab === 'macd' && (
        <div className="space-y-6">
          {/* 상단: 주가 차트 */}
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">주가 차트</h4>
            {candlestickData.length > 0 ? (
              <div className="h-60">
                <PriceAreaChart data={candlestickData} />
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">주가 데이터 없음</div>
            )}
          </div>

          {/* 하단: MACD */}
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">MACD 지표</h4>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={macdData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  
                  <Bar 
                    dataKey="histogram" 
                    fill={(indicators.macd_histogram || 0) > 0 ? '#ef4444' : '#3b82f6'}
                    name="Histogram"
                  />
                  
                  <Line 
                    type="monotone" 
                    dataKey="macd" 
                    stroke="#22c55e" 
                    strokeWidth={2}
                    name="MACD"
                  />
                  <Line 
                    type="monotone" 
                    dataKey="signal" 
                    stroke="#f59e0b" 
                    strokeWidth={2}
                    name="Signal"
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            
            <div className="mt-4 grid grid-cols-3 gap-4">
              <div className="text-center p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                <div className="text-sm text-green-600 dark:text-green-400 font-medium">MACD</div>
                <div className="text-lg font-mono text-green-700 dark:text-green-300">{indicators.macd ? Math.round(indicators.macd).toLocaleString() : 'N/A'}</div>
              </div>
              <div className="text-center p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg">
                <div className="text-sm text-yellow-600 dark:text-yellow-400 font-medium">Signal</div>
                <div className="text-lg font-mono text-yellow-700 dark:text-yellow-300">{indicators.macd_signal ? Math.round(indicators.macd_signal).toLocaleString() : 'N/A'}</div>
              </div>
              <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
                <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">Histogram</div>
                <div className={`text-lg font-mono ${(indicators.macd_histogram || 0) > 0 ? 'text-red-700 dark:text-red-300' : 'text-blue-700 dark:text-blue-300'}`}>
                  {indicators.macd_histogram ? Math.round(indicators.macd_histogram).toLocaleString() : 'N/A'}
                </div>
              </div>
            </div>

            <div className="mt-4 text-center">
              <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                !indicators.macd || !indicators.macd_signal ? 'bg-gray-100 text-gray-600' :
                indicators.macd > indicators.macd_signal ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'
              }`}>
                {!indicators.macd || !indicators.macd_signal ? '데이터 없음' :
                 indicators.macd > indicators.macd_signal ? '매수 신호' : '매도 신호'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 볼린저밴드 + 주가 차트 */}
      {selectedTab === 'bollinger' && (
        <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
          <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">주가 + 볼린저밴드</h4>
          
          {/* 디버깅 정보 (개발 환경에서만) */}
          {process.env.NODE_ENV === 'development' && (
            <div className="mb-4 p-2 bg-yellow-50 dark:bg-yellow-900/20 rounded text-xs text-gray-800 dark:text-gray-200">
              <div>볼린저밴드 값: Upper={indicators.bollinger_upper}, Middle={indicators.bollinger_middle}, Lower={indicators.bollinger_lower}</div>
              <div>데이터 포인트 수: {candlestickData.length}</div>
              <div>첫 번째 데이터 포인트 볼린저밴드: {candlestickData[0] ? `${candlestickData[0].bb_upper}, ${candlestickData[0].bb_middle}, ${candlestickData[0].bb_lower}` : 'N/A'}</div>
            </div>
          )}
          
          {candlestickData.length > 0 && candlestickData.some(d => d.bb_upper !== null || d.bb_middle !== null || d.bb_lower !== null) ? (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={candlestickData} className="dark:bg-gray-800">
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" className="dark:stroke-gray-600" />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fontSize: 12, fill: 'currentColor' }}
                    stroke="#666"
                    className="dark:stroke-gray-400 dark:text-gray-300"
                  />
                  <YAxis 
                    domain={(() => {
                      const values = candlestickData.map(d => d.close).filter(v => v > 0)
                      if (values.length === 0) return ['dataMin - 2%', 'dataMax + 2%']
                      
                      const sortedValues = values.sort((a, b) => a - b)
                      const removeOutliers = 0.1
                      const lowerIndex = Math.floor(sortedValues.length * removeOutliers)
                      const upperIndex = Math.floor(sortedValues.length * (1 - removeOutliers))
                      const filteredValues = sortedValues.slice(lowerIndex, upperIndex)
                      
                      if (filteredValues.length === 0) return ['dataMin - 2%', 'dataMax + 2%']
                      
                      const median = filteredValues[Math.floor(filteredValues.length / 2)]
                      const p5 = filteredValues[Math.floor(filteredValues.length * 0.05)]
                      const p95 = filteredValues[Math.floor(filteredValues.length * 0.95)]
                      
                      const range = Math.max(p95 - median, median - p5)
                      const centeredMin = Math.max(median - range * 1.3, p5)
                      const centeredMax = Math.min(median + range * 1.3, p95)
                      
                      return [centeredMin, centeredMax]
                    })()}
                    tick={{ fontSize: 12, fill: 'currentColor' }}
                    stroke="#666"
                    className="dark:stroke-gray-400 dark:text-gray-300"
                  />
                  <Tooltip content={CustomTooltip} />
                  
                  {/* 볼린저밴드 상단 */}
                  <Line
                    type="monotone"
                    dataKey="bb_upper" 
                    stroke="#dc2626" 
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="상단 밴드"
                    connectNulls={false}
                  />
                  
                  {/* 볼린저밴드 중간선 (MA20) */}
                  <Line 
                    type="monotone" 
                    dataKey="bb_middle" 
                    stroke="#374151" 
                    strokeWidth={2}
                    dot={false}
                    name="중간선 (MA20)"
                    connectNulls={false}
                  />
                  
                  {/* 볼린저밴드 하단 */}
                  <Line
                    type="monotone"
                    dataKey="bb_lower" 
                    stroke="#dc2626" 
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="하단 밴드"
                    connectNulls={false}
                  />
                  
                  {/* 주가 (종가) */}
                  <Line
                    type="monotone"
                    dataKey="close" 
                    stroke="#2563eb"
                    strokeWidth={3}
                    dot={false}
                    name="종가"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500 dark:text-gray-400">
              <div className="mb-2">볼린저밴드 데이터가 없거나 주가 데이터가 부족합니다.</div>
              <div className="text-sm">
                {!indicators.bollinger_upper && !indicators.bollinger_middle && !indicators.bollinger_lower 
                  ? "볼린저밴드 계산값이 없습니다." 
                  : candlestickData.length === 0 
                  ? "주가 데이터가 없습니다."
                  : "데이터를 확인 중입니다."}
              </div>
            </div>
          )}
          
          {/* 볼린저밴드 정보 */}
          <div className="mt-4 grid grid-cols-3 gap-4">
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">상단 밴드</div>
              <div className="text-lg font-mono text-gray-700 dark:text-gray-300">
                {(() => {
                  const latestData = candlestickData[candlestickData.length - 1]
                  return latestData?.bb_upper ? Math.round(latestData.bb_upper).toLocaleString() : 'N/A'
                })()}
              </div>
            </div>
            <div className="text-center p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <div className="text-sm text-blue-600 dark:text-blue-400 font-medium">중간선 (MA20)</div>
              <div className="text-lg font-mono text-blue-700 dark:text-blue-300">
                {(() => {
                  const latestData = candlestickData[candlestickData.length - 1]
                  return latestData?.bb_middle ? Math.round(latestData.bb_middle).toLocaleString() : 'N/A'
                })()}
              </div>
            </div>
            <div className="text-center p-3 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <div className="text-sm text-gray-600 dark:text-gray-400 font-medium">하단 밴드</div>
              <div className="text-lg font-mono text-gray-700 dark:text-gray-300">
                {(() => {
                  const latestData = candlestickData[candlestickData.length - 1]
                  return latestData?.bb_lower ? Math.round(latestData.bb_lower).toLocaleString() : 'N/A'
                })()}
              </div>
            </div>
          </div>
          
          <div className="mt-4 text-center">
            <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
              candlestickData.length > 0 && candlestickData[candlestickData.length - 1]?.bb_middle ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
            }`}>
              {candlestickData.length > 0 && candlestickData[candlestickData.length - 1]?.bb_middle ? '밴드 압축/확장 상태로 변동성 체크' : '데이터 부족'}
            </span>
          </div>
        </div>
      )}
    </div>
  )
}) 