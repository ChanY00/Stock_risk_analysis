// 실시간 주가 데이터 타입 정의
export interface RealTimePrice {
  code: string;
  name: string;
  current_price: number;
  change_amount: number;
  change_percent: number;
  volume: number;
  trading_value: number;
  market_cap: number;
  high_price: number;
  low_price: number;
  open_price: number;
  prev_close: number;
  timestamp: string;
}

// 호가 정보 타입
export interface OrderBookData {
  stock_code: string;
  bid_prices: Array<{ price: number; quantity: number }>;
  ask_prices: Array<{ price: number; quantity: number }>;
  total_bid_qty: number;
  total_ask_qty: number;
  timestamp: string;
}

// 차트 데이터 타입
export interface ChartData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export class RealTimeApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * 개별 종목 실시간 주가 조회
   */
  async getRealTimePrice(stockCode: string): Promise<RealTimePrice | null> {
    try {
      const response = await fetch(`${this.baseUrl}/stocks/real-time/${stockCode}/`);
      
      if (!response.ok) {
        console.error(`Failed to fetch real-time price for ${stockCode}:`, response.status);
        return null;
      }
      
      return await response.json();
    } catch (error) {
      console.error(`Error fetching real-time price for ${stockCode}:`, error);
      return null;
    }
  }

  /**
   * 여러 종목 실시간 주가 조회
   */
  async getMultipleRealTimePrices(stockCodes: string[]): Promise<Record<string, RealTimePrice>> {
    try {
      const codesParam = stockCodes.join(',');
      const response = await fetch(`${this.baseUrl}/stocks/real-time/multiple/?codes=${codesParam}`);
      
      if (!response.ok) {
        // 429 (Rate Limited) 처리
        if (response.status === 429) {
          const errorData = await response.json();
          console.warn(`⏱️ API Rate Limited: ${errorData.message}`);
          throw new Error(`API_RATE_LIMIT: ${errorData.message}`);
        }
        
        console.error('Failed to fetch multiple real-time prices:', response.status);
        return {};
      }
      
      const result = await response.json();
      
      // 새로운 응답 구조 처리
      if (result.data) {
        console.log(`📊 실시간 데이터: ${result.successful}/${result.total_requested}개 성공`);
        if (result.failed > 0) {
          console.warn(`⚠️ 실패한 종목: ${result.failed}개`);
        }
        return result.data;
      }
      
      // 이전 형식과의 호환성
      return result;
      
    } catch (error) {
      console.error('Error fetching multiple real-time prices:', error);
      
      // Rate limit 에러는 다시 던지기
      if (error instanceof Error && error.message?.includes('API_RATE_LIMIT')) {
        throw error;
      }
      
      return {};
    }
  }

  /**
   * KOSPI 200 전체 실시간 주가 조회
   */
  async getKospi200RealTimePrices(): Promise<{ data: Record<string, RealTimePrice>, count: number, timestamp: string }> {
    try {
      const response = await fetch(`${this.baseUrl}/stocks/real-time/kospi200/`);
      
      if (!response.ok) {
        console.error('Failed to fetch KOSPI 200 real-time prices:', response.status);
        return { data: {}, count: 0, timestamp: new Date().toISOString() };
      }
      
      return await response.json();
    } catch (error) {
      console.error('Error fetching KOSPI 200 real-time prices:', error);
      return { data: {}, count: 0, timestamp: new Date().toISOString() };
    }
  }

  /**
   * 일봉 차트 데이터 조회
   */
  async getDailyChartData(stockCode: string, period: 'D' | 'W' | 'M' = 'D'): Promise<ChartData[]> {
    try {
      const response = await fetch(`${this.baseUrl}/stocks/chart/${stockCode}/?period=${period}`);
      
      if (!response.ok) {
        console.error(`Failed to fetch chart data for ${stockCode}:`, response.status);
        return [];
      }
      
      return await response.json();
    } catch (error) {
      console.error(`Error fetching chart data for ${stockCode}:`, error);
      return [];
    }
  }

  /**
   * 호가 정보 조회
   */
  async getOrderBookData(stockCode: string): Promise<OrderBookData | null> {
    try {
      const response = await fetch(`${this.baseUrl}/stocks/orderbook/${stockCode}/`);
      
      if (!response.ok) {
        console.error(`Failed to fetch orderbook for ${stockCode}:`, response.status);
        return null;
      }
      
      return await response.json();
    } catch (error) {
      console.error(`Error fetching orderbook for ${stockCode}:`, error);
      return null;
    }
  }

  /**
   * 종목 검색
   */
  async searchStocks(keyword: string): Promise<Array<{
    code: string;
    name: string;
    market: string;
    sector: string;
    current_price: number;
    change_percent: number;
  }>> {
    try {
      const response = await fetch(`${this.baseUrl}/stocks/search/?keyword=${encodeURIComponent(keyword)}`);
      
      if (!response.ok) {
        console.error(`Failed to search stocks with keyword ${keyword}:`, response.status);
        return [];
      }
      
      return await response.json();
    } catch (error) {
      console.error(`Error searching stocks with keyword ${keyword}:`, error);
      return [];
    }
  }
}

// WebSocket 연결을 위한 클래스
export class RealTimeWebSocketClient {
  private ws: WebSocket | null = null;
  private url: string;
  private callbacks: Map<string, (data: any) => void> = new Map();
  private reconnectInterval: number = 5000;
  private maxReconnectAttempts: number = 5;
  private reconnectAttempts: number = 0;

  constructor(url: string = 'ws://localhost:8000/ws/stocks/') {
    this.url = url;
  }

  /**
   * WebSocket 연결
   */
  connect(): Promise<boolean> {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          resolve(true);
        };

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const { type, stock_code, ...payload } = data;
            
            const callbackKey = `${type}_${stock_code}`;
            const callback = this.callbacks.get(callbackKey);
            
            if (callback) {
              callback(payload);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = () => {
          console.log('WebSocket disconnected');
          this.handleReconnect();
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };

      } catch (error) {
        reject(error);
      }
    });
  }

  /**
   * 자동 재연결 처리
   */
  private handleReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
      
      setTimeout(() => {
        this.connect().catch(() => {
          console.error('Reconnection failed');
        });
      }, this.reconnectInterval);
    }
  }

  /**
   * 실시간 주가 구독
   */
  subscribeToPrice(stockCode: string, callback: (data: RealTimePrice) => void) {
    const message = {
      action: 'subscribe',
      type: 'price',
      stock_code: stockCode
    };

    this.callbacks.set(`price_${stockCode}`, callback);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  /**
   * 실시간 호가 구독
   */
  subscribeToOrderbook(stockCode: string, callback: (data: OrderBookData) => void) {
    const message = {
      action: 'subscribe',
      type: 'orderbook',
      stock_code: stockCode
    };

    this.callbacks.set(`orderbook_${stockCode}`, callback);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  /**
   * 구독 해제
   */
  unsubscribe(type: 'price' | 'orderbook', stockCode: string) {
    const message = {
      action: 'unsubscribe',
      type,
      stock_code: stockCode
    };

    this.callbacks.delete(`${type}_${stockCode}`);
    
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  /**
   * 연결 종료
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.callbacks.clear();
  }
}

// 싱글톤 인스턴스
export const realTimeApiClient = new RealTimeApiClient();
export default realTimeApiClient; 