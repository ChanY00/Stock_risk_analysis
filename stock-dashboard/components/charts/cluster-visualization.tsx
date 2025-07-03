"use client"

import React, { useState, useEffect } from "react"
import { Scatter, ScatterChart, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Cell, ReferenceLine, Legend, AreaChart, Area, BarChart, Bar } from "recharts"
import { ChartContainer, ChartTooltip } from "@/components/ui/chart"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { stocksApi, StockClusterInfo, SimilarStocks, ClusterStocks, Stock } from "@/lib/api"
import { translateSectorToKorean, getSectorColor } from "@/lib/sector-mapping"
import { TrendingUp, TrendingDown, Target, Users, BarChart3, Network, Info, Lightbulb, Maximize2, Minimize2, RotateCcw, Settings } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"
import dynamic from 'next/dynamic'
import { useCallback, useMemo, useRef } from 'react'
import { scaleLinear } from 'd3-scale'
import * as d3 from 'd3-force'

// ForceGraph를 dynamic import로 로드 (SSR 문제 해결)
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { 
  ssr: false,
  loading: () => <div className="h-[600px] flex items-center justify-center bg-slate-900 rounded-lg">
    <div className="text-white">네트워크 그래프 로딩 중...</div>
  </div>
})

interface ClusterVisualizationProps {
  stockCode: string
}

// 네트워크 그래프용 데이터 타입
interface NetworkNode {
  id: string
  name: string
  sector: string
  group: number // 클러스터 ID
  size: number // 시가총액 기반
  color: string
  isCurrentStock: boolean
  stock_code: string
  current_price: number
  market_cap?: number
  per?: number | null
  pbr?: number | null
  roe?: number | null
  similarityScore?: number
  x?: number // ForceGraph2D 호환성
  y?: number // ForceGraph2D 호환성
  vx?: number
  vy?: number
  fx?: number
  fy?: number
  [key: string]: any // ForceGraph2D 호환성
}

interface NetworkLink {
  source: string | NetworkNode
  target: string | NetworkNode
  strength: number // 유사도 강도
  type: 'cluster' | 'sector' | 'similarity'
  [key: string]: any // ForceGraph2D 호환성
}

// 시각화 축 옵션
type VisualizationAxis = 'per_pbr' | 'marketcap_roe' | 'per_roe' | 'pbr_roe'

// 클러스터 시각화를 위한 데이터 형태
interface ClusterVisualizationData {
  stock_code: string
  stock_name: string
  sector: string
  x: number
  y: number
  size: number // 버블 크기 (시가총액 기반)
  cluster_id: number
  isCurrentStock: boolean
  current_price?: number
  market_cap?: number
  per?: number | null
  pbr?: number | null
  roe?: number | null
  sectorColor: string
}

