"use client"

import { useState, useEffect } from 'react'
import { Plus, TrendingUp, TrendingDown, PieChart, BarChart3, Calculator, Target, Trash2, Edit } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Progress } from '@/components/ui/progress'
import { PieChart as RechartsPieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, LineChart, Line } from 'recharts'

export interface PortfolioHolding {
  stockCode: string
  stockName: string
  quantity: number
  averagePrice: number
  currentPrice: number
  totalInvestment: number
  currentValue: number
  profitLoss: number
  profitLossPercent: number
  weight: number
  sector: string
  market: string
}

export interface Portfolio {
  id: string
  name: string
  description?: string
  totalInvestment: number
  currentValue: number
  totalProfitLoss: number
  totalProfitLossPercent: number
  holdings: PortfolioHolding[]
  createdAt: Date
  updatedAt: Date
}

interface PortfolioManagerProps {
  className?: string
}

const SAMPLE_STOCKS = [
  { code: '005930', name: '삼성전자', price: 71000, sector: 'IT', market: 'KOSPI' },
  { code: '000660', name: 'SK하이닉스', price: 134000, sector: 'IT', market: 'KOSPI' },
  { code: '035420', name: 'NAVER', price: 156000, sector: 'IT', market: 'KOSPI' },
  { code: '051910', name: 'LG화학', price: 381000, sector: '화학', market: 'KOSPI' },
  { code: '028260', name: '삼성물산', price: 126000, sector: '건설', market: 'KOSPI' }
]

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#6366f1']

