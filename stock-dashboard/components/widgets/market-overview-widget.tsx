"use client"

import { useState, useEffect } from 'react'
import { TrendingUp, TrendingDown, Activity, BarChart3, PieChart as PieChartIcon } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { MarketOverview, stocksApi } from '@/lib/api'
import { PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from 'recharts'

interface MarketOverviewWidgetProps {
  marketData: MarketOverview | null
  loading?: boolean
}

export function MarketOverviewWidget({ marketData: initialMarketData, loading = false }: MarketOverviewWidgetProps) {
  const [activeTab, setActiveTab] = useState<'indices' | 'sectors' | 'movers'>('indices')
  const [marketData, setMarketData] = useState<MarketOverview | null>(initialMarketData)
  const [isUpdating, setIsUpdating] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  
  // 실시간 업데이트를 위한 주기적 데이터 새로고침
  useEffect(() => {
    const updateMarketData = async () => {
      try {
        setIsUpdating(true)
        const updatedData = await stocksApi.getMarketOverview()
        setMarketData(updatedData)
        setLastUpdated(new Date())
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

  // 시장 지수 데이터 준비
  const marketIndices = Object.entries(marketData.market_summary).map(([key, data]) => ({
    name: key.toUpperCase(),
    current: data.current,
    change: data.change,
    changePercent: data.change_percent,
    volume: data.volume,
    high: data.high,
    low: data.low,
    isPositive: data.change_percent >= 0
  }))

  // 섹터별 성과 데이터 (상위 5개)
  const topSectors = marketData.sector_performance
    .sort((a, b) => b.change_percent - a.change_percent)
    .slice(0, 5)

  const bottomSectors = marketData.sector_performance
    .sort((a, b) => a.change_percent - b.change_percent)
    .slice(0, 5)

  // 차트용 데이터
  const sectorChartData = marketData.sector_performance.map(sector => ({
    name: sector.sector.length > 8 ? sector.sector.substring(0, 8) + '...' : sector.sector,
    value: Math.abs(sector.change_percent),
    change: sector.change_percent,
    fill: sector.change_percent >= 0 ? '#10b981' : '#ef4444'
  }))

  const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']

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
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="indices" className="text-xs">지수</TabsTrigger>
            <TabsTrigger value="sectors" className="text-xs">섹터</TabsTrigger>
            <TabsTrigger value="movers" className="text-xs">등락</TabsTrigger>
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
                    {index.current.toLocaleString()}
                  </span>
                  <span className={`font-mono ${index.isPositive ? 'text-green-600' : 'text-red-600'}`}>
                    {index.isPositive ? '+' : ''}{index.change.toFixed(2)}
                  </span>
                </div>
                <div className="flex justify-between text-xs text-gray-500">
                  <span>거래량: {formatNumber(index.volume)}</span>
                  <span>고가: {index.high.toLocaleString()}</span>
                </div>
                <Progress 
                  value={Math.min(100, ((index.current - index.low) / (index.high - index.low)) * 100)} 
                  className="h-2"
                />
              </div>
            ))}
          </TabsContent>

          <TabsContent value="sectors" className="space-y-4 mt-4">
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sectorChartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                  <XAxis 
                    dataKey="name" 
                    tick={{ fontSize: 10 }}
                    angle={-45}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip 
                    formatter={(value: number, name: string, props: any) => [
                      `${props.payload.change >= 0 ? '+' : ''}${props.payload.change.toFixed(2)}%`,
                      '변동률'
                    ]}
                    labelFormatter={(label) => `섹터: ${label}`}
                  />
                  <Bar dataKey="value" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </TabsContent>

          <TabsContent value="movers" className="space-y-4 mt-4">
            <div className="space-y-3">
              <div>
                <h4 className="text-sm font-semibold text-green-700 mb-2 flex items-center gap-1">
                  <TrendingUp className="h-4 w-4" />
                  상승 섹터
                </h4>
                <div className="space-y-2">
                  {topSectors.map((sector, index) => (
                    <div key={sector.sector} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="w-4 h-4 rounded bg-green-100 text-green-800 text-xs flex items-center justify-center font-bold">
                          {index + 1}
                        </span>
                        <span className="truncate max-w-24">{sector.sector}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-green-600 font-mono">
                          +{sector.change_percent.toFixed(2)}%
                        </span>
                        <Badge variant="outline" className="text-xs px-1">
                          {sector.top_performer.name}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="text-sm font-semibold text-red-700 mb-2 flex items-center gap-1">
                  <TrendingDown className="h-4 w-4" />
                  하락 섹터
                </h4>
                <div className="space-y-2">
                  {bottomSectors.map((sector, index) => (
                    <div key={sector.sector} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="w-4 h-4 rounded bg-red-100 text-red-800 text-xs flex items-center justify-center font-bold">
                          {index + 1}
                        </span>
                        <span className="truncate max-w-24">{sector.sector}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-red-600 font-mono">
                          {sector.change_percent.toFixed(2)}%
                        </span>
                        <Badge variant="outline" className="text-xs px-1">
                          {sector.top_performer.name}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
} 