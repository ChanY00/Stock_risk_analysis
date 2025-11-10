"use client"

import { useState, useMemo, useEffect, useCallback, useRef, memo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart, ComposedChart, Bar, Cell, BarChart } from 'recharts'
import { PriceData } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { TrendingUp, BarChart3 } from 'lucide-react'
import { stocksApi } from '@/lib/api'

interface PriceChartProps {
  data: PriceData[]
  title?: string
  stockCode?: string
}

export const PriceChart = memo(function PriceChart({ data: initialData, title = "주가 차트", stockCode }: PriceChartProps) {
  const [chartType, setChartType] = useState<'line' | 'candle'>('line')
  const [period, setPeriod] = useState<'1W' | '1M' | '3M' | '6M' | '1Y' | 'ALL'>('1M')
  const [loading, setLoading] = useState(false)
  const [apiData, setApiData] = useState<PriceData[]>(initialData || [])
  
  // 데이터 해시를 사용하여 실제로 변경되었는지 확인
  const dataHashRef = useRef<string>('')
  
  // initialData가 변경되었을 때만 apiData 업데이트
  useEffect(() => {
    if (!stockCode && initialData) {
      const currentHash = JSON.stringify(initialData.map(d => d.date))
      if (currentHash !== dataHashRef.current) {
        dataHashRef.current = currentHash
        setApiData(initialData)
      }
    }
  }, [initialData, stockCode])

  // 기간 변경시 새로운 데이터 로드
  useEffect(() => {
    if (!stockCode) {
      return
    }

    const loadPriceData = async () => {
      setLoading(true)
      try {
        let days: number
        switch (period) {
          case '1W':
            days = 7
            break
          case '1M':
            days = 30
            break
          case '3M':
            days = 90
            break
          case '6M':
            days = 180
            break
          case '1Y':
            days = 365
            break
          case 'ALL':
            days = 1000 // 충분히 큰 값
            break
        }

        console.log(`🔄 주가 데이터 로딩: ${stockCode}, 기간: ${period} (${days}일)`)
        const response = await stocksApi.getPriceHistory(stockCode, { days })
        
        // API 응답에서 price_history 추출
        let newData: PriceData[] = []
        if (Array.isArray(response)) {
          newData = response
        } else if (response && typeof response === 'object' && 'price_history' in response) {
          newData = (response as any).price_history || []
        } else {
          console.warn('예상하지 못한 API 응답 구조:', response)
          newData = initialData || []
        }

        console.log(`✅ 새로운 주가 데이터 로드 완료: ${newData.length}개`)
        setApiData(newData)
      } catch (error) {
        console.error('주가 데이터 로딩 실패:', error)
        // 실패 시 초기 데이터로 폴백
        setApiData(initialData || [])
      } finally {
        setLoading(false)
      }
    }

    loadPriceData()
  }, [period, stockCode])

  const data = apiData

  // 기간별 데이터 필터링 - Hook 규칙 준수를 위해 early return 이전으로 이동
  const filteredData = useMemo(() => {
    if (!data || data.length === 0) {
      return []
    }
    const sortedData = [...data].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())
    const now = new Date()
    let startDate: Date

    switch (period) {
      case '1W':
        // 1주 전 계산 - 단순하게 7일 전
        startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
        break
      case '1M':
        startDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate())
        // 월 계산에서만 날짜 보정 적용
        if (startDate.getDate() !== now.getDate()) {
          startDate = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0) // 해당 월의 마지막 날
        }
        break
      case '3M':
        startDate = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate())
        // 월 계산에서만 날짜 보정 적용
        if (startDate.getDate() !== now.getDate()) {
          startDate = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0) // 해당 월의 마지막 날
        }
        break
      case '6M':
        startDate = new Date(now.getFullYear(), now.getMonth() - 6, now.getDate())
        // 월 계산에서만 날짜 보정 적용
        if (startDate.getDate() !== now.getDate()) {
          startDate = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0) // 해당 월의 마지막 날
        }
        break
      case '1Y':
        startDate = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate())
        // 연 계산에서만 날짜 보정 적용 (윤년 등)
        if (startDate.getDate() !== now.getDate()) {
          startDate = new Date(startDate.getFullYear(), startDate.getMonth() + 1, 0) // 해당 월의 마지막 날
        }
        break
      case 'ALL':
        return sortedData
    }

    const filtered = sortedData.filter(item => new Date(item.date) >= startDate)
    
    // 디버깅 로그
    console.log(`Period: ${period}, Total data: ${sortedData.length}, Start date: ${startDate.toISOString().split('T')[0]}, Filtered: ${filtered.length}`)
    
    return filtered
  }, [data, period])

  // 데이터를 차트에 맞게 변환
  const chartData = filteredData.map((item, index) => {
    const prevClose = index > 0 ? filteredData[index - 1].close : item.open
    const isRising = item.close >= item.open
    const changeFromPrev = item.close - prevClose
    
    return {
      date: new Date(item.date).toLocaleDateString('ko-KR', { 
        month: 'short', 
        day: 'numeric' 
      }),
      fullDate: item.date,
      close: item.close,
      high: item.high,
      low: item.low,
      open: item.open,
      volume: item.volume,
      isRising,
      changeFromPrev,
      // 캔들스틱 데이터
      candleRange: [item.low, item.high], // 심지 범위
      candleBody: [Math.min(item.open, item.close), Math.max(item.open, item.close)], // 몸통 범위
      candleColor: isRising ? '#ef4444' : '#3b82f6'
    }
  })

  // 가격 범위 계산 (필터링된 데이터가 없을 경우 처리)
  const prices = filteredData.map(d => d.close)
  const volumes = filteredData.map(d => d.volume)
  
  // 필터링된 데이터가 없을 경우 기본값 사용
  const minPrice = filteredData.length > 0 ? Math.min(...filteredData.map(d => d.low)) : 0
  const maxPrice = filteredData.length > 0 ? Math.max(...filteredData.map(d => d.high)) : 100000
  const maxVolume = volumes.length > 0 ? Math.max(...volumes) : 0
  const priceRange = maxPrice - minPrice
  const yAxisMin = Math.max(0, minPrice - priceRange * 0.05)
  const yAxisMax = maxPrice + priceRange * 0.05

  // 첫째날과 마지막날 가격으로 색상 결정
  const isGain = filteredData[filteredData.length - 1]?.close >= filteredData[0]?.close
  const chartColor = isGain ? '#ef4444' : '#3b82f6'

  const periods = useMemo(() => [
    { label: '1주', value: '1W' as const },
    { label: '1개월', value: '1M' as const },
    { label: '3개월', value: '3M' as const },
    { label: '6개월', value: '6M' as const },
    { label: '1년', value: '1Y' as const },
    { label: '전체', value: 'ALL' as const },
  ], [])

  const CustomTooltip = useCallback(({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-white p-3 border rounded-lg shadow-lg">
          <p className="font-medium text-gray-900">{label}</p>
          <div className="mt-2 space-y-1">
            <p className="text-sm">
              <span className="text-gray-600">시가: </span>
              <span className="font-mono">{data.open.toLocaleString()}원</span>
            </p>
            <p className="text-sm">
              <span className="text-gray-600">고가: </span>
              <span className="font-mono text-red-600">{data.high.toLocaleString()}원</span>
            </p>
            <p className="text-sm">
              <span className="text-gray-600">저가: </span>
              <span className="font-mono text-blue-600">{data.low.toLocaleString()}원</span>
            </p>
            <p className="text-sm">
              <span className="text-gray-600">종가: </span>
              <span className="font-mono font-medium">{data.close.toLocaleString()}원</span>
            </p>
            <p className="text-sm">
              <span className="text-gray-600">거래량: </span>
              <span className="font-mono">{data.volume.toLocaleString()}</span>
            </p>
            <p className="text-sm">
              <span className="text-gray-600">전일대비: </span>
              <span className={`font-mono ${data.changeFromPrev >= 0 ? 'text-red-600' : 'text-blue-600'}`}>
                {data.changeFromPrev >= 0 ? '+' : ''}{data.changeFromPrev.toLocaleString()}원
              </span>
            </p>
          </div>
        </div>
      )
    }
    return null
  }, [])

  // 캔들스틱 커스텀 셰이프
  const CandlestickBar = useCallback((props: any) => {
    const { payload, x, y, width, height } = props
    if (!payload) return null

    const { high, low, open, close, isRising } = payload
    const color = isRising ? '#ef4444' : '#3b82f6'
    
    // 가격을 Y좌표로 변환하는 함수
    const priceToY = (price: number) => {
      const ratio = (yAxisMax - price) / (yAxisMax - yAxisMin)
      return y + ratio * height
    }

    const highY = priceToY(high)
    const lowY = priceToY(low)
    const openY = priceToY(open)
    const closeY = priceToY(close)
    
    const bodyTop = Math.min(openY, closeY)
    const bodyBottom = Math.max(openY, closeY)
    const bodyHeight = Math.max(1, bodyBottom - bodyTop)
    
    const centerX = x + width / 2
    const bodyWidth = Math.min(width * 0.6, 8) // 캔들 폭 제한

    return (
      <g>
        {/* 위쪽 심지 */}
        <line
          x1={centerX}
          y1={highY}
          x2={centerX}
          y2={bodyTop}
          stroke={color}
          strokeWidth={1}
        />
        {/* 아래쪽 심지 */}
        <line
          x1={centerX}
          y1={bodyBottom}
          x2={centerX}
          y2={lowY}
          stroke={color}
          strokeWidth={1}
        />
        {/* 캔들 몸통 */}
        <rect
          x={centerX - bodyWidth / 2}
          y={bodyTop}
          width={bodyWidth}
          height={bodyHeight}
          fill={isRising ? color : 'white'}
          stroke={color}
          strokeWidth={1}
        />
      </g>
    )
  }, [yAxisMax, yAxisMin])

  return (
    <div className="w-full space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
        <div className="flex items-center space-x-4">
          {/* 기간 선택 버튼 */}
          <div className="flex space-x-1">
            {periods.map((p) => (
              <Button
                key={p.value}
                variant={period === p.value ? 'default' : 'outline'}
                size="sm"
                disabled={loading}
                onClick={() => setPeriod(p.value)}
                className="text-xs px-2 py-1"
              >
                {p.label}
              </Button>
            ))}
            {loading && <span className="text-xs text-gray-500 ml-2">로딩 중...</span>}
          </div>
          
          {/* 차트 타입 선택 */}
          <div className="flex space-x-2">
            <Button
              variant={chartType === 'line' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setChartType('line')}
            >
              <TrendingUp className="h-4 w-4 mr-1" />
              선 차트
            </Button>
            <Button
              variant={chartType === 'candle' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setChartType('candle')}
            >
              <BarChart3 className="h-4 w-4 mr-1" />
              캔들 차트
            </Button>
          </div>
          
          <div className="flex items-center space-x-4 text-sm">
            <span className="text-gray-600">기간: {filteredData.length}일</span>
            <span className={`font-medium ${isGain ? 'text-red-600' : 'text-blue-600'}`}>
              {isGain ? '상승' : '하락'} 추세
            </span>
          </div>
        </div>
      </div>
      
      {/* 주가 차트 */}
      <div className="h-80">
        {filteredData.length === 0 ? (
          <div className="h-full flex items-center justify-center text-gray-500 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
            <div className="text-center">
              <TrendingUp className="h-12 w-12 mx-auto text-gray-400 mb-2" />
              <div className="text-lg font-medium">선택한 기간에 데이터가 없습니다</div>
              <div className="text-sm mt-1">다른 기간을 선택해보세요</div>
            </div>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            {chartType === 'line' ? (
              <AreaChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <defs>
                  <linearGradient id={`colorPrice`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={chartColor} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={chartColor} stopOpacity={0.05}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="date" 
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <YAxis 
                  domain={[yAxisMin, yAxisMax]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickFormatter={(value) => `${value.toLocaleString()}`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  type="monotone"
                  dataKey="close"
                  stroke={chartColor}
                  strokeWidth={2}
                  fill={`url(#colorPrice)`}
                  dot={false}
                  activeDot={{ r: 4, fill: chartColor }}
                />
              </AreaChart>
            ) : (
              <ComposedChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis 
                  dataKey="date" 
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <YAxis 
                  domain={[yAxisMin, yAxisMax]}
                  axisLine={false}
                  tickLine={false}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                  tickFormatter={(value) => `${value.toLocaleString()}`}
                />
                <Tooltip content={<CustomTooltip />} />
                
                {/* 캔들스틱을 위한 더미 Bar (실제로는 안 보임) */}
                <Bar 
                  dataKey="high" 
                  fill="transparent"
                  shape={<CandlestickBar />}
                />
              </ComposedChart>
            )}
          </ResponsiveContainer>
        )}
      </div>

      {/* 거래량 차트 - 데이터가 있을 때만 표시 */}
      {filteredData.length > 0 && (
        <div className="h-32 mt-8">
          <h4 className="text-sm font-medium text-gray-700 mb-3">거래량</h4>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis 
                dataKey="date" 
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 10, fill: '#6b7280' }}
                height={20}
              />
              <YAxis 
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 10, fill: '#6b7280' }}
                tickFormatter={(value) => {
                  if (value >= 1e6) return `${(value / 1e6).toFixed(0)}M`
                  if (value >= 1e3) return `${(value / 1e3).toFixed(0)}K`
                  return value.toString()
                }}
                width={50}
              />
              <Tooltip 
                formatter={(value: number) => [value.toLocaleString(), '거래량']}
                labelFormatter={(label) => `날짜: ${label}`}
              />
              <Bar dataKey="volume" radius={[1, 1, 0, 0]}>
                {chartData.map((entry, index) => {
                  const color = entry.isRising ? '#ef444466' : '#3b82f666'
                  return <Cell key={`volume-${index}`} fill={color} />
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      
      {/* 차트 요약 정보 - 데이터가 있을 때만 표시 */}
      {filteredData.length > 0 && (
        <>
          <div className="mt-8 grid grid-cols-4 gap-4 text-sm bg-gray-50 p-4 rounded-lg">
            <div className="text-center">
              <div className="text-gray-600">시작가</div>
              <div className="font-mono font-medium">{filteredData[0]?.close.toLocaleString() || '-'}원</div>
            </div>
            <div className="text-center">
              <div className="text-gray-600">종료가</div>
              <div className="font-mono font-medium">{filteredData[filteredData.length - 1]?.close.toLocaleString() || '-'}원</div>
            </div>
            <div className="text-center">
              <div className="text-gray-600">최고가</div>
              <div className="font-mono font-medium text-red-600">{maxPrice > 0 ? maxPrice.toLocaleString() : '-'}원</div>
            </div>
            <div className="text-center">
              <div className="text-gray-600">최저가</div>
              <div className="font-mono font-medium text-blue-600">{minPrice > 0 ? minPrice.toLocaleString() : '-'}원</div>
            </div>
          </div>

          {/* 추가 통계 정보 - 간격 추가 */}
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm bg-white p-4 rounded-lg border">
            <div className="text-center">
              <div className="text-gray-600">평균 거래량</div>
              <div className="font-mono font-medium">
                {volumes.length > 0 ? Math.round(volumes.reduce((a, b) => a + b, 0) / volumes.length).toLocaleString() : '-'}
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-600">최대 거래량</div>
              <div className="font-mono font-medium">{maxVolume > 0 ? maxVolume.toLocaleString() : '-'}</div>
            </div>
            <div className="text-center">
              <div className="text-gray-600">상승일</div>
              <div className="font-mono font-medium text-red-600">
                {chartData.filter(d => d.changeFromPrev > 0).length}일
              </div>
            </div>
            <div className="text-center">
              <div className="text-gray-600">하락일</div>
              <div className="font-mono font-medium text-blue-600">
                {chartData.filter(d => d.changeFromPrev < 0).length}일
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
})
