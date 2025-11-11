"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import {
  Search,
  Star,
  Clock,
  TrendingUp,
  TrendingDown,
  Filter,
  RefreshCw,
  BarChart3,
  User,
  LogOut,
  LogIn,
} from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  stocksApi,
  Stock as ApiStock,
  MarketOverview,
  handleApiError,
} from "@/lib/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

// Phase 3 개선 컴포넌트들
import { MarketOverviewWidget } from "@/components/widgets/market-overview-widget";
// TopMarketCapTicker 제거: 상단 카드 그리드에 통합
import {
  AdvancedFilters,
  FilterCriteria,
} from "@/components/filters/advanced-filters";

import { MarketStatusIndicator } from "@/components/ui/market-status-indicator";
import {
  StockPriceCell,
  StockPriceData,
} from "@/components/ui/stock-price-cell";
import { ThemeToggle } from "@/components/ui/theme-toggle";

// 섹터 매핑 유틸리티
import {
  translateSectorToKorean,
  translateSectorToKoreanShort,
  getSectorColor,
} from "@/lib/sector-mapping";

// AI 점수 계산 유틸리티
import { computeAiScore } from "@/lib/ai-score-utils";

// 전역 감정 데이터 스토어
import { sentimentStore, calculateSentimentScore } from "@/lib/sentiment-store";

// 실시간 주가 Hook - WebSocket 기반으로 변경
import { useGlobalWebSocket } from "@/hooks/use-global-websocket";
// Index WS removed; rely on REST polling via MarketOverviewWidget/stocksApi

// 인증 Hook 추가
import { useAuth } from "@/contexts/AuthContext";

// 백엔드 API 타입을 프론트엔드 인터페이스에 맞게 변환
interface Stock {
  id: string;
  code: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  volume: number;
  marketCap: number | null;
  per: number | null;
  pbr: number | null;
  sentiment: number; // 계산된 감정 점수 (0-1)
  aiScore?: number; // AI 종합 점수 (0-100)
  sentimentData?: {
    // 상세 감정 데이터 (선택적)
    positive: number;
    negative: number;
    neutral?: number;
    lastUpdated?: string;
  };
  market: string;
  sector: string;
}

interface RecentSearch {
  id: string;
  code: string;
  name: string;
  timestamp: Date;
}

// 전역 감정 스토어 사용

// 배치로 감정 분석 데이터를 로드하는 함수
const loadSentimentDataBatch = async (stockCodes: string[]) => {
  const promises = stockCodes.map(async (code) => {
    try {
      const sentimentData = await stocksApi.getSentimentAnalysis(code);
      if (sentimentData) {
        const positive =
          typeof sentimentData.positive === "string"
            ? parseFloat(sentimentData.positive)
            : sentimentData.positive;
        const negative =
          typeof sentimentData.negative === "string"
            ? parseFloat(sentimentData.negative)
            : sentimentData.negative;
        const neutral = sentimentData.neutral
          ? typeof sentimentData.neutral === "string"
            ? parseFloat(sentimentData.neutral)
            : sentimentData.neutral
          : 0;

        // 전역 스토어에 저장
        sentimentStore.setSentiment(code, positive, negative, neutral);

        return { code, positive, negative, neutral };
      } else {
        // 감정 분석 데이터가 없는 경우 (null 반환)
        console.log(`감정 분석 데이터 없음: ${code}`);
        return null;
      }
    } catch (error) {
      console.log(`감정 분석 데이터 로드 실패: ${code}`, error);
      return null;
    }
  });

  const results = await Promise.allSettled(promises);
  const loadedCount = results.filter(
    (r) => r.status === "fulfilled" && r.value !== null
  ).length;
  console.log(
    `감정 분석 데이터 로드 완료: ${loadedCount}/${stockCodes.length}`
  );
};

// API 데이터를 로컬 인터페이스로 변환하는 함수 (실시간 데이터 포함)
const convertApiStockToStock = (
  apiStock: ApiStock,
  realTimeData?: any,
  sentimentOverride?: { positive: number; negative: number; neutral?: number }
): Stock => {
  const realTime = realTimeData?.[apiStock.stock_code];

  let sentiment: number;
  let sentimentData: Stock["sentimentData"];

  // 1. 직접 제공된 감정 데이터 사용 (우선순위 1)
  // 2. 전역 스토어에서 데이터 사용 (우선순위 2)
  // 3. 랜덤 값 사용 (fallback)
  const sentimentAnalysis =
    sentimentOverride || sentimentStore.getSentiment(apiStock.stock_code);

  if (sentimentAnalysis) {
    // 실제 감정 분석 데이터가 있으면 사용
    sentiment = calculateSentimentScore(
      sentimentAnalysis.positive,
      sentimentAnalysis.negative,
      sentimentAnalysis.neutral || 0
    );
    sentimentData = {
      positive: sentimentAnalysis.positive,
      negative: sentimentAnalysis.negative,
      neutral: sentimentAnalysis.neutral,
      lastUpdated: new Date().toISOString(),
    };
  } else {
    // 데이터가 없으면 임시 랜덤 값 사용
    sentiment = Math.random() * 0.4 + 0.3; // 0.3-0.7
    // sentimentData는 undefined로 남겨둠 (실제 데이터 없음을 표시)
  }

  return {
    id: apiStock.stock_code,
    code: apiStock.stock_code,
    name: apiStock.stock_name,
    price: realTime?.current_price || apiStock.current_price,
    change: realTime?.change_amount || 0,
    changePercent: realTime?.change_percent || 0,
    volume: realTime?.volume || 0,
    marketCap: realTime?.market_cap || apiStock.market_cap,
    per: apiStock.per,
    pbr: apiStock.pbr,
    sentiment,
    aiScore: undefined,
    sentimentData,
    market: apiStock.market,
    sector: apiStock.sector,
  };
};

