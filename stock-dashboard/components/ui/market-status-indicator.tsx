"use client"

import { useState, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Clock, Calendar, Info, TrendingUp, Pause } from "lucide-react"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"

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

// 시장 상태를 가져오는 함수 (실제로는 API 호출)
const getMarketStatus = (): MarketStatus => {
  const now = new Date()
  const koreanTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }))
  const currentHour = koreanTime.getHours()
  const currentMinute = koreanTime.getMinutes()
  const dayOfWeek = koreanTime.getDay() // 0: 일요일, 1-5: 평일, 6: 토요일
  
  // 평일 9:00-15:30 체크
  const isWeekday = dayOfWeek >= 1 && dayOfWeek <= 5
  const isMarketHours = currentHour >= 9 && (currentHour < 15 || (currentHour === 15 && currentMinute <= 30))
  const isOpen = isWeekday && isMarketHours
  
  let status = ""
  let reason = ""
  
  if (isOpen) {
    status = "개장"
    reason = "정규장 시간"
  } else if (isWeekday) {
    if (currentHour < 9) {
      status = "장 시작 전"
      reason = `장 시작까지 ${9 - currentHour}시간 ${60 - currentMinute}분`
    } else {
      status = "장 마감"
      reason = "정규장 종료"
    }
  } else if (dayOfWeek === 6) {
    status = "휴장"
    reason = "토요일"
  } else if (dayOfWeek === 0) {
    status = "휴장"
    reason = "일요일"
  } else {
    status = "휴장"
    reason = "공휴일"
  }
  
  return {
    isOpen,
    status,
    reason,
    currentTime: koreanTime.toLocaleString("ko-KR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit"
    }),
    lastTradingDay: "2025-01-06",
    nextTradingDay: "2025-01-07",
    marketHours: {
      open: "09:00",
      close: "15:30"
    }
  }
}

export function MarketStatusIndicator({ 
  status, 
  showDetails = true, 
  variant = "detailed",
  className = "" 
}: MarketStatusIndicatorProps) {
  const [marketStatus, setMarketStatus] = useState<MarketStatus | null>(status || null)
  
  useEffect(() => {
    // 초기 상태 설정
    if (!status) {
      setMarketStatus(getMarketStatus())
    }
    
    // 1분마다 시장 상태 업데이트
    const interval = setInterval(() => {
      if (!status) {
        setMarketStatus(getMarketStatus())
      }
    }, 60000)
    
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
                현재 시간: {currentStatus.currentTime}
              </div>
              <div className="text-gray-600 dark:text-gray-400">
                운영시간: {currentStatus.marketHours.open} - {currentStatus.marketHours.close}
              </div>
              {!currentStatus.isOpen && currentStatus.lastTradingDay && (
                <div className="text-gray-600 dark:text-gray-400">
                  마지막 거래일: {currentStatus.lastTradingDay}
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
            <span className="text-gray-700 dark:text-gray-300">현재 시간: {currentStatus.currentTime}</span>
          </div>
          
          <div className="flex items-center gap-2">
            <Calendar className="h-4 w-4 text-gray-400 dark:text-gray-500" />
            <span className="text-gray-700 dark:text-gray-300">운영시간: {currentStatus.marketHours.open} - {currentStatus.marketHours.close}</span>
          </div>
          
          {!currentStatus.isOpen && currentStatus.lastTradingDay && showDetails && (
            <div className="mt-3 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
              <div className="flex items-center gap-2 text-yellow-800 dark:text-yellow-200">
                <Info className="h-4 w-4" />
                <span className="font-medium">휴장일 안내</span>
              </div>
              <div className="mt-1 text-sm text-yellow-700 dark:text-yellow-300">
                현재 표시되는 주가는 마지막 거래일({currentStatus.lastTradingDay})의 종가입니다.
              </div>
              {currentStatus.nextTradingDay && (
                <div className="text-sm text-yellow-700 dark:text-yellow-300">
                  다음 거래일: {currentStatus.nextTradingDay}
                </div>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
} 