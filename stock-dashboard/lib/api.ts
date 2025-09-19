// API Configuration - 환경에 따른 동적 URL 설정

const getApiBaseUrl = (): string => {
  // 브라우저 환경에서는 환경변수 또는 localhost 사용
  if (typeof window !== "undefined") {
    return process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
  }

  // 서버 환경(SSR, API Routes)에서는 내부 URL 사용
  return (
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000/api"
  );
};

const API_BASE_URL = getApiBaseUrl();

// CSRF 토큰 관리
const getCsrfToken = (): string | null => {
  if (typeof document === "undefined") return null;

  const cookie = document.cookie
    .split("; ")
    .find((row) => row.startsWith("csrftoken="));

  return cookie ? cookie.split("=")[1] : null;
};

// Authentication Types
export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  date_joined: string;
}

export interface AuthResponse {
  message: string;
  user: User;
}

export interface AuthStatus {
  authenticated: boolean;
  user: User | null;
}

export interface RegisterData {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  first_name?: string;
  last_name?: string;
}

export interface LoginData {
  username: string;
  password: string;
}

// Stock Types
export interface Stock {
  stock_code: string;
  stock_name: string;
  market: string;
  sector: string;
  current_price: number;
  market_cap: number;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  dividend_yield: number | null;
  volatility?: number | null;
  monthly_return?: number | null;
}

export interface StockDetail extends Stock {
  financial_data?: FinancialData; // 단일 객체로 수정
  price_history?: PriceData[];
  technical_indicators?: TechnicalIndicators;
  price_data?: {
    // 추가 가격 데이터
    date: string;
    open_price: number;
    high_price: number;
    low_price: number;
    close_price: number;
    volume: number;
  };
}

export interface FinancialData {
  year: number;
  revenue: number;
  operating_income: number;
  net_income: number;
  eps: number;
  total_assets?: number;
  total_liabilities?: number;
  total_equity?: number;
}

export interface PriceData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface TechnicalIndicators {
  ma5: number | null;
  ma20: number | null;
  ma60: number | null;
  rsi: number | null;
  macd: number | null;
  macd_signal: number | null;
  macd_histogram: number | null;
  bollinger_upper: number | null;
  bollinger_middle: number | null;
  bollinger_lower: number | null;
  stochastic_k: number | null;
  stochastic_d: number | null;
}

export interface SentimentAnalysis {
  stock_code: string;
  stock_name: string;
  updated_at: string;
  positive: string | number;
  negative: string | number;
  top_keywords: string;
  neutral?: string | number;
  sentiment_score?: number;

  dominant_sentiment?: "positive" | "negative" | "neutral";
  keyword_array?: string[];
}

// 최근 N일 감정 추이 데이터 타입
export interface SentimentTrendData {
  date: string;
  positive: number;
  negative: number;
  neutral?: number;
  sentiment_score: number; // -1 ~ 1 범위
  total_posts?: number;
}

export interface MarketOverview {
  market_summary: {
    [key: string]: {
      current: number;
      change: number;
      change_percent: number;
      volume: number;
      high: number;
      low: number;
      trade_value: number;
    };
  };
  sector_performance: {
    sector: string;
    change_percent: number;
    top_performer: {
      name: string;
      code: string;
      change_percent: number;
    };
  }[];
}

export interface StockAnalysis {
  stock_code: string;
  stock_name: string;
  technical_indicators: TechnicalIndicators | null;
  sentiment_analysis?: SentimentAnalysis | null;
  fundamental_analysis: {
    per_rank?: number;
    pbr_rank?: number;
    roe_rank?: number;
    dividend_yield_rank?: number;
    overall_rank?: number;
  };
}

export interface FinancialAnalysis {
  stock_code: string;
  stock_name: string;
  financials: { [year: string]: FinancialData };
}

export interface ClusterData {
  name: string;
  code: string;
  x: number;
  y: number;
  cluster: number;
  isTarget: boolean;
  sector?: string;
  current_price?: number;
  per?: number | null;
  pbr?: number | null;
  roe?: number | null;
}