export default function Dashboard() {
  // 인증 상태 추가
  const { user, isAuthenticated, logout } = useAuth();

  const [searchQuery, setSearchQuery] = useState("");
  const [stocks, setStocks] = useState<Stock[]>([]);
  const [filteredStocks, setFilteredStocks] = useState<Stock[]>([]);
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(
    null
  );
  const [topMcapItems, setTopMcapItems] = useState<{ code: string; name: string; marketCap: number | null }[]>([])
  const [recentSearches, setRecentSearches] = useState<RecentSearch[]>([]);

  // 최근 검색 관리 함수들
  const loadRecentSearches = () => {
    try {
      const saved = localStorage.getItem("kospi-recent-searches");
      if (saved) {
        const parsed = JSON.parse(saved).map((item: any) => ({
          ...item,
          timestamp: new Date(item.timestamp),
        }));
        setRecentSearches(parsed);
      }
    } catch (error) {
      console.error("최근 검색 로드 실패:", error);
    }
  };

  const addToRecentSearches = (stock: Stock) => {
    try {
      const newSearch: RecentSearch = {
        id: `${stock.code}-${Date.now()}`,
        code: stock.code,
        name: stock.name,
        timestamp: new Date(),
      };

      setRecentSearches((prev) => {
        // 중복 제거 (같은 종목코드가 이미 있으면 제거)
        const filtered = prev.filter((item) => item.code !== stock.code);
        // 새 검색을 맨 앞에 추가하고 최대 10개까지만 유지
        const updated = [newSearch, ...filtered].slice(0, 10);

        // localStorage에 저장
        localStorage.setItem("kospi-recent-searches", JSON.stringify(updated));

        return updated;
      });
    } catch (error) {
      console.error("최근 검색 추가 실패:", error);
    }
  };

  const clearRecentSearches = () => {
    try {
      localStorage.removeItem("kospi-recent-searches");
      setRecentSearches([]);
    } catch (error) {
      console.error("최근 검색 삭제 실패:", error);
    }
  };
  const [favorites, setFavorites] = useState<Stock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");
  const [sortBy, setSortBy] = useState<string>("market_cap"); // 백엔드 정렬 키와 일치하도록 변경
  const [filterBy, setFilterBy] = useState<string>("all");
  const [filterCriteria, setFilterCriteria] = useState<FilterCriteria>({});

  // 페이지네이션 상태
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(8); // 시가총액 상위 종목을 더 많이 보여주기 위해 15개로 변경

  // 탭 상태 관리
  const [activeTab, setActiveTab] = useState("stocks");

  // 시장 상태 관리
  const [isMarketOpen, setIsMarketOpen] = useState<boolean>(true);
  const [lastTradingDay, setLastTradingDay] = useState<string>("");

  // 실시간 주가 Hook - 현재 화면의 종목들만 조회 (memoized)
  const currentPageStocks = useMemo(() => {
    return filteredStocks.slice(
      (currentPage - 1) * itemsPerPage,
      currentPage * itemsPerPage
    );
  }, [filteredStocks, currentPage, itemsPerPage]);

  // 현재 페이지 종목 코드들 (memoized)
  const currentStockCodes = useMemo(() => {
    return currentPageStocks.map((stock) => stock.code);
  }, [currentPageStocks]);

  // 상단 카드용: 시총 상위 30 종목 코드 (실시간 구독 포함)
  const topMcapCodes = useMemo(() => {
    return topMcapItems.map((s) => s.code);
  }, [topMcapItems]);

  // 관심종목 코드들 (memoized)
  const favoriteStockCodes = useMemo(() => {
    return favorites.map((stock) => stock.code);
  }, [favorites]);

  // 통합된 실시간 주가 Hook - 현재 페이지 + 관심종목 모두 포함
  // 데이터 로딩이 완료된 후에만 구독 시작 (타이밍 문제 해결)
  // 휴장일에는 웹소켓 구독하지 않음
  const allStockCodes = useMemo(() => {
    // 로딩 중이거나 시장이 휴장 중이면 빈 배열 반환 (WebSocket 구독 방지)
    if (loading) {
      console.log("🔕 Skipping stock codes - still loading data");
      return [];
    }
    
    if (!isMarketOpen) {
      console.log("🔕 Skipping stock codes - market is closed");
      return [];
    }
    
    const combined = [...currentStockCodes, ...favoriteStockCodes, ...topMcapCodes];
    // 중복 제거 및 안정화
    const unique = [...new Set(combined)].filter(Boolean).sort();
    console.log("🔍 All stock codes combined:", {
      loading,
      isMarketOpen,
      currentPage: currentStockCodes.length,
      favorites: favoriteStockCodes.length,
      topMcap: topMcapCodes.length,
      total: unique.length,
      codes: unique.slice(0, 5), // 처음 5개만 로그
    });
    return unique;
  }, [currentStockCodes, favoriteStockCodes, topMcapCodes, loading, isMarketOpen]);

  const {
    data: realTimePrices = {},
    loading: realTimeLoading = false,
    error: realTimeError = null,
    connected: realTimeConnected = false,
    lastUpdated,
    refetch: refetchRealTime,
  } = useGlobalWebSocket({
    stockCodes: allStockCodes,
    autoSubscribe: true, // 실시간 구독 활성화
  });

  // 편의상 별칭 생성 (기존 코드 호환성을 위해)
  const favoriteRealTimePrices = realTimePrices;
  const favoriteRealTimeLoading = realTimeLoading;
  const favoriteRealTimeError = realTimeError;
  const favoriteConnected = realTimeConnected;
  const favoriteLastUpdated = lastUpdated;
  const refetchFavoriteRealTime = refetchRealTime;

  // 관심종목 관리 함수들
  const addToFavorites = async (stock: Stock) => {
    console.log("관심종목 추가 시작:", stock.code, stock.name);
    try {
      const result = await stocksApi.addToWatchlist(stock.code);
      console.log("관심종목 추가 API 결과:", result);

      if (result.success) {
        // 백엔드에서 최신 관심종목 목록을 다시 가져와서 동기화
        const updatedWatchlist = await stocksApi.getWatchlist();
        console.log("업데이트된 관심종목 목록:", updatedWatchlist);

        if (updatedWatchlist && updatedWatchlist.length > 0) {
          const watchlistStocks = updatedWatchlist.map((item) => {
            const baseStock = stocks.find((s) => s.code === item.stock_code);
            if (baseStock) {
              return {
                ...baseStock,
                price: item.current_price,
                changePercent: item.change_percent || 0,
              };
            }
            return {
              id: item.stock_code,
              code: item.stock_code,
              name: item.stock_name,
              price: item.current_price,
              change: item.current_price * ((item.change_percent || 0) / 100),
              changePercent: item.change_percent || 0,
              volume: 0,
              marketCap: null,
              per: null,
              pbr: null,
              sentiment: 0.5,
              market: item.market || "KOSPI",
              sector: item.sector || "기타",
            };
          });
          setFavorites(watchlistStocks);
        }

        console.log("✅ 관심종목 추가 성공:", result.message);
      } else {
        console.error("❌ 관심종목 추가 실패:", result.message);
      }
    } catch (error) {
      console.error("관심종목 추가 실패:", error);
    }
  };

  const removeFromFavorites = async (stockCode: string) => {
    console.log("관심종목 삭제 시작:", stockCode);
    try {
      const result = await stocksApi.removeFromWatchlist(stockCode);
      console.log("관심종목 삭제 API 결과:", result);

      if (result.success) {
        // 백엔드에서 최신 관심종목 목록을 다시 가져와서 동기화
        const updatedWatchlist = await stocksApi.getWatchlist();
        console.log("업데이트된 관심종목 목록:", updatedWatchlist);

        if (updatedWatchlist && updatedWatchlist.length > 0) {
          const watchlistStocks = updatedWatchlist.map((item) => {
            const baseStock = stocks.find((s) => s.code === item.stock_code);
            if (baseStock) {
              return {
                ...baseStock,
                price: item.current_price,
                changePercent: item.change_percent || 0,
              };
            }
            return {
              id: item.stock_code,
              code: item.stock_code,
              name: item.stock_name,
              price: item.current_price,
              change: item.current_price * ((item.change_percent || 0) / 100),
              changePercent: item.change_percent || 0,
              volume: 0,
              marketCap: null,
              per: null,
              pbr: null,
              sentiment: 0.5,
              market: item.market || "KOSPI",
              sector: item.sector || "기타",
            };
          });
          setFavorites(watchlistStocks);
        } else {
          setFavorites([]);
        }

        console.log("✅ 관심종목 삭제 성공:", result.message);
      } else {
        console.error("❌ 관심종목 삭제 실패:", result.message);
      }
    } catch (error) {
      console.error("관심종목 삭제 실패:", error);
    }
  };

  const isFavorite = (stockCode: string) => {
    return favorites.some((stock) => stock.code === stockCode);
  };

  // 로그아웃 핸들러
  const handleLogout = async () => {
    try {
      await logout();
      // 로그아웃 후 필요한 추가 작업 (예: 관심종목 초기화)
      setFavorites([]);
    } catch (error) {
      console.error("로그아웃 실패:", error);
    }
  };

  // 데이터 로드
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      setError("");

      try {
        console.log("🔄 데이터 로딩 시작...");
        console.log(
          "API Base URL:",
          process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
        );

        // 병렬로 데이터 로드 (시장 상태 포함) - 시가총액 내림차순 정렬 추가
        const [stocksData, marketData, watchlistData, marketStatusData] = await Promise.all([
          stocksApi.getStocks({ sort_by: 'market_cap', sort_order: 'desc' }).catch((error) => {
            console.error("❌ 주식 데이터 로드 실패:", error);
            throw error; // 주식 데이터는 필수이므로 에러를 다시 던짐
          }),
          stocksApi.getMarketOverview().catch((error) => {
            console.warn("⚠️ 시장 개요 로드 실패:", error.message);
            return null;
          }),
          stocksApi.getWatchlist().catch((error) => {
            console.warn("⚠️ 관심종목 로드 실패:", error.message);
            return [];
          }),
          stocksApi.getMarketStatus().catch((error) => {
            console.warn("⚠️ 시장 상태 로드 실패:", error.message);
            return null;
          }),
        ]);

        // 시장 상태 설정
        if (marketStatusData) {
          setIsMarketOpen(marketStatusData.is_open);
          console.log(`🏢 시장 상태: ${marketStatusData.is_open ? '개장' : '휴장'} - ${marketStatusData.message}`);
          
          // 휴장일일 때 마지막 거래일 계산
          if (!marketStatusData.is_open) {
            const getLastTradingDay = () => {
              const now = new Date();
              const koreanTime = new Date(now.toLocaleString("en-US", { timeZone: "Asia/Seoul" }));
              let checkDate = new Date(koreanTime);
              
              for (let i = 0; i < 10; i++) {
                checkDate.setDate(checkDate.getDate() - 1);
                const dayOfWeek = checkDate.getDay();
                if (dayOfWeek !== 0 && dayOfWeek !== 6) {
                  return checkDate.toISOString().split('T')[0];
                }
              }
              return koreanTime.toISOString().split('T')[0];
            };
            
            const calculatedLastTradingDay = getLastTradingDay();
            setLastTradingDay(calculatedLastTradingDay);
            console.log(`📅 마지막 거래일: ${calculatedLastTradingDay}`);
          }
        }

        console.log("✅ 주식 데이터 로드 성공:", stocksData.count, "개 종목");

        // 감정 분석 데이터 배치 로드 (백그라운드에서)
        const stockCodes = stocksData.results.map((item) => item.stock_code);
        loadSentimentDataBatch(stockCodes)
          .then(() => {
            // 감정 분석 데이터 로드 완료 후 주식 데이터 다시 변환
            console.log("🎭 감정 분석 데이터 로드 완료, 주식 데이터 업데이트");
            const updatedStocks = stocksData.results
              .map((item) => convertApiStockToStock(item))
              .map((s) => ({
                ...s,
                aiScore: computeAiScore({
                  sentiment: s.sentiment,
                  changePercent: s.changePercent,
                  technicalIndicators: undefined, // TODO: 기술지표 데이터 추가
                }),
              }));
            setStocks(updatedStocks);
            setFilteredStocks(updatedStocks);
          })
          .catch((error) => {
            console.warn("감정 분석 데이터 배치 로드 실패:", error);
          });

        // 상단 카드용 시총 상위 30 데이터 준비 (문자열/콤마 처리 포함)
        let mcapItems = stocksData.results
          .map((s) => {
            const raw = (s.market_cap ?? 0) as any;
            const cap = Number(String(raw).replace(/,/g, '')) || 0;
            return { code: s.stock_code, name: s.stock_name, marketCap: cap };
          })
          .filter((s) => (s.marketCap || 0) > 0)
          .sort((a, b) => (b.marketCap || 0) - (a.marketCap || 0))
          .slice(0, 30);

        console.log("📊 Top market cap items (before fallback):", mcapItems.length, mcapItems.slice(0, 3));

        // Fallback: 시가총액 데이터가 비어있을 때 초깃값으로 상위 30개 종목을 사용하여
        // 실시간 구독을 활성화하고 비어있는 회색 영역이 보이지 않도록 함
        if (!mcapItems || mcapItems.length === 0) {
          console.warn("⚠️ No market cap data, using fallback (first 30 stocks)");
          mcapItems = stocksData.results
            .slice(0, 30)
            .map((s) => {
              const raw = (s.market_cap ?? 0) as any;
              const cap = Number(String(raw).replace(/,/g, '')) || 0;
              return { code: s.stock_code, name: s.stock_name, marketCap: cap };
            });
        }
        
        console.log("✅ Final top mcap items:", mcapItems.length, "stocks", mcapItems.slice(0, 3).map(s => s.code));
        setTopMcapItems(mcapItems);

        // AI 점수 계산 (공통 유틸리티 사용)

        const convertedStocks = stocksData.results
          .map((item) => convertApiStockToStock(item))
          .map((s) => ({
            ...s,
            aiScore: computeAiScore({
              sentiment: s.sentiment,
              changePercent: s.changePercent,
              technicalIndicators: undefined, // TODO: 기술지표 데이터 추가
            }),
          }));
        setStocks(convertedStocks);
        setFilteredStocks(convertedStocks);

        if (marketData) {
          setMarketOverview(marketData);
        }

        // 실제 관심종목 데이터 사용
        console.log("관심종목 데이터 로드 결과:", watchlistData);

        if (watchlistData && watchlistData.length > 0) {
          console.log("백엔드에서 가져온 관심종목:", watchlistData);
          const watchlistStocks = watchlistData.map((item) => {
            const baseStock = convertedStocks.find(
              (s) => s.code === item.stock_code
            );
            if (baseStock) {
              return {
                ...baseStock,
                price: item.current_price,
                changePercent: item.change_percent || 0,
                aiScore: baseStock.aiScore,
              };
            }
            // 기본 주식 정보가 없는 경우 최소한의 정보로 생성
            return {
              id: item.stock_code,
              code: item.stock_code,
              name: item.stock_name,
              price: item.current_price,
              change: item.current_price * ((item.change_percent || 0) / 100),
              changePercent: item.change_percent || 0,
              volume: 0,
              marketCap: null,
              per: null,
              pbr: null,
              sentiment: 0.5,
              aiScore: computeAiScore({
                sentiment: 0.5,
                changePercent: item.change_percent || 0,
                technicalIndicators: undefined,
              }),
              market: item.market || "KOSPI",
              sector: item.sector || "기타",
            };
          });
          setFavorites(watchlistStocks);
          console.log("설정된 관심종목:", watchlistStocks);
        } else {
          console.log("백엔드 관심종목이 비어있음, 빈 배열로 설정");
          setFavorites([]);
        }
      } catch (err: any) {
        const errorMessage = handleApiError(err);
        console.error("❌ 데이터 로드 중 오류:", {
          error: err,
          message: errorMessage,
          code: err.code,
          response: err.response,
        });

        // 백엔드 연결 실패 시에도 계속 진행 (목업 데이터 사용)
        if (
          err.code === "ECONNREFUSED" ||
          err.code === "NETWORK_ERROR" ||
          err.message?.includes("Network Error")
        ) {
          console.warn("🔄 백엔드 연결 실패, 목업 데이터로 폴백");
          setError("백엔드 서버에 연결할 수 없어 기본 데이터를 사용합니다.");

          // 목업 데이터로 폴백
          try {
            const mockStocksData = await stocksApi
              .getStocks()
              .catch(() => ({ count: 0, results: [] }));
            if (mockStocksData.results.length > 0) {
              const convertedStocks = mockStocksData.results.map((item) =>
                convertApiStockToStock(item)
              );
              setStocks(convertedStocks);
              setFilteredStocks(convertedStocks);
              console.log(
                "✅ 목업 데이터 로드 성공:",
                convertedStocks.length,
                "개 종목"
              );
            }
          } catch (mockError) {
            console.error("❌ 목업 데이터 로드도 실패:", mockError);
          }
        } else {
          setError(errorMessage);
        }
      } finally {
        setLoading(false);
      }
    };

    loadData();
    // 최근 검색 데이터 로드
    loadRecentSearches();
  }, []);

  // Index WS removed; MarketOverviewWidget will poll REST periodically

  // 필터링 로직 (기존 + 고급 필터)
  useEffect(() => {
    let filtered = stocks.filter(
      (stock) =>
        stock.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        stock.code.includes(searchQuery)
    );

    // 기존 간단한 필터 적용
    if (filterBy === "positive") {
      filtered = filtered.filter((stock) => stock.change > 0);
    } else if (filterBy === "negative") {
      filtered = filtered.filter((stock) => stock.change < 0);
    } else if (filterBy === "high-sentiment") {
      filtered = filtered.filter((stock) => stock.sentiment > 0.6);
    } else if (filterBy === "top-ai") {
      filtered = filtered
        .slice()
        .sort((a, b) => (b.aiScore ?? 0) - (a.aiScore ?? 0))
        .slice(0, 50);
    }

    // 고급 필터 적용
    if (filterCriteria.search) {
      const searchTerm = filterCriteria.search.toLowerCase();
      filtered = filtered.filter(
        (stock) =>
          stock.name.toLowerCase().includes(searchTerm) ||
          stock.code.toLowerCase().includes(searchTerm)
      );
    }

    if (filterCriteria.sectors && filterCriteria.sectors.length > 0) {
      filtered = filtered.filter((stock) =>
        filterCriteria.sectors!.includes(stock.sector)
      );
    }

    if (filterCriteria.priceRange) {
      const [min, max] = filterCriteria.priceRange;
      filtered = filtered.filter(
        (stock) => stock.price >= min && stock.price <= max
      );
    }

    if (
      filterCriteria.perRange &&
      filterCriteria.perRange[0] !== filterCriteria.perRange[1]
    ) {
      const [min, max] = filterCriteria.perRange;
      filtered = filtered.filter(
        (stock) => stock.per !== null && stock.per >= min && stock.per <= max
      );
    }

    if (
      filterCriteria.pbrRange &&
      filterCriteria.pbrRange[0] !== filterCriteria.pbrRange[1]
    ) {
      const [min, max] = filterCriteria.pbrRange;
      filtered = filtered.filter(
        (stock) => stock.pbr !== null && stock.pbr >= min && stock.pbr <= max
      );
    }

    if (filterCriteria.sentimentRange) {
      const [min, max] = filterCriteria.sentimentRange;
      const sentimentPercent = (stock: Stock) => stock.sentiment * 100;
      filtered = filtered.filter((stock) => {
        const sentiment = sentimentPercent(stock);
        return sentiment >= min && sentiment <= max;
      });
    }

    if (
      filterCriteria.sentimentType &&
      filterCriteria.sentimentType !== "all"
    ) {
      filtered = filtered.filter((stock) => {
        if (filterCriteria.sentimentType === "positive")
          return stock.sentiment >= 0.6;
        if (filterCriteria.sentimentType === "negative")
          return stock.sentiment < 0.4;
        if (filterCriteria.sentimentType === "neutral")
          return stock.sentiment >= 0.4 && stock.sentiment < 0.6;
        return true;
      });
    }

    // 정렬 적용
    let currentSortBy = filterCriteria.sortBy || sortBy;
    let currentSortOrder = filterCriteria.sortOrder || "desc";
    // AI 상위 필터가 선택된 경우, 정렬을 강제로 AI 점수 내림차순으로 고정
    if (filterBy === "top-ai") {
      currentSortBy = "ai";
      currentSortOrder = "desc";
    }

    filtered.sort((a, b) => {
      let aValue: number, bValue: number;

      switch (currentSortBy) {
        case "price":
          aValue = a.price;
          bValue = b.price;
          break;
        case "change":
          aValue = a.changePercent;
          bValue = b.changePercent;
          break;
        case "volume":
          aValue = a.volume;
          bValue = b.volume;
          break;
        case "sentiment":
          aValue = a.sentiment;
          bValue = b.sentiment;
          break;
        case "market_cap":
        case "marketCap": // 두 가지 형식 모두 지원
          aValue = a.marketCap || 0;
          bValue = b.marketCap || 0;
          break;
        case "per":
          aValue = a.per || 0;
          bValue = b.per || 0;
          break;
        case "pbr":
          aValue = a.pbr || 0;
          bValue = b.pbr || 0;
          break;
        case "ai":
          aValue = a.aiScore ?? 0;
          bValue = b.aiScore ?? 0;
          break;
        default:
          return currentSortOrder === "asc"
            ? a.name.localeCompare(b.name)
            : b.name.localeCompare(a.name);
      }

      return currentSortOrder === "asc" ? aValue - bValue : bValue - aValue;
    });

    setFilteredStocks(filtered);
  }, [searchQuery, stocks, sortBy, filterBy, filterCriteria]);

  // 페이지네이션 계산
  const totalPages = Math.ceil(filteredStocks.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const endIndex = startIndex + itemsPerPage;
  const currentStocks = filteredStocks.slice(startIndex, endIndex);

  // 페이지 변경 핸들러
  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  // 필터가 변경될 때마다 첫 페이지로 리셋
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, filterBy, filterCriteria]);

  const formatNumber = (num: number | null) => {
    if (num === null || num === undefined) return "-";
    if (num >= 1e12) return `${(num / 1e12).toFixed(1)}조`;
    if (num >= 1e8) return `${(num / 1e8).toFixed(1)}억`;
    if (num >= 1e4) return `${(num / 1e4).toFixed(1)}만`;
    return num.toLocaleString();
  };

  const formatTimeAgo = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days > 0) return `${days}일 전`;
    if (hours > 0) return `${hours}시간 전`;
    return `${minutes}분 전`;
  };

  const getSentimentColor = (sentiment: number) => {
    if (sentiment >= 0.7) return "text-green-600";
    if (sentiment >= 0.5) return "text-yellow-600";
    return "text-red-600";
  };

  const getSentimentBadge = (sentiment: number) => {
    if (sentiment >= 0.7)
      return (
        <Badge variant="default" className="bg-green-100 text-green-800">
          긍정
        </Badge>
      );
    if (sentiment >= 0.5) return <Badge variant="secondary">중립</Badge>;
    return <Badge variant="destructive">부정</Badge>;
  };

  // 사용 가능한 시장과 섹터 추출
  const availableSectors = Array.from(new Set(stocks.map((s) => s.sector)));

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-slate-50 to-stone-50 dark:from-gray-900 dark:via-gray-800 dark:to-gray-900">
      {/* 개선된 헤더 */}
      <header className="bg-white/90 dark:bg-gray-900/90 backdrop-blur-sm border-b border-gray-200/50 dark:border-gray-700/50 sticky top-0 z-50 shadow-sm">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                {/* Investment Insight 텍스트 로고 */}
                <div className="flex items-baseline gap-3">
                  <span className="text-4xl font-edu-handwriting font-bold bg-gradient-to-r from-slate-600 to-blue-600 dark:from-slate-300 dark:to-blue-400 bg-clip-text text-transparent modern-underline">
                    investment
                  </span>
                  <span className="text-4xl font-edu-handwriting font-bold bg-gradient-to-r from-blue-600 to-slate-700 dark:from-blue-400 dark:to-slate-300 bg-clip-text text-transparent modern-underline">
                    insight
                  </span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {/* 시장 상태 표시기 추가 */}
              <MarketStatusIndicator variant="badge" />

              {/* 인증 상태에 따른 버튼 표시 */}
              {isAuthenticated ? (
                <div className="flex items-center gap-2">
                  <ThemeToggle />
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex items-center gap-2"
                      >
                        <User className="h-4 w-4" />
                        {user?.first_name || user?.username || "사용자"}
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      <DropdownMenuLabel>내 계정</DropdownMenuLabel>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem>
                        <User className="mr-2 h-4 w-4" />
                        프로필
                      </DropdownMenuItem>
                      <DropdownMenuItem>
                        <Star className="mr-2 h-4 w-4" />
                        관심종목 ({favorites.length})
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem onClick={handleLogout}>
                        <LogOut className="mr-2 h-4 w-4" />
                        로그아웃
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <ThemeToggle />
                  <Link href="/login">
                    <Button variant="outline" size="sm">
                      <LogIn className="mr-2 h-4 w-4" />
                      로그인
                    </Button>
                  </Link>
                  <Link href="/register">
                    <Button size="sm">회원가입</Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-8">
        <div className="mb-12">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-slate-700 via-gray-800 to-slate-600 dark:from-slate-300 dark:via-gray-200 dark:to-slate-400 bg-clip-text text-transparent mb-3">
            🚀 KOSPI 200 Real-Time Dashboard
          </h1>
          <p className="text-lg text-gray-600 dark:text-gray-300 font-medium">
            KOSPI 200 종목의 실시간 정보와 시장 동향을 확인하세요
          </p>
          {/* 상승률 상위 10개 마퀴 배너 */}
        <RisingTicker
          stocks={topMcapItems.map((item) => {
            const base = stocks.find((s) => s.code === item.code);
            const rt: any = (realTimePrices as any)[item.code];
            const merged = base
              ? { ...base }
              : {
                  id: item.code,
                  code: item.code,
                  name: item.name,
                  price: 0,
                  change: 0,
                  changePercent: 0,
                  volume: 0,
                  marketCap: item.marketCap,
                  per: null,
                  pbr: null,
                  sentiment: 0.5,
                  aiScore: undefined,
                  market: "KOSPI",
                  sector: "기타",
                };
            if (rt) {
              merged.price = rt.current_price ?? merged.price;
              merged.change = rt.change_amount ?? merged.change;
              merged.changePercent = rt.change_percent ?? merged.changePercent;
              merged.volume = rt.volume ?? merged.volume;
            }
            return merged;
          })}
          mode="top_mcap"
          max={30}
        />
        </div>

        {/* 인터렉티브 카드(시총 상위 30를 상단 카드로 노출) */}
        {!loading && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            <Card
              className="group hover:shadow-lg transition-all duration-300 hover:scale-105 cursor-pointer border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              onClick={() => setActiveTab("stocks")}
            >
              <CardContent className="p-6 h-32">
                <div className="flex items-start justify-between h-full">
                  <div className="flex-1">
                    <p className="text-gray-500 dark:text-gray-400 font-medium mb-3 text-sm">
                      전체 종목
                    </p>
                    <p className="text-2xl font-bold text-gray-800 dark:text-white group-hover:text-slate-700 dark:group-hover:text-gray-300 transition-colors duration-300 mb-1">
                      {filteredStocks.length.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      페이지 {currentPage} / {totalPages}
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-slate-100 dark:bg-slate-700 rounded-lg flex items-center justify-center group-hover:bg-slate-200 dark:group-hover:bg-slate-600 transition-colors duration-300">
                    <TrendingUp className="h-6 w-6 text-slate-600 dark:text-slate-300" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card
              className="group hover:shadow-lg transition-all duration-300 hover:scale-105 cursor-pointer border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              onClick={() => setActiveTab("favorites")}
            >
              <CardContent className="p-6 h-32">
                <div className="flex items-start justify-between h-full">
                  <div className="flex-1">
                    <p className="text-gray-500 dark:text-gray-400 font-medium mb-3 text-sm">
                      관심 종목
                    </p>
                    <p className="text-2xl font-bold text-gray-800 dark:text-white group-hover:text-slate-700 dark:group-hover:text-gray-300 transition-colors duration-300 mb-1">
                      {favorites.length}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      {favoriteConnected ? "실시간 연결" : "정적 데이터"}
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-amber-100 dark:bg-amber-900/30 rounded-lg flex items-center justify-center group-hover:bg-amber-200 dark:group-hover:bg-amber-900/50 transition-colors duration-300">
                    <Star className="h-6 w-6 text-amber-600 dark:text-amber-400" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card
              className="group hover:shadow-lg transition-all duration-300 hover:scale-105 cursor-pointer border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              onClick={() => {
                setActiveTab("stocks");
                setTimeout(() => {
                  const searchInput = document.querySelector(
                    'input[placeholder*="종목명"]'
                  ) as HTMLInputElement;
                  if (searchInput) {
                    searchInput.focus();
                  }
                }, 100);
              }}
            >
              <CardContent className="p-6 h-32">
                <div className="flex items-start justify-between h-full">
                  <div className="flex-1">
                    <p className="text-gray-500 dark:text-gray-400 font-medium mb-3 text-sm">
                      검색 & 필터
                    </p>
                    <p className="text-2xl font-bold text-gray-800 dark:text-white group-hover:text-slate-700 dark:group-hover:text-gray-300 transition-colors duration-300 mb-1">
                      빠른 검색
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      종목명/코드 검색
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-blue-100 dark:bg-blue-900/30 rounded-lg flex items-center justify-center group-hover:bg-blue-200 dark:group-hover:bg-blue-900/50 transition-colors duration-300">
                    <Search className="h-6 w-6 text-blue-600 dark:text-blue-400" />
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card
              className="group hover:shadow-lg transition-all duration-300 hover:scale-105 cursor-pointer border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800"
              onClick={() => setActiveTab("recent")}
            >
              <CardContent className="p-6 h-32">
                <div className="flex items-start justify-between h-full">
                  <div className="flex-1">
                    <p className="text-gray-500 dark:text-gray-400 font-medium mb-3 text-sm">
                      최근 검색
                    </p>
                    <p className="text-2xl font-bold text-gray-800 dark:text-white group-hover:text-slate-700 dark:group-hover:text-gray-300 transition-colors duration-300 mb-1">
                      {recentSearches.length}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500">
                      검색 기록
                    </p>
                  </div>
                  <div className="w-12 h-12 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg flex items-center justify-center group-hover:bg-emerald-200 dark:group-hover:bg-emerald-900/50 transition-colors duration-300">
                    <Clock className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {error && (
          <Alert
            variant="destructive"
            className="mb-8 border-red-200 bg-red-50"
          >
            <AlertCircle className="h-5 w-5" />
            <AlertDescription className="font-medium">{error}</AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Main Content */}
          <div className="lg:col-span-3 order-2 lg:order-1 space-y-8">
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm p-6">
              <Tabs
                value={activeTab}
                onValueChange={setActiveTab}
                className="w-full"
              >
                <TabsList className="grid w-full grid-cols-3 bg-gray-100 dark:bg-gray-700 border-0 p-1 h-12">
                  <TabsTrigger
                    value="stocks"
                    className="rounded-lg font-semibold data-[state=active]:bg-white dark:data-[state=active]:bg-gray-600 data-[state=active]:shadow-sm transition-all duration-200 text-gray-700 dark:text-gray-300"
                  >
                    전체 종목
                  </TabsTrigger>
                  <TabsTrigger
                    value="favorites"
                    className="rounded-lg font-semibold data-[state=active]:bg-white dark:data-[state=active]:bg-gray-600 data-[state=active]:shadow-sm transition-all duration-200 text-gray-700 dark:text-gray-300"
                  >
                    관심 종목
                  </TabsTrigger>
                  <TabsTrigger
                    value="recent"
                    className="rounded-lg font-semibold data-[state=active]:bg-white dark:data-[state=active]:bg-gray-600 data-[state=active]:shadow-sm transition-all duration-200 text-gray-700 dark:text-gray-300"
                  >
                    최근 검색
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="stocks" className="space-y-6 mt-6">
                  <div className="flex flex-col sm:flex-row gap-4">
                    <div className="relative flex-1 group">
                      <Search className="absolute left-4 top-4 h-5 w-5 text-gray-400 dark:text-gray-500 group-focus-within:text-slate-600 dark:group-focus-within:text-slate-400 transition-colors duration-200" />
                      <Input
                        placeholder="종목명 또는 코드 검색 (예: 삼성전자, 005930)"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="pl-12 h-14 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-900 dark:text-white placeholder:text-gray-500 dark:placeholder:text-gray-400 shadow-sm rounded-xl group-focus-within:ring-2 group-focus-within:ring-slate-200 dark:group-focus-within:ring-slate-700 group-focus-within:border-slate-300 dark:group-focus-within:border-slate-600 transition-all duration-200 text-lg"
                      />
                      {searchQuery && (
                        <div className="absolute right-4 top-4">
                          <div className="text-sm text-gray-500 dark:text-gray-400 bg-slate-100 dark:bg-slate-700 px-3 py-1 rounded-full font-medium">
                            {filteredStocks.length}개 결과
                          </div>
                        </div>
                      )}
                    </div>
                    <div className="flex gap-3">
                      <Select value={filterBy} onValueChange={setFilterBy}>
                        <SelectTrigger className="w-40 h-14 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm rounded-xl hover:shadow-md transition-all duration-200 text-gray-900 dark:text-white">
                          <Filter className="h-5 w-5 mr-2 text-gray-600 dark:text-gray-400" />
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="border-gray-200 dark:border-gray-700 shadow-lg bg-white dark:bg-gray-800">
                          <SelectItem
                            value="all"
                            className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                          >
                            전체
                          </SelectItem>
                          <SelectItem
                            value="positive"
                            className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                          >
                            상승
                          </SelectItem>
                          <SelectItem
                            value="negative"
                            className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                          >
                            하락
                          </SelectItem>
                          <SelectItem
                            value="high-sentiment"
                            className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                          >
                            긍정 심리
                          </SelectItem>
                          <SelectItem
                            value="top-ai"
                            className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                          >
                            AI 종합 점수 상위
                          </SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>

                  <Card className="border border-gray-200 shadow-sm bg-white rounded-xl overflow-hidden">
                    <CardContent className="p-0">
                      {loading ? (
                        <div className="p-8 space-y-4">
                          {[...Array(10)].map((_, i) => (
                            <Skeleton
                              key={i}
                              className="h-20 w-full rounded-lg bg-gray-200"
                            />
                          ))}
                        </div>
                      ) : (
                        <Table>
                          <TableHeader>
                            <TableRow className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700">
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 py-4 w-48">
                                종목
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-32 text-center">
                                섹터
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-36 text-right">
                                현재가
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-28 text-right">
                                변동률
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-24 text-right">
                                거래량
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-20 text-right">
                                AI 종합 점수
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-24 text-center">
                                감정
                              </TableHead>
                              <TableHead className="font-bold text-gray-700 dark:text-gray-300 w-16 text-center">
                                관심
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {currentStocks.map((stock, index) => {
                              // 실시간 데이터가 있으면 우선 사용
                              const realTimeData = realTimePrices[stock.code];
                              const currentPrice =
                                realTimeData?.current_price || stock.price;
                              const changeAmount =
                                realTimeData?.change_amount || stock.change;
                              const changePercent =
                                realTimeData?.change_percent ||
                                stock.changePercent;
                              const currentVolume =
                                realTimeData?.volume || stock.volume;

                              // 시장 휴장 여부 판단
                              const isMarketClosedNow = !isMarketOpen;

                              // StockPriceCell용 데이터 구성
                              const stockPriceData: StockPriceData = {
                                price: currentPrice,
                                change: changeAmount,
                                changePercent: changePercent,
                                volume: currentVolume,
                                isRealTime: !!realTimeData && realTimeConnected && isMarketOpen,
                                isMarketClosed: isMarketClosedNow,
                                lastTradingDay: lastTradingDay || undefined,
                                timestamp: realTimeData?.timestamp,
                              };

                              return (
                                <TableRow
                                  key={stock.id}
                                  className="cursor-pointer bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors duration-200 group border-b border-gray-100 dark:border-gray-700"
                                >
                                  <TableCell className="py-4">
                                    <div
                                      className="cursor-pointer"
                                      onClick={() => {
                                        addToRecentSearches(stock);
                                        window.open(
                                          `/stock/${stock.code}`,
                                          "_blank"
                                        );
                                      }}
                                    >
                                      <div className="font-semibold text-gray-900 dark:text-white group-hover:text-slate-700 dark:group-hover:text-gray-300 hover:text-blue-600 dark:hover:text-blue-400 transition-colors duration-200">
                                        {stock.name}
                                      </div>
                                      <div className="text-sm text-gray-500 dark:text-gray-400 font-medium flex items-center gap-2">
                                        {stock.code}
                                        {realTimeData && (
                                          <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300">
                                            실시간
                                          </span>
                                        )}
                                      </div>
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-center">
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Badge
                                            variant="outline"
                                            className="border-gray-300 dark:border-gray-600 hover:border-slate-400 dark:hover:border-slate-500 transition-colors duration-200 text-xs cursor-help max-w-full truncate text-gray-700 dark:text-gray-300"
                                          >
                                            {translateSectorToKoreanShort(
                                              stock.sector
                                            )}
                                          </Badge>
                                        </TooltipTrigger>
                                        <TooltipContent
                                          side="top"
                                          className="bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700"
                                        >
                                          <div className="text-xs text-gray-900 dark:text-gray-100">
                                            {translateSectorToKorean(
                                              stock.sector
                                            )}
                                          </div>
                                        </TooltipContent>
                                      </Tooltip>
                                    </TooltipProvider>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <StockPriceCell
                                      data={stockPriceData}
                                      compact={true}
                                    />
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <div
                                      className={`font-semibold transition-colors duration-200 ${
                                        changePercent >= 0
                                          ? "text-red-600"
                                          : "text-blue-600"
                                      }`}
                                    >
                                      {changePercent >= 0 ? "+" : ""}
                                      {changePercent.toFixed(2)}%
                                      {realTimeData && (
                                        <div className="text-xs font-normal mt-1 opacity-75">
                                          ({changeAmount >= 0 ? "+" : ""}
                                          {changeAmount.toLocaleString()}원)
                                        </div>
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <div className="font-mono font-medium text-gray-700 dark:text-gray-300">
                                      {formatNumber(currentVolume)}
                                    </div>
                                    {realTimeData &&
                                      realTimeData.trading_value && (
                                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1 font-mono">
                                          {formatNumber(
                                            realTimeData.trading_value
                                          )}
                                          원
                                        </div>
                                      )}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    <span className="font-mono font-bold text-gray-900 dark:text-white">
                                      {typeof stock.aiScore === "number"
                                        ? stock.aiScore
                                        : "-"}
                                    </span>
                                  </TableCell>
                                  <TableCell className="text-center">
                                    <div className="flex flex-col items-center space-y-1">
                                      {getSentimentBadge(stock.sentiment)}
                                      <span
                                        className={`text-sm font-semibold ${getSentimentColor(
                                          stock.sentiment
                                        )} transition-colors duration-200`}
                                      >
                                        {(stock.sentiment * 100).toFixed(0)}%
                                      </span>
                                      {stock.sentimentData && (
                                        <div className="text-xs text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-700 rounded px-2 py-1 whitespace-nowrap">
                                          긍정{" "}
                                          {(
                                            stock.sentimentData.positive * 100
                                          ).toFixed(0)}
                                          % / 부정{" "}
                                          {(
                                            stock.sentimentData.negative * 100
                                          ).toFixed(0)}
                                          %
                                        </div>
                                      )}
                                    </div>
                                  </TableCell>
                                  <TableCell className="text-center">
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            disabled={!isAuthenticated}
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              if (isFavorite(stock.code)) {
                                                removeFromFavorites(stock.code);
                                              } else {
                                                addToFavorites(stock);
                                              }
                                            }}
                                            className={`hover:scale-110 transition-all duration-200 rounded-full ${
                                              !isAuthenticated
                                                ? "cursor-not-allowed opacity-50"
                                                : isFavorite(stock.code)
                                                ? "text-amber-600 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-900/30"
                                                : "text-gray-400 dark:text-gray-500 hover:text-amber-600 dark:hover:text-amber-400 hover:bg-amber-50 dark:hover:bg-amber-900/20"
                                            }`}
                                          >
                                            <Star
                                              className={`h-5 w-5 ${
                                                isFavorite(stock.code)
                                                  ? "fill-current"
                                                  : ""
                                              }`}
                                            />
                                          </Button>
                                        </TooltipTrigger>
                                        {!isAuthenticated && (
                                          <TooltipContent>
                                            <p>로그인 후 관심종목을 추가할 수 있습니다</p>
                                          </TooltipContent>
                                        )}
                                      </Tooltip>
                                    </TooltipProvider>
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      )}
                    </CardContent>
                  </Card>

                  {/* 페이지네이션 */}
                  {!loading && filteredStocks.length > 0 && (
                    <div className="space-y-6">
                      {/* 페이지 정보 */}
                      <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
                        <div className="flex items-center gap-4">
                          <span className="font-medium">
                            {startIndex + 1}-
                            {Math.min(endIndex, filteredStocks.length)} /{" "}
                            {filteredStocks.length}개 종목
                          </span>
                          <Select
                            value={itemsPerPage.toString()}
                            onValueChange={(value) => {
                              setItemsPerPage(parseInt(value));
                              setCurrentPage(1);
                            }}
                          >
                            <SelectTrigger className="w-28 border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 shadow-sm rounded-lg text-gray-900 dark:text-white">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent className="border-gray-200 dark:border-gray-700 shadow-lg bg-white dark:bg-gray-800">
                              <SelectItem
                                value="10"
                                className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                              >
                                10개
                              </SelectItem>
                              <SelectItem
                                value="15"
                                className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                              >
                                15개
                              </SelectItem>
                              <SelectItem
                                value="20"
                                className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                              >
                                20개
                              </SelectItem>
                              <SelectItem
                                value="30"
                                className="text-gray-900 dark:text-white hover:bg-gray-100 dark:hover:bg-gray-700"
                              >
                                30개
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="font-medium">
                          페이지 {currentPage} / {totalPages}
                        </div>
                      </div>

                      {/* 페이지네이션 컨트롤 */}
                      {totalPages > 1 && (
                        <div className="flex justify-center">
                          <Pagination>
                            <PaginationContent className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-sm p-2 text-gray-900 dark:text-white">
                              <PaginationItem>
                                <PaginationPrevious
                                  onClick={() =>
                                    currentPage > 1 &&
                                    handlePageChange(currentPage - 1)
                                  }
                                  className={`${
                                    currentPage <= 1
                                      ? "pointer-events-none opacity-50"
                                      : "cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300"
                                  } rounded-lg transition-colors duration-200 text-gray-700 dark:text-gray-300`}
                                />
                              </PaginationItem>

                              {/* 페이지 번호들 */}
                              {Array.from(
                                { length: Math.min(5, totalPages) },
                                (_, i) => {
                                  let pageNumber: number;

                                  if (totalPages <= 5) {
                                    pageNumber = i + 1;
                                  } else if (currentPage <= 3) {
                                    pageNumber = i + 1;
                                  } else if (currentPage >= totalPages - 2) {
                                    pageNumber = totalPages - 4 + i;
                                  } else {
                                    pageNumber = currentPage - 2 + i;
                                  }

                                  return (
                                    <PaginationItem key={pageNumber}>
                                      <PaginationLink
                                        onClick={() =>
                                          handlePageChange(pageNumber)
                                        }
                                        isActive={pageNumber === currentPage}
                                        className="cursor-pointer rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300 transition-colors duration-200 data-[active]:bg-slate-600 dark:data-[active]:bg-slate-500 data-[active]:text-white text-gray-700 dark:text-gray-300"
                                      >
                                        {pageNumber}
                                      </PaginationLink>
                                    </PaginationItem>
                                  );
                                }
                              )}

                              <PaginationItem>
                                <PaginationNext
                                  onClick={() =>
                                    currentPage < totalPages &&
                                    handlePageChange(currentPage + 1)
                                  }
                                  className={`${
                                    currentPage >= totalPages
                                      ? "pointer-events-none opacity-50"
                                      : "cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-700 dark:hover:text-gray-300"
                                  } rounded-lg transition-colors duration-200 text-gray-700 dark:text-gray-300`}
                                />
                              </PaginationItem>
                            </PaginationContent>
                          </Pagination>
                        </div>
                      )}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="favorites">
                  <Card className="border border-gray-200 dark:border-gray-700 shadow-sm bg-white dark:bg-gray-800 rounded-xl overflow-hidden">
                    <CardHeader className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                      <CardTitle className="flex items-center gap-3 text-xl font-bold text-gray-800 dark:text-gray-200">
                        <Star className="h-6 w-6 text-amber-600" />
                        관심 종목
                        {/* 관심종목 실시간 상태 표시 */}
                        <div className="ml-auto flex items-center gap-3">
                          {favoriteRealTimeLoading ? (
                            <Badge
                              variant="secondary"
                              className="bg-gray-200 text-gray-700 border-0"
                            >
                              <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                              업데이트 중
                            </Badge>
                          ) : favoriteConnected ? (
                            <Badge
                              variant="outline"
                              className="border-emerald-300 text-emerald-700 bg-emerald-50"
                            >
                              <div className="w-2 h-2 bg-emerald-500 rounded-full mr-1"></div>
                              실시간 연결
                            </Badge>
                          ) : null}

                          {/* 관심종목 수동 새로고침 버튼 */}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => refetchFavoriteRealTime?.()}
                            disabled={favoriteRealTimeLoading}
                            className="border-gray-300 text-gray-600 hover:bg-gray-100"
                          >
                            <RefreshCw
                              className={`h-4 w-4 ${
                                favoriteRealTimeLoading ? "animate-spin" : ""
                              }`}
                            />
                          </Button>
                        </div>
                      </CardTitle>
                      <CardDescription className="text-gray-600 dark:text-gray-400 font-medium">
                        자주 확인하는 종목들
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="p-6">
                      {favorites.length === 0 ? (
                        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                          <Star className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
                          <p className="text-lg font-medium">
                            관심 종목이 없습니다
                          </p>
                          <p className="text-sm mt-2">
                            종목 목록에서 ⭐ 버튼을 클릭해서 관심종목을
                            추가해보세요
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {favorites.map((stock, index) => {
                            // 관심종목용 실시간 데이터가 있으면 우선 사용
                            const realTimeData =
                              favoriteRealTimePrices[stock.code];
                            const currentPrice =
                              realTimeData?.current_price || stock.price;
                            const changeAmount =
                              realTimeData?.change_amount || stock.change;
                            const changePercent =
                              realTimeData?.change_percent ||
                              stock.changePercent;
                            const currentVolume =
                              realTimeData?.volume || stock.volume;

                            return (
                              <div
                                key={stock.id}
                                className="flex items-center justify-between p-5 border border-gray-200 rounded-lg hover:bg-gray-50 hover:shadow-md transition-all duration-200 cursor-pointer group"
                              >
                                <div className="flex-1">
                                  <div className="font-bold text-lg text-gray-900 group-hover:text-slate-700 transition-colors duration-200">
                                    {stock.name}
                                  </div>
                                  <div className="text-sm text-gray-500 font-medium mt-1">
                                    {stock.code}
                                    {realTimeData && (
                                      <span className="ml-2 inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                                        실시간
                                      </span>
                                    )}
                                  </div>
                                  {currentVolume > 0 && (
                                    <div className="text-xs text-gray-400 mt-2 font-medium">
                                      거래량: {currentVolume.toLocaleString()}
                                      {realTimeData &&
                                        realTimeData.trading_value && (
                                          <span className="ml-3">
                                            거래대금:{" "}
                                            {formatNumber(
                                              realTimeData.trading_value
                                            )}
                                          </span>
                                        )}
                                    </div>
                                  )}
                                </div>
                                <div className="text-right">
                                  <div className="font-mono text-xl font-bold text-gray-900 transition-colors duration-200">
                                    {formatNumber(currentPrice)}원
                                  </div>
                                  <div
                                    className={`text-sm font-bold mt-1 ${
                                      changePercent >= 0
                                        ? "text-red-600"
                                        : "text-blue-600"
                                    }`}
                                  >
                                    {changePercent >= 0 ? "+" : ""}
                                    {changePercent.toFixed(2)}%
                                    {changeAmount !== 0 && (
                                      <span className="ml-1 font-medium">
                                        ({changeAmount >= 0 ? "+" : ""}
                                        {changeAmount.toLocaleString()}원)
                                      </span>
                                    )}
                                  </div>
                                  {realTimeData && realTimeData.timestamp && (
                                    <div className="text-xs text-emerald-600 mt-1 font-medium">
                                      {new Date(
                                        realTimeData.timestamp.slice(0, 4) +
                                          "-" +
                                          realTimeData.timestamp.slice(4, 6) +
                                          "-" +
                                          realTimeData.timestamp.slice(6, 8) +
                                          " " +
                                          realTimeData.timestamp.slice(8, 10) +
                                          ":" +
                                          realTimeData.timestamp.slice(10, 12) +
                                          ":" +
                                          realTimeData.timestamp.slice(12, 14)
                                      ).toLocaleTimeString()}
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>

                <TabsContent value="recent">
                  <Card className="border border-gray-200 dark:border-gray-700 shadow-sm bg-white dark:bg-gray-800 rounded-xl overflow-hidden">
                    <CardHeader className="bg-gray-50 dark:bg-gray-700 border-b border-gray-200 dark:border-gray-600">
                      <CardTitle className="flex items-center justify-between text-xl font-bold text-gray-800 dark:text-gray-200">
                        <div className="flex items-center gap-3">
                          <Clock className="h-6 w-6 text-slate-600" />
                          최근 검색
                        </div>
                        {recentSearches.length > 0 && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={clearRecentSearches}
                            className="border-red-300 text-red-600 hover:bg-red-50 hover:border-red-400"
                          >
                            전체 삭제
                          </Button>
                        )}
                      </CardTitle>
                      <CardDescription className="text-gray-600 dark:text-gray-400 font-medium">
                        최근에 조회한 종목들 (최대 10개까지 저장)
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="p-6">
                      {recentSearches.length === 0 ? (
                        <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                          <Clock className="h-12 w-12 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
                          <p className="text-lg font-medium">
                            최근 검색 기록이 없습니다
                          </p>
                          <p className="text-sm mt-2">
                            종목명을 클릭하거나 상세보기를 클릭하면 자동으로
                            기록됩니다
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-3">
                          {recentSearches.map((search) => {
                            // 해당 종목이 전체 종목 리스트에 있는지 확인
                            const stockInfo = stocks.find(
                              (s) => s.code === search.code
                            );

                            return (
                              <div
                                key={search.id}
                                className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:bg-gray-50 hover:shadow-md transition-all duration-200 cursor-pointer group"
                                onClick={() => {
                                  if (stockInfo) {
                                    addToRecentSearches(stockInfo);
                                    window.open(
                                      `/stock/${search.code}`,
                                      "_blank"
                                    );
                                  }
                                }}
                              >
                                <div className="flex-1">
                                  <div className="font-bold text-gray-900 group-hover:text-blue-600 transition-colors duration-200">
                                    {search.name}
                                  </div>
                                  <div className="text-sm text-gray-500 font-medium mt-1">
                                    {search.code}
                                  </div>
                                </div>
                                <div className="flex items-center gap-3">
                                  <div className="text-sm text-gray-400 font-medium">
                                    {formatTimeAgo(search.timestamp)}
                                  </div>
                                  {stockInfo && (
                                    <TooltipProvider>
                                      <Tooltip>
                                        <TooltipTrigger asChild>
                                          <Button
                                            variant="ghost"
                                            size="sm"
                                            disabled={!isAuthenticated}
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              if (isFavorite(search.code)) {
                                                removeFromFavorites(search.code);
                                              } else {
                                                addToFavorites(stockInfo);
                                              }
                                            }}
                                            className={`hover:scale-110 transition-all duration-200 rounded-full ${
                                              !isAuthenticated
                                                ? "cursor-not-allowed opacity-50"
                                                : isFavorite(search.code)
                                                ? "text-amber-600 hover:text-amber-700 hover:bg-amber-50"
                                                : "text-gray-400 hover:text-amber-600 hover:bg-amber-50"
                                            }`}
                                          >
                                            <Star
                                              className={`h-4 w-4 ${
                                                isFavorite(search.code)
                                                  ? "fill-current"
                                                  : ""
                                              }`}
                                            />
                                          </Button>
                                        </TooltipTrigger>
                                        {!isAuthenticated && (
                                          <TooltipContent>
                                            <p>로그인 후 관심종목을 추가할 수 있습니다</p>
                                          </TooltipContent>
                                        )}
                                      </Tooltip>
                                    </TooltipProvider>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </TabsContent>
              </Tabs>
            </div>
          </div>

          {/* Sidebar - 우측에 위치 */}
          <div className="lg:col-span-1 order-1 lg:order-2 space-y-6">
            <div className="hover:shadow-md transition-shadow duration-200">
              <MarketStatusIndicator variant="detailed" showDetails={true} />
            </div>

            {/* Market Overview: 항상 마운트하여 내부에서 자체적으로 폴링 */}
            <div className="hover:shadow-md transition-shadow duration-200">
              <MarketOverviewWidget marketData={marketOverview} loading={loading} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// 상승률 상위 10개를 카드 형태로 오른쪽에서 왼쪽으로 흘러가게 표시하는 컴포넌트
function RisingTicker({ stocks, mode = "gainers", max = 10, rotateMs = 7000 }: { stocks: Stock[]; mode?: "gainers" | "top_mcap"; max?: number; rotateMs?: number }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [visibleSlots, setVisibleSlots] = useState(6);
  const [startIndex, setStartIndex] = useState(0);
  const [hasMeasured, setHasMeasured] = useState(false);
  const [slotWidth, setSlotWidth] = useState<number | null>(null);

  const top = useMemo(() => {
    const base = stocks.slice();
    if (mode === "gainers") {
      base.sort((a, b) => (b.changePercent || 0) - (a.changePercent || 0));
    }
    return base.slice(0, max);
  }, [stocks, mode, max]);

  // 컨테이너 폭을 기준으로 표시할 카드 슬롯 수 및 각 슬롯 너비 계산
  useEffect(() => {
    const measure = () => {
      const containerWidth = containerRef.current?.offsetWidth || 0;
      if (!containerWidth) return;
      const minCardWidth = 240; // 카드 최소 폭 (내용 가독성 개선)
      const gapPx = 16; // gap-4 (px)
      const paddingX = 16; // px-2 => 8px * 2 (좌우)
      const innerWidth = Math.max(0, containerWidth - paddingX);
      const slots = Math.max(1, Math.min(10, Math.floor(innerWidth / (minCardWidth + gapPx))));
      setVisibleSlots(slots);
      const widthForEach = Math.max(
        200,
        Math.floor((innerWidth - (slots - 1) * gapPx) / slots)
      );
      setSlotWidth(widthForEach);
      setHasMeasured(true);
    };
    const t = setTimeout(measure, 100);
    window.addEventListener("resize", measure);
    return () => {
      clearTimeout(t);
      window.removeEventListener("resize", measure);
    };
  }, [stocks]);

  // 일정 간격으로 콘텐츠만 회전
  useEffect(() => {
    if (top.length === 0) return;
    const step = Math.max(1, visibleSlots);
    const id = setInterval(() => {
      setStartIndex((idx) => (idx + step) % top.length);
    }, rotateMs);
    return () => clearInterval(id);
  }, [top.length, visibleSlots, rotateMs]);

  // top 배열 변경 시 인덱스 초기화
  useEffect(() => {
    setStartIndex(0);
  }, [top.length]);

  const isEmpty = top.length === 0;

  // 현재 표시할 종목들 계산 (고정 슬롯 수)
  const windowStocks: (Stock | undefined)[] = useMemo(() => {
    const arr: (Stock | undefined)[] = [];
    for (let i = 0; i < visibleSlots; i++) {
      arr.push(top.length ? top[(startIndex + i) % top.length] : undefined);
    }
    return arr;
  }, [top, startIndex, visibleSlots]);

  return (
    <div ref={containerRef} className="marquee-container w-full h-20 mt-3 overflow-hidden">
      {isEmpty ? (
        <div className="w-full h-full flex items-center justify-center text-sm text-gray-500 dark:text-gray-400">
          {hasMeasured ? '표시할 시가총액 상위 종목이 없습니다' : '불러오는 중...'}
        </div>
      ) : (
        <div className="flex h-full items-center gap-4 px-2">
          {windowStocks.map((s, idx) => {
            if (!s) {
              return <div key={`empty-${idx}`} className="flex-shrink-0" style={{ width: slotWidth ?? 220 }} />;
            }
            const sign = (s.changePercent || 0) >= 0 ? "+" : "";
            const isPositive = (s.changePercent || 0) >= 0;
            return (
              <div
                key={`${s.code}-${idx}`}
                className="flex-shrink-0 bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors duration-200 shadow-sm dark:shadow-gray-900/20"
                style={{ width: slotWidth ?? 240 }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="text-gray-900 dark:text-white font-semibold text-sm truncate">
                      {s.name}
                    </div>
                    <div className="text-gray-600 dark:text-gray-400 text-xs">
                      {s.code}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="text-right">
                      <div
                        className={`font-bold text-lg ${
                          isPositive ? "text-red-400" : "text-blue-400"
                        }`}
                      >
                        {sign}
                        {(s.changePercent || 0).toFixed(2)}%
                      </div>
                      <div className="text-gray-500 dark:text-gray-400 text-xs">
                        AI: {s.aiScore || "-"}
                      </div>
                    </div>
                    <div className="w-8 h-8 bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center">
                      {isPositive ? (
                        <TrendingUp className="w-4 h-4 text-red-400" />
                      ) : (
                        <TrendingDown className="w-4 h-4 text-blue-400" />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
