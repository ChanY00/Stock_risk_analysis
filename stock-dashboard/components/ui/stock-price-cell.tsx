"use client"

import { Badge } from "@/components/ui/badge"
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip"
import { Clock, Calendar, Pause } from "lucide-react"

export interface StockPriceData {
  price: number
  change: number
  changePercent: number
  volume: number
  isRealTime: boolean
  isMarketClosed: boolean
  lastTradingDay?: string
  timestamp?: string
}

interface StockPriceCellProps {
  data: StockPriceData
  showBadge?: boolean
  compact?: boolean
}

export function StockPriceCell({ data, showBadge = true, compact = false }: StockPriceCellProps) {
  const formatPrice = (price: number) => {
    return price.toLocaleString('ko-KR')
  }
  
  const formatChange = (change: number, percent: number) => {
    const sign = change >= 0 ? '+' : ''
    const priceStr = `${sign}${change.toLocaleString('ko-KR')}`
    const percentStr = `${sign}${percent.toFixed(2)}%`
    return { priceStr, percentStr }
  }
  
  const getChangeColor = (change: number) => {
    if (change > 0) return 'text-red-600'
    if (change < 0) return 'text-blue-600'
    return 'text-gray-600'
  }
  
  const getChangeBgColor = (change: number) => {
    if (change > 0) return 'bg-red-50'
    if (change < 0) return 'bg-blue-50'
    return 'bg-gray-50'
  }
  
  const { priceStr, percentStr } = formatChange(data.change, data.changePercent)
  
  if (compact) {
    return (
      <div className="w-full text-right">
        <div className="inline-flex items-center gap-1">
          <span className="font-mono font-medium">
            {formatPrice(data.price)}원
          </span>
          {showBadge && data.isMarketClosed && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="secondary" className="text-xs p-1 cursor-help">
                    <Pause className="h-3 w-3" />
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="top">
                  <div className="text-xs">
                    <div className="font-medium">휴장</div>
                    {data.lastTradingDay && (
                      <div>마지막 거래일: {data.lastTradingDay}</div>
                    )}
                    <div>전일 종가 기준입니다</div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          {showBadge && data.isRealTime && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="default" className="bg-green-600 text-xs p-1 cursor-help">
                    <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="top">
                  <div className="text-xs">실시간 데이터</div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          {showBadge && !data.isMarketClosed && !data.isRealTime && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge variant="outline" className="text-xs p-1 cursor-help">
                    <Clock className="h-3 w-3" />
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="top">
                  <div className="text-xs">지연 데이터</div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
      </div>
    )
  }
  
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <span className="font-semibold text-lg">
          {formatPrice(data.price)}원
        </span>
        {showBadge && (
          <div>
            {data.isMarketClosed ? (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="secondary" className="cursor-help p-1.5">
                      <Pause className="h-3 w-3" />
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <div className="text-xs">
                      <div className="font-medium">휴장</div>
                      {data.lastTradingDay && (
                        <div>마지막 거래일: {data.lastTradingDay}</div>
                      )}
                      <div>전일 종가 기준입니다</div>
                    </div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : data.isRealTime ? (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="default" className="bg-green-600 p-1.5 cursor-help">
                      <div className="w-2 h-2 bg-white rounded-full animate-pulse" />
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <div className="text-xs">실시간 데이터</div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ) : (
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Badge variant="outline" className="p-1.5 cursor-help">
                      <Clock className="h-3 w-3" />
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    <div className="text-xs">지연 데이터</div>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            )}
          </div>
        )}
      </div>
      
      <div className={`flex items-center gap-2 p-2 rounded-md ${getChangeBgColor(data.change)}`}>
        <span className={`text-sm font-medium ${getChangeColor(data.change)}`}>
          {priceStr}원
        </span>
        <span className={`text-sm font-medium ${getChangeColor(data.change)}`}>
          ({percentStr})
        </span>
      </div>
      
      {/* 날짜와 업데이트 시간 표시 */}
      <div className="text-xs text-gray-500">
        {new Date().toLocaleDateString('ko-KR', {
          year: 'numeric',
          month: '2-digit',
          day: '2-digit'
        })} {new Date().toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit'
        })}
      </div>
    </div>
  )
} 