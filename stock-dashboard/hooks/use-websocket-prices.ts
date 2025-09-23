'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

export interface StockPrice {
  stock_code: string;
  current_price: number;
  change_amount: number;
  change_percent: number;
  volume: number;
  trading_value: number;
  timestamp: string;
  source: string;
}

export interface ConnectionStatus {
  connected: boolean;
  reconnecting: boolean;
  error: string | null;
}

export interface UseWebSocketPricesOptions {
  stockCodes?: string[];
  autoSubscribe?: boolean;
}

interface UseWebSocketPricesReturn {
  prices: Record<string, StockPrice>;
  connectionStatus: ConnectionStatus;
  subscribe: (stockCodes: string[]) => void;
  unsubscribe: (stockCodes: string[]) => void;
  subscriptions: string[];
  data?: Record<string, StockPrice>;
  loading?: boolean;
  error?: string | null;
  connected?: boolean;
  lastUpdated?: Date | null;
  refetch?: () => void;
}

export function useWebSocketPrices(options: UseWebSocketPricesOptions = {}): UseWebSocketPricesReturn {
  const { stockCodes = [], autoSubscribe = true } = options;
  
  // stockCodes 배열을 안정화 (useMemo로 메모이제이션)
  const stableStockCodes = useMemo(() => {
    const filtered = stockCodes.filter(code => code && code.trim());
    return [...new Set(filtered)]; // 중복 제거
  }, [JSON.stringify(stockCodes.sort())]);
  
  const [prices, setPrices] = useState<Record<string, StockPrice>>({});
  const [subscriptions, setSubscriptions] = useState<string[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    connected: false,
    reconnecting: false,
    error: null,
  });
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const maxReconnectAttempts = 5;
  const pricesRef = useRef<Record<string, StockPrice>>({});
  const previousStockCodes = useRef<string[]>([]);
  
  // 성능 최적화를 위한 배치 업데이트
  const batchUpdateRef = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    pendingUpdates: Record<string, StockPrice>;
  }>({
    timer: null,
    pendingUpdates: {}
  });

  // 배치 업데이트 처리
  const WS_DEBUG: boolean = (() => {
    try {
      const val = (typeof globalThis !== 'undefined' && (globalThis as any).process?.env?.NEXT_PUBLIC_WS_DEBUG) as string | undefined
      return val === 'true'
    } catch {
      return false
    }
  })()

  const processBatchUpdate = useCallback(() => {
    if (Object.keys(batchUpdateRef.current.pendingUpdates).length > 0) {
      if (WS_DEBUG) console.log('🔄 Processing batch update:', batchUpdateRef.current.pendingUpdates);
      setPrices((prev: Record<string, StockPrice>): Record<string, StockPrice> => {
        const updated = { ...prev, ...batchUpdateRef.current.pendingUpdates };
        pricesRef.current = updated;
        setLastUpdated(new Date());
        if (WS_DEBUG) console.log('✅ Prices state updated:', updated);
        return updated;
      });
      batchUpdateRef.current.pendingUpdates = {};
    }
    batchUpdateRef.current.timer = null;
  }, []);

  // 개별 가격 업데이트를 배치에 추가
  const addToBatch = useCallback((stockPrice: StockPrice) => {
    if (WS_DEBUG) console.log('📦 Adding to batch:', stockPrice);
    batchUpdateRef.current.pendingUpdates[stockPrice.stock_code] = stockPrice;
    
    // 기존 타이머가 있으면 취소하고 새로 설정
    if (batchUpdateRef.current.timer) {
      clearTimeout(batchUpdateRef.current.timer);
    }
    
    // 100ms 후에 배치 업데이트 실행
    batchUpdateRef.current.timer = setTimeout(processBatchUpdate, 100);
  }, [processBatchUpdate]);

  const connectWebSocket = useCallback(() => {
    if (WS_DEBUG) console.log('🔌 Attempting to connect to WebSocket...');
    
    // 클라이언트 사이드에서만 실행되도록 체크
    if (typeof window === 'undefined') {
      if (WS_DEBUG) console.warn('⚠️ WebSocket connection attempted on server side');
      return;
    }
    
    // WebSocket 지원 확인
    if (typeof WebSocket === 'undefined') {
      console.error('❌ WebSocket is not supported by this browser');
      setConnectionStatus({
        connected: false,
        reconnecting: false,
        error: 'WebSocket is not supported by this browser',
      });
      return;
    }
    
    setConnectionStatus((prev: ConnectionStatus): ConnectionStatus => ({ ...prev, reconnecting: true, error: null }));

    try {
      const NODE_ENV: string = (() => {
        try { return ((globalThis as any).process?.env?.NODE_ENV) || 'development' } catch { return 'development' }
      })()
      const wsUrl = NODE_ENV === 'production' 
        ? 'wss://your-production-domain.com/ws/stocks/realtime/'
        : 'ws://localhost:8000/ws/stocks/realtime/';

      if (WS_DEBUG) {
        console.log('🌐 WebSocket URL:', wsUrl);
        console.log('🌍 Environment:', NODE_ENV);
        console.log('🔍 WebSocket constructor:', typeof WebSocket);
        console.log('🔍 Window object:', typeof window);
      }
      
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        if (WS_DEBUG) console.log('✅ WebSocket connected successfully');
        setConnectionStatus({
          connected: true,
          reconnecting: false,
          error: null,
        });
        reconnectAttemptsRef.current = 0;
      };

      ws.current.onmessage = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data);
          if (WS_DEBUG) console.log('📥 WebSocket received data:', data);

          switch (data.type) {
            case 'connection_status':
              if (WS_DEBUG) console.log('📡 Connection status:', data.message);
              if (data.subscribed_stocks && Array.isArray(data.subscribed_stocks)) {
        setSubscriptions(data.subscribed_stocks as string[]);
              }
              break;

            case 'subscribe_response':
              if (WS_DEBUG) console.log('📊 Subscription updated:', data.message);
              if (data.total_subscriptions && Array.isArray(data.total_subscriptions)) {
                setSubscriptions(data.total_subscriptions as string[]);
              }
              break;

            case 'unsubscribe_response':
              if (WS_DEBUG) console.log('📊 Unsubscription updated:', data.message);
              if (data.total_subscriptions && Array.isArray(data.total_subscriptions)) {
                setSubscriptions(data.total_subscriptions as string[]);
              }
              break;

            case 'price_update':
              if (WS_DEBUG) console.log('💰 Price update received:', data.data);
              if (data.data) {
                // 데이터 검증 로그
                const priceData = data.data;
                if (WS_DEBUG) console.log('🔍 Price data details:', {
                  stock_code: priceData.stock_code,
                  current_price: priceData.current_price,
                  change_amount: priceData.change_amount,
                  change_percent: priceData.change_percent,
                  volume: priceData.volume,
                  trading_value: priceData.trading_value,
                  timestamp: priceData.timestamp
                });
                addToBatch(data.data);
              }
              break;

            case 'batch_price_update':
              if (data.messages && Array.isArray(data.messages)) {
                // 배치 업데이트 처리
                const batchUpdates: Record<string, StockPrice> = {};
                data.messages.forEach((msg: any) => {
                  if (msg.data) {
                    batchUpdates[msg.data.stock_code] = msg.data;
                  }
                });
                
                if (Object.keys(batchUpdates).length > 0) {
                  setPrices((prev: Record<string, StockPrice>) => {
                    const updated = { ...prev, ...batchUpdates };
                    pricesRef.current = updated;
                    return updated;
                  });
                }
              }
              break;

            case 'error':
              console.error('❌ WebSocket error:', data.message);
              setConnectionStatus((prev: ConnectionStatus) => ({ ...prev, error: data.message }));
              break;

            default:
              if (WS_DEBUG) console.log('🔍 Unknown message type:', data.type);
          }
        } catch (error) {
          console.error('❌ Failed to parse WebSocket message:', error);
        }
      };

      ws.current.onclose = (event: CloseEvent) => {
        if (WS_DEBUG) console.log('🔌 WebSocket connection closed:', event.code, event.reason);
        if (WS_DEBUG) console.log('🔍 Close event details:', {
          code: event.code,
          reason: event.reason,
          wasClean: event.wasClean,
          type: event.type
        });
        
        setConnectionStatus((prev: ConnectionStatus): ConnectionStatus => ({ 
          ...prev, 
          connected: false,
          error: event.code !== 1000 ? `Connection closed: ${event.reason || 'Unknown reason'} (code: ${event.code})` : null
        }));

        // 자동 재연결 시도
        if (reconnectAttemptsRef.current < maxReconnectAttempts && event.code !== 1000) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);
          if (WS_DEBUG) console.log(`🔄 Attempting to reconnect in ${delay}ms... (${reconnectAttemptsRef.current + 1}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            reconnectAttemptsRef.current++;
            connectWebSocket();
          }, delay);
        } else {
          setConnectionStatus((prev: ConnectionStatus): ConnectionStatus => ({ 
            ...prev, 
            reconnecting: false,
            error: 'Failed to connect after multiple attempts'
          }));
        }
      };

      ws.current.onerror = (error: Event) => {
        console.error('❌ WebSocket error occurred:', error);
        console.error('🔍 Error event details:', {
          type: error.type,
          target: (error.target as WebSocket)?.readyState,
          currentState: ws.current?.readyState,
          url: wsUrl,
          timestamp: new Date().toISOString()
        });
        
        // 더 상세한 에러 메시지 생성
        let errorMessage = 'WebSocket connection error';
        if (ws.current) {
          switch (ws.current.readyState) {
            case WebSocket.CONNECTING:
              errorMessage = 'Failed to connect to WebSocket server (CONNECTING)';
              break;
            case WebSocket.OPEN:
              errorMessage = 'WebSocket error while connected (OPEN)';
              break;
            case WebSocket.CLOSING:
              errorMessage = 'WebSocket error while closing (CLOSING)';
              break;
            case WebSocket.CLOSED:
              errorMessage = 'WebSocket connection closed unexpectedly (CLOSED)';
              break;
          }
        }
        
        setConnectionStatus((prev: ConnectionStatus) => ({ 
          ...prev, 
          error: errorMessage
        }));
      };

    } catch (error) {
      console.error('❌ Failed to create WebSocket connection:', error);
      console.error('🔍 Creation error details:', {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        timestamp: new Date().toISOString()
      });
      
      setConnectionStatus({
        connected: false,
        reconnecting: false,
        error: `Failed to create WebSocket connection: ${error instanceof Error ? error.message : String(error)}`,
      });
    }
  }, [addToBatch]);

  const subscribe = useCallback((stockCodes: string[]) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const message = {
        action: 'subscribe',
        stock_codes: stockCodes,
      };
      ws.current.send(JSON.stringify(message));
      console.log('📤 Sent subscription request:', stockCodes);
    } else {
      console.warn('⚠️ WebSocket is not connected. Cannot subscribe.');
    }
  }, []);

  const unsubscribe = useCallback((stockCodes: string[]) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      const message = {
        action: 'unsubscribe',
        stock_codes: stockCodes,
      };
      ws.current.send(JSON.stringify(message));
      console.log('📤 Sent unsubscription request:', stockCodes);
    } else {
      console.warn('⚠️ WebSocket is not connected. Cannot unsubscribe.');
    }
  }, []);

  useEffect(() => {
    // 클라이언트 사이드에서만 실행
    if (typeof window !== 'undefined') {
      connectWebSocket();
    }

    return () => {
      // 클린업
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      
      if (batchUpdateRef.current.timer) {
        clearTimeout(batchUpdateRef.current.timer);
      }

      if (ws.current) {
        ws.current.close(1000, 'Component unmounting');
      }
    };
  }, [connectWebSocket]);

  // 자동 구독/해제 처리 (디바운싱 적용)
  useEffect(() => {
    if (!autoSubscribe || !connectionStatus.connected) {
      if (WS_DEBUG) console.log('🔕 Auto-subscribe skipped:', { 
        autoSubscribe, 
        connected: connectionStatus.connected,
        stockCodesLength: stableStockCodes.length 
      });
      return;
    }

    // 300ms 디바운싱 적용
    const timeoutId: ReturnType<typeof setTimeout> = setTimeout(() => {
      const currentCodes = stableStockCodes;
      const previousCodes = previousStockCodes.current;

      // 배열 내용 비교 (순서 무관)
      const currentSorted = [...currentCodes].sort();
      const previousSorted = [...previousCodes].sort();
      const isSame = JSON.stringify(currentSorted) === JSON.stringify(previousSorted);

      if (WS_DEBUG) console.log('🔍 Subscription check:', {
        currentCodes: currentCodes.slice(0, 3), // 처음 3개만 로그
        currentCodesLength: currentCodes.length,
        previousCodes: previousCodes.slice(0, 3), // 처음 3개만 로그
        previousCodesLength: previousCodes.length,
        same: isSame
      });

      // 동일하면 아무것도 하지 않음
      if (isSame) {
        if (WS_DEBUG) console.log('📍 No changes in stock codes, skipping subscription update');
        return;
      }

      // 새로 추가된 종목들 구독
      const toSubscribe = currentCodes.filter((code: string) => !previousCodes.includes(code));
      if (toSubscribe.length > 0) {
        if (WS_DEBUG) console.log('🔔 Auto-subscribing to:', toSubscribe.length, 'stocks:', toSubscribe.slice(0, 5));
        subscribe(toSubscribe);
      }

      // 제거된 종목들 구독 해제
      const toUnsubscribe = previousCodes.filter((code: string) => !currentCodes.includes(code));
      if (toUnsubscribe.length > 0) {
        if (WS_DEBUG) console.log('🔕 Auto-unsubscribing from:', toUnsubscribe.length, 'stocks:', toUnsubscribe.slice(0, 5));
        unsubscribe(toUnsubscribe);
      }

      // 이전 코드 업데이트
      previousStockCodes.current = currentCodes;
      if (WS_DEBUG) console.log('📝 Updated previousStockCodes to:', currentCodes.length, 'stocks');
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [stableStockCodes, connectionStatus.connected, autoSubscribe, subscribe, unsubscribe]);

  return {
    prices,
    connectionStatus,
    subscribe,
    unsubscribe,
    subscriptions,
    data: prices,
    loading: connectionStatus.reconnecting,
    error: connectionStatus.error,
    connected: connectionStatus.connected,
    lastUpdated,
    refetch: connectWebSocket,
  };
} 