export function ClusterVisualization({ stockCode }: ClusterVisualizationProps) {
  const [stockClusterInfo, setStockClusterInfo] = useState<StockClusterInfo | null>(null)
  const [spectralSimilarStocks, setSpectralSimilarStocks] = useState<SimilarStocks | null>(null)
  const [agglomerativeSimilarStocks, setAgglomerativeSimilarStocks] = useState<SimilarStocks | null>(null)
  const [spectralClusterData, setSpectralClusterData] = useState<ClusterStocks | null>(null)
  const [agglomerativeClusterData, setAgglomerativeClusterData] = useState<ClusterStocks | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const [selectedTab, setSelectedTab] = useState<'spectral' | 'agglomerative'>('spectral')
  const [visualizationAxis, setVisualizationAxis] = useState<VisualizationAxis>('per_pbr')
  const [selectedSector, setSelectedSector] = useState<string>('all')
  const [viewMode, setViewMode] = useState<'bubble' | 'network'>('bubble')
  const [networkMode, setNetworkMode] = useState<'2d' | '3d'>('2d')
  const [is3DMode, setIs3DMode] = useState(false)
  const forceGraphRef = useRef<any>(null)

  // ForceGraph2D의 내장 tooltip 제거 (단순화)
  useEffect(() => {
    const removeTooltips = () => {
      const tooltips = document.querySelectorAll('.float-tooltip-kap')
      tooltips.forEach(tooltip => tooltip?.remove?.())
    }

    // 더 긴 간격으로 tooltip 제거 (성능 개선)
    const interval = setInterval(removeTooltips, 500)
    
    return () => clearInterval(interval)
  }, [])

  // 축 옵션 설정
  const axisOptions = {
    per_pbr: { x: 'PER', y: 'PBR', xKey: 'per', yKey: 'pbr' },
    marketcap_roe: { x: '시가총액(조원)', y: 'ROE(%)', xKey: 'market_cap', yKey: 'roe' },
    per_roe: { x: 'PER', y: 'ROE(%)', xKey: 'per', yKey: 'roe' },
    pbr_roe: { x: 'PBR', y: 'ROE(%)', xKey: 'pbr', yKey: 'roe' }
  }

  // 클러스터 시각화 데이터 변환 함수
  const transformToVisualizationData = (stocks: Stock[], clusterId: number, currentStockCode: string): ClusterVisualizationData[] => {
    const maxMarketCap = Math.max(...stocks.map(s => s.market_cap || 0))
    const minMarketCap = Math.min(...stocks.filter(s => s.market_cap).map(s => s.market_cap || 0))
    
    return stocks.map((stock) => {
      const getAxisValue = (key: string, stock: Stock): number => {
        switch(key) {
          case 'per': return stock.per || 0
          case 'pbr': return stock.pbr || 0
          case 'roe': return stock.roe || 0
          case 'market_cap': return (stock.market_cap || 0) / 1000000000000 // 조원 단위
          default: return 0
        }
      }

      const xValue = getAxisValue(axisOptions[visualizationAxis].xKey, stock)
      const yValue = getAxisValue(axisOptions[visualizationAxis].yKey, stock)
      
      // 버블 크기 계산 (시가총액 기반, 6-20 범위)
      const marketCapRatio = stock.market_cap ? 
        ((stock.market_cap - minMarketCap) / (maxMarketCap - minMarketCap)) : 0
      const bubbleSize = 6 + (marketCapRatio * 14)

      return {
        stock_code: stock.stock_code,
        stock_name: stock.stock_name,
        sector: stock.sector,
        x: xValue,
        y: yValue,
        size: bubbleSize,
        cluster_id: clusterId,
        isCurrentStock: stock.stock_code === currentStockCode,
        current_price: stock.current_price,
        market_cap: stock.market_cap,
        per: stock.per,
        pbr: stock.pbr,
        roe: stock.roe,
        sectorColor: getSectorColor(translateSectorToKorean(stock.sector))
      }
    }).filter(item => item.x > 0 && item.y > 0) // 유효한 데이터만
  }

  // 평균값 계산
  const calculateAverages = (data: ClusterVisualizationData[]) => {
    if (data.length === 0) return { avgX: 0, avgY: 0 }
    const validData = data.filter(d => d.x > 0 && d.y > 0)
    const avgX = validData.reduce((sum, d) => sum + d.x, 0) / validData.length
    const avgY = validData.reduce((sum, d) => sum + d.y, 0) / validData.length
    return { avgX, avgY }
  }

  // 섹터 필터링
  const filterBySector = (data: ClusterVisualizationData[]): ClusterVisualizationData[] => {
    if (selectedSector === 'all') return data
    return data.filter(item => item.sector === selectedSector)
  }

  // 네트워크 그래프 데이터 생성 (메모이제이션으로 안정화)
  const createNetworkGraphData = useCallback((stocks: Stock[], clusterId: number, currentStockCode: string, axis: VisualizationAxis) => {
    // 상위 15개 종목으로 확대하여 풍부한 시각화
    const topStocks = stocks.slice(0, 15)
    
    // 축에 따른 데이터 값 추출 함수
    const getAxisValue = (key: string, stock: Stock): number => {
      switch (key) {
        case 'per': return stock.per || 0
        case 'pbr': return stock.pbr || 0
        case 'roe': return stock.roe || 0
        case 'market_cap': return stock.market_cap || 0
        default: return 0
      }
    }
    
    const [xKey, yKey] = axis.split('_')
    const currentStock = topStocks.find(s => s.stock_code === currentStockCode)
    if (!currentStock) return { nodes: [], links: [] }

    const currentXValue = getAxisValue(xKey.replace('marketcap', 'market_cap'), currentStock)
    const currentYValue = getAxisValue(yKey, currentStock)
    
    // 선택된 축 기준으로 정확한 2D 좌표 계산
    const positions = topStocks.map(s => {
      const xVal = getAxisValue(xKey.replace('marketcap', 'market_cap'), s)
      const yVal = getAxisValue(yKey, s)
      return { stock: s, x: xVal, y: yVal }
    })

    // 좌표 정규화 (현재 주식을 중심(0,0)으로)
    const normalizedPositions = positions.map(pos => ({
      ...pos,
      normalizedX: pos.x - currentXValue,
      normalizedY: pos.y - currentYValue
    }))

    // 화면 좌표계로 스케일링 (더 넓은 범위로 분산)
    const xValues = normalizedPositions.map(p => p.normalizedX).filter(x => isFinite(x))
    const yValues = normalizedPositions.map(p => p.normalizedY).filter(y => isFinite(y))
    
    const xRange = Math.max(...xValues) - Math.min(...xValues)
    const yRange = Math.max(...yValues) - Math.min(...yValues)
    
    const maxRange = Math.max(xRange, yRange) || 1
    const scale = 400 / maxRange // 화면에서 400px 범위 내에 분산

    // 거리 계산 및 방사형 배치를 위한 전처리
    const distancesWithStock = normalizedPositions.map(pos => {
      const distance = Math.sqrt(pos.normalizedX * pos.normalizedX + pos.normalizedY * pos.normalizedY)
      return { ...pos, distance }
    })

    // 현재 주식 제외하고 거리 순 정렬
    const otherStocks = distancesWithStock
      .filter(item => item.stock.stock_code !== currentStockCode)
      .sort((a, b) => a.distance - b.distance)

    // 방사형 배치를 위한 노드 생성
    const nodes: NetworkNode[] = []

    // 1. 현재 주식을 중심에 배치
    const currentStockData = distancesWithStock.find(item => item.stock.stock_code === currentStockCode)
    if (currentStockData) {
      const maxMarketCap = Math.max(...topStocks.map(s => s.market_cap || 1))
      const nodeSize = 12 + ((currentStockData.stock.market_cap || 0) / maxMarketCap * 8) // 중심 노드는 더 크게

      nodes.push({
        id: currentStockData.stock.stock_code,
        name: currentStockData.stock.stock_name,
        sector: currentStockData.stock.sector,
        group: clusterId,
        size: nodeSize,
        color: '#FF6B6B', // 빨간색으로 강조
        isCurrentStock: true,
        stock_code: currentStockData.stock.stock_code,
        current_price: currentStockData.stock.current_price,
        market_cap: currentStockData.stock.market_cap,
        per: currentStockData.stock.per,
        pbr: currentStockData.stock.pbr,
        roe: currentStockData.stock.roe,
        targetX: 0, // 중심에 고정
        targetY: 0,
        metricDistance: 0,
        fx: 0, // 물리 엔진에서 위치 고정
        fy: 0
      })
    }

    // 2. 다른 주식들을 거리에 따라 방사형으로 배치
    const maxRadialDistance = Math.max(...otherStocks.map(item => item.distance)) || 1
    const colorPalette = [
      '#4F46E5', '#7C3AED', '#8B5CF6', '#A855F7', '#C084FC',
      '#06B6D4', '#0EA5E9', '#3B82F6', '#6366F1', '#EC4899',
      '#F59E0B', '#10B981', '#84CC16', '#F97316', '#EF4444'
    ]

    otherStocks.forEach((item, index) => {
      const maxMarketCap = Math.max(...topStocks.map(s => s.market_cap || 1))
      const nodeSize = 8 + ((item.stock.market_cap || 0) / maxMarketCap * 10)

      // 거리에 비례한 반지름 (100-400px 범위)
      const normalizedDistance = item.distance / maxRadialDistance
      const radius = 100 + (normalizedDistance * 300)

      // 균등하게 퍼지도록 각도 계산 (약간의 랜덤성 추가)
      const baseAngle = (index / otherStocks.length) * 2 * Math.PI
      const randomOffset = (Math.random() - 0.5) * 0.3 // ±0.15 라디안 랜덤
      const angle = baseAngle + randomOffset

      const targetX = radius * Math.cos(angle)
      const targetY = radius * Math.sin(angle)

      // 거리에 따른 색상 선택 (가까운 것일수록 따뜻한 색)
      const colorIndex = Math.floor(normalizedDistance * (colorPalette.length - 1))

      nodes.push({
        id: item.stock.stock_code,
        name: item.stock.stock_name,
        sector: item.stock.sector,
        group: clusterId,
        size: nodeSize,
        color: colorPalette[Math.min(colorIndex, colorPalette.length - 1)],
        isCurrentStock: false,
        stock_code: item.stock.stock_code,
        current_price: item.stock.current_price,
        market_cap: item.stock.market_cap,
        per: item.stock.per,
        pbr: item.stock.pbr,
        roe: item.stock.roe,
        targetX: targetX,
        targetY: targetY,
        metricDistance: item.distance,
        angle: angle, // 각도 정보 저장
        radius: radius // 반지름 정보 저장
      })
    })
    
    // 거리 기반 링크 생성
    const links: NetworkLink[] = []
    const currentNodeId = currentStockCode
    const maxLinkDistance = Math.max(...nodes.filter(n => !n.isCurrentStock).map(n => n.metricDistance || 0))

    // 현재 주식에서 모든 다른 주식으로의 링크 (거리에 반비례한 강도)
    nodes.forEach(node => {
      if (node.id !== currentNodeId) {
        const normalizedDistance = (node.metricDistance || 0) / maxLinkDistance
        const linkStrength = Math.max(0.1, 1 - normalizedDistance) // 가까울수록 강한 연결
        
        links.push({
          source: currentNodeId,
          target: node.id,
          strength: linkStrength,
          type: 'similarity',
          distance: node.metricDistance || 0
        })
      }
    })
    
    // 가까운 기업들끼리 추가 연결 (상위 5개 가장 가까운 기업들)
    const closeNodes = nodes.filter(n => !n.isCurrentStock).slice(0, 5)
    for (let i = 0; i < closeNodes.length; i++) {
      for (let j = i + 1; j < closeNodes.length; j++) {
        const distance1 = closeNodes[i].metricDistance || 0
        const distance2 = closeNodes[j].metricDistance || 0
        const avgDistance = (distance1 + distance2) / 2
        const linkStrength = Math.max(0.05, 0.3 * (1 - avgDistance / maxLinkDistance))
        
        links.push({
          source: closeNodes[i].id,
          target: closeNodes[j].id,
          strength: linkStrength,
          type: 'cluster',
          distance: avgDistance
        })
      }
    }
    
    return { nodes, links }
  }, [])

  // 네트워크 뷰 데이터 생성
  const createNetworkViewData = (stocks: Stock[], clusterId: number, currentStockCode: string) => {
    // 상위 20개 종목만 선택 (성능을 위해)
    const topStocks = stocks.slice(0, 20)
    
    return topStocks.map(stock => ({
      ...stock,
      isCurrentStock: stock.stock_code === currentStockCode,
      sectorColor: getSectorColor(translateSectorToKorean(stock.sector)),
      size: stock.market_cap ? Math.max(20, Math.min((stock.market_cap / 1000000000000) * 10, 60)) : 30
    }))
  }

  // 기존 네트워크 뷰 컴포넌트 (간단한 버전)  
  const SimpleNetworkView = ({ data, title }: { data: Stock[], title: string }) => {
    const networkData = createNetworkViewData(data, 0, stockCode)
    
    return (
      <div className="h-[500px] relative bg-gray-900 rounded-lg overflow-hidden p-4">
        <div className="absolute top-4 left-4 text-white text-sm bg-black/50 px-3 py-1 rounded">
          {title} - 간단 네트워크 뷰
        </div>
        
        {/* 네트워크 노드들 */}
        <div className="relative w-full h-full">
          {networkData.map((stock, index) => {
            // 원형 배치를 위한 각도 계산
            const angle = (index / networkData.length) * 2 * Math.PI
            const radius = 150
            const centerX = 400
            const centerY = 250
            const x = centerX + radius * Math.cos(angle)
            const y = centerY + radius * Math.sin(angle)
            
            return (
              <div
                key={stock.stock_code}
                className={`absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-all duration-300 hover:scale-110 ${
                  stock.stock_code === stockCode ? 'animate-pulse' : ''
                }`}
                style={{
                  left: `${x}px`,
                  top: `${y}px`,
                  width: `${stock.size || 30}px`,
                  height: `${stock.size || 30}px`,
                }}
                title={`${stock.stock_name} (${stock.stock_code})\n섹터: ${translateSectorToKorean(stock.sector)}\n현재가: ${stock.current_price ? stock.current_price.toLocaleString() : 'N/A'}원${stock.market_cap ? `\n시총: ${(stock.market_cap / 1000000000000).toFixed(1)}조원` : ''}`}
              >
                {/* 노드 */}
                <div
                  className={`w-full h-full rounded-full border-2 flex items-center justify-center text-xs font-medium text-white ${
                    stock.stock_code === stockCode 
                      ? 'border-red-500 bg-red-600 shadow-lg shadow-red-500/50' 
                      : 'border-gray-300'
                  }`}
                  style={{
                    backgroundColor: stock.stock_code === stockCode ? '#dc2626' : getSectorColor(translateSectorToKorean(stock.sector)),
                    boxShadow: stock.stock_code === stockCode ? '0 0 20px rgba(220, 38, 38, 0.5)' : 'none'
                  }}
                >
                  {stock.stock_name.substring(0, 2)}
                </div>
                
                {/* 연결선들 (현재 주식에서 다른 주식들로) */}
                {stock.stock_code === stockCode && networkData.map((targetStock, targetIndex) => {
                  if (targetStock.stock_code === stockCode) return null
                  
                  const targetAngle = (targetIndex / networkData.length) * 2 * Math.PI
                  const targetX = centerX + radius * Math.cos(targetAngle)
                  const targetY = centerY + radius * Math.sin(targetAngle)
                  
                  const distance = Math.sqrt((targetX - x) ** 2 + (targetY - y) ** 2)
                  const angleToTarget = Math.atan2(targetY - y, targetX - x)
                  
                  return (
                    <div
                      key={`line-${targetStock.stock_code}`}
                      className="absolute bg-red-400 opacity-30"
                      style={{
                        width: `${distance}px`,
                        height: '2px',
                        left: '50%',
                        top: '50%',
                        transformOrigin: '0 50%',
                        transform: `rotate(${angleToTarget}rad)`,
                        zIndex: -1
                      }}
                    />
                  )
                })}
                
                {/* 같은 섹터끼리 연결선 */}
                {networkData.map((targetStock, targetIndex) => {
                  if (targetStock.stock_code === stock.stock_code || targetStock.sector !== stock.sector) return null
                  
                  const targetAngle = (targetIndex / networkData.length) * 2 * Math.PI
                  const targetX = centerX + radius * Math.cos(targetAngle)
                  const targetY = centerY + radius * Math.sin(targetAngle)
                  
                  const distance = Math.sqrt((targetX - x) ** 2 + (targetY - y) ** 2)
                  const angleToTarget = Math.atan2(targetY - y, targetX - x)
                  
                  return (
                    <div
                      key={`sector-line-${targetStock.stock_code}`}
                      className="absolute opacity-20"
                      style={{
                        width: `${distance}px`,
                        height: '1px',
                        left: '50%',
                        top: '50%',
                        backgroundColor: getSectorColor(translateSectorToKorean(stock.sector)),
                        transformOrigin: '0 50%',
                        transform: `rotate(${angleToTarget}rad)`,
                        zIndex: -2
                      }}
                    />
                  )
                })}
              </div>
            )
          })}
          
          {/* 중앙 현재 주식 표시 */}
          <div
            className="absolute transform -translate-x-1/2 -translate-y-1/2 text-white text-center"
            style={{ left: '400px', top: '250px' }}
          >
            <div className="bg-black/70 px-3 py-2 rounded-lg">
              <div className="text-sm font-bold">현재 종목</div>
              <div className="text-lg">{stockCode}</div>
            </div>
          </div>
        </div>
        
        {/* 범례 */}
        <div className="absolute bottom-4 right-4 bg-black/80 text-white p-3 rounded-lg text-xs">
          <div className="mb-2 font-medium">범례</div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-red-600 rounded-full"></div>
              <span>현재 종목</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-gray-400 rounded-full"></div>
              <span>클러스터 종목</span>
            </div>
            <div>크기: 시가총액</div>
            <div>색상: 섹터</div>
          </div>
        </div>
      </div>
    )
  }

  // 네트워크 그래프 컴포넌트 (실시간 업데이트 안정화)
  const ObsidianNetworkGraph = useCallback(({ data, title, clusterId, axis }: { data: Stock[], title: string, clusterId: number, axis: VisualizationAxis }) => {
    const forceGraphRef = useRef<any>(null)
    const [localAxis, setLocalAxis] = useState<VisualizationAxis>(axis)
    const [stableData, setStableData] = useState<Stock[]>([])
    const [graphData, setGraphData] = useState<{ nodes: NetworkNode[], links: NetworkLink[] }>({ nodes: [], links: [] })
    const dataHashRef = useRef<string>('')
    
    // 데이터 안정화 - 실시간 가격 변동은 무시하고 구조적 데이터만 사용
    useEffect(() => {
      if (data && data.length > 0) {
        // 가격을 제외한 구조적 데이터만 비교하여 변경 감지
        const structuralData = data.map(stock => ({
          stock_code: stock.stock_code,
          stock_name: stock.stock_name,
          sector: stock.sector,
          market_cap: stock.market_cap,
          per: stock.per,
          pbr: stock.pbr,
          roe: stock.roe
        }))
        
        // 구조적 데이터 해시 생성
        const currentHash = JSON.stringify(structuralData)
        
        // 해시가 다를 때만 업데이트
        if (currentHash !== dataHashRef.current) {
          console.log('네트워크 그래프: 구조적 데이터 변경 감지, 업데이트 진행')
          dataHashRef.current = currentHash
          setStableData(data)
        }
      }
    }, [data]) // stableData 의존성 제거하여 순환 방지
    
    // 그래프 데이터 메모이제이션 - 안정화된 데이터 사용
    useEffect(() => {
      if (stableData.length === 0) {
        setGraphData({ nodes: [], links: [] })
        return
      }
      
      console.log('네트워크 그래프 데이터 생성:', { 
        stockCount: stableData.length, 
        clusterId, 
        axis: localAxis
      })
      
      const newGraphData = createNetworkGraphData(stableData, clusterId, stockCode, localAxis)
      setGraphData(newGraphData)
    }, [stableData, clusterId, localAxis]) // createNetworkGraphData, stockCode 의존성 제거

    // 방사형 배치를 위한 물리엔진 설정
    useEffect(() => {
      if (forceGraphRef.current && graphData.nodes.length > 0) {
        console.log('물리 엔진 설정 시작:', graphData.nodes.length, '개 노드')
        const fg = forceGraphRef.current
        
        // 약간의 지연 후 물리 엔진 설정 (ForceGraph2D 초기화 대기)
        const timeoutId = setTimeout(() => {
          // 방사형 배치 유지를 위한 물리 엔진 설정
          fg.d3Force('x', d3.forceX((d: any) => d.targetX || 0).strength(0.8))
          fg.d3Force('y', d3.forceY((d: any) => d.targetY || 0).strength(0.8))
          fg.d3Force('charge').strength(-50)
          fg.d3Force('link').strength(0.01).distance((d: any) => {
            return Math.min(50, Math.max(20, (d.distance || 0) * 0.5))
          })
          fg.d3Force('center', d3.forceCenter(0, 0).strength(0.05))
          
          // 중심 노드 위치 완전 고정
          fg.d3Force('radial', d3.forceRadial((d: any) => {
            if (d.isCurrentStock) return 0
            return d.radius || 100
          }, 0, 0).strength(0.5))
          
          fg.d3ReheatSimulation()
          console.log('물리 엔진 설정 완료')
        }, 300)
        
        return () => clearTimeout(timeoutId)
      }
    }, [graphData.nodes])

    // 축 변경 시 처리 - 부모 컴포넌트 state 변경 제거 (리렌더링 방지)

    // 노드 렌더링
    const nodeCanvasObject = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const radius = node.size / 2 || 5
      const fontSize = Math.max(8, 9 / globalScale)
      
      ctx.fillStyle = node.color || '#999'
      ctx.globalAlpha = 0.8
      ctx.beginPath()
      ctx.arc(node.x || 0, node.y || 0, radius, 0, 2 * Math.PI)
      ctx.fill()
      
      if (node.isCurrentStock) {
        ctx.strokeStyle = '#fff'
        ctx.lineWidth = 3 / globalScale
        ctx.stroke()
      }
      
      ctx.globalAlpha = 1
      ctx.font = `${fontSize}px Sans-Serif`
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = 'white'
      ctx.strokeStyle = 'black'
      ctx.lineWidth = 1.5 / globalScale
      
      const textX = (node.x || 0) + radius + 3
      const textY = node.y || 0
      
      ctx.strokeText(node.name, textX, textY)
      ctx.fillText(node.name, textX, textY)
    }, [])
    
    // 링크 렌더링
    const linkCanvasObject = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const start = link.source
      const end = link.target
      const isCentralLink = start.id === stockCode || end.id === stockCode
      const linkStrength = link.strength || 0.1
      
      if (isCentralLink) {
        const intensity = Math.min(1, linkStrength)
        const red = Math.floor(255 * intensity)
        const blue = Math.floor(255 * (1 - intensity))
        ctx.strokeStyle = `rgba(${red}, 100, ${blue}, ${0.3 + intensity * 0.5})`
        ctx.lineWidth = (0.5 + intensity * 2) / globalScale
      } else {
        ctx.strokeStyle = 'rgba(150, 180, 255, 0.2)'
        ctx.lineWidth = (0.3 + linkStrength) / globalScale
      }
      
      ctx.beginPath()
      ctx.moveTo(start.x, start.y)
      ctx.lineTo(end.x, end.y)
      ctx.stroke()
      ctx.globalAlpha = 1
    }, [stockCode])

    // 데이터가 없는 경우에만 로딩 표시
    if (!data || data.length === 0 || graphData.nodes.length === 0) {
      return (
        <div className="h-[800px] relative bg-slate-950 rounded-lg overflow-hidden flex items-center justify-center">
          <div className="text-white text-center space-y-4">
            <div className="animate-spin w-8 h-8 border-2 border-white border-t-transparent rounded-full mx-auto"></div>
            <div className="text-sm">네트워크 그래프 초기화 중...</div>
            <div className="text-xs text-gray-400">
              {!data || data.length === 0 ? '클러스터 데이터 로딩 중' : `${graphData.nodes.length}개 노드 준비 중`}
            </div>
          </div>
        </div>
      )
    }

    return (
      <div className="h-[800px] relative bg-slate-950 rounded-lg overflow-hidden network-graph-container">
        <div className="absolute top-4 left-4 z-10 space-y-2">
          <div className="bg-black/80 text-white p-3 rounded-lg text-xs space-y-2">
            <div className="font-medium">{title}</div>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => forceGraphRef.current?.zoomToFit(400, 100)} className="h-6 px-2 text-xs">
                <Maximize2 className="w-3 h-3" />
              </Button>
              <Button size="sm" variant="outline" onClick={() => forceGraphRef.current?.d3ReheatSimulation()} className="h-6 px-2 text-xs">
                <RotateCcw className="w-3 h-3" />
              </Button>
            </div>
          </div>
          
          <div className="bg-black/80 text-white p-3 rounded-lg text-xs space-y-2">
            <div className="font-medium flex items-center gap-2">
              <Settings className="w-3 h-3" />
              거리 기준
            </div>
            <Select value={localAxis} onValueChange={(value: VisualizationAxis) => setLocalAxis(value)}>
              <SelectTrigger className="w-full h-7 text-xs bg-white/10 border-white/20 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="per_pbr">PER vs PBR</SelectItem>
                <SelectItem value="marketcap_roe">시가총액 vs ROE</SelectItem>
                <SelectItem value="per_roe">PER vs ROE</SelectItem>
                <SelectItem value="pbr_roe">PBR vs ROE</SelectItem>
              </SelectContent>
            </Select>
            <div className="text-xs text-gray-400">
              선택한 지표의 차이에 따라<br/>네트워크 상의 거리가 결정됩니다
            </div>
            <div className="text-xs text-green-400 mt-1">
              🎯 현재 기준: {axisOptions[localAxis].x} vs {axisOptions[localAxis].y}
            </div>
          </div>
          
          <div className="bg-black/80 text-white p-3 rounded-lg text-xs space-y-2">
            <div className="font-medium">범례</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-red-400 rounded-full border-2 border-white"></div>
                <span>현재 종목 (중심)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full" style={{background: 'linear-gradient(90deg, #ff6666 0%, #6666ff 100%)', width: '12px', height: '2px'}}></div>
                <span>거리별 연결 (빨강=가까움)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-0.5 h-3 bg-blue-400/30" style={{width: '0.5px'}}></div>
                <span>유사 기업 연결</span>
              </div>
              <div className="text-xs text-yellow-300 mt-1">
                📏 중심에서 거리 = 지표 차이
              </div>
              <div className="text-xs text-green-300">
                🎯 방사형 배치 (가까운 순)
              </div>
            </div>
          </div>
        </div>
        
        <ForceGraph2D
          key={`network-${clusterId}-${localAxis}-${graphData.nodes.length}`}
          ref={forceGraphRef}
          graphData={graphData}
          width={1400}
          height={800}
          warmupTicks={120}
          cooldownTicks={60}
          nodeCanvasObject={nodeCanvasObject}
          linkCanvasObject={linkCanvasObject}
          nodeId="id"
          backgroundColor="rgb(15, 23, 42)"
          enableNodeDrag={false}
          enableZoomInteraction={true}
          enablePanInteraction={true}
          nodeLabel={() => ''}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.4}
          onEngineStop={() => {
            console.log('네트워크 그래프 물리 시뮬레이션 완료')
            setTimeout(() => {
              forceGraphRef.current?.zoomToFit(400, 100)
            }, 500)
          }}
        />
      </div>
    )
  }, [stockCode])

  useEffect(() => {
    const loadClusterData = async () => {
      setLoading(true)
      setError("")
      
      try {
        // 1. 주식의 클러스터 정보 로드
        const clusterInfo = await stocksApi.getStockClusterInfo(stockCode)
        setStockClusterInfo(clusterInfo)
        
        // 2. 각 클러스터 타입별 유사 주식 로드
        const [spectralSimilar, agglomerativeSimilar] = await Promise.all([
          stocksApi.getSimilarStocksByCluster(stockCode, 'spectral', 15).catch(() => null),
          stocksApi.getSimilarStocksByCluster(stockCode, 'agglomerative', 15).catch(() => null)
        ])
        
        setSpectralSimilarStocks(spectralSimilar)
        setAgglomerativeSimilarStocks(agglomerativeSimilar)
        
        // 3. 클러스터별 전체 주식 데이터 로드
        if (clusterInfo.clusters.spectral) {
          const spectralCluster = await stocksApi.getClusterStocks('spectral', clusterInfo.clusters.spectral.cluster_id).catch(() => null)
          setSpectralClusterData(spectralCluster)
        }
        
        if (clusterInfo.clusters.agglomerative) {
          const agglomerativeCluster = await stocksApi.getClusterStocks('agglomerative', clusterInfo.clusters.agglomerative.cluster_id).catch(() => null)
          setAgglomerativeClusterData(agglomerativeCluster)
        }
        
      } catch (err) {
        console.error('클러스터 데이터 로드 실패:', err)
        setError('클러스터 데이터를 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    if (stockCode) {
      loadClusterData()
    }
  }, [stockCode])

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-96 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <Card>
        <CardContent className="pt-6">
          <div className="text-center text-red-500">{error}</div>
        </CardContent>
      </Card>
    )
  }

  if (!stockClusterInfo) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>주식 클러스터 분석</CardTitle>
          <CardDescription>
            머신러닝 기반 클러스터링 분석을 통해 유사한 특성을 가진 종목들을 찾아드립니다.
          </CardDescription>
        </CardHeader>
        <CardContent className="py-12">
          <div className="text-center text-muted-foreground">
            <div className="mb-4">
              <svg className="w-16 h-16 mx-auto opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium mb-2">클러스터 분석 데이터 준비 중</h3>
            <p className="text-sm max-w-md mx-auto">
              해당 종목의 클러스터링 분석이 진행 중이거나 데이터가 준비되지 않았습니다.<br/>
              분석이 완료되면 유사한 투자 특성을 가진 종목들을 그룹별로 시각화해드립니다.
            </p>
          </div>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* 클러스터 정보 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {stockClusterInfo.clusters.spectral && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Badge variant="outline">재무제표</Badge>
                재무제표 기반 클러스터
              </CardTitle>
              <CardDescription>
                {stockClusterInfo.clusters.spectral.cluster_name}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">클러스터 ID</span>
                  <span className="text-sm font-medium">{stockClusterInfo.clusters.spectral.cluster_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">주요 섹터</span>
                  <span className="text-sm font-medium">
                    {stockClusterInfo.clusters.spectral.cluster_analysis.dominant_sectors.slice(0, 2).map(translateSectorToKorean).join(', ')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">종목 수</span>
                  <span className="text-sm font-medium">{stockClusterInfo.clusters.spectral.cluster_analysis.stock_count}개</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {stockClusterInfo.clusters.agglomerative && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Badge variant="outline">수익 변동성</Badge>
                수익 변동성 기반 클러스터
              </CardTitle>
              <CardDescription>
                {stockClusterInfo.clusters.agglomerative.cluster_name}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">클러스터 ID</span>
                  <span className="text-sm font-medium">{stockClusterInfo.clusters.agglomerative.cluster_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">주요 섹터</span>
                  <span className="text-sm font-medium">
                    {stockClusterInfo.clusters.agglomerative.cluster_analysis.dominant_sectors.slice(0, 2).map(translateSectorToKorean).join(', ')}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-muted-foreground">종목 수</span>
                  <span className="text-sm font-medium">{stockClusterInfo.clusters.agglomerative.cluster_analysis.stock_count}개</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* 클러스터별 시각화 탭 */}
      <Tabs value={selectedTab} onValueChange={(value) => setSelectedTab(value as 'spectral' | 'agglomerative')}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="spectral" disabled={!stockClusterInfo.clusters.spectral}>
            재무제표 기반
          </TabsTrigger>
          <TabsTrigger value="agglomerative" disabled={!stockClusterInfo.clusters.agglomerative}>
            수익 변동성 기반
          </TabsTrigger>
        </TabsList>

        {/* Spectral 클러스터 */}
        <TabsContent value="spectral" className="space-y-6">
          {spectralClusterData && spectralSimilarStocks && (
            <>
              {/* 클러스터 분석 정보 */}
              <Card>
                <CardHeader>
                  <CardTitle>클러스터 분석 (재무제표 기반)</CardTitle>
                  <CardDescription>
                    {spectralClusterData.cluster_analysis.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {spectralClusterData.cluster_analysis.stock_count}
                      </div>
                      <div className="text-sm text-muted-foreground">총 종목 수</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {spectralClusterData.cluster_analysis.avg_market_cap ? 
                          `${(spectralClusterData.cluster_analysis.avg_market_cap / 1000000000000).toFixed(1)}조` : 'N/A'}
                      </div>
                      <div className="text-sm text-muted-foreground">평균 시가총액</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {spectralClusterData.cluster_analysis.avg_per ? 
                          spectralClusterData.cluster_analysis.avg_per.toFixed(1) : 'N/A'}
                      </div>
                      <div className="text-sm text-muted-foreground">평균 PER</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 클러스터 시각화 */}
              <Card>
                <CardHeader>
                  <CardTitle>클러스터 시각화 (재무제표 기반)</CardTitle>
                  <CardDescription>
                    재무제표 지표 기반 클러스터 분포. 버블 크기는 시가총액, 색상은 섹터를 나타냅니다.
                  </CardDescription>
                  <div className="flex flex-wrap gap-4 mt-4">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium">뷰 모드:</label>
                      <Select value={viewMode} onValueChange={(value: 'bubble' | 'network') => setViewMode(value)}>
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="bubble">📊 버블 차트</SelectItem>
                          <SelectItem value="network">🕸️ 네트워크 뷰</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {viewMode === 'bubble' && (
                      <>
                        <div className="flex items-center gap-2">
                          <label className="text-sm font-medium">축 선택:</label>
                          <Select value={visualizationAxis} onValueChange={(value: VisualizationAxis) => setVisualizationAxis(value)}>
                            <SelectTrigger className="w-40">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="per_pbr">PER vs PBR</SelectItem>
                              <SelectItem value="marketcap_roe">시가총액 vs ROE</SelectItem>
                              <SelectItem value="per_roe">PER vs ROE</SelectItem>
                              <SelectItem value="pbr_roe">PBR vs ROE</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex items-center gap-2">
                          <label className="text-sm font-medium">섹터 필터:</label>
                          <Select value={selectedSector} onValueChange={setSelectedSector}>
                            <SelectTrigger className="w-40">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">전체</SelectItem>
                              {Array.from(new Set(spectralClusterData.stocks.map(s => s.sector))).map(sector => (
                                <SelectItem key={sector} value={sector}>
                                  {translateSectorToKorean(sector)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {viewMode === 'network' ? (
                    <div className="relative">
                      <ObsidianNetworkGraph 
                        data={spectralClusterData.stocks} 
                        title="재무제표 기반 클러스터" 
                        clusterId={stockClusterInfo.clusters.spectral!.cluster_id}
                        axis={visualizationAxis}
                      />
                    </div>
                  ) : (
                    <>
                      <ChartContainer
                        config={{
                          cluster: { label: "클러스터", color: "hsl(var(--chart-1))" },
                        }}
                        className="h-[500px]"
                      >
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart 
                            data={filterBySector(transformToVisualizationData(spectralClusterData.stocks, stockClusterInfo.clusters.spectral!.cluster_id, stockCode))} 
                            margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis 
                              type="number" 
                              dataKey="x" 
                              name={axisOptions[visualizationAxis].x}
                              label={{ value: axisOptions[visualizationAxis].x, position: 'insideBottom', offset: -5 }}
                              domain={['dataMin', 'dataMax']}
                            />
                            <YAxis 
                              type="number" 
                              dataKey="y" 
                              name={axisOptions[visualizationAxis].y}
                              label={{ value: axisOptions[visualizationAxis].y, angle: -90, position: 'insideLeft' }}
                              domain={['dataMin', 'dataMax']}
                            />
                            
                            {/* 평균값 가이드라인 */}
                            {(() => {
                              const data = filterBySector(transformToVisualizationData(spectralClusterData.stocks, stockClusterInfo.clusters.spectral!.cluster_id, stockCode))
                              const { avgX, avgY } = calculateAverages(data)
                              return (
                                <>
                                  <ReferenceLine x={avgX} stroke="#666" strokeDasharray="5 5" strokeOpacity={0.6} />
                                  <ReferenceLine y={avgY} stroke="#666" strokeDasharray="5 5" strokeOpacity={0.6} />
                                </>
                              )
                            })()}
                            
                            <ChartTooltip
                              content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                  const data = payload[0].payload as ClusterVisualizationData
                                  return (
                                    <div className="bg-background border rounded-lg p-3 shadow-lg max-w-xs">
                                      <div className="flex items-center gap-2 mb-2">
                                        <div 
                                          className="w-3 h-3 rounded-full"
                                          style={{ backgroundColor: data.sectorColor }}
                                        />
                                        <p className="font-semibold text-sm">{data.stock_name}</p>
                                      </div>
                                      <p className="text-xs text-muted-foreground mb-1">{data.stock_code}</p>
                                      <p className="text-xs">섹터: {translateSectorToKorean(data.sector)}</p>
                                      {data.current_price && (
                                        <p className="text-xs">현재가: {data.current_price.toLocaleString()}원</p>
                                      )}
                                      {data.market_cap && (
                                        <p className="text-xs">시가총액: {(data.market_cap / 1000000000000).toFixed(1)}조원</p>
                                      )}
                                      <div className="grid grid-cols-2 gap-1 mt-1 text-xs">
                                        {data.per && <p>PER: {data.per.toFixed(1)}</p>}
                                        {data.pbr && <p>PBR: {data.pbr.toFixed(1)}</p>}
                                        {data.roe && <p>ROE: {data.roe.toFixed(1)}%</p>}
                                      </div>
                                    </div>
                                  )
                                }
                                return null
                              }}
                            />
                            
                            <Scatter dataKey="y" name="종목">
                              {filterBySector(transformToVisualizationData(spectralClusterData.stocks, stockClusterInfo.clusters.spectral!.cluster_id, stockCode)).map((entry, index) => (
                                <Cell 
                                  key={`cell-${index}`}
                                  fill={entry.sectorColor}
                                  stroke={entry.isCurrentStock ? "#dc2626" : entry.sectorColor}
                                  strokeWidth={entry.isCurrentStock ? 4 : 1}
                                  fillOpacity={entry.isCurrentStock ? 1 : 0.7}
                                  r={Math.max(4, Math.min(entry.size, 25))} // 크기 제한 추가
                                  className={entry.isCurrentStock ? 'animate-pulse' : ''}
                                />
                              ))}
                            </Scatter>
                            
                            {/* 섹터별 범례 */}
                            <Legend 
                              content={() => {
                                const data = filterBySector(transformToVisualizationData(spectralClusterData.stocks, stockClusterInfo.clusters.spectral!.cluster_id, stockCode))
                                const sectors = Array.from(new Set(data.map(d => d.sector)))
                                return (
                                  <div className="flex flex-wrap gap-3 justify-center mt-4">
                                    {sectors.map(sector => (
                                      <div key={sector} className="flex items-center gap-1">
                                        <div 
                                          className="w-3 h-3 rounded-full" 
                                          style={{ backgroundColor: getSectorColor(translateSectorToKorean(sector)) }}
                                        />
                                        <span className="text-xs">{translateSectorToKorean(sector)}</span>
                                      </div>
                                    ))}
                                  </div>
                                )
                              }}
                            />
                          </ScatterChart>
                        </ResponsiveContainer>
                      </ChartContainer>
                      
                      {/* 차트 설명 */}
                      <div className="mt-4 p-3 bg-muted/50 rounded-lg">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                          <div>
                            <strong>버블 크기:</strong> 시가총액 (클수록 대형주)
                          </div>
                          <div>
                            <strong>색상:</strong> 섹터별 구분
                          </div>
                          <div>
                            <strong>빨간 테두리:</strong> 현재 선택된 종목
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-muted-foreground">
                          점선: 클러스터 평균값 | 버블 클릭: 상세 정보 | 필터: 섹터별 분석
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* 유사 종목 목록 */}
              <Card>
                <CardHeader>
                  <CardTitle>유사 종목 (재무제표 기반)</CardTitle>
                  <CardDescription>
                    동일한 재무제표 기반 클러스터에 속하는 종목들입니다.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3">
                    {spectralSimilarStocks.similar_stocks.slice(0, 10).map((stock, index) => (
                      <div key={stock.stock_code} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-all duration-200 hover:shadow-md">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-6 h-6 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                            {index + 1}
                          </div>
                          <div 
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: getSectorColor(translateSectorToKorean(stock.sector)) }}
                          />
                          <div>
                            <div className="font-medium">{stock.stock_name}</div>
                            <div className="text-sm text-muted-foreground">
                              {stock.stock_code} • {translateSectorToKorean(stock.sector)}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {stock.current_price ? stock.current_price.toLocaleString() : 'N/A'}원
                          </div>
                          <div className="text-xs text-muted-foreground flex gap-2">
                            <span>PER: {stock.per ? stock.per.toFixed(1) : 'N/A'}</span>
                            <span>PBR: {stock.pbr ? stock.pbr.toFixed(1) : 'N/A'}</span>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            시총: {stock.market_cap ? `${(stock.market_cap / 1000000000000).toFixed(1)}조` : 'N/A'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Agglomerative 클러스터 */}
        <TabsContent value="agglomerative" className="space-y-6">
          {agglomerativeClusterData && agglomerativeSimilarStocks && (
            <>
              {/* 클러스터 분석 정보 */}
              <Card>
                <CardHeader>
                  <CardTitle>클러스터 분석 (수익 변동성 기반)</CardTitle>
                  <CardDescription>
                    {agglomerativeClusterData.cluster_analysis.description}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-blue-600">
                        {agglomerativeClusterData.cluster_analysis.stock_count}
                      </div>
                      <div className="text-sm text-muted-foreground">총 종목 수</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-green-600">
                        {agglomerativeClusterData.cluster_analysis.avg_market_cap ? 
                          `${(agglomerativeClusterData.cluster_analysis.avg_market_cap / 1000000000000).toFixed(1)}조` : 'N/A'}
                      </div>
                      <div className="text-sm text-muted-foreground">평균 시가총액</div>
                    </div>
                    <div className="text-center p-4 border rounded-lg">
                      <div className="text-2xl font-bold text-purple-600">
                        {agglomerativeClusterData.cluster_analysis.avg_per ? 
                          agglomerativeClusterData.cluster_analysis.avg_per.toFixed(1) : 'N/A'}
                      </div>
                      <div className="text-sm text-muted-foreground">평균 PER</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 클러스터 시각화 */}
              <Card>
                <CardHeader>
                  <CardTitle>클러스터 시각화 (수익 변동성 기반)</CardTitle>
                  <CardDescription>
                    수익 변동성 지표 기반 클러스터 분포. 버블 크기는 시가총액, 색상은 섹터를 나타냅니다.
                  </CardDescription>
                  <div className="flex flex-wrap gap-4 mt-4">
                    <div className="flex items-center gap-2">
                      <label className="text-sm font-medium">뷰 모드:</label>
                      <Select value={viewMode} onValueChange={(value: 'bubble' | 'network') => setViewMode(value)}>
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="bubble">📊 버블 차트</SelectItem>
                          <SelectItem value="network">🕸️ 네트워크 뷰</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    {viewMode === 'bubble' && (
                      <>
                        <div className="flex items-center gap-2">
                          <label className="text-sm font-medium">축 선택:</label>
                          <Select value={visualizationAxis} onValueChange={(value: VisualizationAxis) => setVisualizationAxis(value)}>
                            <SelectTrigger className="w-40">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="per_pbr">PER vs PBR</SelectItem>
                              <SelectItem value="marketcap_roe">시가총액 vs ROE</SelectItem>
                              <SelectItem value="per_roe">PER vs ROE</SelectItem>
                              <SelectItem value="pbr_roe">PBR vs ROE</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex items-center gap-2">
                          <label className="text-sm font-medium">섹터 필터:</label>
                          <Select value={selectedSector} onValueChange={setSelectedSector}>
                            <SelectTrigger className="w-40">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="all">전체</SelectItem>
                              {Array.from(new Set(agglomerativeClusterData.stocks.map(s => s.sector))).map(sector => (
                                <SelectItem key={sector} value={sector}>
                                  {translateSectorToKorean(sector)}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                      </>
                    )}
                  </div>
                </CardHeader>
                <CardContent>
                  {viewMode === 'network' ? (
                    <div className="relative">
                      <ObsidianNetworkGraph 
                        data={agglomerativeClusterData.stocks} 
                        title="수익 변동성 기반 클러스터" 
                        clusterId={stockClusterInfo.clusters.agglomerative!.cluster_id}
                        axis={visualizationAxis}
                      />
                    </div>
                  ) : (
                    <>
                      <ChartContainer
                        config={{
                          cluster: { label: "클러스터", color: "hsl(var(--chart-2))" },
                        }}
                        className="h-[500px]"
                      >
                        <ResponsiveContainer width="100%" height="100%">
                          <ScatterChart 
                            data={filterBySector(transformToVisualizationData(agglomerativeClusterData.stocks, stockClusterInfo.clusters.agglomerative!.cluster_id, stockCode))} 
                            margin={{ top: 20, right: 30, bottom: 60, left: 60 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                            <XAxis 
                              type="number" 
                              dataKey="x" 
                              name={axisOptions[visualizationAxis].x}
                              label={{ value: axisOptions[visualizationAxis].x, position: 'insideBottom', offset: -5 }}
                              domain={['dataMin', 'dataMax']}
                            />
                            <YAxis 
                              type="number" 
                              dataKey="y" 
                              name={axisOptions[visualizationAxis].y}
                              label={{ value: axisOptions[visualizationAxis].y, angle: -90, position: 'insideLeft' }}
                              domain={['dataMin', 'dataMax']}
                            />
                            
                            {/* 평균값 가이드라인 */}
                            {(() => {
                              const data = filterBySector(transformToVisualizationData(agglomerativeClusterData.stocks, stockClusterInfo.clusters.agglomerative!.cluster_id, stockCode))
                              const { avgX, avgY } = calculateAverages(data)
                              return (
                                <>
                                  <ReferenceLine x={avgX} stroke="#666" strokeDasharray="5 5" strokeOpacity={0.6} />
                                  <ReferenceLine y={avgY} stroke="#666" strokeDasharray="5 5" strokeOpacity={0.6} />
                                </>
                              )
                            })()}
                            
                            <ChartTooltip
                              content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                  const data = payload[0].payload as ClusterVisualizationData
                                  return (
                                    <div className="bg-background border rounded-lg p-3 shadow-lg max-w-xs">
                                      <div className="flex items-center gap-2 mb-2">
                                        <div 
                                          className="w-3 h-3 rounded-full"
                                          style={{ backgroundColor: data.sectorColor }}
                                        />
                                        <p className="font-semibold text-sm">{data.stock_name}</p>
                                      </div>
                                      <p className="text-xs text-muted-foreground mb-1">{data.stock_code}</p>
                                      <p className="text-xs">섹터: {translateSectorToKorean(data.sector)}</p>
                                      {data.current_price && (
                                        <p className="text-xs">현재가: {data.current_price.toLocaleString()}원</p>
                                      )}
                                      {data.market_cap && (
                                        <p className="text-xs">시가총액: {(data.market_cap / 1000000000000).toFixed(1)}조원</p>
                                      )}
                                      <div className="grid grid-cols-2 gap-1 mt-1 text-xs">
                                        {data.per && <p>PER: {data.per.toFixed(1)}</p>}
                                        {data.pbr && <p>PBR: {data.pbr.toFixed(1)}</p>}
                                        {data.roe && <p>ROE: {data.roe.toFixed(1)}%</p>}
                                      </div>
                                    </div>
                                  )
                                }
                                return null
                              }}
                            />
                            
                            <Scatter dataKey="y" name="종목">
                              {filterBySector(transformToVisualizationData(agglomerativeClusterData.stocks, stockClusterInfo.clusters.agglomerative!.cluster_id, stockCode)).map((entry, index) => (
                                <Cell 
                                  key={`cell-${index}`}
                                  fill={entry.sectorColor}
                                  stroke={entry.isCurrentStock ? "#dc2626" : entry.sectorColor}
                                  strokeWidth={entry.isCurrentStock ? 4 : 1}
                                  fillOpacity={entry.isCurrentStock ? 1 : 0.7}
                                  r={Math.max(4, Math.min(entry.size, 25))} // 크기 제한 추가
                                  className={entry.isCurrentStock ? 'animate-pulse' : ''}
                                />
                              ))}
                            </Scatter>
                            
                            {/* 섹터별 범례 */}
                            <Legend 
                              content={() => {
                                const data = filterBySector(transformToVisualizationData(agglomerativeClusterData.stocks, stockClusterInfo.clusters.agglomerative!.cluster_id, stockCode))
                                const sectors = Array.from(new Set(data.map(d => d.sector)))
                                return (
                                  <div className="flex flex-wrap gap-3 justify-center mt-4">
                                    {sectors.map(sector => (
                                      <div key={sector} className="flex items-center gap-1">
                                        <div 
                                          className="w-3 h-3 rounded-full" 
                                          style={{ backgroundColor: getSectorColor(translateSectorToKorean(sector)) }}
                                        />
                                        <span className="text-xs">{translateSectorToKorean(sector)}</span>
                                      </div>
                                    ))}
                                  </div>
                                )
                              }}
                            />
                          </ScatterChart>
                        </ResponsiveContainer>
                      </ChartContainer>
                      
                      {/* 차트 설명 */}
                      <div className="mt-4 p-3 bg-muted/50 rounded-lg">
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
                          <div>
                            <strong>버블 크기:</strong> 시가총액 (클수록 대형주)
                          </div>
                          <div>
                            <strong>색상:</strong> 섹터별 구분
                          </div>
                          <div>
                            <strong>빨간 테두리:</strong> 현재 선택된 종목
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-muted-foreground">
                          점선: 클러스터 평균값 | 버블 클릭: 상세 정보 | 필터: 섹터별 분석
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>

              {/* 유사 종목 목록 */}
              <Card>
                <CardHeader>
                  <CardTitle>유사 종목 (수익 변동성 기반)</CardTitle>
                  <CardDescription>
                    동일한 수익 변동성 기반 클러스터에 속하는 종목들입니다.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid gap-3">
                    {agglomerativeSimilarStocks.similar_stocks.slice(0, 10).map((stock, index) => (
                      <div key={stock.stock_code} className="flex items-center justify-between p-3 border rounded-lg hover:bg-muted/50 transition-all duration-200 hover:shadow-md">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center justify-center w-6 h-6 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                            {index + 1}
                          </div>
                          <div 
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: getSectorColor(translateSectorToKorean(stock.sector)) }}
                          />
                          <div>
                            <div className="font-medium">{stock.stock_name}</div>
                            <div className="text-sm text-muted-foreground">
                              {stock.stock_code} • {translateSectorToKorean(stock.sector)}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-medium">
                            {stock.current_price ? stock.current_price.toLocaleString() : 'N/A'}원
                          </div>
                          <div className="text-xs text-muted-foreground flex gap-2">
                            <span>PER: {stock.per ? stock.per.toFixed(1) : 'N/A'}</span>
                            <span>PBR: {stock.pbr ? stock.pbr.toFixed(1) : 'N/A'}</span>
                          </div>
                          <div className="text-xs text-muted-foreground">
                            시총: {stock.market_cap ? `${(stock.market_cap / 1000000000000).toFixed(1)}조` : 'N/A'}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
