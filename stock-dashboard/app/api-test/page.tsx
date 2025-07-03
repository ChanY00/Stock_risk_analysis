"use client"

import { useState, useEffect } from "react"
import { stocksApi, Stock, MarketOverview, handleApiError } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { AlertCircle, CheckCircle, TrendingUp, TrendingDown } from "lucide-react"
import { Alert, AlertDescription } from "@/components/ui/alert"

export default function ApiTestPage() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>("")
  const [searchQuery, setSearchQuery] = useState("")
  const [testResults, setTestResults] = useState<string[]>([])

  const addTestResult = (message: string) => {
    setTestResults(prev => [...prev, `${new Date().toLocaleTimeString()}: ${message}`])
  }

  const testApiConnection = async () => {
    setLoading(true)
    setError("")
    setTestResults([])
    
    try {
      addTestResult("🔄 API 연결 테스트 시작...")
      
      // 1. 시장 개요 테스트
      addTestResult("📊 시장 개요 데이터 조회 중...")
      const marketData = await stocksApi.getMarketOverview()
      setMarketOverview(marketData)
      addTestResult(`✅ 시장 개요 조회 성공 (지수 ${Object.keys(marketData.market_summary).length}개)`)
      
      // 2. 주식 목록 테스트
      addTestResult("📈 주식 목록 조회 중...")
      const stocksData = await stocksApi.getStocks()
      setStocks(stocksData.results.slice(0, 20)) // 처음 20개만 표시
      addTestResult(`✅ 주식 목록 조회 성공 (총 ${stocksData.count}개 종목)`)
      
      // 3. 특정 주식 상세 정보 테스트
      if (stocksData.results.length > 0) {
        const firstStock = stocksData.results[0]
        addTestResult(`🔍 ${firstStock.stock_name} 상세 정보 조회 중...`)
        const stockDetail = await stocksApi.getStock(firstStock.stock_code)
        addTestResult(`✅ ${stockDetail.stock_name} 상세 정보 조회 성공`)
        
        // 4. 기술적 분석 테스트
        addTestResult(`📊 ${firstStock.stock_name} 기술적 분석 조회 중...`)
        const analysis = await stocksApi.getStockAnalysis(firstStock.stock_code)
        addTestResult(`✅ ${analysis.stock_name} 기술적 분석 조회 성공`)
      }
      
      addTestResult("🎉 모든 API 테스트 완료!")
      
    } catch (err: any) {
      const errorMessage = handleApiError(err)
      setError(errorMessage)
      addTestResult(`❌ API 테스트 실패: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  const searchStocks = async () => {
    if (!searchQuery.trim()) return
    
    setLoading(true)
    setError("")
    
    try {
      addTestResult(`🔍 "${searchQuery}" 검색 중...`)
      const searchResults = await stocksApi.getStocks({ search: searchQuery })
      setStocks(searchResults.results)
      addTestResult(`✅ 검색 완료 (${searchResults.count}개 결과)`)
    } catch (err: any) {
      const errorMessage = handleApiError(err)
      setError(errorMessage)
      addTestResult(`❌ 검색 실패: ${errorMessage}`)
    } finally {
      setLoading(false)
    }
  }

  const formatNumber = (num: number | null) => {
    if (num === null || num === undefined) return '-'
    if (num >= 1e12) return `${(num / 1e12).toFixed(1)}조`
    if (num >= 1e8) return `${(num / 1e8).toFixed(1)}억`
    if (num >= 1e4) return `${(num / 1e4).toFixed(1)}만`
    return num.toLocaleString()
  }

  const formatPrice = (price: number | null) => {
    if (price === null || price === undefined) return '-'
    return `${price.toLocaleString()}원`
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">백엔드 API 연동 테스트</h1>
          <p className="text-muted-foreground">Django 백엔드와의 연결을 테스트합니다</p>
        </div>
        <Button onClick={testApiConnection} disabled={loading}>
          {loading ? "테스트 중..." : "API 테스트 시작"}
        </Button>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* 테스트 결과 로그 */}
      <Card>
        <CardHeader>
          <CardTitle>테스트 로그</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="bg-black text-green-400 p-4 rounded-md font-mono text-sm max-h-60 overflow-y-auto">
            {testResults.length === 0 ? (
              <div className="text-gray-500">아직 테스트가 시작되지 않았습니다...</div>
            ) : (
              testResults.map((result, index) => (
                <div key={index} className="mb-1">{result}</div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* 시장 개요 */}
      {marketOverview && (
        <Card>
          <CardHeader>
            <CardTitle>시장 개요</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(marketOverview.market_summary).map(([name, data]) => (
                <div key={name} className="p-4 border rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-lg">{name.toUpperCase()}</h3>
                    {data.change >= 0 ? (
                      <TrendingUp className="h-4 w-4 text-green-600" />
                    ) : (
                      <TrendingDown className="h-4 w-4 text-red-600" />
                    )}
                  </div>
                  <div className="space-y-1 text-sm">
                    <div className="flex justify-between">
                      <span>현재가:</span>
                      <span className="font-medium">{data.current.toLocaleString()}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>변동:</span>
                      <span className={data.change >= 0 ? "text-green-600" : "text-red-600"}>
                        {data.change >= 0 ? "+" : ""}{data.change.toFixed(2)} ({data.change_percent >= 0 ? "+" : ""}{data.change_percent.toFixed(2)}%)
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>거래량:</span>
                      <span>{formatNumber(data.volume)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 주식 검색 */}
      <Card>
        <CardHeader>
          <CardTitle>주식 검색</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="종목명 또는 종목코드 검색..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && searchStocks()}
            />
            <Button onClick={searchStocks} disabled={loading}>
              검색
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 주식 목록 */}
      <Card>
        <CardHeader>
          <CardTitle>주식 목록</CardTitle>
          <CardDescription>
            {stocks.length > 0 ? `${stocks.length}개 종목` : "아직 데이터가 없습니다"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : stocks.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>종목코드</TableHead>
                  <TableHead>종목명</TableHead>
                  <TableHead>시장</TableHead>
                  <TableHead>섹터</TableHead>
                  <TableHead>현재가</TableHead>
                  <TableHead>시가총액</TableHead>
                  <TableHead>PER</TableHead>
                  <TableHead>PBR</TableHead>
                  <TableHead>ROE</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {stocks.map((stock) => (
                  <TableRow key={stock.stock_code}>
                    <TableCell className="font-medium">{stock.stock_code}</TableCell>
                    <TableCell>{stock.stock_name}</TableCell>
                    <TableCell>
                      <Badge variant={stock.market === 'KOSPI' ? 'default' : 'secondary'}>
                        {stock.market}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">{stock.sector}</TableCell>
                    <TableCell>{formatPrice(stock.current_price)}</TableCell>
                    <TableCell>{formatNumber(stock.market_cap)}</TableCell>
                    <TableCell>{stock.per ? stock.per.toFixed(1) : '-'}</TableCell>
                    <TableCell>{stock.pbr ? stock.pbr.toFixed(1) : '-'}</TableCell>
                    <TableCell>{stock.roe ? stock.roe.toFixed(1) + '%' : '-'}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              API 테스트를 시작하거나 검색을 수행하세요
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
} 