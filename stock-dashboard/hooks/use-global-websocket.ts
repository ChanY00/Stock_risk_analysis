'use client';

import { useWebSocketPrices, type StockPrice } from './use-websocket-prices';

export interface UseGlobalWebSocketOptions {
  stockCodes?: string[];
  autoSubscribe?: boolean;
}

export interface UseGlobalWebSocketReturn {
  data: Record<string, StockPrice>;
  loading: boolean;
  error: string | null;
  connected: boolean;
  lastUpdated: Date | null;
  refetch: () => void;
}

export function useGlobalWebSocket(options: UseGlobalWebSocketOptions = {}): UseGlobalWebSocketReturn {
  const { stockCodes = [], autoSubscribe = true } = options;
  
  const {
    prices,
    connectionStatus,
    lastUpdated,
    subscribe,
    unsubscribe,
  } = useWebSocketPrices({
    stockCodes,
    autoSubscribe,
  });

  const refetch = () => {
    if (stockCodes.length > 0) {
      // 재구독으로 데이터 갱신
      unsubscribe(stockCodes);
      setTimeout(() => subscribe(stockCodes), 100);
    }
  };

  return {
    data: prices,
    loading: connectionStatus.reconnecting,
    error: connectionStatus.error,
    connected: connectionStatus.connected,
    lastUpdated: lastUpdated || null,
    refetch,
  };
} 