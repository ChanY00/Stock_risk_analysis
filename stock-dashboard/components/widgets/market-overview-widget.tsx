"use client"

import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Activity } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { MarketOverview, stocksApi } from '@/lib/api'

interface MarketOverviewWidgetProps {
  marketData: MarketOverview | null
  loading?: boolean
}

export function MarketOverviewWidget({ marketData: initialMarketData, loading = false }: MarketOverviewWidgetProps) {
  // 간소화: 지수 탭만 유지
  const [activeTab, setActiveTab] = useState<'indices'>('indices')
  const [marketData, setMarketData] = useState<MarketOverview | null>(initialMarketData)
  const [isUpdating, setIsUpdating] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  
  // 실시간 업데이트를 위한 주기적 데이터 새로고침
  useEffect(() => {
    const updateMarketData = async () => {
      try {
        setIsUpdating(true)
        console.log('📈 Fetching market overview...')
        const updatedData = await stocksApi.getMarketOverview()
        // 백엔드가 비어있는 객체를 반환하는 경우 방어
        if (updatedData && updatedData.market_summary) {
          setMarketData(updatedData)
          setLastUpdated(new Date())
        } else {
          console.warn('⚠️ Market overview returned empty payload')
        }
      } catch (error) {
        console.error('시장 데이터 업데이트 실패:', error)
      } finally {
        setIsUpdating(false)
      }
    }
    
    // 초기 데이터가 없으면 즉시 로드
    if (!marketData) {
      updateMarketData()
    }
    
    // 30초마다 데이터 업데이트
    const interval = setInterval(updateMarketData, 30000)
    
    return () => clearInterval(interval)
  }, [marketData])
  
  // 초기 데이터 업데이트
  useEffect(() => {
    setMarketData(initialMarketData)
    if (initialMarketData) {
      setLastUpdated(new Date())
    }
  }, [initialMarketData])

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            시장 현황
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
              <div className="h-8 bg-gray-200 rounded"></div>
            </div>
            <div className="animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-2"></div>
              <div className="h-8 bg-gray-200 rounded"></div>
            </div>
          </div>
        </CardContent>
      </Card>
    )
  }

  if (!marketData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            시장 현황
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-gray-500">
            시장 데이터를 불러올 수 없습니다
          </div>
        </CardContent>
      </Card>
    )
  }

  // 시장 지수 데이터 준비 - KOSPI/KOSDAQ만 표시
  const entries = Object.entries(marketData.market_summary || {})
  const marketIndices = entries
    .filter(([key]) => ['kospi', 'kosdaq'].includes(key.toLowerCase()))
    .map(([key, data]) => ({
      name: key.toUpperCase(),
      current: Number(data.current) || 0,
      change: Number(data.change) || 0,
      changePercent: Number(data.change_percent) || 0,
      volume: Number(data.volume) || 0,
      high: Number(data.high) || 0,
      low: Number(data.low) || 0,
      isPositive: data.change_percent >= 0
    }))

  // 섹터/등락 UI 제거

  const formatNumber = (num: number) => {
    if (num >= 1e12) return `${(num / 1e12).toFixed(1)}조`
    if (num >= 1e8) return `${(num / 1e8).toFixed(1)}억`
    if (num >= 1e4) return `${(num / 1e4).toFixed(1)}만`
    return num.toLocaleString()
  }

  const formatPercent = (num: number) => {
    const sign = num >= 0 ? '+' : ''
    return `${sign}${num.toFixed(2)}%`
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5" />
          시장 현황
          {isUpdating && (
            <div className="ml-auto flex items-center gap-1 text-blue-600">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse"></div>
              <span className="text-xs">업데이트 중</span>
            </div>
          )}
        </CardTitle>
        <CardDescription>
          실시간 시장 지수 및 섹터별 동향
          {lastUpdated && (
            <span className="block text-xs text-gray-500 mt-1">
              마지막 업데이트: {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as any)}>
          <TabsList className="grid w-full grid-cols-1">
            <TabsTrigger value="indices" className="text-xs">지수</TabsTrigger>
          </TabsList>

          <TabsContent value="indices" className="space-y-4 mt-4">
            {marketIndices.map((index) => (
              <div key={index.name} className="space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{index.name}</span>
                    {index.isPositive ? (
                      <TrendingUp className="h-4 w-4 text-green-600" />
                    ) : (
                      <TrendingDown className="h-4 w-4 text-red-600" />
                    )}
                  </div>
                  <Badge 
                    variant={index.isPositive ? "default" : "destructive"}
                    className={index.isPositive ? "bg-green-100 text-green-800" : ""}
                  >
                    {formatPercent(index.changePercent)}
                  </Badge>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="font-mono font-medium">
                    {Number(index.current || 0).toLocaleString()}
                  </span>
                  <span className={`font-mono ${index.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                    {index.isPositive ? '+' : ''}{Number(index.change || 0).toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>거래량: {formatNumber(Number(index.volume || 0))}</span>
                  <span>고가: {Number(index.high || 0).toLocaleString()}</span>
                </div>
                <Progress 
                  value={Math.min(100, ((index.current - index.low) / (index.high - index.low)) * 100)} 
                  className="h-2"
                />
              </div>
            ))}
          </TabsContent>

          {/* 섹터 및 등락 탭 제거 */}
        </Tabs>
      </CardContent>
    </Card>
  )
} 