export function PortfolioManager({ className = "" }: PortfolioManagerProps) {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([])
  const [selectedPortfolio, setSelectedPortfolio] = useState<Portfolio | null>(null)
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showAddHoldingDialog, setShowAddHoldingDialog] = useState(false)
  const [editingHolding, setEditingHolding] = useState<PortfolioHolding | null>(null)

  // 폼 상태
  const [portfolioForm, setPortfolioForm] = useState({
    name: '',
    description: ''
  })

  const [holdingForm, setHoldingForm] = useState({
    stockCode: '',
    stockName: '',
    quantity: '',
    averagePrice: ''
  })

  // 로컬 스토리지에서 포트폴리오 로드
  useEffect(() => {
    const saved = localStorage.getItem('portfolios')
    if (saved) {
      try {
        const parsedPortfolios = JSON.parse(saved).map((p: any) => ({
          ...p,
          createdAt: new Date(p.createdAt),
          updatedAt: new Date(p.updatedAt)
        }))
        setPortfolios(parsedPortfolios)
        if (parsedPortfolios.length > 0) {
          setSelectedPortfolio(parsedPortfolios[0])
        }
      } catch (error) {
        console.error('Failed to load portfolios:', error)
      }
    }
  }, [])

  // 포트폴리오 저장
  const savePortfolios = (updatedPortfolios: Portfolio[]) => {
    setPortfolios(updatedPortfolios)
    localStorage.setItem('portfolios', JSON.stringify(updatedPortfolios))
  }

  // 포트폴리오 생성
  const createPortfolio = () => {
    if (!portfolioForm.name.trim()) return

    const newPortfolio: Portfolio = {
      id: Date.now().toString(),
      name: portfolioForm.name.trim(),
      description: portfolioForm.description.trim(),
      totalInvestment: 0,
      currentValue: 0,
      totalProfitLoss: 0,
      totalProfitLossPercent: 0,
      holdings: [],
      createdAt: new Date(),
      updatedAt: new Date()
    }

    const updatedPortfolios = [...portfolios, newPortfolio]
    savePortfolios(updatedPortfolios)
    setSelectedPortfolio(newPortfolio)
    setPortfolioForm({ name: '', description: '' })
    setShowCreateDialog(false)
  }

  // 포트폴리오 삭제
  const deletePortfolio = (portfolioId: string) => {
    const updatedPortfolios = portfolios.filter(p => p.id !== portfolioId)
    savePortfolios(updatedPortfolios)
    
    if (selectedPortfolio?.id === portfolioId) {
      setSelectedPortfolio(updatedPortfolios.length > 0 ? updatedPortfolios[0] : null)
    }
  }

  // 보유 종목 추가/수정
  const saveHolding = () => {
    if (!selectedPortfolio || !holdingForm.stockCode || !holdingForm.quantity || !holdingForm.averagePrice) return

    const quantity = parseInt(holdingForm.quantity)
    const averagePrice = parseFloat(holdingForm.averagePrice)
    const stock = SAMPLE_STOCKS.find(s => s.code === holdingForm.stockCode)
    
    if (!stock) return

    const holding: PortfolioHolding = {
      stockCode: holdingForm.stockCode,
      stockName: holdingForm.stockName || stock.name,
      quantity,
      averagePrice,
      currentPrice: stock.price,
      totalInvestment: quantity * averagePrice,
      currentValue: quantity * stock.price,
      profitLoss: (quantity * stock.price) - (quantity * averagePrice),
      profitLossPercent: ((stock.price - averagePrice) / averagePrice) * 100,
      weight: 0, // 계산될 예정
      sector: stock.sector,
      market: stock.market
    }

    let updatedHoldings: PortfolioHolding[]
    
    if (editingHolding) {
      // 수정
      updatedHoldings = selectedPortfolio.holdings.map(h => 
        h.stockCode === editingHolding.stockCode ? holding : h
      )
      setEditingHolding(null)
    } else {
      // 추가
      const existingIndex = selectedPortfolio.holdings.findIndex(h => h.stockCode === holdingForm.stockCode)
      if (existingIndex >= 0) {
        // 기존 종목 수량 변경
        updatedHoldings = selectedPortfolio.holdings.map((h, index) => 
          index === existingIndex ? holding : h
        )
      } else {
        // 새 종목 추가
        updatedHoldings = [...selectedPortfolio.holdings, holding]
      }
    }

    // 포트폴리오 업데이트
    const updatedPortfolio = calculatePortfolioMetrics({
      ...selectedPortfolio,
      holdings: updatedHoldings,
      updatedAt: new Date()
    })

    const updatedPortfolios = portfolios.map(p => 
      p.id === selectedPortfolio.id ? updatedPortfolio : p
    )

    savePortfolios(updatedPortfolios)
    setSelectedPortfolio(updatedPortfolio)
    setHoldingForm({ stockCode: '', stockName: '', quantity: '', averagePrice: '' })
    setShowAddHoldingDialog(false)
  }

  // 포트폴리오 메트릭 계산
  const calculatePortfolioMetrics = (portfolio: Portfolio): Portfolio => {
    const totalInvestment = portfolio.holdings.reduce((sum, h) => sum + h.totalInvestment, 0)
    const currentValue = portfolio.holdings.reduce((sum, h) => sum + h.currentValue, 0)
    const totalProfitLoss = currentValue - totalInvestment
    const totalProfitLossPercent = totalInvestment > 0 ? (totalProfitLoss / totalInvestment) * 100 : 0

    // 비중 계산
    const holdingsWithWeight = portfolio.holdings.map(h => ({
      ...h,
      weight: currentValue > 0 ? (h.currentValue / currentValue) * 100 : 0
    }))

    return {
      ...portfolio,
      totalInvestment,
      currentValue,
      totalProfitLoss,
      totalProfitLossPercent,
      holdings: holdingsWithWeight
    }
  }

  // 보유 종목 삭제
  const deleteHolding = (stockCode: string) => {
    if (!selectedPortfolio) return

    const updatedHoldings = selectedPortfolio.holdings.filter(h => h.stockCode !== stockCode)
    const updatedPortfolio = calculatePortfolioMetrics({
      ...selectedPortfolio,
      holdings: updatedHoldings,
      updatedAt: new Date()
    })

    const updatedPortfolios = portfolios.map(p => 
      p.id === selectedPortfolio.id ? updatedPortfolio : p
    )

    savePortfolios(updatedPortfolios)
    setSelectedPortfolio(updatedPortfolio)
  }

  // 섹터별 분포 데이터
  const getSectorDistribution = () => {
    if (!selectedPortfolio) return []
    
    const sectorMap: { [key: string]: number } = {}
    selectedPortfolio.holdings.forEach(h => {
      sectorMap[h.sector] = (sectorMap[h.sector] || 0) + h.currentValue
    })

    return Object.entries(sectorMap).map(([sector, value]) => ({
      name: sector,
      value,
      percentage: selectedPortfolio.currentValue > 0 ? (value / selectedPortfolio.currentValue) * 100 : 0
    }))
  }

  const formatNumber = (num: number) => {
    if (num >= 1e8) return `${(num / 1e8).toFixed(1)}억`
    if (num >= 1e4) return `${(num / 1e4).toFixed(1)}만`
    return num.toLocaleString()
  }

  const formatPercent = (num: number) => {
    const sign = num >= 0 ? '+' : ''
    return `${sign}${num.toFixed(2)}%`
  }

  return (
    <div className={className}>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <PieChart className="h-5 w-5" />
                포트폴리오 관리
              </CardTitle>
              <CardDescription>가상 포트폴리오를 생성하고 성과를 추적하세요</CardDescription>
            </div>
            <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  포트폴리오 생성
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>새 포트폴리오 생성</DialogTitle>
                  <DialogDescription>
                    포트폴리오 이름과 설명을 입력하세요
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4">
                  <div>
                    <Label htmlFor="name">포트폴리오 이름</Label>
                    <Input
                      id="name"
                      value={portfolioForm.name}
                      onChange={(e) => setPortfolioForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="예: 성장주 포트폴리오"
                    />
                  </div>
                  <div>
                    <Label htmlFor="description">설명 (선택사항)</Label>
                    <Input
                      id="description"
                      value={portfolioForm.description}
                      onChange={(e) => setPortfolioForm(prev => ({ ...prev, description: e.target.value }))}
                      placeholder="포트폴리오 설명"
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                    취소
                  </Button>
                  <Button onClick={createPortfolio}>생성</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </CardHeader>

        <CardContent>
          {portfolios.length === 0 ? (
            <div className="text-center py-12">
              <PieChart className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <h3 className="text-lg font-medium mb-2">포트폴리오가 없습니다</h3>
              <p className="text-gray-500 mb-4">첫 번째 포트폴리오를 생성해보세요</p>
              <Button onClick={() => setShowCreateDialog(true)}>
                <Plus className="h-4 w-4 mr-2" />
                포트폴리오 생성
              </Button>
            </div>
          ) : (
            <>
              {/* 포트폴리오 선택 */}
              <div className="flex items-center gap-4 mb-6">
                <Select
                  value={selectedPortfolio?.id}
                  onValueChange={(value) => {
                    const portfolio = portfolios.find(p => p.id === value)
                    setSelectedPortfolio(portfolio || null)
                  }}
                >
                  <SelectTrigger className="w-64">
                    <SelectValue placeholder="포트폴리오 선택" />
                  </SelectTrigger>
                  <SelectContent>
                    {portfolios.map((portfolio) => (
                      <SelectItem key={portfolio.id} value={portfolio.id}>
                        {portfolio.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                
                {selectedPortfolio && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deletePortfolio(selectedPortfolio.id)}
                    className="text-red-600 hover:text-red-700"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                )}
              </div>

              {selectedPortfolio && (
                <Tabs defaultValue="overview" className="space-y-6">
                  <TabsList>
                    <TabsTrigger value="overview">개요</TabsTrigger>
                    <TabsTrigger value="holdings">보유 종목</TabsTrigger>
                    <TabsTrigger value="analysis">분석</TabsTrigger>
                  </TabsList>

                  <TabsContent value="overview" className="space-y-6">
                    {/* 포트폴리오 요약 */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-sm text-gray-600 mb-2">총 투자금</div>
                          <div className="text-2xl font-bold">
                            {formatNumber(selectedPortfolio.totalInvestment)}원
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-sm text-gray-600 mb-2">현재 가치</div>
                          <div className="text-2xl font-bold">
                            {formatNumber(selectedPortfolio.currentValue)}원
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-sm text-gray-600 mb-2">손익</div>
                          <div className={`text-2xl font-bold ${
                            selectedPortfolio.totalProfitLoss >= 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {selectedPortfolio.totalProfitLoss >= 0 ? '+' : ''}
                            {formatNumber(selectedPortfolio.totalProfitLoss)}원
                          </div>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="pt-6">
                          <div className="text-sm text-gray-600 mb-2">수익률</div>
                          <div className={`text-2xl font-bold flex items-center gap-1 ${
                            selectedPortfolio.totalProfitLossPercent >= 0 ? 'text-green-600' : 'text-red-600'
                          }`}>
                            {selectedPortfolio.totalProfitLossPercent >= 0 ? (
                              <TrendingUp className="h-5 w-5" />
                            ) : (
                              <TrendingDown className="h-5 w-5" />
                            )}
                            {formatPercent(selectedPortfolio.totalProfitLossPercent)}
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </TabsContent>

                  <TabsContent value="holdings" className="space-y-6">
                    {/* 보유 종목 추가 */}
                    <div className="flex justify-between items-center">
                      <h3 className="text-lg font-medium">보유 종목</h3>
                      <Dialog open={showAddHoldingDialog} onOpenChange={setShowAddHoldingDialog}>
                        <DialogTrigger asChild>
                          <Button>
                            <Plus className="h-4 w-4 mr-2" />
                            종목 추가
                          </Button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogHeader>
                            <DialogTitle>
                              {editingHolding ? '보유 종목 수정' : '새 종목 추가'}
                            </DialogTitle>
                          </DialogHeader>
                          <div className="space-y-4">
                            <div>
                              <Label>종목 선택</Label>
                              <Select
                                value={holdingForm.stockCode}
                                onValueChange={(value) => {
                                  const stock = SAMPLE_STOCKS.find(s => s.code === value)
                                  setHoldingForm(prev => ({
                                    ...prev,
                                    stockCode: value,
                                    stockName: stock?.name || ''
                                  }))
                                }}
                              >
                                <SelectTrigger>
                                  <SelectValue placeholder="종목을 선택하세요" />
                                </SelectTrigger>
                                <SelectContent>
                                  {SAMPLE_STOCKS.map((stock) => (
                                    <SelectItem key={stock.code} value={stock.code}>
                                      {stock.name} ({stock.code})
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                            <div>
                              <Label>보유 수량</Label>
                              <Input
                                type="number"
                                value={holdingForm.quantity}
                                onChange={(e) => setHoldingForm(prev => ({ ...prev, quantity: e.target.value }))}
                                placeholder="100"
                              />
                            </div>
                            <div>
                              <Label>평균 매수가</Label>
                              <Input
                                type="number"
                                value={holdingForm.averagePrice}
                                onChange={(e) => setHoldingForm(prev => ({ ...prev, averagePrice: e.target.value }))}
                                placeholder="70000"
                              />
                            </div>
                          </div>
                          <DialogFooter>
                            <Button variant="outline" onClick={() => setShowAddHoldingDialog(false)}>
                              취소
                            </Button>
                            <Button onClick={saveHolding}>
                              {editingHolding ? '수정' : '추가'}
                            </Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </div>

                    {/* 보유 종목 테이블 */}
                    <Card>
                      <CardContent className="p-0">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>종목</TableHead>
                              <TableHead>수량</TableHead>
                              <TableHead>평균가</TableHead>
                              <TableHead>현재가</TableHead>
                              <TableHead>투자금</TableHead>
                              <TableHead>평가금</TableHead>
                              <TableHead>손익</TableHead>
                              <TableHead>비중</TableHead>
                              <TableHead></TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {selectedPortfolio.holdings.map((holding) => (
                              <TableRow key={holding.stockCode}>
                                <TableCell>
                                  <div>
                                    <div className="font-medium">{holding.stockName}</div>
                                    <div className="text-sm text-gray-500">{holding.stockCode}</div>
                                  </div>
                                </TableCell>
                                <TableCell className="font-mono">
                                  {holding.quantity.toLocaleString()}주
                                </TableCell>
                                <TableCell className="font-mono">
                                  {holding.averagePrice.toLocaleString()}원
                                </TableCell>
                                <TableCell className="font-mono">
                                  {holding.currentPrice.toLocaleString()}원
                                </TableCell>
                                <TableCell className="font-mono">
                                  {formatNumber(holding.totalInvestment)}원
                                </TableCell>
                                <TableCell className="font-mono">
                                  {formatNumber(holding.currentValue)}원
                                </TableCell>
                                <TableCell>
                                  <div className={`font-mono ${
                                    holding.profitLoss >= 0 ? 'text-green-600' : 'text-red-600'
                                  }`}>
                                    {holding.profitLoss >= 0 ? '+' : ''}
                                    {formatNumber(holding.profitLoss)}원
                                    <div className="text-xs">
                                      ({formatPercent(holding.profitLossPercent)})
                                    </div>
                                  </div>
                                </TableCell>
                                <TableCell>
                                  <div className="font-mono">{holding.weight.toFixed(1)}%</div>
                                  <Progress value={holding.weight} className="w-16 h-1 mt-1" />
                                </TableCell>
                                <TableCell>
                                  <div className="flex gap-1">
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => {
                                        setEditingHolding(holding)
                                        setHoldingForm({
                                          stockCode: holding.stockCode,
                                          stockName: holding.stockName,
                                          quantity: holding.quantity.toString(),
                                          averagePrice: holding.averagePrice.toString()
                                        })
                                        setShowAddHoldingDialog(true)
                                      }}
                                    >
                                      <Edit className="h-4 w-4" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="sm"
                                      onClick={() => deleteHolding(holding.stockCode)}
                                      className="text-red-600 hover:text-red-700"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </Button>
                                  </div>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </CardContent>
                    </Card>
                  </TabsContent>

                  <TabsContent value="analysis" className="space-y-6">
                    {/* 섹터별 분포 */}
                    <Card>
                      <CardHeader>
                        <CardTitle>섹터별 분포</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="h-64">
                          <ResponsiveContainer width="100%" height="100%">
                            <RechartsPieChart>
                              <Pie
                                data={getSectorDistribution()}
                                cx="50%"
                                cy="50%"
                                outerRadius={80}
                                dataKey="value"
                                label={({ name, percentage }) => `${name} ${percentage.toFixed(1)}%`}
                              >
                                {getSectorDistribution().map((entry, index) => (
                                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                                ))}
                              </Pie>
                              <Tooltip 
                                formatter={(value: number) => [formatNumber(value) + '원', '금액']}
                              />
                            </RechartsPieChart>
                          </ResponsiveContainer>
                        </div>
                      </CardContent>
                    </Card>
                  </TabsContent>
                </Tabs>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
} 