export interface SimilarStock {
  stock_code: string;
  stock_name: string;
  sector: string;
  current_price: number;
  per: number | null;
  pbr: number | null;
  roe: number | null;
  market_cap: number;
}

export interface WatchlistItem {
  stock_code: string;
  stock_name: string;
  current_price: number;
  change_percent?: number | null;
  market: string;
  sector: string;
  market_cap?: number;
  per?: number | null;
  pbr?: number | null;
  roe?: number | null;
  dividend_yield?: number | null;
}

export interface WatchlistResponse {
  success: boolean;
  message: string;
  data?: WatchlistItem[];
}

// Portfolio Types
export interface Portfolio {
  id: number;
  name: string;
  description?: string;
  holdings_count: number;
  total_investment: number;
  current_value: number;
  total_profit_loss: number;
  total_profit_loss_percent: number;
  holdings: PortfolioHolding[];
  created_at: string;
  updated_at: string;
}

export interface PortfolioHolding {
  id: number;
  stock_code: string;
  stock_name: string;
  sector?: string;
  market?: string;
  quantity: number;
  average_price: number;
  current_price: number;
  weight: number;
  total_investment: number;
  current_value: number;
  profit_loss: number;
  profit_loss_percent: number;
  created_at: string;
  updated_at: string;
}

export interface CreatePortfolioRequest {
  name: string;
  description?: string;
}

export interface CreateHoldingRequest {
  stock_code: string;
  quantity: number;
  average_price: number;
}

export interface Alert {
  id: number;
  stock: string;
  stock_name: string;
  condition: "above" | "below";
  target_price: number;
  is_active: boolean;
  message: string;
  is_triggered: boolean;
  created_at: string;
  triggered_at: string | null;
}

export interface CreateAlertRequest {
  stock_code: string;
  condition: "above" | "below";
  target_price: number;
  message?: string;
}

// 클러스터링 관련 타입들
export interface ClusterAnalysis {
  cluster_type: "spectral" | "agglomerative";
  cluster_id: number;
  cluster_name: string;
  description: string;
  dominant_sectors: string[];
  stock_count: number;
  avg_market_cap: number | null;
  avg_per: number | null;
  avg_pbr: number | null;
  characteristics: {
    sector_distribution: Record<string, number>;
    market_cap_range: {
      min: number | null;
      max: number | null;
    };
  };
}

export interface ClusterOverview {
  cluster_type: "spectral" | "agglomerative";
  total_clusters: number;
  clusters: ClusterAnalysis[];
}

export interface ClusterStocks {
  cluster_analysis: ClusterAnalysis;
  stocks: Stock[];
  similar_clusters: ClusterAnalysis[];
}

export interface StockClusterInfo {
  stock_code: string;
  stock_name: string;
  clusters: {
    spectral: {
      cluster_id: number;
      cluster_name: string;
      cluster_analysis: ClusterAnalysis;
    } | null;
    agglomerative: {
      cluster_id: number;
      cluster_name: string;
      cluster_analysis: ClusterAnalysis;
    } | null;
  };
}

export interface SimilarStocks {
  base_stock: {
    stock_code: string;
    stock_name: string;
    sector: string;
  };
  cluster_type: "spectral" | "agglomerative";
  similar_stocks: Stock[];
}

// AI Report type
export interface AIReport {
  investment_opinion: "매수 타이밍" | "매도 타이밍" | "관망";
  financial_analysis: string;
  technical_analysis: string;
  sentiment_analysis: string;
  recommendation: {
    stock_name: string;
    reason: string;
  };
  // optional: multiple recommendations
  recommendations?: Array<{
    stock_name: string;
    reason: string;
  }>;
  excluded_sections?: string[];
}

