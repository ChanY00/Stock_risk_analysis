"use client"

import { useState, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Clock, Calendar, Info, TrendingUp, Pause } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { stocksApi } from "@/lib/api"

export interface MarketStatus {
  isOpen: boolean
  status: string
  reason: string
  currentTime: string
  lastTradingDay?: string
  nextTradingDay?: string
  marketHours: {
    open: string
    close: string
  }
}

interface MarketStatusIndicatorProps {
  status?: MarketStatus
  showDetails?: boolean
  variant?: "compact" | "detailed" | "badge"
  className?: string
}

// 마지막 거래일 계산 헬퍼 함수 (주말 제외, 공휴일은 백엔드에서 처리)
const getLastTradingDay = (): string => {
  const now = new Date()
  const koreanTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }))
  let checkDate = new Date(koreanTime)
  
  // 오늘이 평일이고 15:30 이후면 오늘이 마지막 거래일
  const currentHour = checkDate.getHours()
  const currentMinute = checkDate.getMinutes()
  const dayOfWeek = checkDate.getDay()
  
  if (dayOfWeek >= 1 && dayOfWeek <= 5 && (currentHour > 15 || (currentHour === 15 && currentMinute >= 30))) {
    return checkDate.toISOString().split('T')[0]
  }
  
  // 그 외의 경우 이전 평일 찾기
  for (let i = 0; i < 10; i++) {
    checkDate.setDate(checkDate.getDate() - 1)
    const dayOfWeek = checkDate.getDay()
    
    // 주말이 아니면 거래일로 가정
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      return checkDate.toISOString().split('T')[0]
    }
  }
  
  return koreanTime.toISOString().split('T')[0]
}

// 다음 거래일 계산 헬퍼 함수 (주말 제외, 공휴일은 백엔드에서 처리)
const getNextTradingDay = (): string => {
  const now = new Date()
  const koreanTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }))
  let checkDate = new Date(koreanTime)
  
  // 최대 10일 후까지 확인
  for (let i = 0; i < 10; i++) {
    checkDate.setDate(checkDate.getDate() + 1)
    const dayOfWeek = checkDate.getDay()
    
    // 주말이 아니면 거래일로 가정
    if (dayOfWeek !== 0 && dayOfWeek !== 6) {
      return checkDate.toISOString().split('T')[0]
    }
  }
  
  return koreanTime.toISOString().split('T')[0]
}

