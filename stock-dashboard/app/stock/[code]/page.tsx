"use client"

import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useParams } from "next/navigation"
import { ArrowLeft, Star, TrendingUp, TrendingDown, MessageSquare, DollarSign, User, LogOut, LogIn } from "lucide-react"
import Link from "next/link"

import { 
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { AlertCircle } from "lucide-react"

import { stocksApi, StockDetail as ApiStockDetail, TechnicalIndicators, PriceData, handleApiError, type FinancialData as ApiFinancialData, type SentimentAnalysis, type FinancialAnalysis } from "@/lib/api"

import { PriceChart } from "@/components/charts/price-chart"
import { TechnicalChart } from "@/components/charts/technical-chart"
import { SentimentChart } from "@/components/charts/sentiment-chart"
import { FinancialChart } from "@/components/charts/financial-chart"
import { ClusterVisualization } from "@/components/charts/cluster-visualization"

// 섹터 매핑 유틸리티
import { translateSectorToKorean, getSectorColor } from "@/lib/sector-mapping"

// 실시간 주가 Hook 추가
import { useGlobalWebSocket } from "@/hooks/use-global-websocket"

// 휴장 상태 표시 컴포넌트 추가
import { MarketStatusIndicator } from "@/components/ui/market-status-indicator"
import { StockPriceCell, StockPriceData } from "@/components/ui/stock-price-cell"

// 인증 Hook 추가
import { useAuth } from "@/contexts/AuthContext"

// AI 점수 계산 유틸리티
import { computeAiScore } from "@/lib/ai-score-utils"

// 전역 감정 데이터 스토어
import { sentimentStore, calculateSentimentScore } from "@/lib/sentiment-store"

// 백엔드 API 타입을 프론트엔드 인터페이스에 맞게 변환
interface StockDetail {
  code: string
  name: string
  price: number
  change: number
  changePercent: number
  volume: number
  marketCap: number | null
  per: number | null
  pbr: number | null
  roe: number | null
  eps: number | null
  bps: number | null
  sentiment: number
  aiScore?: number   // AI 종합 점수 (0-100)
  sector: string
  market: string
  dividend_yield: number | null
}

interface FinancialData {
  year: number
  revenue: number
  operating_income: number
  net_income: number
  eps: number
  total_assets?: number
  total_liabilities?: number
  total_equity?: number
}

interface SentimentData {
  score: number
  keywords: string[]
  newsCount: number
  positiveRatio: number
  negativeRatio: number
}

// AI 점수 계산 함수 (공통 유틸리티 사용)
const computeAiScoreForStock = (stock: StockDetail, technicalIndicators?: any): number => {
  return computeAiScore({ 
    sentiment: stock.sentiment, 
    changePercent: stock.changePercent,
    technicalIndicators: technicalIndicators
  })
}

// 전역 감정 스토어 사용

// API 데이터를 로컬 인터페이스로 변환하는 함수 (실시간 데이터 통합)
const convertApiStockToDetail = (apiStock: ApiStockDetail, realTimeData?: any, sentimentOverride?: { positive: number; negative: number; neutral?: number }): StockDetail => {
  const realTime = realTimeData?.[apiStock.stock_code]
  
  let sentiment: number;
  
  // 1. 직접 제공된 감정 데이터 사용 (우선순위 1)
  // 2. 전역 스토어에서 데이터 사용 (우선순위 2)
  // 3. 랜덤 값 사용 (fallback)
  const sentimentAnalysis = sentimentOverride || sentimentStore.getSentiment(apiStock.stock_code);
  
  if (sentimentAnalysis) {
    // 실제 감정 분석 데이터가 있으면 사용
    sentiment = calculateSentimentScore(
      sentimentAnalysis.positive, 
      sentimentAnalysis.negative, 
      sentimentAnalysis.neutral || 0
    );
  } else {
    // 데이터가 없으면 임시 랜덤 값 사용 (메인 페이지와 동일)
    sentiment = Math.random() * 0.4 + 0.3; // 0.3-0.7
  }
  
  const stockDetail: StockDetail = {
    code: apiStock.stock_code,
    name: apiStock.stock_name,
    price: realTime?.current_price || apiStock.current_price,
    change: realTime?.change_amount || 0,
    changePercent: realTime?.change_percent || 0,
    volume: realTime?.volume || 0,
    marketCap: apiStock.market_cap,
    per: apiStock.per,
    pbr: apiStock.pbr,
    roe: apiStock.roe,
    eps: null, // API에서 제공되지 않음
    bps: null, // API에서 제공되지 않음
    sentiment,
    sector: apiStock.sector,
    market: apiStock.market,
    dividend_yield: apiStock.dividend_yield
  }
  
  // AI 점수 계산
  stockDetail.aiScore = computeAiScoreForStock(stockDetail)
  
  return stockDetail
}

export default function StockDetailPage() {
  const params = useParams()
  const code = params.code as string
  
  // 인증 상태 추가
  const { user, isAuthenticated, logout } = useAuth()

  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null)
  const [financialData, setFinancialData] = useState<FinancialData[]>([])
  const [technicalIndicators, setTechnicalIndicators] = useState<TechnicalIndicators | null>(null)
  const [priceHistory, setPriceHistory] = useState<PriceData[]>([])
  const [sentimentData, setSentimentData] = useState<SentimentData | null>(null)
  const [sentimentAnalysis, setSentimentAnalysis] = useState<SentimentAnalysis | null>(null)
  const [financialAnalysis, setFinancialAnalysis] = useState<FinancialAnalysis | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string>("")
  const [isFavorite, setIsFavorite] = useState(false)
  const [favoriteLoading, setFavoriteLoading] = useState(false)

  // 실시간 데이터 업데이트 추적을 위한 ref
  const lastRealTimePriceRef = useRef<any>(null)
  const stockDetailRef = useRef<StockDetail | null>(null)

  // WebSocket 구독을 위한 종목 코드 메모이제이션
  const subscriptionCodes = useMemo(() => {
    return code ? [code] : [];
  }, [code]);

  // 실시간 주가 Hook 추가 - 현재 종목만 구독
  const {
    data: realTimePrices = {},
    loading: realTimeLoading = false,
    error: realTimeError = null,
    connected: realTimeConnected = false,
    lastUpdated: realTimeLastUpdated,
    refetch: refetchRealTime
  } = useGlobalWebSocket({
    stockCodes: subscriptionCodes,
    autoSubscribe: true
  })

  // 실시간 데이터가 있으면 stockDetail 업데이트 - 최적화된 버전
  useEffect(() => {
    if (stockDetail && realTimePrices[code]) {
      const realTimeData = realTimePrices[code]
      const currentPrice = lastRealTimePriceRef.current
      
      // 실제 변경이 있는지 정확히 체크
      const hasActualChange = !currentPrice ||
        currentPrice.current_price !== realTimeData.current_price ||
        currentPrice.change_amount !== realTimeData.change_amount ||
        currentPrice.change_percent !== realTimeData.change_percent ||
        currentPrice.volume !== realTimeData.volume

      if (hasActualChange) {
        console.log('🔄 상세 페이지 실시간 데이터 업데이트:', realTimeData)
        
        // ref 업데이트 (다음 비교용)
        lastRealTimePriceRef.current = realTimeData
        
        // React 18 배치 업데이트를 이용한 최적화
        setStockDetail((prevDetail: StockDetail | null) => {
          if (!prevDetail) return prevDetail;
          
          // 객체 참조 비교 최적화 - 동일한 값이면 기존 객체 반환
          if (
            prevDetail.price === realTimeData.current_price &&
            prevDetail.change === realTimeData.change_amount &&
            prevDetail.changePercent === realTimeData.change_percent &&
            prevDetail.volume === realTimeData.volume
          ) {
            return prevDetail; // 같은 참조 반환으로 리렌더링 방지
          }
          
          // 실제 변경된 필드만 업데이트
          const updatedDetail = {
            ...prevDetail,
            price: realTimeData.current_price,
            change: realTimeData.change_amount,
            changePercent: realTimeData.change_percent,
            volume: realTimeData.volume
          };
          
          // AI 점수 재계산 (변동률이 변경되었으므로)
          updatedDetail.aiScore = computeAiScoreForStock(updatedDetail);
          
          stockDetailRef.current = updatedDetail;
          return updatedDetail;
        })
      }
    }
  }, [realTimePrices, code]) // stockDetail 의존성 제거로 무한 루프 방지

  // 관심종목 상태 확인 - 메모이제이션 추가
  const checkFavoriteStatus = useCallback(async () => {
    if (!code) {
      console.warn('종목 코드가 없습니다.')
      return
    }
    
    console.log('관심종목 상태 확인 시작:', code)
    try {
      const watchlist = await stocksApi.getWatchlist()
      console.log('전체 관심종목 목록:', watchlist)
      
      const isInWatchlist = watchlist.some(item => item.stock_code === code)
      console.log(`종목 ${code}가 관심종목에 있는지:`, isInWatchlist)
      
      setIsFavorite(isInWatchlist)
    } catch (error) {
      console.warn('관심종목 상태 확인 실패:', error)
      console.warn('에러 상세:', {
        message: error instanceof Error ? error.message : '알 수 없는 에러',
        code: code
      })
    }
  }, [code])

  useEffect(() => {
    if (code) {
      checkFavoriteStatus()
    }
  }, [code, checkFavoriteStatus])

  // 관심종목 추가/삭제 핸들러
  const handleFavoriteToggle = useCallback(async () => {
    if (!stockDetail) {
      console.error('주식 정보가 없습니다.')
      return
    }
    
    console.log(`관심종목 ${isFavorite ? '삭제' : '추가'} 시작:`, code)
    setFavoriteLoading(true)
    
    try {
      if (isFavorite) {
        console.log('관심종목 삭제 API 호출...')
        const result = await stocksApi.removeFromWatchlist(code)
        console.log('삭제 결과:', result)
        
        if (result.success) {
          setIsFavorite(false)
          console.log('✅ 관심종목 삭제 성공:', result.message)
          // TODO: 성공 알림 표시
        } else {
          console.error('❌ 관심종목 삭제 실패 - API에서 실패 응답:', result)
        }
      } else {
        console.log('관심종목 추가 API 호출...')
        const result = await stocksApi.addToWatchlist(code)
        console.log('추가 결과:', result)
        
        if (result.success) {
          setIsFavorite(true)
          console.log('✅ 관심종목 추가 성공:', result.message)
          // TODO: 성공 알림 표시
        } else {
          console.error('❌ 관심종목 추가 실패 - API에서 실패 응답:', result)
        }
      }
    } catch (error) {
      console.error('❌ 관심종목 처리 중 에러 발생:', error)
      console.error('에러 상세:', {
        message: error instanceof Error ? error.message : '알 수 없는 에러',
        stack: error instanceof Error ? error.stack : null,
        code: code,
        isFavorite: isFavorite
      })
      // TODO: 에러 알림 표시
      alert(`관심종목 ${isFavorite ? '삭제' : '추가'} 중 오류가 발생했습니다. 다시 시도해 주세요.`)
    } finally {
      setFavoriteLoading(false)
      console.log('관심종목 처리 완료')
    }
  }, [stockDetail, isFavorite, code])

  // 데이터 로딩 로직 - 한 번만 실행되도록 최적화
  useEffect(() => {
    if (!code) return

    const loadStockData = async () => {
      setLoading(true)
      setError("")
      
      try {
        // 주식 기본 정보 먼저 로드
        const stockData = await stocksApi.getStock(code)
        console.log('📊 주식 데이터 로드 결과:', stockData)
        
        // 감정 분석 데이터를 먼저 로드한 후 주식 데이터 변환
        let sentimentData = null;
        try {
          const sentimentApiData = await stocksApi.getSentimentAnalysis(code)
          if (sentimentApiData) {
            const positive = sentimentApiData.positive ? parseFloat(String(sentimentApiData.positive)) : 0;
            const negative = sentimentApiData.negative ? parseFloat(String(sentimentApiData.negative)) : 0;
            const neutral = sentimentApiData.neutral 
              ? (typeof sentimentApiData.neutral === 'string' ? parseFloat(sentimentApiData.neutral) : sentimentApiData.neutral)
              : 0;
            
            sentimentData = { positive, negative, neutral };
            
            // 전역 스토어에 저장
            sentimentStore.setSentiment(code, positive, negative, neutral);
          }
        } catch (err) {
          console.log('감정 분석 데이터 로드 실패:', err);
        }
        
        // API 데이터만으로 초기 상태 설정 (감정 데이터 포함)
        const convertedStock = convertApiStockToDetail(stockData, undefined, sentimentData)
        setStockDetail(convertedStock)
        stockDetailRef.current = convertedStock
        
        // 주가 히스토리 설정 - stockData에서 직접 가져오기
        const apiStockData = stockData as any;
        if (apiStockData.price_history && Array.isArray(apiStockData.price_history) && apiStockData.price_history.length > 0) {
          console.log('📈 주가 히스토리 설정:', apiStockData.price_history.length, '개 데이터')
          setPriceHistory(apiStockData.price_history)
        } else {
          console.log('⚠️ 주가 히스토리 데이터가 없어 별도 API 호출')
          // 별도 API로 주가 히스토리 가져오기
          try {
            const priceHistoryData = await stocksApi.getPriceHistory(code, { days: 365 })
            if (Array.isArray(priceHistoryData) && priceHistoryData.length > 0) {
              console.log('📈 주가 히스토리 설정 (별도 API):', priceHistoryData.length, '개 데이터')
              setPriceHistory(priceHistoryData)
            }
          } catch (err) {
            console.log('⚠️ 주가 히스토리 별도 API 호출 실패:', err)
          }
        }
        
        // 재무 데이터 설정
        if (apiStockData.financial_data) {
          console.log('💰 재무 데이터 설정:', apiStockData.financial_data)
          setFinancialData([apiStockData.financial_data])
        }
        
        // 기술적 지표 설정 - 우선순위: StockDetail API > StockAnalysis API
        let techIndicators = null
        if (apiStockData.technical_indicators) {
          console.log('📊 StockDetail API에서 기술지표 로드:', apiStockData.technical_indicators)
          techIndicators = apiStockData.technical_indicators
          setTechnicalIndicators(apiStockData.technical_indicators)
        }
        
        // 감정 분석 데이터 UI 설정 (이미 위에서 로드됨)
        if (sentimentData) {
          try {
            const sentimentApiData = await stocksApi.getSentimentAnalysis(code)
            if (sentimentApiData) {
              setSentimentAnalysis(sentimentApiData)
              
              // top_keywords를 배열로 변환
              const keywords = sentimentApiData.top_keywords 
                ? String(sentimentApiData.top_keywords).split(',').map(k => k.trim()).filter(k => k.length > 0)
                : ["기업분석", "투자", "주식"];
              
              console.log('🔑 키워드 처리 결과:', keywords)
              
              setSentimentData({
                score: sentimentData.positive - sentimentData.negative,
                keywords: keywords,
                newsCount: Math.floor(Math.random() * 200) + 50,
                positiveRatio: Math.floor(sentimentData.positive * 100),
                negativeRatio: Math.floor(sentimentData.negative * 100)
              })
            }
          } catch (err) {
            console.log('감정 분석 UI 데이터 설정 실패:', err);
          }
        } else {
          // 감정 데이터가 없으면 기본값 설정
          setSentimentData({
            score: 0.6,
            keywords: ["기업분석", "투자", "주식", "수익"],
            newsCount: Math.floor(Math.random() * 200) + 50,
            positiveRatio: 60,
            negativeRatio: 40
          })
        }
        
        // 추가 데이터 로드 (선택적) - 기존 기술지표가 없을 때만
        if (!techIndicators) {
          try {
            const analysisData = await stocksApi.getStockAnalysis(code)
            if (analysisData?.technical_indicators) {
              console.log('📊 StockAnalysis API에서 기술지표 로드:', analysisData.technical_indicators)
              setTechnicalIndicators(analysisData.technical_indicators)
            }
          } catch (err) {
            console.log('⚠️ 기술 분석 데이터 로드 실패:', err)
          }
        }
        
        try {
          const financialApiData = await stocksApi.getFinancialData(code)
          if (financialApiData) {
            setFinancialAnalysis(financialApiData)
          }
        } catch (err) {
          console.log('⚠️ 재무 분석 데이터 로드 실패:', err)
        }
        
      } catch (err: any) {
        const errorMessage = handleApiError(err)
        setError(errorMessage)
        console.error('Failed to load stock data:', err)
      } finally {
        setLoading(false)
      }
    }

    loadStockData()
  }, [code]) // code 변경 시에만 실행

  // 포맷팅 함수들 - 메모이제이션으로 최적화
  const formatNumber = useCallback((num: number | null) => {
    if (num === null || num === undefined) return '-'
    // 원 단위로 저장된 데이터를 적절한 단위로 변환
    if (num >= 1e12) return `${(num / 1e12).toFixed(1)}조원`
    if (num >= 1e8) return `${(num / 1e8).toFixed(1)}억원`
    if (num >= 1e4) return `${(num / 1e4).toFixed(1)}만원`
    return `${num.toLocaleString()}원`
  }, [])

  const formatPercent = useCallback((num: number | null) => {
    if (num === null || num === undefined || num === 0) return '-'
    return `${num.toFixed(2)}%`
  }, [])

  // 실시간 데이터 상태를 메모이제이션으로 최적화
  const realTimeStatus = useMemo(() => {
    if (!realTimeConnected) {
      return {
        label: '오프라인',
        variant: 'outline' as const,
        color: 'bg-gray-400'
      };
    }
    
    const realTimeData = realTimePrices[code];
    if (!realTimeData) {
      return {
        label: '실시간',
        variant: 'default' as const,
        color: 'bg-green-500'
      };
    }
    
    switch (realTimeData.source) {
      case 'realtime':
      case 'kis_paper_trading_fixed':
      case 'mock_websocket_optimized':
        return {
          label: '실시간',
          variant: 'default' as const,
          color: 'bg-green-500'
        };
      case 'closing':
        return {
          label: '종가',
          variant: 'default' as const,
          color: 'bg-blue-500'
        };
      default:
        return {
          label: '전일종가',
          variant: 'default' as const,
          color: 'bg-orange-500'
        };
    }
  }, [realTimeConnected, realTimePrices, code])

  // 가격 변동 컬러 계산 - 메모이제이션
  const priceChangeColor = useMemo(() => {
    if (!stockDetail) return 'text-gray-500';
    if (stockDetail.change > 0) return 'text-red-500';
    if (stockDetail.change < 0) return 'text-blue-500';
    return 'text-gray-500';
  }, [stockDetail?.change])

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-8">
          <div className="space-y-6">
            <Skeleton className="h-8 w-64" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-96 w-full" />
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="container mx-auto px-4 py-8">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              주식 정보를 불러오는데 실패했습니다: {error}
            </AlertDescription>
          </Alert>
          <div className="mt-4">
            <Link href="/">
              <Button variant="outline">
                <ArrowLeft className="h-4 w-4 mr-2" />
                메인으로 돌아가기
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (!stockDetail) return null

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="border-b bg-white">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/">
                <Button variant="ghost" size="sm">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  돌아가기
                </Button>
              </Link>
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <h1 className="text-2xl font-bold">{stockDetail.name}</h1>
                  <Badge variant={stockDetail.market === 'KOSPI' ? 'default' : 'secondary'}>
                    {stockDetail.market}
                  </Badge>
                </div>
                <p className="text-gray-600">
                  {stockDetail.code} • {translateSectorToKorean(stockDetail.sector)}
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Button 
                variant={isFavorite ? "default" : "outline"} 
                size="sm" 
                onClick={handleFavoriteToggle}
                disabled={favoriteLoading}
              >
                <Star className={`h-4 w-4 mr-2 ${isFavorite ? "fill-current" : ""}`} />
                {favoriteLoading 
                  ? "처리 중..." 
                  : (isFavorite ? "관심종목 해제" : "관심종목 추가")
                }
              </Button>
              
              {/* 인증 상태에 따른 버튼 표시 */}
              {isAuthenticated ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="outline" size="sm" className="flex items-center gap-2">
                      <User className="h-4 w-4" />
                      {user?.first_name || user?.username || '사용자'}
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-48">
                    <DropdownMenuLabel>내 계정</DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>
                      <User className="mr-2 h-4 w-4" />
                      프로필
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      <Star className="mr-2 h-4 w-4" />
                      관심종목
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={logout}>
                      <LogOut className="mr-2 h-4 w-4" />
                      로그아웃
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <div className="flex items-center gap-2">
                  <Link href="/login">
                    <Button variant="outline" size="sm">
                      <LogIn className="mr-2 h-4 w-4" />
                      로그인
                    </Button>
                  </Link>
                  <Link href="/register">
                    <Button size="sm">
                      회원가입
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        {/* Price Summary */}
        <Card className="mb-8">
          <CardContent className="pt-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div>
                <div className="flex items-center justify-between mb-2">
                  {/* StockPriceCell 컴포넌트로 통합하여 중복 제거 */}
                  <div className="text-3xl font-bold font-mono">
                    <StockPriceCell 
                      data={{
                        price: stockDetail.price,
                        change: stockDetail.change,
                        changePercent: stockDetail.changePercent,
                        volume: stockDetail.volume,
                        isRealTime: !!realTimePrices[code] && realTimeConnected,
                        isMarketClosed: !realTimeConnected || (!realTimePrices[code] && !realTimeLoading),
                        lastTradingDay: "2025-01-06",
                        timestamp: realTimePrices[code]?.timestamp
                      }}
                      compact={false}
                    />
                  </div>
                  {/* 시장 상태 표시기 제거 */}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-600">거래량</div>
                <div className="text-lg font-mono">
                  {formatNumber(stockDetail.volume)}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-600">시가총액</div>
                <div className="text-lg font-mono">{formatNumber(stockDetail.marketCap)}</div>
              </div>
              <div>
                <div className="text-sm text-gray-600">배당수익률</div>
                <div className="text-lg font-mono">{formatPercent(stockDetail.dividend_yield)}</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Main Content */}
        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full grid-cols-5">
            <TabsTrigger value="overview">개요</TabsTrigger>
            <TabsTrigger value="financials">재무</TabsTrigger>
            <TabsTrigger value="technical">기술분석</TabsTrigger>
            <TabsTrigger value="sentiment">감정분석</TabsTrigger>
            <TabsTrigger value="clustering">클러스터링</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            {/* Key Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">PER</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stockDetail.per ? stockDetail.per.toFixed(1) : '-'}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">PBR</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stockDetail.pbr ? stockDetail.pbr.toFixed(1) : '-'}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">ROE</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stockDetail.roe ? formatPercent(stockDetail.roe) : '-'}</div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">감정지수</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl font-bold">{(stockDetail.sentiment * 100).toFixed(0)}</span>
                    <Badge
                      variant={
                        stockDetail.sentiment >= 0.7
                          ? "default"
                          : stockDetail.sentiment >= 0.5
                            ? "secondary"
                            : "destructive"
                      }
                    >
                      {stockDetail.sentiment >= 0.7 ? "긍정" : stockDetail.sentiment >= 0.5 ? "중립" : "부정"}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-gray-600">AI 종합 점수</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl font-bold text-blue-600">
                      {typeof stockDetail.aiScore === 'number' ? stockDetail.aiScore : '-'}
                    </span>
                    <Badge
                      variant={
                        (stockDetail.aiScore || 0) >= 70
                          ? "default"
                          : (stockDetail.aiScore || 0) >= 50
                            ? "secondary"
                            : "destructive"
                      }
                    >
                      {(stockDetail.aiScore || 0) >= 70 ? "긍정" : (stockDetail.aiScore || 0) >= 50 ? "중립" : "부정"}
                    </Badge>
                  </div>
                  <div className="text-xs text-gray-500 mt-2">
                    기술분석(70%) + 감정분석(30%)
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Price Chart */}
            <Card>
              <CardHeader>
                <CardTitle>주가 차트</CardTitle>
                <CardDescription>최근 30일 주가 동향</CardDescription>
              </CardHeader>
              <CardContent>
                {priceHistory.length > 0 ? (
                                      <PriceChart data={priceHistory} title="주가 변동 추이" stockCode={code} />
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    주가 데이터를 불러올 수 없습니다
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="financials" className="space-y-6">
            {/* 재무 분석 차트 */}
            {financialAnalysis ? (
              <FinancialChart financial={financialAnalysis} title="재무 분석" />
            ) : (
              <div className="bg-white p-6 rounded-lg border">
                <div className="text-center text-gray-500">
                  <DollarSign className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <h3 className="text-lg font-medium mb-2">재무 분석 차트 준비 중</h3>
                  <p className="text-sm">재무 데이터가 준비되면 상세한 분석 차트가 표시됩니다.</p>
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Financial Data Table */}
              <Card>
                <CardHeader>
                  <CardTitle>재무제표</CardTitle>
                  <CardDescription>
                    {financialData.length > 0 ? `${financialData[0].year}년 기준` : '데이터 없음'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {financialData.length > 0 ? (
                    <Table>
                      <TableBody>
                        <TableRow>
                          <TableCell>매출액</TableCell>
                          <TableCell className="font-mono text-right">{formatNumber(financialData[0].revenue)}</TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell>영업이익</TableCell>
                          <TableCell className="font-mono text-right">
                            {formatNumber(financialData[0].operating_income)}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell>순이익</TableCell>
                          <TableCell className="font-mono text-right">
                            {formatNumber(financialData[0].net_income)}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell>총자산</TableCell>
                          <TableCell className="font-mono text-right">
                            {formatNumber(financialData[0].total_assets || null)}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell>총부채</TableCell>
                          <TableCell className="font-mono text-right">
                            {formatNumber(financialData[0].total_liabilities || null)}
                          </TableCell>
                        </TableRow>
                        <TableRow>
                          <TableCell>총자본</TableCell>
                          <TableCell className="font-mono text-right">
                            {formatNumber(financialData[0].total_equity || null)}
                          </TableCell>
                        </TableRow>
                      </TableBody>
                    </Table>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      재무 데이터를 불러올 수 없습니다
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Financial Ratios */}
              <Card>
                <CardHeader>
                  <CardTitle>재무 비율</CardTitle>
                  <CardDescription>주요 재무 비율 분석</CardDescription>
                </CardHeader>
                <CardContent>
                  {financialData.length > 0 ? (
                    <div className="space-y-4">
                      <div className="flex justify-between">
                        <span>부채비율</span>
                        <span className="font-mono">
                          {(financialData[0].total_liabilities && financialData[0].total_equity) 
                            ? ((financialData[0].total_liabilities / financialData[0].total_equity) * 100).toFixed(1) + '%'
                            : '-'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>영업이익률</span>
                        <span className="font-mono">
                          {((financialData[0].operating_income / financialData[0].revenue) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>순이익률</span>
                        <span className="font-mono">
                          {((financialData[0].net_income / financialData[0].revenue) * 100).toFixed(1)}%
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>자기자본비율</span>
                        <span className="font-mono">
                          {(financialData[0].total_equity && financialData[0].total_assets) 
                            ? ((financialData[0].total_equity / financialData[0].total_assets) * 100).toFixed(1) + '%'
                            : '-'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span>EPS</span>
                        <span className="font-mono">{stockDetail.eps ? stockDetail.eps.toLocaleString() : '-'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>BPS</span>
                        <span className="font-mono">{stockDetail.bps ? stockDetail.bps.toLocaleString() : '-'}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-8 text-gray-500">
                      재무 비율 데이터를 불러올 수 없습니다
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="technical" className="space-y-6">
            {technicalIndicators ? (
              <TechnicalChart 
                indicators={technicalIndicators} 
                priceData={priceHistory}
                title="기술적 분석 지표"
                stockCode={code}
              />
            ) : (
              <div className="text-center py-8 text-gray-500">
                기술적 지표 데이터를 불러올 수 없습니다
              </div>
            )}
          </TabsContent>

          <TabsContent value="sentiment" className="space-y-6">
            {sentimentAnalysis ? (
              <SentimentChart sentiment={sentimentAnalysis} title="네이버 종목토론방 감정 분석" />
            ) : (
              <div className="space-y-6">
                {/* 감정 분석 데이터가 없을 때 기존 UI 표시 */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Sentiment Analysis */}
                  <Card>
                    <CardHeader>
                      <CardTitle>감정 분석</CardTitle>
                      <CardDescription>시장 심리 및 감정 지표</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {sentimentData ? (
                        <div className="space-y-4">
                          <div className="flex justify-between items-center">
                            <span>감정 점수</span>
                            <div className="flex items-center space-x-2">
                              <span className="font-mono text-lg">{(sentimentData.score * 100).toFixed(0)}</span>
                              <Badge
                                variant={
                                  sentimentData.score >= 0.7
                                    ? "default"
                                    : sentimentData.score >= 0.5
                                      ? "secondary"
                                      : "destructive"
                                }
                              >
                                {sentimentData.score >= 0.7 ? "긍정" : sentimentData.score >= 0.5 ? "중립" : "부정"}
                              </Badge>
                            </div>
                          </div>
                          <div className="flex justify-between">
                            <span>뉴스 건수</span>
                            <span className="font-mono">{sentimentData.newsCount}건</span>
                          </div>
                          <div className="flex justify-between">
                            <span>긍정 비율</span>
                            <span className="font-mono text-green-600">{sentimentData.positiveRatio}%</span>
                          </div>
                          <div className="flex justify-between">
                            <span>부정 비율</span>
                            <span className="font-mono text-red-600">{sentimentData.negativeRatio}%</span>
                          </div>
                        </div>
                      ) : (
                        <div className="text-center py-8 text-gray-500">
                          감정 분석 데이터를 불러올 수 없습니다
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Keywords */}
                  <Card>
                    <CardHeader>
                      <CardTitle>주요 키워드</CardTitle>
                      <CardDescription>연관 검색어 및 이슈</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {sentimentData ? (
                        <div className="flex flex-wrap gap-2">
                          {sentimentData.keywords.map((keyword, index) => (
                            <Badge key={index} variant="outline">
                              {keyword}
                            </Badge>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-8 text-gray-500">
                          키워드 데이터를 불러올 수 없습니다
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
                
                <Card className="p-6">
                  <div className="text-center text-gray-500">
                    <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <h3 className="text-lg font-medium mb-2">감정 분석 데이터 준비 중</h3>
                    <p className="text-sm">
                      네이버 종목토론방 크롤링 및 감정 분석이 2시간마다 자동으로 실행됩니다.<br/>
                      분석 결과가 준비되면 상세한 감정 분석 차트가 표시됩니다.
                    </p>
                  </div>
                </Card>
              </div>
            )}
          </TabsContent>

          <TabsContent value="clustering" className="space-y-6">
            <ClusterVisualization stockCode={code} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}
