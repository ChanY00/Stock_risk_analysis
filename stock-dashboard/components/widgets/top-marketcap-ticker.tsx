'/* @ts-nocheck */'
'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { TrendingUp, TrendingDown } from 'lucide-react'

type TickerItem = {
  code: string
  name: string
  marketCap: number | null
}

type RealTimeMap = Record<string, {
  current_price?: number
  change_amount?: number
  change_percent?: number
  volume?: number
  timestamp?: string
}>

interface TopMarketCapTickerProps {
  items: TickerItem[]
  realtime?: RealTimeMap
  chunkSize?: number
  rotateMs?: number
}

export function TopMarketCapTicker({ items, realtime = {}, chunkSize = 5, rotateMs = 4000 }: TopMarketCapTickerProps) {
  const sorted = useMemo(() => {
    return items
      .slice()
      .filter((i) => i.marketCap && i.marketCap > 0)
      .sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))
      .slice(0, 30)
  }, [items])

  const [index, setIndex] = useState(0)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (sorted.length === 0) return
    if (intervalRef.current) clearInterval(intervalRef.current)
    intervalRef.current = setInterval(() => {
      setIndex((prev) => (prev + chunkSize) % Math.max(sorted.length, 1))
    }, rotateMs)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [sorted, chunkSize, rotateMs])

  const slice = useMemo(() => {
    if (sorted.length === 0) return []
    const end = index + chunkSize
    if (end <= sorted.length) return sorted.slice(index, end)
    // wrap-around
    const first = sorted.slice(index)
    const rest = sorted.slice(0, end - sorted.length)
    return [...first, ...rest]
  }, [sorted, index, chunkSize])

  const formatNumber = (num: number | null | undefined) => {
    if (num === null || num === undefined) return '-'
    return num.toLocaleString()
  }

  const getChangeColor = (pct: number | undefined) => {
    if (pct === undefined) return 'text-gray-500'
    return pct >= 0 ? 'text-red-600' : 'text-blue-600'
  }

  return (
    <div className="w-full bg-gray-50 dark:bg-gray-900/50 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-gray-700 dark:text-gray-300">시가총액 상위 30 (실시간)</div>
        <div className="text-xs text-gray-500">{index + 1}–{Math.min(index + chunkSize, 30)} / {Math.min(sorted.length, 30)}</div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        {slice.map((s) => {
          const rt = realtime[s.code] || {}
          const price = rt.current_price
          const pct = rt.change_percent
          const isUp = (pct || 0) >= 0
          return (
            <div key={s.code} className="flex items-center justify-between bg-white dark:bg-gray-800 rounded-md px-3 py-2 border border-gray-200 dark:border-gray-700 hover:shadow-sm transition">
              <div className="min-w-0">
                <div className="text-sm font-semibold text-gray-900 dark:text-white truncate">{s.name}</div>
                <div className="text-xs text-gray-500">{s.code}</div>
              </div>
              <div className="text-right ml-3">
                <div className="text-sm font-mono text-gray-900 dark:text-gray-100">{formatNumber(price)}</div>
                <div className={`text-xs font-semibold flex items-center justify-end gap-1 ${getChangeColor(pct)}`}>
                  {pct !== undefined ? (
                    <>
                      {isUp ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                      {(pct ?? 0) >= 0 ? '+' : ''}{(pct ?? 0).toFixed(2)}%
                    </>
                  ) : (
                    <span className="text-gray-400">-</span>
                  )}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}