// API Utility Class
class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    requireAuth: boolean = false
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;

    // 디버그 로깅 추가
    console.log(`🔗 API 요청: ${options.method || "GET"} ${url}`);

    // CSRF 토큰 처리
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    // POST 요청에 CSRF 토큰 추가
    if (
      options.method === "POST" ||
      options.method === "PUT" ||
      options.method === "DELETE"
    ) {
      const csrfToken = getCsrfToken();
      if (csrfToken) {
        headers["X-CSRFToken"] = csrfToken;
        console.log(`🔐 CSRF 토큰 추가: ${csrfToken.substring(0, 8)}...`);
      }
    }

    const config: RequestInit = {
      headers,
      credentials: "include",
      ...options,
    };

    try {
      const response = await fetch(url, config);
      // 응답 상태 로깅
      console.log(
        `📡 API 응답: ${response.status} ${response.statusText} - ${url}`
      );

      // 비회원 접근 시 인증 오류나 404 무시 (특정 엔드포인트)
      if (!response.ok && !requireAuth) {
        if (response.status === 401 || response.status === 404) {
          // 비회원도 접근 가능한 API의 경우 기본값 반환
          if (endpoint.includes("/watchlist/")) {
            console.log(`⚠️ Watchlist API 404/401 오류 - 빈 배열 반환: ${url}`);
            return [] as T;
          }
          if (endpoint.includes("/auth/status/")) {
            console.log(
              `⚠️ Auth Status API 404/401 오류 - 기본값 반환: ${url}`
            );
            return { authenticated: false, user: null } as T;
          }
          if (endpoint.includes("/market-overview/")) {
            console.log(
              `⚠️ Market Overview API 404/401 오류 - 기본값 반환: ${url}`
            );
            return {
              market_summary: {},
              sector_performance: [],
            } as T;
          }
          if (endpoint.includes("/sentiment/")) {
            console.log(`⚠️ Sentiment API 404 오류 - null 반환: ${url}`);
            return null as T;
          }
        }
      }
      if (!response.ok) {
        console.error(
          `❌ API 오류: ${response.status} ${response.statusText} - ${url}`
        );
        if (
          response.headers.get("content-type")?.includes("application/json")
        ) {
          const errorData = await response.json();

          // Django REST Framework 에러 형식 처리
          let errorMessage = "";
          if (
            errorData.non_field_errors &&
            Array.isArray(errorData.non_field_errors)
          ) {
            errorMessage = errorData.non_field_errors[0];
          } else if (errorData.detail) {
            errorMessage = errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          } else if (typeof errorData === "string") {
            errorMessage = errorData;
          } else {
            // 필드별 에러 처리
            const fieldErrors = Object.values(errorData).flat();
            errorMessage =
              Array.isArray(fieldErrors) && fieldErrors.length > 0
                ? (fieldErrors[0] as string)
                : `HTTP error! status: ${response.status}`;
          }
          throw new Error(errorMessage);
        } else {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
      }

      // DELETE 요청의 경우 빈 응답 처리
      if (options.method === "DELETE" && response.status === 204) {
        console.log(`✅ API 성공: ${url} (빈 응답)`);
        return undefined as T;
      }

      // 응답 내용이 있는 경우에만 JSON 파싱

      const contentType = response.headers.get("content-type");
      if (contentType && contentType.includes("application/json")) {
        const data = await response.json();
        console.log(`✅ API 성공: ${url}`, data);
        return data;
      } else {
        console.log(`✅ API 성공: ${url} (비JSON 응답)`);
        return undefined as T;
      }
    } catch (error) {
      console.error(`💥 API 요청 실패: ${url}`, error);
      // 비회원 접근이 허용된 API에서 네트워크 오류 시 기본값 반환
      if (!requireAuth) {
        if (endpoint.includes("/watchlist/")) {
          return [] as T;
        }
        if (endpoint.includes("/auth/status/")) {
          return { authenticated: false, user: null } as T;
        }
        if (endpoint.includes("/market-overview/")) {
          return {
            market_summary: {},
            sector_performance: [],
          } as T;
        }
        if (endpoint.includes("/sentiment/")) {
          return null as T;
        }
      }
      throw error;
    }
  }

  // Authentication APIs (인증 필요)
  async register(userData: RegisterData): Promise<AuthResponse> {
    return this.request<AuthResponse>(
      "/auth/register/",
      {
        method: "POST",
        body: JSON.stringify(userData),
      },
      true
    );
  }

  async login(credentials: LoginData): Promise<AuthResponse> {
    return this.request<AuthResponse>(
      "/auth/login/",
      {
        method: "POST",
        body: JSON.stringify(credentials),
      },
      true
    );
  }

  async logout(): Promise<{ message: string }> {
    return this.request<{ message: string }>(
      "/auth/logout/",
      {
        method: "POST",
      },
      true
    );
  }

  async getAuthStatus(): Promise<AuthStatus> {
    return this.request<AuthStatus>("/auth/status/", {}, false);
  }

  async checkUsername(
    username: string
  ): Promise<{ available: boolean; message: string }> {
    return this.request<{ available: boolean; message: string }>(
      "/auth/check-username/",
      {
        method: "POST",
        body: JSON.stringify({ username }),
      },
      false
    );
  }

  async updateProfile(userData: Partial<User>): Promise<AuthResponse> {
    return this.request<AuthResponse>(
      "/auth/profile/",
      {
        method: "PUT",
        body: JSON.stringify(userData),
      },
      true
    );
  }

  async getProfile(): Promise<User> {
    return this.request<User>("/auth/profile/", {}, true);
  }

  async requestPasswordReset(
    email: string
  ): Promise<{ message: string; temp_password?: string }> {
    return this.request<{ message: string; temp_password?: string }>(
      "/auth/password-reset/request/",
      {
        method: "POST",
        body: JSON.stringify({ email }),
      },
      false
    );
  }

  async resetPassword(
    email: string,
    newPassword: string
  ): Promise<{ message: string }> {
    return this.request<{ message: string }>(
      "/auth/password-reset/confirm/",
      {
        method: "POST",
        body: JSON.stringify({ email, new_password: newPassword }),
      },
      false
    );
  }

  // Stock APIs (비회원 접근 가능)
  async getStocks(
    options: { page?: number; search?: string } = {}
  ): Promise<{ count: number; results: Stock[] }> {
    const params = new URLSearchParams();
    if (options.page) params.append("page", options.page.toString());
    if (options.search) params.append("search", options.search);

    const queryString = params.toString();
    const endpoint = queryString ? `/stocks/?${queryString}` : "/stocks/";

    return this.request<{ count: number; results: Stock[] }>(
      endpoint,
      {},
      false
    );
  }

  async getStock(code: string): Promise<StockDetail> {
    return this.request<StockDetail>(`/stocks/${code}/`, {}, false);
  }

  async getStockAnalysis(code: string): Promise<StockAnalysis> {
    return this.request<StockAnalysis>(`/analysis/stocks/${code}/`, {}, false);
  }

  async getPriceHistory(
    code: string,
    options: { days?: number; start_date?: string; end_date?: string } = {}
  ): Promise<PriceData[]> {
    const params = new URLSearchParams();
    if (options.days) params.append("days", options.days.toString());
    if (options.start_date) params.append("start_date", options.start_date);
    if (options.end_date) params.append("end_date", options.end_date);

    const queryString = params.toString();
    const endpoint = queryString
      ? `/stocks/${code}/price-history/?${queryString}`
      : `/stocks/${code}/price-history/`;

    return this.request<PriceData[]>(endpoint, {}, false);
  }

  async getSentimentAnalysis(code: string): Promise<SentimentAnalysis | null> {
    try {
      return await this.request<SentimentAnalysis>(
        `/sentiment/${code}/`,
        {},
        false
      );
    } catch (error: any) {
      // 404 오류는 감정 분석 데이터가 없음을 의미하므로 null 반환
      if (
        error.message?.includes("404") ||
        error.message?.includes("감정 분석 데이터가 없습니다")
      ) {
        console.log(`감정 분석 데이터 없음: ${code}`);
        return null;
      }
      // 다른 오류는 다시 던짐
      throw error;
    }
  }

  // 감정 추이 조회 (기본 14일)
  async getSentimentTrend(
    code: string,
    days: number = 14
  ): Promise<SentimentTrendData[]> {
    return this.request<SentimentTrendData[]>(
      `/sentiment/${code}/trend/?days=${days}`,
      {},
      false
    );
  }

  async getFinancialData(code: string): Promise<FinancialAnalysis> {
    return this.request<FinancialAnalysis>(`/financials/${code}/`, {}, false);
  }

  async getMarketOverview(): Promise<MarketOverview> {
    const data = await this.request<MarketOverview>("/market-overview/", {}, false);
    // 숫자 필드가 문자열로 올 수 있어 정규화
    if (data?.market_summary) {
      Object.keys(data.market_summary).forEach((k) => {
        const v = (data.market_summary as any)[k];
        if (!v) return;
        v.current = Number(v.current) || 0;
        v.change = Number(v.change) || 0;
        v.change_percent = Number(v.change_percent) || 0;
        v.volume = Number(v.volume) || 0;
        v.high = Number(v.high) || 0;
        v.low = Number(v.low) || 0;
        v.trade_value = Number(v.trade_value) || 0;
      });
    }
    return data;
  }

  async getClusterData(code: string): Promise<ClusterData[]> {
    return this.request<ClusterData[]>(`/analysis/cluster/${code}/`, {}, false);
  }

  async getSimilarStocks(code: string): Promise<SimilarStock[]> {
    return this.request<SimilarStock[]>(
      `/analysis/similar/${code}/`,
      {},
      false
    );
  }

  // Watchlist APIs (올바른 백엔드 엔드포인트 사용)
  async getWatchlist(): Promise<WatchlistItem[]> {
    try {
      // 백엔드에서 관심종목 리스트 배열을 반환함
      const watchlistArray = await this.request<
        Array<{
          id: number;
          name: string;
          stocks: WatchlistItem[];
        }>
      >("/analysis/watchlist/", {}, false);

      // 첫 번째 관심종목 리스트의 종목들만 반환 (기존 프론트엔드 로직과 호환)
      if (watchlistArray && watchlistArray.length > 0) {
        return watchlistArray[0].stocks || [];
      }
      return [];
    } catch (error) {
      console.warn("관심종목 로드 실패:", error);
      return [];
    }
  }

  async addToWatchlist(stockCode: string): Promise<WatchlistResponse> {
    try {
      // 첫 번째 관심종목 리스트(ID: 1)에 추가
      const result = await this.request<{ message: string }>(
        `/analysis/watchlist/1/stocks/${stockCode}/`,
        {
          method: "POST",
        },
        false
      );

      return {
        success: true,
        message: result.message,
      };
    } catch (error) {
      return {
        success: false,
        message: error instanceof Error ? error.message : "관심종목 추가 실패",
      };
    }
  }

  async removeFromWatchlist(stockCode: string): Promise<WatchlistResponse> {
    try {
      // 첫 번째 관심종목 리스트(ID: 1)에서 삭제

      const result = await this.request<{ message: string }>(
        `/analysis/watchlist/1/stocks/${stockCode}/`,
        {
          method: "DELETE",
        },
        false
      );

      return {
        success: true,
        message: result.message,
      };
    } catch (error) {
      return {
        success: false,

        message: error instanceof Error ? error.message : "관심종목 삭제 실패",
      };
    }
  }

  // Portfolio APIs
  async getPortfolios(): Promise<Portfolio[]> {
    return this.request<Portfolio[]>("/portfolios/", {}, false);
  }

  async getPortfolio(portfolioId: number): Promise<Portfolio> {
    return this.request<Portfolio>(`/portfolios/${portfolioId}/`, {}, false);
  }

  async createPortfolio(data: CreatePortfolioRequest): Promise<Portfolio> {
    return this.request<Portfolio>(
      "/portfolios/",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      false
    );
  }

  async updatePortfolio(
    portfolioId: number,
    data: Partial<CreatePortfolioRequest>
  ): Promise<Portfolio> {
    return this.request<Portfolio>(
      `/portfolios/${portfolioId}/`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
      false
    );
  }

  async deletePortfolio(portfolioId: number): Promise<void> {
    await this.request<void>(
      `/portfolios/${portfolioId}/`,
      {
        method: "DELETE",
      },
      false
    );
  }

  async getHoldings(portfolioId: number): Promise<PortfolioHolding[]> {
    return this.request<PortfolioHolding[]>(
      `/portfolios/${portfolioId}/holdings/`,
      {},
      false
    );
  }

  async addHolding(
    portfolioId: number,
    data: CreateHoldingRequest
  ): Promise<PortfolioHolding> {
    return this.request<PortfolioHolding>(
      `/portfolios/${portfolioId}/holdings/`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      false
    );
  }

  async updateHolding(
    portfolioId: number,
    holdingId: number,
    data: Partial<CreateHoldingRequest>
  ): Promise<PortfolioHolding> {
    return this.request<PortfolioHolding>(
      `/portfolios/${portfolioId}/holdings/${holdingId}/`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
      false
    );
  }

  async deleteHolding(portfolioId: number, holdingId: number): Promise<void> {
    await this.request<void>(
      `/portfolios/${portfolioId}/holdings/${holdingId}/`,
      {
        method: "DELETE",
      },
      false
    );
  }

  async updatePortfolioWeights(portfolioId: number): Promise<Portfolio> {
    const result = await this.request<{ portfolio: Portfolio }>(
      `/portfolios/${portfolioId}/update-weights/`,
      {
        method: "POST",
      },
      false
    );
    return result.portfolio;
  }

  // Alert API methods
  async getAlerts(): Promise<Alert[]> {
    return this.request<Alert[]>("/analysis/alerts/", {}, true);
  }

  async createAlert(data: CreateAlertRequest): Promise<Alert> {
    return this.request<Alert>(
      "/analysis/alerts/",
      {
        method: "POST",
        body: JSON.stringify(data),
      },
      true
    );
  }

  async deleteAlert(alertId: number): Promise<void> {
    return this.request<void>(
      `/analysis/alerts/${alertId}/`,
      {
        method: "DELETE",
      },
      true
    );
  }

  async checkAlerts(): Promise<{
    triggered_count: number;
    triggered_alerts: Alert[];
  }> {
    return this.request<{ triggered_count: number; triggered_alerts: Alert[] }>(
      "/analysis/alerts/check/",
      {
        method: "POST",
      },
      true
    );
  }

  // 클러스터링 관련 API
  async getClusterOverview(
    type: "spectral" | "agglomerative" = "spectral"
  ): Promise<ClusterOverview> {
    return this.request<ClusterOverview>(
      `/analysis/clusters/?type=${type}`,
      {},
      false
    );
  }

  async getClusterStocks(
    clusterType: "spectral" | "agglomerative",
    clusterId: number
  ): Promise<ClusterStocks> {
    return this.request<ClusterStocks>(
      `/analysis/clusters/${clusterType}/${clusterId}/`,
      {},
      false
    );
  }

  async getStockClusterInfo(stockCode: string): Promise<StockClusterInfo> {
    return this.request<StockClusterInfo>(
      `/analysis/stocks/${stockCode}/cluster/`,
      {},
      false
    );
  }

  async getSimilarStocksByCluster(
    stockCode: string,
    type: "spectral" | "agglomerative" = "spectral",
    limit: number = 10
  ): Promise<SimilarStocks> {
    return this.request<SimilarStocks>(
      `/analysis/stocks/${stockCode}/similar/?type=${type}&limit=${limit}`,
      {},
      false
    );
  }

  // AI Report API (requires authentication)
  async generateReport(code: string): Promise<AIReport> {
    return this.request<AIReport>(
      `/analysis/report/${code}/`,
      { method: "POST" },
      true
    );
  }
}