export function MarketStatusIndicator({ 
  status, 
  showDetails = true, 
  variant = "detailed",
  className = "" 
}: MarketStatusIndicatorProps) {
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(status || null)
  const [loading, setLoading] = useState(false)
  
  useEffect(() => {
    // 백엔드에서 실제 시장 상태 가져오기
    const fetchMarketStatus = async () => {
      if (status) return // prop으로 전달된 상태가 있으면 사용
      
      try {
        setLoading(true)
        const response = await stocksApi.getMarketStatus()
        
        // 백엔드 응답을 컴포넌트 인터페이스에 맞게 변환
        const lastTradingDay = response.is_open 
          ? undefined 
          : getLastTradingDay()
        
        const nextTradingDay = !response.is_open && response.next_open
          ? new Date(response.next_open).toISOString().split('T')[0]
          : getNextTradingDay()
        
        setMarketStatus({
          isOpen: response.is_open,
          status: response.status,
          reason: response.message,
          currentTime: response.current_time_str,
          lastTradingDay,
          nextTradingDay,
          marketHours: {
            open: "09:00",
            close: "15:30"
          }
        })
      } catch (error) {
        console.error("시장 상태 조회 실패:", error)
        // 폴백: 클라이언트 측 계산
        const now = new Date()
        const koreanTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }))
        const currentHour = koreanTime.getHours()
        const currentMinute = koreanTime.getMinutes()
        const dayOfWeek = koreanTime.getDay()
        
        const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5
        const isMarketHours = currentHour >= 9 && (currentHour < 15 || (currentHour === 15 && currentMinute <= 30))
        const isOpen = isWeekday && isMarketHours
        
        let statusText = ""
        let reason = ""
        
        if (isOpen) {
          statusText = "개장"
          reason = "정규장 시간"
        } else if (isWeekday) {
          if (currentHour < 9) {
            statusText = "장 시작 전"
            reason = `장 시작까지 ${9 - currentHour}시간 ${60 - currentMinute}분`
          } else {
            statusText = "장 마감"
            reason = "정규장 종료"
          }
        } else if (dayOfWeek === 6) {
          statusText = "휴장"
          reason = "토요일"
        } else if (dayOfWeek === 0) {
          statusText = "휴장"
          reason = "일요일"
        }
        
        setMarketStatus({
          isOpen,
          status: statusText,
          reason,
          currentTime: koreanTime.toLocaleString("ko-KR", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit"
          }),
          lastTradingDay: getLastTradingDay(),
          nextTradingDay: getNextTradingDay(),
          marketHours: {
            open: "09:00",
            close: "15:30"
          }
        })
      } finally {
        setLoading(false)
      }
    }
    
    // 초기 로드
    fetchMarketStatus()
    
    // 1분마다 시장 상태 업데이트
    const interval = setInterval(fetchMarketStatus, 60000)
    
    return () => clearInterval(interval)
  }, [status])
  
  const currentStatus = status || marketStatus
  
  if (!currentStatus) {
    return null
  }
  
  const getStatusColor = () => {
    if (currentStatus.isOpen) {
      return "bg-green-500"
    } else if (currentStatus.status === "장 시작 전") {
      return "bg-yellow-500"
    } else {
      return "bg-gray-500"
    }
  }
  
  const getStatusIcon = () => {
    if (currentStatus.isOpen) {
      return <TrendingUp className="h-4 w-4" />
    } else if (currentStatus.status === "장 시작 전") {
      return <Clock className="h-4 w-4" />
    } else {
      return <Pause className="h-4 w-4" />
    }
  }
  
  const getStatusBadgeVariant = () => {
    if (currentStatus.isOpen) {
      return "default"
    } else if (currentStatus.status === "장 시작 전") {
      return "secondary"
    } else {
      return "outline"
    }
  }
  
  // Badge 형태
  if (variant === "badge") {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Badge 
              variant={getStatusBadgeVariant()} 
              className={`${className} cursor-help`}
            >
              <div className={`w-2 h-2 rounded-full mr-2 ${getStatusColor()}`} />
              {currentStatus.status}
            </Badge>
          </TooltipTrigger>
          <TooltipContent side="bottom" className="max-w-xs bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700">
            <div className="text-sm">
              <div className="font-medium text-gray-900 dark:text-gray-100">{currentStatus.reason}</div>
              <div className="text-gray-600 dark:text-gray-400 mt-1">
                현재 시간: {currentStatus.currentTime.replace(/\s*UTC\+09:00/g, '').trim()}
              </div>
              <div className="text-gray-600 dark:text-gray-400">
                운영시간: {currentStatus.marketHours.open} - {currentStatus.marketHours.close}
              </div>
              {!currentStatus.isOpen && currentStatus.lastTradingDay && (
                <div className="text-gray-600 dark:text-gray-400">
                  마지막 거래일: {currentStatus.lastTradingDay}
                </div>
              )}
              {!currentStatus.isOpen && currentStatus.nextTradingDay && (
                <div className="text-gray-600 dark:text-gray-400">
                  다음 거래일: {currentStatus.nextTradingDay}
                </div>
              )}
            </div>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }
  
  // Compact 형태
  if (variant === "compact") {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <div className={`w-3 h-3 rounded-full ${getStatusColor()} ${currentStatus.isOpen ? 'animate-pulse' : ''}`} />
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">
          {currentStatus.status}
        </span>
        <span className="text-xs text-gray-500 dark:text-gray-400">
          {currentStatus.reason}
        </span>
      </div>
    )
  }
  
  // Detailed 형태 (기본값)
  return (
    <Card className={`${className}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <h3 className="font-semibold text-lg text-gray-900 dark:text-gray-100">시장 상태</h3>
          </div>
          <Badge variant={getStatusBadgeVariant()}>
            <div className={`w-2 h-2 rounded-full mr-2 ${getStatusColor()} ${currentStatus.isOpen ? 'animate-pulse' : ''}`} />
            {currentStatus.status}
          </Badge>
        </div>
        
        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-gray-400 dark:text-gray-500" />
            <span className="text-gray-700 dark:text-gray-300">{currentStatus.reason}</span>
          </div>
          
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-gray-400 dark:text-gray-500" />
            <span className="text-gray-700 dark:text-gray-300">현재 시간: {currentStatus.currentTime.replace(/\s*UTC\+09:00/g, '').trim()}</span>
          </div>
          
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400 dark:text-gray-500" />
            <span className="text-gray-700 dark:text-gray-300">운영시간: {currentStatus.marketHours.open} - {currentStatus.marketHours.close}</span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
} 