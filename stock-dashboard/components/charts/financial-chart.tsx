"use client"

import { useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts'
import { FinancialAnalysis } from '@/lib/api'
import { TrendingUp, DollarSign, Building, PieChart as PieIcon, AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

interface FinancialChartProps {
  financial: FinancialAnalysis
  title?: string
}

export function FinancialChart({ financial, title = "재무 분석" }: FinancialChartProps) {
  const [viewType, setViewType] = useState<'overview' | 'trends' | 'ratios' | 'assets'>('overview')

  if (!financial || !financial.financials || Object.keys(financial.financials).length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
        재무 데이터가 없습니다.
      </div>
    )
  }

  // 재무 데이터를 차트용으로 변환 (DB에 원 단위로 저장됨)
  const financialData = Object.entries(financial.financials)
    .map(([year, data]) => ({
      year: parseInt(year),
      revenue: data.revenue, // 원 단위
      operating_income: data.operating_income, // 원 단위
      net_income: data.net_income, // 원 단위
      eps: data.eps, // 원 단위
      total_assets: data.total_assets || 0, // 원 단위
      total_liabilities: data.total_liabilities || 0, // 원 단위
      total_equity: data.total_equity || 0 // 원 단위
    }))
    .sort((a, b) => a.year - b.year)

  // 최신년도 데이터
  const latestData = financialData[financialData.length - 1]
  
  // 2024년 데이터 특별 처리 - 순이익이 0인 경우 확인
  const has2024Data = financialData.some(data => data.year === 2024)
  const data2024 = financialData.find(data => data.year === 2024)
  const isNetIncomeZero = data2024 && data2024.net_income === 0
  
  // 자산 구성 파이차트 데이터
  const assetComposition = latestData ? [
    { name: '부채', value: latestData.total_liabilities, color: '#ef4444' },
    { name: '자본', value: latestData.total_equity, color: '#10b981' }
  ].filter(item => item.value > 0) : []

  // 재무비율 계산
  const calculateRatios = (data: typeof latestData) => {
    if (!data) return null
    
    return {
      debt_ratio: data.total_equity > 0 ? (data.total_liabilities / data.total_equity * 100).toFixed(1) : 'N/A',
      equity_ratio: data.total_assets > 0 ? (data.total_equity / data.total_assets * 100).toFixed(1) : 'N/A',
      operating_margin: data.revenue > 0 ? (data.operating_income / data.revenue * 100).toFixed(1) : 'N/A',
      net_margin: data.revenue > 0 ? (data.net_income / data.revenue * 100).toFixed(1) : 'N/A'
    }
  }

  const ratios = calculateRatios(latestData)

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white dark:bg-gray-800 p-4 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg">
          <p className="font-semibold text-gray-900 dark:text-white">{label}년</p>
          <div className="mt-2 space-y-1">
            {payload.map((entry: any, index: number) => (
              <p key={index} className="text-sm">
                <span className="text-gray-600 dark:text-gray-400">{entry.name}: </span>
                <span className="font-mono font-medium" style={{ color: entry.color }}>
                  {typeof entry.value === 'number' 
                    ? entry.dataKey === 'eps' 
                      ? `${entry.value.toLocaleString()}원`
                      : entry.value >= 1e12
                      ? `${(entry.value / 1e12).toFixed(1)}조원`
                      : entry.value >= 1e8
                      ? `${(entry.value / 1e8).toFixed(1)}억원`
                      : entry.value >= 1e4
                      ? `${(entry.value / 1e4).toFixed(1)}만원`
                      : `${entry.value.toLocaleString()}원`
                    : entry.value}
                </span>
              </p>
            ))}
          </div>
        </div>
      )
    }
    return null
  }

  // 손실 기업 여부 확인
  const hasOperatingLoss = latestData && latestData.operating_income < 0
  const hasNetLoss = latestData && latestData.net_income < 0

  // 데이터 품질 검증 함수들
  const validateFinancialData = (data: any) => {
    const issues = [];
    
    // 1. 영업이익 > 매출액 체크
    if (data.revenue > 0 && data.operating_income > data.revenue) {
      issues.push({
        type: 'OPERATING_GT_REVENUE',
        message: '영업이익이 매출액보다 큽니다',
        severity: 'warning'
      });
    }
    
    // 2. 매출액이 너무 작은 경우 (대기업 기준)
    if (data.revenue > 0 && data.operating_income > 0 && data.revenue < data.operating_income * 0.1) {
      issues.push({
        type: 'REVENUE_TOO_SMALL',
        message: '매출액 데이터를 확인 중입니다',
        severity: 'error'
      });
    }
    
    // 3. 자산-부채-자본 불일치 체크
    if (data.total_assets && data.total_liabilities && data.total_equity) {
      const calculated = data.total_liabilities + data.total_equity;
      const diffPct = Math.abs(data.total_assets - calculated) / data.total_assets * 100;
      if (diffPct > 10) {
        issues.push({
          type: 'BALANCE_SHEET_MISMATCH',
          message: '재무상태표 데이터를 확인 중입니다',
          severity: 'warning'
        });
      }
    }
    
    // 4. 비정상적 EPS 체크
    if (data.eps > 500000) {
      issues.push({
        type: 'ABNORMAL_EPS',
        message: 'EPS 단위를 확인 중입니다',
        severity: 'warning'
      });
    }
    
    return issues;
  };

  // 안전한 값 표시 함수 (원 단위 데이터용)
  const formatSafeValue = (value: number | null | undefined, unit: string = '조원', issues: any[] = []) => {
    if (value === null || value === undefined) return 'N/A';
    if (value === 0) return '0';
    
    // 이슈가 있는 경우 경고 표시
    const hasDataIssue = issues.some(issue => 
      issue.type === 'OPERATING_GT_REVENUE' || 
      issue.type === 'REVENUE_TOO_SMALL' ||
      issue.type === 'ABNORMAL_EPS'
    );
    
    // 원 단위로 저장된 데이터를 적절한 단위로 변환
    const absValue = Math.abs(value);
    let formattedValue: string;
    
    if (absValue >= 1e12) {
      // 1조원 이상
      formattedValue = `${(value / 1e12).toFixed(1)}조원`;
    } else if (absValue >= 1e8) {
      // 1억원 이상
      formattedValue = `${(value / 1e8).toFixed(1)}억원`;
    } else if (absValue >= 1e4) {
      // 1만원 이상
      formattedValue = `${(value / 1e4).toFixed(1)}만원`;
    } else {
      // 1만원 미만
      formattedValue = `${value.toLocaleString()}원`;
    }
    
    if (hasDataIssue) {
      return `${formattedValue} ⚠️`;
    }
    
    return formattedValue;
  };

  // 데이터 품질 경고 컴포넌트
  const DataQualityAlert = ({ issues }: { issues: any[] }) => {
    if (issues.length === 0) return null;
    
    const errorIssues = issues.filter(i => i.severity === 'error');
    const warningIssues = issues.filter(i => i.severity === 'warning');
    
    return (
      <div className="space-y-2 mb-4">
        {errorIssues.length > 0 && (
          <Alert className="border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-red-800 dark:text-red-200">
              <strong>데이터 확인 필요:</strong>
              <ul className="mt-1 ml-4 list-disc">
                {errorIssues.map((issue, idx) => (
                  <li key={idx}>{issue.message}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
        
        {warningIssues.length > 0 && (
          <Alert className="border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-900/20">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription className="text-yellow-800 dark:text-yellow-200">
              <strong>참고사항:</strong>
              <ul className="mt-1 ml-4 list-disc">
                {warningIssues.map((issue, idx) => (
                  <li key={idx}>{issue.message}</li>
                ))}
              </ul>
            </AlertDescription>
          </Alert>
        )}
      </div>
    );
  };

  // 각 연도별 데이터 검증
  const dataWithQuality = financialData.map((data: any) => {
    const issues = validateFinancialData(data);
    return {
      ...data,
      issues,
      dataQuality: issues.length === 0 ? 'good' : 
                   issues.some((i: any) => i.severity === 'error') ? 'poor' : 'fair'
    };
  });

  // 전체 데이터 이슈 수집
  const allIssues = dataWithQuality.flatMap((d: any) => d.issues);
  
  // 이전 연도 데이터 (전년 대비 계산용)
  const previousData = financialData.length > 1 ? financialData[financialData.length - 2] : null;
  
  // 최신 데이터에서 이슈 정보 추가
  const latestDataWithIssues = dataWithQuality[dataWithQuality.length - 1] || latestData;

  return (
    <div className="w-full space-y-6">
      {/* 헤더 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
          {has2024Data && (
            <Badge variant="secondary" className="bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200">
              2024년 최신 데이터
            </Badge>
          )}
        </div>
        
        {/* 뷰 타입 선택 */}
        <div className="flex space-x-2">
          <Button
            variant={viewType === 'overview' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewType('overview')}
            className="text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <DollarSign className="h-4 w-4 mr-1" />
            개요
          </Button>
          <Button
            variant={viewType === 'trends' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewType('trends')}
            className="text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <TrendingUp className="h-4 w-4 mr-1" />
            추세
          </Button>
          <Button
            variant={viewType === 'ratios' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewType('ratios')}
            className="text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <Building className="h-4 w-4 mr-1" />
            비율
          </Button>
          <Button
            variant={viewType === 'assets' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewType('assets')}
            className="text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700"
          >
            <PieIcon className="h-4 w-4 mr-1" />
            자산
          </Button>
        </div>
      </div>

      {/* 2024년 데이터 알림 */}
      {isNetIncomeZero && (
        <Alert>
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>
            2024년 순이익 데이터가 0으로 표시되고 있습니다. 이는 아직 확정되지 않은 데이터이거나 
            DART 공시에서 해당 항목이 누락되었을 수 있습니다.
          </AlertDescription>
        </Alert>
      )}

      {/* 데이터 품질 경고 */}
      <DataQualityAlert issues={allIssues} />

      {/* 재무 개요 */}
      {viewType === 'overview' && latestData && (
        <div className="space-y-6">
          {/* 핵심 재무 지표 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                         <Card className={`bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 ${latestDataWithIssues.issues?.some((i: any) => i.type === 'REVENUE_TOO_SMALL') ? 'border-red-200 dark:border-red-800' : ''}`}>
               <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                 <CardTitle className="text-sm font-medium text-gray-700 dark:text-gray-300">매출액</CardTitle>
                 <DollarSign className="h-4 w-4 text-muted-foreground dark:text-gray-400" />
               </CardHeader>
               <CardContent>
                 <div className="text-2xl font-bold text-gray-900 dark:text-white">
                   {formatSafeValue(latestDataWithIssues.revenue, '조', latestDataWithIssues.issues || [])}
                 </div>
                 <p className="text-xs text-muted-foreground dark:text-gray-400">
                   전년 대비: {
                     previousData 
                       ? `${((latestDataWithIssues.revenue - previousData.revenue) / previousData.revenue * 100).toFixed(1)}%`
                       : 'N/A'
                   }
                 </p>
               </CardContent>
             </Card>
             <Card className={`bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 ${latestDataWithIssues.issues?.some((i: any) => i.type === 'OPERATING_GT_REVENUE') ? 'border-yellow-200 dark:border-yellow-800' : ''}`}>
               <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                 <CardTitle className="text-sm font-medium text-gray-700 dark:text-gray-300">영업이익</CardTitle>
                 <TrendingUp className="h-4 w-4 text-muted-foreground dark:text-gray-400" />
               </CardHeader>
               <CardContent>
                 <div className={`text-2xl font-bold text-gray-900 dark:text-white ${latestDataWithIssues.operating_income < 0 ? 'text-red-600 dark:text-red-400' : ''}`}>
                   {formatSafeValue(latestDataWithIssues.operating_income, '조', latestDataWithIssues.issues || [])}
                 </div>
                 <p className="text-xs text-muted-foreground dark:text-gray-400">
                   {latestDataWithIssues.operating_income < 0 ? '영업손실' : ''}
                   {previousData 
                     ? `전년 대비: ${((latestDataWithIssues.operating_income - previousData.operating_income) / Math.abs(previousData.operating_income) * 100).toFixed(1)}%`
                     : ''
                   }
                 </p>
               </CardContent>
             </Card>
             <Card className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
               <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                 <CardTitle className="text-sm font-medium text-gray-700 dark:text-gray-300">순이익</CardTitle>
                 <Building className="h-4 w-4 text-muted-foreground dark:text-gray-400" />
               </CardHeader>
               <CardContent>
                 <div className={`text-2xl font-bold text-gray-900 dark:text-white ${latestDataWithIssues.net_income < 0 ? 'text-red-600 dark:text-red-400' : latestDataWithIssues.net_income === 0 ? 'text-gray-500 dark:text-gray-400' : ''}`}>
                   {latestDataWithIssues.net_income === 0 
                     ? (latestDataWithIssues.year === 2024 ? '미공시' : '0')
                     : formatSafeValue(latestDataWithIssues.net_income, '조', latestDataWithIssues.issues || [])
                   }
                 </div>
                 <p className="text-xs text-muted-foreground dark:text-gray-400">
                   {latestDataWithIssues.net_income < 0 ? '순손실' : ''}
                   {latestDataWithIssues.net_income === 0 && latestDataWithIssues.year === 2024 ? '2024년 실적 대기 중' : ''}
                   {latestDataWithIssues.net_income === 0 && latestDataWithIssues.year !== 2024 && latestDataWithIssues.eps && latestDataWithIssues.eps !== 0 ? ' (EPS는 존재, 데이터 확인 필요)' : ''}
                 </p>
               </CardContent>
             </Card>
             <Card className={`bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 ${latestDataWithIssues.issues?.some((i: any) => i.type === 'ABNORMAL_EPS') ? 'border-yellow-200 dark:border-yellow-800' : ''}`}>
               <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                 <CardTitle className="text-sm font-medium text-gray-700 dark:text-gray-300">EPS</CardTitle>
                 <PieIcon className="h-4 w-4 text-muted-foreground dark:text-gray-400" />
               </CardHeader>
               <CardContent>
                 <div className="text-2xl font-bold text-gray-900 dark:text-white">
                   {latestDataWithIssues.eps === null || latestDataWithIssues.eps === undefined || latestDataWithIssues.eps === 0
                     ? 'N/A'
                     : `${latestDataWithIssues.eps.toLocaleString()}원`
                   }
                 </div>
                 <p className="text-xs text-muted-foreground dark:text-gray-400">주당순이익</p>
               </CardContent>
             </Card>
          </div>

          {/* 연도별 성장률 표시 */}
          {financialData.length >= 2 && (
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
              <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">전년 대비 성장률</h4>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {(() => {
                  const currentYear = financialData[financialData.length - 1]
                  const previousYear = financialData[financialData.length - 2]
                  
                  const revenueGrowth = previousYear.revenue > 0 ? 
                    ((currentYear.revenue - previousYear.revenue) / previousYear.revenue * 100).toFixed(1) : 'N/A'
                  const operatingGrowth = previousYear.operating_income !== 0 ? 
                    ((currentYear.operating_income - previousYear.operating_income) / Math.abs(previousYear.operating_income) * 100).toFixed(1) : 'N/A'
                  const netGrowth = previousYear.net_income !== 0 && currentYear.net_income !== 0 ? 
                    ((currentYear.net_income - previousYear.net_income) / Math.abs(previousYear.net_income) * 100).toFixed(1) : 'N/A'
                  
                  return (
                    <>
                      <div className="text-center">
                        <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">매출액 성장률</div>
                        <div className={`text-xl font-bold ${parseFloat(revenueGrowth) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {revenueGrowth !== 'N/A' ? `${parseFloat(revenueGrowth) >= 0 ? '+' : ''}${revenueGrowth}%` : 'N/A'}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">영업이익 성장률</div>
                        <div className={`text-xl font-bold ${parseFloat(operatingGrowth) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {operatingGrowth !== 'N/A' ? `${parseFloat(operatingGrowth) >= 0 ? '+' : ''}${operatingGrowth}%` : 'N/A'}
                        </div>
                      </div>
                      <div className="text-center">
                        <div className="text-sm text-gray-600 dark:text-gray-400 mb-1">순이익 성장률</div>
                        <div className={`text-xl font-bold ${netGrowth === 'N/A' ? 'text-gray-500 dark:text-gray-400' : parseFloat(netGrowth) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                          {netGrowth !== 'N/A' ? `${parseFloat(netGrowth) >= 0 ? '+' : ''}${netGrowth}%` : 'N/A'}
                        </div>
                      </div>
                    </>
                  )
                })()}
              </div>
            </div>
          )}

          {/* 최근 실적 차트 */}
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
            <h4 className="text-lg font-medium text-gray-800 dark:text-white mb-4">최근 실적 현황</h4>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={financialData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="year" />
                  <YAxis 
                    domain={(() => {
                      const values = financialData.map(d => Math.max(d.revenue, d.operating_income, d.net_income)).filter(v => v > 0)
                      if (values.length === 0) return ['dataMin', 'dataMax']
                      
                      const sortedValues = values.sort((a, b) => a - b)
                      const removeOutliers = 0.1
                      const lowerIndex = Math.floor(sortedValues.length * removeOutliers)
                      const upperIndex = Math.floor(sortedValues.length * (1 - removeOutliers))
                      const filteredValues = sortedValues.slice(lowerIndex, upperIndex)
                      
                      if (filteredValues.length === 0) return ['dataMin', 'dataMax']
                      
                      const median = filteredValues[Math.floor(filteredValues.length / 2)]
                      const p5 = filteredValues[Math.floor(filteredValues.length * 0.05)]
                      const p95 = filteredValues[Math.floor(filteredValues.length * 0.95)]
                      
                      const range = Math.max(p95 - median, median - p5)
                      const centeredMin = Math.max(median - range * 1.3, p5)
                      const centeredMax = Math.min(median + range * 1.3, p95)
                      
                      return [centeredMin, centeredMax]
                    })()}
                    tickFormatter={(value) => {
                      if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조`;
                      if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억`;
                      if (value >= 1e4) return `${(value / 1e4).toFixed(1)}만`;
                      return `${value.toLocaleString()}`;
                    }}
                    tick={{ fontSize: 12, fill: '#6b7280' }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                  <Bar dataKey="revenue" name="매출액" fill="#3b82f6" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="operating_income" name="영업이익" fill="#10b981" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="net_income" name="순이익" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* 추세 분석 */}
      {viewType === 'trends' && (
        <div className="bg-white p-6 rounded-lg border">
          <h4 className="text-lg font-medium text-gray-800 mb-4">재무 추세 분석</h4>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={financialData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="year" />
                <YAxis 
                  tickFormatter={(value) => value >= 100000 ? `${(value / 100000).toFixed(0)}억` : `${value.toLocaleString()}백만`}
                  tick={{ fontSize: 12, fill: '#6b7280' }}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="revenue" 
                  name="매출액" 
                  stroke="#3b82f6" 
                  strokeWidth={3}
                  dot={{ r: 6 }}
                />
                <Line 
                  type="monotone" 
                  dataKey="operating_income" 
                  name="영업이익" 
                  stroke="#10b981" 
                  strokeWidth={3}
                  dot={{ r: 6 }}
                />
                <Line 
                  type="monotone" 
                  dataKey="net_income" 
                  name="순이익" 
                  stroke="#8b5cf6" 
                  strokeWidth={3}
                  dot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* 재무 비율 */}
      {viewType === 'ratios' && ratios && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white p-6 rounded-lg border text-center">
              <div className="text-3xl font-bold text-red-600 mb-2">{ratios.debt_ratio}%</div>
              <div className="text-sm text-gray-600">부채비율</div>
              <div className="text-xs text-gray-500 mt-1">부채/자본</div>
            </div>
            <div className="bg-white p-6 rounded-lg border text-center">
              <div className="text-3xl font-bold text-green-600 mb-2">{ratios.equity_ratio}%</div>
              <div className="text-sm text-gray-600">자기자본비율</div>
              <div className="text-xs text-gray-500 mt-1">자본/자산</div>
            </div>
            <div className="bg-white p-6 rounded-lg border text-center">
              <div className="text-3xl font-bold text-blue-600 mb-2">{ratios.operating_margin}%</div>
              <div className="text-sm text-gray-600">영업이익률</div>
              <div className="text-xs text-gray-500 mt-1">영업이익/매출</div>
            </div>
            <div className="bg-white p-6 rounded-lg border text-center">
              <div className="text-3xl font-bold text-purple-600 mb-2">{ratios.net_margin}%</div>
              <div className="text-sm text-gray-600">순이익률</div>
              <div className="text-xs text-gray-500 mt-1">순이익/매출</div>
            </div>
          </div>
        </div>
      )}

      {/* 자산 구성 */}
      {viewType === 'assets' && latestData && assetComposition.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 자산 구성 파이차트 */}
          <div className="bg-white p-6 rounded-lg border">
            <h4 className="text-lg font-medium text-gray-800 mb-4">자본 구조</h4>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={assetComposition}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {assetComposition.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value: number) => {
                      if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조원`;
                      if (value >= 1e8) return `${(value / 1e8).toFixed(1)}억원`;
                      if (value >= 1e4) return `${(value / 1e4).toFixed(1)}만원`;
                      return `${value.toLocaleString()}원`;
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            {/* 범례 */}
            <div className="flex justify-center space-x-6 mt-4">
              {assetComposition.map((item, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <div 
                    className="w-4 h-4 rounded-full" 
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm text-gray-600">
                    {item.name} ({item.value >= 1e12
                      ? `${(item.value / 1e12).toFixed(1)}조원`
                      : item.value >= 1e8
                      ? `${(item.value / 1e8).toFixed(1)}억원`
                      : item.value >= 1e4
                      ? `${(item.value / 1e4).toFixed(1)}만원`
                      : `${item.value.toLocaleString()}원`})
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 재무 건전성 */}
          <div className="bg-white p-6 rounded-lg border">
            <h4 className="text-lg font-medium text-gray-800 mb-4">재무 상태</h4>
            <div className="space-y-4">
              <div className="border-b pb-4">
                <div className="text-sm text-gray-600 mb-2">총자산</div>
                <div className="text-2xl font-bold text-gray-800">
                  {latestData.total_assets >= 1e12
                    ? `${(latestData.total_assets / 1e12).toFixed(1)}조원`
                    : latestData.total_assets >= 1e8
                    ? `${(latestData.total_assets / 1e8).toFixed(1)}억원`
                    : `${latestData.total_assets.toLocaleString()}원`}
                </div>
              </div>
              <div className="border-b pb-4">
                <div className="text-sm text-gray-600 mb-2">부채</div>
                <div className="text-xl font-semibold text-red-600">
                  {latestData.total_liabilities >= 1e12
                    ? `${(latestData.total_liabilities / 1e12).toFixed(1)}조원`
                    : latestData.total_liabilities >= 1e8
                    ? `${(latestData.total_liabilities / 1e8).toFixed(1)}억원`
                    : `${latestData.total_liabilities.toLocaleString()}원`}
                </div>
              </div>
              <div>
                <div className="text-sm text-gray-600 mb-2">자본</div>
                <div className="text-xl font-semibold text-green-600">
                  {latestData.total_equity >= 1e12
                    ? `${(latestData.total_equity / 1e12).toFixed(1)}조원`
                    : latestData.total_equity >= 1e8
                    ? `${(latestData.total_equity / 1e8).toFixed(1)}억원`
                    : `${latestData.total_equity.toLocaleString()}원`}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
} 