// Export singleton instance
export const apiClient = new ApiClient(API_BASE_URL);

// Authentication API convenience functions
export const authApi = {
  register: (userData: RegisterData) => apiClient.register(userData),
  login: (credentials: LoginData) => apiClient.login(credentials),
  logout: () => apiClient.logout(),
  getStatus: () => apiClient.getAuthStatus(),
  checkUsername: (username: string) => apiClient.checkUsername(username),
  updateProfile: (userData: Partial<User>) => apiClient.updateProfile(userData),
  getProfile: () => apiClient.getProfile(),
  requestPasswordReset: (email: string) =>
    apiClient.requestPasswordReset(email),
  resetPassword: (email: string, newPassword: string) =>
    apiClient.resetPassword(email, newPassword),
};

// Stock API convenience functions (stocksApi - 기존 이름 유지)
export const stocksApi = {
  getStocks: (options?: { page?: number; search?: string }) =>
    apiClient.getStocks(options),
  getStock: (code: string) => apiClient.getStock(code),
  getStockAnalysis: (code: string) => apiClient.getStockAnalysis(code),
  getPriceHistory: (
    code: string,
    options?: { days?: number; start_date?: string; end_date?: string }
  ) => apiClient.getPriceHistory(code, options),
  getSentimentAnalysis: (code: string) => apiClient.getSentimentAnalysis(code),
  getSentimentTrend: (code: string, days?: number) =>
    apiClient.getSentimentTrend(code, days),
  getFinancialData: (code: string) => apiClient.getFinancialData(code),
  getMarketOverview: () => apiClient.getMarketOverview(),
  getClusterData: (code: string) => apiClient.getClusterData(code),
  getSimilarStocks: (code: string) => apiClient.getSimilarStocks(code),
  // Watchlist methods
  getWatchlist: () => apiClient.getWatchlist(),
  addToWatchlist: (stockCode: string) => apiClient.addToWatchlist(stockCode),
  removeFromWatchlist: (stockCode: string) =>
    apiClient.removeFromWatchlist(stockCode),

  // 클러스터링 관련 메서드
  getClusterOverview: (type?: "spectral" | "agglomerative") =>
    apiClient.getClusterOverview(type),
  getClusterStocks: (
    clusterType: "spectral" | "agglomerative",
    clusterId: number
  ) => apiClient.getClusterStocks(clusterType, clusterId),
  getStockClusterInfo: (stockCode: string) =>
    apiClient.getStockClusterInfo(stockCode),
  getSimilarStocksByCluster: (
    stockCode: string,
    type?: "spectral" | "agglomerative",
    limit?: number
  ) => apiClient.getSimilarStocksByCluster(stockCode, type, limit),
  // AI Report
  generateReport: (code: string) => apiClient.generateReport(code),
};

