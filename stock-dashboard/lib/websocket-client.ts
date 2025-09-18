export interface RealTimePriceData {
  stock_code: string;
  current_price: number;
  change_amount: number;
  change_percent: number;
  volume: number;
  trading_value: number;
  timestamp: string;
  source: 'websocket';
}

export interface WebSocketMessage {
  type: 'connection_status' | 'price_update' | 'subscribe_response' | 'unsubscribe_response' | 'error' | 'subscriptions';
  data?: RealTimePriceData;
  subscribed_stocks?: string[];
  subscribed?: string[];
  unsubscribed?: string[];
  total_subscriptions?: string[];
  status?: string;
  message?: string;
  timestamp?: string;
}

export type PriceUpdateCallback = (data: RealTimePriceData) => void;
export type ConnectionStatusCallback = (connected: boolean, message?: string) => void;

export class RealTimeStockClient {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 3000; // 3초
  private isConnecting = false;
  
  // 콜백들
  private priceCallbacks: Map<string, PriceUpdateCallback[]> = new Map();
  private connectionCallbacks: ConnectionStatusCallback[] = [];
  private subscriptions: Set<string> = new Set();
  
  constructor(baseUrl: string = 'ws://localhost:8000') {
    this.url = `${baseUrl}/ws/stocks/realtime/`;
  }
  
  /**
   * WebSocket 연결
   */
  async connect(): Promise<boolean> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return true;
    }
    
    this.isConnecting = true;
    
    try {
      console.log('🔌 Connecting to real-time stock service...');
      
      this.ws = new WebSocket(this.url);
      
      this.ws.onopen = this.handleOpen.bind(this);
      this.ws.onmessage = this.handleMessage.bind(this);
      this.ws.onclose = this.handleClose.bind(this);
      this.ws.onerror = this.handleError.bind(this);
      
      // 연결 대기 (최대 5초)
      return new Promise((resolve) => {
        const timeout = setTimeout(() => {
          resolve(false);
        }, 5000);
        
        const checkConnection = () => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            clearTimeout(timeout);
            resolve(true);
          }
        };
        
        this.ws!.addEventListener('open', checkConnection);
      });
      
    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.isConnecting = false;
      return false;
    }
  }
  
  /**
   * 연결 해제
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.subscriptions.clear();
    this.priceCallbacks.clear();
    console.log('🔌 Disconnected from real-time stock service');
  }
  
  /**
   * 종목 구독
   */
  subscribe(stockCodes: string[], callback: PriceUpdateCallback): void {
    stockCodes.forEach(code => {
      if (!this.priceCallbacks.has(code)) {
        this.priceCallbacks.set(code, []);
      }
      this.priceCallbacks.get(code)!.push(callback);
    });
    
    if (this.isConnected()) {
      this.sendMessage({
        action: 'subscribe',
        stock_codes: stockCodes
      });
    } else {
      console.warn('WebSocket not connected, queuing subscription...');
      // 연결 후 자동으로 구독하도록 큐에 저장
      stockCodes.forEach(code => this.subscriptions.add(code));
    }
  }
  
  /**
   * 종목 구독 해제
   */
  unsubscribe(stockCodes: string[]): void {
    stockCodes.forEach(code => {
      this.priceCallbacks.delete(code);
      this.subscriptions.delete(code);
    });
    
    if (this.isConnected()) {
      this.sendMessage({
        action: 'unsubscribe',
        stock_codes: stockCodes
      });
    }
  }
  
  /**
   * 연결 상태 콜백 등록
   */
  onConnectionChange(callback: ConnectionStatusCallback): void {
    this.connectionCallbacks.push(callback);
  }
  
  /**
   * 현재 구독 목록 조회
   */
  getSubscriptions(): void {
    if (this.isConnected()) {
      this.sendMessage({ action: 'get_subscriptions' });
    }
  }
  
  /**
   * 연결 상태 확인
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }
  
  /**
   * 현재 구독 중인 종목 목록
   */
  getCurrentSubscriptions(): string[] {
    return Array.from(this.subscriptions);
  }
  
  // Private methods
  
  private handleOpen(): void {
    console.log('🟢 WebSocket connected successfully');
    this.isConnecting = false;
    this.reconnectAttempts = 0;
    
    // 연결 상태 콜백 호출
    this.connectionCallbacks.forEach(callback => 
      callback(true, 'Real-time service connected')
    );
    
    // 대기 중인 구독들 처리
    if (this.subscriptions.size > 0) {
      this.sendMessage({
        action: 'subscribe',
        stock_codes: Array.from(this.subscriptions)
      });
    }
  }
  
  private handleMessage(event: MessageEvent): void {
    try {
      const message: WebSocketMessage = JSON.parse(event.data);
      
      switch (message.type) {
        case 'connection_status':
          console.log('📱 Connection status:', message.message);
          if (message.subscribed_stocks) {
            message.subscribed_stocks.forEach(code => 
              this.subscriptions.add(code)
            );
          }
          break;
          
        case 'price_update':
          if (message.data) {
            this.handlePriceUpdate(message.data);
          }
          break;
          
        case 'subscribe_response':
          console.log('📊 Subscription response:', message.message);
          if (message.subscribed) {
            message.subscribed.forEach(code => 
              this.subscriptions.add(code)
            );
          }
          break;
          
        case 'unsubscribe_response':
          console.log('📊 Unsubscription response:', message.message);
          if (message.unsubscribed) {
            message.unsubscribed.forEach(code => 
              this.subscriptions.delete(code)
            );
          }
          break;
          
        case 'error':
          console.error('❌ WebSocket error:', message.message);
          break;
          
        case 'subscriptions':
          if (message.subscribed_stocks) {
            console.log('📋 Current subscriptions:', message.subscribed_stocks);
          }
          break;
      }
      
    } catch (error) {
      console.error('Error parsing WebSocket message:', error);
    }
  }
  
  private handlePriceUpdate(data: RealTimePriceData): void {
    const callbacks = this.priceCallbacks.get(data.stock_code);
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          console.error(`Error in price callback for ${data.stock_code}:`, error);
        }
      });
    }
  }
  
  private handleClose(event: CloseEvent): void {
    console.log('🟡 WebSocket connection closed:', event.code, event.reason);
    this.ws = null;
    this.isConnecting = false;
    
    // 연결 상태 콜백 호출
    this.connectionCallbacks.forEach(callback => 
      callback(false, 'Connection lost')
    );
    
    // 자동 재연결
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnect();
    } else {
      console.error('❌ Maximum reconnection attempts reached');
    }
  }
  
  private handleError(error: Event): void {
    console.error('🔴 WebSocket error:', error);
    this.isConnecting = false;
  }
  
  private reconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * this.reconnectAttempts;
    
    console.log(`🔄 Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    
    setTimeout(() => {
      this.connect();
    }, delay);
  }
  
  private sendMessage(message: any): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('Cannot send message: WebSocket not connected');
    }
  }
}

// 싱글톤 인스턴스
export const realTimeClient = new RealTimeStockClient(); 

// Market indices WebSocket client (KOSPI/KOSDAQ)
export type MarketIndicesCallback = (data: {
  market_summary: Record<string, {
    current: number; change: number; change_percent: number; volume: number; high: number; low: number; trade_value: number;
  }>;
}) => void;

// MarketIndicesClient removed: REST polling is used instead of WS