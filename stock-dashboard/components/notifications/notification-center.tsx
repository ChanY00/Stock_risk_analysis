"use client"

import { useState, useEffect, useCallback } from 'react'
import { Bell, X, Settings, TrendingUp, TrendingDown, AlertTriangle, Target, LogIn } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Check, ChevronsUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Switch } from '@/components/ui/switch'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Alert, AlertDescription } from '@/components/ui/alert'

// API imports
import { stocksApi, alertApi, authApi, type Stock, type Alert as ApiAlert, type CreateAlertRequest } from '@/lib/api'

export interface PriceAlert {
  id: string
  stockCode: string
  stockName: string
  type: 'above' | 'below'
  targetPrice: number
  currentPrice: number
  isActive: boolean
  createdAt: Date
}

export interface Notification {
  id: string
  type: 'price_alert' | 'market' | 'system'
  title: string
  message: string
  timestamp: Date
  isRead: boolean
  priority: 'high' | 'medium' | 'low'
  data?: any
}

interface NotificationCenterProps {
  className?: string
}

export function NotificationCenter({ className = "" }: NotificationCenterProps) {
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [priceAlerts, setPriceAlerts] = useState<ApiAlert[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showCreateAlert, setShowCreateAlert] = useState(false)
  const [stocks, setStocks] = useState<Stock[]>([])
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  
  // 알림 설정
  const [notificationSettings, setNotificationSettings] = useState({
    priceAlerts: true,
    marketUpdates: false,
    systemNotifications: true
  })

  // 가격 알림 생성 폼
  const [alertForm, setAlertForm] = useState({
    stockCode: '',
    type: 'above' as 'above' | 'below',
    targetPrice: '',
    message: ''
  })

  // 종목 검색 상태
  const [stockSearchOpen, setStockSearchOpen] = useState(false)
  const [stockSearchValue, setStockSearchValue] = useState('')

  // 인증 상태 확인
  const checkAuthStatus = useCallback(async () => {
    try {
      const authStatus = await authApi.getStatus()
      setIsAuthenticated(authStatus.authenticated)
    } catch (error) {
      console.error('인증 상태 확인 실패:', error)
      setIsAuthenticated(false)
    }
  }, [])

  // 전체 종목 목록 로드
  const loadStocks = useCallback(async () => {
    try {
      setLoading(true)
      const stocksData = await stocksApi.getStocks()
      setStocks(stocksData.results)
    } catch (error) {
      console.error('종목 목록 로드 실패:', error)
      setError('종목 목록을 불러올 수 없습니다')
    } finally {
      setLoading(false)
    }
  }, [])

  // 알람 목록 로드
  const loadAlerts = useCallback(async () => {
    if (!isAuthenticated) return
    
    try {
      const alerts = await alertApi.getAlerts()
      setPriceAlerts(alerts)
    } catch (error) {
      console.error('알람 목록 로드 실패:', error)
    }
  }, [isAuthenticated])

  // 초기 로드
  useEffect(() => {
    checkAuthStatus()
    loadStocks()
  }, [checkAuthStatus, loadStocks])

  // 정기적으로 인증 상태 확인 (30초마다)
  useEffect(() => {
    const interval = setInterval(() => {
      checkAuthStatus()
    }, 30000) // 30초마다 확인

    return () => clearInterval(interval)
  }, [checkAuthStatus])

  // 로그아웃 이벤트 감지
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'logout-event') {
        setIsAuthenticated(false)
        setPriceAlerts([])
        setNotifications([])  // 일반 알림들도 초기화
        setError('')
      }
    }
    
    window.addEventListener('storage', handleStorageChange)
    
    // 같은 탭에서의 로그아웃 감지
    const handleLogoutEvent = () => {
      setIsAuthenticated(false)
      setPriceAlerts([])
      setNotifications([])  // 일반 알림들도 초기화
      setError('')
    }
    
    window.addEventListener('logout', handleLogoutEvent)
    
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('logout', handleLogoutEvent)
    }
  }, [])

  // 인증 상태 변경 시 알람 로드 및 정리
  useEffect(() => {
    if (isAuthenticated) {
      loadAlerts()
    } else {
      // 로그아웃 시 알람 목록 초기화
      setPriceAlerts([])
      setError('')
    }
  }, [isAuthenticated, loadAlerts])

  // 로컬 스토리지에서 데이터 로드
  useEffect(() => {
    const savedNotifications = localStorage.getItem('notifications')
    const savedSettings = localStorage.getItem('notification-settings')

    if (savedNotifications) {
      try {
        const parsed = JSON.parse(savedNotifications).map((n: any) => ({
          ...n,
          timestamp: new Date(n.timestamp)
        }))
        setNotifications(parsed)
      } catch (error) {
        console.error('Failed to load notifications:', error)
      }
    }

    if (savedSettings) {
      try {
        setNotificationSettings(JSON.parse(savedSettings))
      } catch (error) {
        console.error('Failed to load notification settings:', error)
      }
    }
  }, [])

  // 데이터 저장
  const saveNotifications = useCallback((newNotifications: Notification[]) => {
    setNotifications(newNotifications)
    localStorage.setItem('notifications', JSON.stringify(newNotifications))
  }, [])

  // 알림 추가
  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp' | 'isRead'>) => {
    const newNotification: Notification = {
      ...notification,
      id: Date.now().toString(),
      timestamp: new Date(),
      isRead: false
    }

    const updatedNotifications = [newNotification, ...notifications].slice(0, 100) // 최대 100개
    saveNotifications(updatedNotifications)

    // 브라우저 알림 (권한이 있는 경우)
    if (Notification.permission === 'granted') {
      new Notification(notification.title, {
        body: notification.message,
        icon: '/favicon.ico'
      })
    }
  }, [notifications, saveNotifications])

  // 가격 알림 생성
  const createPriceAlert = async () => {
    if (!isAuthenticated) {
      setError('알람 생성은 로그인이 필요합니다')
      return
    }

    if (!alertForm.stockCode || !alertForm.targetPrice) {
      setError('종목과 목표가를 모두 입력해주세요')
      return
    }

    const stock = stocks.find(s => s.stock_code === alertForm.stockCode)
    if (!stock) {
      setError('선택한 종목을 찾을 수 없습니다')
      return
    }

    try {
      setLoading(true)
      setError('')

             const alertData: CreateAlertRequest = {
         stock_code: alertForm.stockCode,
         condition: alertForm.type,
         target_price: parseFloat(alertForm.targetPrice),
         message: alertForm.message || `${stock.stock_name} 가격 알림`
       }

      await alertApi.createAlert(alertData)
      
      // 알람 목록 새로고침
      await loadAlerts()
      
      // 폼 초기화
      setAlertForm({ stockCode: '', type: 'above', targetPrice: '', message: '' })
      setShowCreateAlert(false)

      // 성공 알림
      addNotification({
        type: 'system',
        title: '가격 알림 생성됨',
        message: `${stock.stock_name} ${alertForm.type === 'above' ? '상승' : '하락'} 알림이 생성되었습니다.`,
        priority: 'low'
      })
    } catch (error: any) {
      console.error('알람 생성 실패:', error)
      setError(error.message || '알람 생성에 실패했습니다')
    } finally {
      setLoading(false)
    }
  }

  // 가격 알림 삭제
  const deletePriceAlert = async (alertId: number) => {
    if (!isAuthenticated) return

    // 낙관적 업데이트: 즉시 UI에서 제거
    const originalAlerts = [...priceAlerts]
    setPriceAlerts(prev => prev.filter(alert => alert.id !== alertId))
    
    try {
      await alertApi.deleteAlert(alertId)
      
      addNotification({
        type: 'system',
        title: '알림 삭제됨',
        message: '가격 알림이 삭제되었습니다.',
        priority: 'low'
      })
    } catch (error) {
      console.error('알람 삭제 실패:', error)
      // 실패 시 원래 상태로 복원
      setPriceAlerts(originalAlerts)
      setError('알림 삭제에 실패했습니다')
    }
  }

  // 알림 읽음 처리
  const markAsRead = (notificationId: string) => {
    const updatedNotifications = notifications.map(n => 
      n.id === notificationId ? { ...n, isRead: true } : n
    )
    saveNotifications(updatedNotifications)
  }

  // 모든 알림 읽음 처리
  const markAllAsRead = () => {
    const updatedNotifications = notifications.map(n => ({ ...n, isRead: true }))
    saveNotifications(updatedNotifications)
  }

  // 알림 삭제
  const deleteNotification = (notificationId: string) => {
    const updatedNotifications = notifications.filter(n => n.id !== notificationId)
    saveNotifications(updatedNotifications)
  }

  // 브라우저 알림 권한 요청
  useEffect(() => {
    if (Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  // 샘플 알림 생성 (개발용) - 로그인된 사용자에게만 표시
  useEffect(() => {
    if (notifications.length === 0 && isAuthenticated) {
      const sampleNotifications: Notification[] = [
        {
          id: '1',
          type: 'market',
          title: '시장 마감',
          message: 'KOSPI 2,650.25 (+1.2%), KOSDAQ 850.32 (+0.8%)',
          timestamp: new Date(Date.now() - 60000),
          isRead: false,
          priority: 'medium'
        },
        {
          id: '2',
          type: 'system',
          title: '시스템 업데이트',
          message: '새로운 차트 기능이 추가되었습니다.',
          timestamp: new Date(Date.now() - 300000),
          isRead: true,
          priority: 'low'
        }
      ]
      setNotifications(sampleNotifications)
    }
  }, [notifications.length, isAuthenticated])

  const unreadCount = notifications.filter(n => !n.isRead).length

  const getNotificationIcon = (type: Notification['type']) => {
    switch (type) {
      case 'price_alert':
        return <Target className="h-4 w-4" />
      case 'market':
        return <TrendingUp className="h-4 w-4" />
      case 'system':
        return <Settings className="h-4 w-4" />
      default:
        return <Bell className="h-4 w-4" />
    }
  }

  const getPriorityColor = (priority: Notification['priority']) => {
    switch (priority) {
      case 'high':
        return 'border-l-red-500'
      case 'medium':
        return 'border-l-yellow-500'
      case 'low':
        return 'border-l-gray-300'
      default:
        return 'border-l-gray-300'
    }
  }

  const formatTimeAgo = (date: Date) => {
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / (1000 * 60))
    const hours = Math.floor(diff / (1000 * 60 * 60))
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days > 0) return `${days}일 전`
    if (hours > 0) return `${hours}시간 전`
    if (minutes > 0) return `${minutes}분 전`
    return '방금 전'
  }

  return (
    <div className={className}>
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <Button variant="ghost" size="sm" className="relative">
            <Bell className="h-5 w-5" />
            {unreadCount > 0 && (
              <Badge 
                variant="destructive" 
                className="absolute -top-1 -right-1 h-5 w-5 rounded-full p-0 text-xs flex items-center justify-center"
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </Badge>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-96 p-0" align="end">
          <Card className="border-0 shadow-none">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">알림</CardTitle>
                <div className="flex gap-2">
                  {unreadCount > 0 && (
                    <Button variant="ghost" size="sm" onClick={markAllAsRead}>
                      모두 읽음
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => setShowSettings(true)}>
                    <Settings className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            
            <CardContent className="p-0">
              <div className="flex border-b">
                <Button 
                  variant="ghost" 
                  size="sm" 
                  className="flex-1 rounded-none"
                  onClick={() => {
                    if (!isAuthenticated) {
                      setError('알람 생성은 로그인이 필요합니다')
                      return
                    }
                    setShowCreateAlert(true)
                  }}
                >
                  <Target className="h-4 w-4 mr-2" />
                  가격 알림
                </Button>
              </div>

              {error && (
                <div className="p-4 border-b">
                  <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                </div>
              )}

              <ScrollArea className="h-96">
                {!isAuthenticated ? (
                  <div className="p-8 text-center text-gray-500">
                    <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p className="mb-4">로그인 후 알림을 확인할 수 있습니다</p>
                    <Button onClick={() => {
                      setIsOpen(false)
                      window.location.href = '/login'
                    }}>
                      로그인하러 가기
                    </Button>
                  </div>
                ) : notifications.length === 0 ? (
                  <div className="p-8 text-center text-gray-500">
                    <Bell className="h-12 w-12 mx-auto mb-4 opacity-50" />
                    <p>알림이 없습니다</p>
                  </div>
                ) : (
                  <div className="divide-y">
                    {notifications.map((notification) => (
                      <div
                        key={notification.id}
                        className={`p-4 hover:bg-gray-50 transition-colors cursor-pointer group border-l-4 ${getPriorityColor(notification.priority)} ${
                          notification.isRead ? 'opacity-75' : ''
                        }`}
                        onClick={() => markAsRead(notification.id)}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              {getNotificationIcon(notification.type)}
                              <span className={`font-medium text-sm ${notification.isRead ? 'text-gray-600' : 'text-gray-900'}`}>
                                {notification.title}
                              </span>
                              {!notification.isRead && (
                                <div className="w-2 h-2 bg-blue-500 rounded-full" />
                              )}
                            </div>
                            <p className={`text-sm ${notification.isRead ? 'text-gray-500' : 'text-gray-700'} mb-1`}>
                              {notification.message}
                            </p>
                            <p className="text-xs text-gray-400">
                              {formatTimeAgo(notification.timestamp)}
                            </p>
                          </div>
                          
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation()
                              deleteNotification(notification.id)
                            }}
                            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100"
                          >
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </ScrollArea>
            </CardContent>
          </Card>
        </PopoverContent>
      </Popover>

      {/* 가격 알림 생성 다이얼로그 */}
      <Dialog open={showCreateAlert} onOpenChange={setShowCreateAlert}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>가격 알림 생성</DialogTitle>
            <DialogDescription>
              {isAuthenticated 
                ? "관심 종목의 목표가 도달 시 알림을 받으세요" 
                : "가격 알림 생성을 위해서는 로그인이 필요합니다"
              }
            </DialogDescription>
          </DialogHeader>
          
          {!isAuthenticated ? (
            <div className="py-4 text-center">
              <LogIn className="h-12 w-12 mx-auto mb-4 text-gray-400" />
              <p className="text-gray-600 mb-4">로그인 후 가격 알림을 설정할 수 있습니다</p>
              <Button onClick={() => {
                setShowCreateAlert(false)
                window.location.href = '/login'
              }}>
                로그인하러 가기
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <Label>종목 선택</Label>
                <Popover open={stockSearchOpen} onOpenChange={setStockSearchOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      variant="outline"
                      role="combobox"
                      aria-expanded={stockSearchOpen}
                      className="w-full justify-between"
                    >
                      {alertForm.stockCode ? (
                        (() => {
                          const stock = stocks.find(s => s.stock_code === alertForm.stockCode)
                          return stock ? `${stock.stock_name} (${stock.stock_code})` : alertForm.stockCode
                        })()
                      ) : (
                        "종목을 검색하세요..."
                      )}
                      <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-full p-0">
                    <Command>
                      <CommandInput 
                        placeholder="종목명 또는 코드로 검색..." 
                        value={stockSearchValue}
                        onValueChange={setStockSearchValue}
                      />
                      <CommandList>
                        <CommandEmpty>
                          {loading ? "종목 목록을 불러오는 중..." : "검색 결과가 없습니다."}
                        </CommandEmpty>
                        <CommandGroup>
                          {stocks
                            .filter(stock => 
                              stock.stock_name.toLowerCase().includes(stockSearchValue.toLowerCase()) ||
                              stock.stock_code.toLowerCase().includes(stockSearchValue.toLowerCase())
                            )
                            .slice(0, 50) // 최대 50개만 표시 (성능 고려)
                            .map((stock) => (
                              <CommandItem
                                key={stock.stock_code}
                                value={`${stock.stock_name} ${stock.stock_code}`}
                                onSelect={() => {
                                  setAlertForm(prev => ({ ...prev, stockCode: stock.stock_code }))
                                  setStockSearchOpen(false)
                                  setStockSearchValue('')
                                  setError('') // 에러 초기화
                                }}
                              >
                                <Check
                                  className={cn(
                                    "mr-2 h-4 w-4",
                                    alertForm.stockCode === stock.stock_code ? "opacity-100" : "opacity-0"
                                  )}
                                />
                                <div className="flex flex-col">
                                  <span className="font-medium">{stock.stock_name}</span>
                                  <span className="text-sm text-gray-500">
                                    {stock.stock_code} - {stock.current_price?.toLocaleString()}원
                                  </span>
                                </div>
                              </CommandItem>
                            ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
              </div>
              <div>
                <Label>알림 조건</Label>
                <Select
                  value={alertForm.type}
                  onValueChange={(value: 'above' | 'below') => setAlertForm(prev => ({ ...prev, type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="above">목표가 이상</SelectItem>
                    <SelectItem value="below">목표가 이하</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>목표가 (원)</Label>
                <Input
                  type="number"
                  value={alertForm.targetPrice}
                  onChange={(e) => setAlertForm(prev => ({ ...prev, targetPrice: e.target.value }))}
                  placeholder="70000"
                />
              </div>
              <div>
                <Label>메모 (선택사항)</Label>
                <Input
                  value={alertForm.message}
                  onChange={(e) => setAlertForm(prev => ({ ...prev, message: e.target.value }))}
                  placeholder="알림 메모를 입력하세요"
                />
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateAlert(false)}>
              취소
            </Button>
            {isAuthenticated && (
              <Button onClick={createPriceAlert} disabled={loading}>
                {loading ? '생성 중...' : '생성'}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 설정 다이얼로그 */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>알림 설정</DialogTitle>
            <DialogDescription>
              받고 싶은 알림 유형을 선택하세요
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>가격 알림</Label>
              <Switch
                checked={notificationSettings.priceAlerts}
                onCheckedChange={(checked) => {
                  const newSettings = { ...notificationSettings, priceAlerts: checked }
                  setNotificationSettings(newSettings)
                  localStorage.setItem('notification-settings', JSON.stringify(newSettings))
                }}
              />
            </div>
            <div className="flex items-center justify-between">
              <Label>시장 업데이트</Label>
              <Switch
                checked={notificationSettings.marketUpdates}
                onCheckedChange={(checked) => {
                  const newSettings = { ...notificationSettings, marketUpdates: checked }
                  setNotificationSettings(newSettings)
                  localStorage.setItem('notification-settings', JSON.stringify(newSettings))
                }}
              />
            </div>
            <Separator />
            <div>
              <h4 className="font-medium mb-2">활성 가격 알림</h4>
              {!isAuthenticated ? (
                <p className="text-sm text-gray-500">로그인 후 알림을 확인할 수 있습니다</p>
              ) : priceAlerts.length === 0 ? (
                <p className="text-sm text-gray-500">설정된 가격 알림이 없습니다</p>
              ) : (
                <div className="space-y-2">
                  {priceAlerts.map((alert) => (
                    <div key={alert.id} className="flex items-center justify-between p-2 border rounded">
                      <div className="text-sm">
                        <span className="font-medium">{alert.stock_name}</span>
                        <span className="text-gray-500 ml-2">
                          {alert.condition === 'above' ? '≥' : '≤'} {alert.target_price.toLocaleString()}원
                        </span>
                        {!alert.is_active && (
                          <Badge variant="secondary" className="ml-2 text-xs">비활성</Badge>
                        )}
                        {alert.is_triggered && (
                          <Badge variant="destructive" className="ml-2 text-xs">발동됨</Badge>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deletePriceAlert(alert.id)}
                        className="h-6 w-6 p-0 text-red-500 hover:text-red-700"
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}