// Portfolio API convenience functions
export const portfolioApi = {
  getPortfolios: () => apiClient.getPortfolios(),
  getPortfolio: (portfolioId: number) => apiClient.getPortfolio(portfolioId),
  createPortfolio: (data: CreatePortfolioRequest) =>
    apiClient.createPortfolio(data),
  updatePortfolio: (
    portfolioId: number,
    data: Partial<CreatePortfolioRequest>
  ) => apiClient.updatePortfolio(portfolioId, data),
  deletePortfolio: (portfolioId: number) =>
    apiClient.deletePortfolio(portfolioId),

  // Holdings methods
  getHoldings: (portfolioId: number) => apiClient.getHoldings(portfolioId),
  addHolding: (portfolioId: number, data: CreateHoldingRequest) =>
    apiClient.addHolding(portfolioId, data),
  updateHolding: (
    portfolioId: number,
    holdingId: number,
    data: Partial<CreateHoldingRequest>
  ) => apiClient.updateHolding(portfolioId, holdingId, data),
  deleteHolding: (portfolioId: number, holdingId: number) =>
    apiClient.deleteHolding(portfolioId, holdingId),
  updateWeights: (portfolioId: number) =>
    apiClient.updatePortfolioWeights(portfolioId),
};

// Alert API convenience functions
export const alertApi = {
  getAlerts: () => apiClient.getAlerts(),
  createAlert: (data: CreateAlertRequest) => apiClient.createAlert(data),
  deleteAlert: (alertId: number) => apiClient.deleteAlert(alertId),
  checkAlerts: () => apiClient.checkAlerts(),
};

// Legacy support - stockApi alias
export const stockApi = stocksApi;

// Error handling utility
export const handleApiError = (error: any): string => {
  if (error.message) {
    return error.message;
  }
  return "알 수 없는 오류가 발생했습니다.";
};
