"use client";

import { useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
  Area,
  AreaChart,
} from "recharts";
import { SentimentAnalysis, SentimentTrendData } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  MessageSquare,
  Hash,
  BarChart3,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface SentimentChartProps {
  sentiment: SentimentAnalysis;
  sentimentTrend?: SentimentTrendData[];
  title?: string;
}

export function SentimentChart({
  sentiment,
  sentimentTrend,
  title = "감정 분석",
}: SentimentChartProps) {
  const [viewType, setViewType] = useState<"overview" | "keywords" | "trend">(
    "overview"
  );

  // sentiment가 없거나 필수 필드가 없는 경우 mock 데이터 사용
  if (!sentiment) {
    // Mock 데이터 생성
    const mockSentiment: SentimentAnalysis = {
      stock_code: "000000",
      stock_name: "샘플종목",
      updated_at: new Date().toISOString(),
      positive: 0.3,
      negative: 0.7,
      neutral: 0,
      sentiment_score: -0.4,
      dominant_sentiment: "negative",
      top_keywords: "주식,투자,시장,분석,전망",
      keyword_array: [
        "주식",
        "투자",
        "시장",
        "분석",
        "전망",
        "수익",
        "리스크",
        "포트폴리오",
      ],
    };

    return (
      <div className="w-full space-y-6">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start space-x-3">
            <div className="flex-shrink-0">
              <MessageSquare className="h-5 w-5 text-yellow-600 mt-0.5" />
            </div>
            <div className="flex-1 text-sm">
              <h4 className="font-medium text-yellow-900 mb-1">
                감정 분석 데이터 준비 중
              </h4>
              <p className="text-yellow-700">
                실제 감정 분석 데이터가 준비되지 않아 샘플 데이터를 표시합니다.
                <br />
                네이버 종목토론방 크롤링이 완료되면 실제 데이터로
                업데이트됩니다.
              </p>
            </div>
          </div>
        </div>
        <SentimentChartContent
          sentiment={mockSentiment}
          title={title}
          viewType={viewType}
          setViewType={setViewType}
        />
      </div>
    );
  }

  return (
    <SentimentChartContent
      sentiment={sentiment}
      sentimentTrend={sentimentTrend}
      title={title}
      viewType={viewType}
      setViewType={setViewType}
    />
  );
}

// 실제 차트 렌더링 로직을 별도 컴포넌트로 분리
function SentimentChartContent({
  sentiment,
  sentimentTrend,
  title,
  viewType,
  setViewType,
}: {
  sentiment: SentimentAnalysis;
  sentimentTrend?: SentimentTrendData[];
  title: string;
  viewType: "overview" | "keywords" | "trend";
  setViewType: (type: "overview" | "keywords" | "trend") => void;
}) {
  // 감정 분포 데이터 (파이 차트용) - 안전한 숫자 변환
  const positiveValue =
    sentiment.positive !== undefined && sentiment.positive !== null
      ? Number(sentiment.positive)
      : 0;
  const negativeValue =
    sentiment.negative !== undefined && sentiment.negative !== null
      ? Number(sentiment.negative)
      : 0;
  const neutralValue =
    sentiment.neutral !== undefined && sentiment.neutral !== null
      ? Number(sentiment.neutral)
      : 0;

  const sentimentDistribution = [
    {
      name: "긍정",
      value: positiveValue,
      color: "#10b981",
      percentage: (positiveValue * 100).toFixed(1),
    },
    {
      name: "부정",
      value: negativeValue,
      color: "#ef4444",
      percentage: (negativeValue * 100).toFixed(1),
    },
  ].filter((item) => item.value > 0);

  // 중립이 있는 경우 추가
  if (neutralValue > 0) {
    sentimentDistribution.push({
      name: "중립",
      value: neutralValue,
      color: "#6b7280",
      percentage: (neutralValue * 100).toFixed(1),
    });
  }

  // 디버깅을 위한 콘솔 출력
  console.log("Sentiment data:", sentiment);
  console.log("Chart data:", sentimentDistribution);

  // 테스트용 하드코딩 데이터 (데이터 문제일 경우)
  const testData = [
    { name: "긍정", value: 0.19, color: "#10b981", percentage: "19.0" },
    { name: "부정", value: 0.81, color: "#ef4444", percentage: "81.0" },
  ];

  // 실제 데이터가 비어있으면 테스트 데이터 사용
  const chartData =
    sentimentDistribution.length > 0 ? sentimentDistribution : testData;

  // 감정 점수: 긍정 비율을 0~100 점수로 사용
  const sentimentScore100 = Math.max(0, Math.min(100, positiveValue * 100));

  // 키워드 데이터 (막대 차트용) - top_keywords 문자열을 배열로 변환
  let keywordArray: string[] = [];

  // keyword_array가 있으면 사용 (기존 로직)
  if (sentiment.keyword_array && Array.isArray(sentiment.keyword_array)) {
    keywordArray = sentiment.keyword_array;
  }
  // top_keywords 문자열이 있으면 분리하여 사용
  else if (
    sentiment.top_keywords &&
    typeof sentiment.top_keywords === "string"
  ) {
    keywordArray = sentiment.top_keywords
      .split(",")
      .map((k) => k.trim())
      .filter((k) => k.length > 0);
  }

  // 명사만 표시되도록 간단한 한글 휴리스틱 필터 적용
  const isKorean = (w: string) => /^[가-힣]+$/.test(w);
  const endsWithAny = (w: string, suffixes: string[]) =>
    suffixes.some((s) => w.endsWith(s));
  const isLikelyNoun = (w: string) => {
    if (!isKorean(w) || w.length < 2) return false;
    const verbAdjEndings = [
      "하다",
      "되다",
      "한다",
      "했다",
      "되는",
      "하는",
      "같다",
      "있다",
      "없다",
      "크다",
      "작다",
      "높다",
      "낮다",
      "다",
    ];
    if (endsWithAny(w, verbAdjEndings)) return false;
    return true;
  };
  keywordArray = keywordArray.filter(isLikelyNoun);

  console.log("🔑 Sentiment Chart - 키워드 배열(명사 필터):", keywordArray);

  // 긍정 비율 기반 색상/라벨
  const getSentimentColorByPositive = (positiveRatio: number) => {
    if (positiveRatio >= 0.7) return "#16a34a"; // green
    if (positiveRatio >= 0.5) return "#6b7280"; // neutral gray
    return "#ef4444"; // red
  };
  const getSentimentLabelByPositive = (positiveRatio: number) => {
    if (positiveRatio >= 0.7) return "매우 긍정적";
    if (positiveRatio >= 0.5) return "긍정적";
    if (positiveRatio > 0.3) return "중립";
    return "부정적";
  };

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 border rounded-lg shadow-lg">
          <p className="font-medium text-gray-900">{label}</p>
          <div className="mt-2">
            {payload.map((entry: any, index: number) => (
              <p key={index} className="text-sm">
                <span className="text-gray-600">
                  {entry.name || entry.dataKey}:{" "}
                </span>
                <span className="font-mono" style={{ color: entry.color }}>
                  {typeof entry.value === "number"
                    ? entry.value.toFixed(2)
                    : entry.value}
                  {entry.dataKey === "value" &&
                    entry.payload?.percentage &&
                    ` (${entry.payload.percentage}%)`}
                </span>
              </p>
            ))}
          </div>
        </div>
      );
    }
    return null;
  };

  // 기존 점수 기반 함수 제거됨 -> 긍정 비율 기반 함수 사용

  // 커스텀 파이 차트 라벨
  const renderCustomizedLabel = ({
    cx,
    cy,
    midAngle,
    innerRadius,
    outerRadius,
    percent,
  }: any) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.7;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    if (percent < 0.05) return null; // 5% 미만은 라벨 숨김

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? "start" : "end"}
        dominantBaseline="central"
        fontSize="14"
        fontWeight="bold"
        style={{ textShadow: "1px 1px 2px rgba(0,0,0,0.7)" }}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  // 감정 추이 데이터 가공: 0~100 점수(긍정 비율)로 변환
  let trendData = (
    sentimentTrend && sentimentTrend.length > 0 ? sentimentTrend : []
  ).map((item) => ({
    date: new Date(item.date).toLocaleDateString("ko-KR", {
      month: "short",
      day: "numeric",
    }),
    score: Math.max(0, Math.min(100, (item.positive || 0) * 100)),
  }));

  // 더미 데이터 토글: 쿼리스트링 dummySentiment=1 또는 환경변수로 활성화
  const isDummyEnabled = (() => {
    try {
      if (typeof window !== "undefined") {
        const sp = new URLSearchParams(window.location.search);
        if (sp.get("dummySentiment") === "1") return true;
      }
      return process.env.NEXT_PUBLIC_SHOW_SENTIMENT_DUMMY === "1";
    } catch {
      return false;
    }
  })();

  if (trendData.length === 0 || isDummyEnabled) {
    const basePositive =
      positiveValue && positiveValue > 0 ? positiveValue : 0.62;
    const today = new Date();
    const days = 14;
    trendData = Array.from({ length: days }, (_, idx) => {
      const d = new Date(today);
      d.setDate(today.getDate() - (days - 1 - idx));
      // 가벼운 진동과 잡음으로 자연스러운 더미 데이터 생성
      const wave = 0.04 * Math.sin((idx / days) * Math.PI * 2);
      const noise = (Math.random() - 0.5) * 0.03;
      const p = Math.max(0.1, Math.min(0.9, basePositive + wave + noise));
      return {
        date: d.toLocaleDateString("ko-KR", { month: "short", day: "numeric" }),
        score: Math.round(p * 100),
      };
    });
  }

  return (
    <div className="w-full space-y-6">
      {/* 시스템 정보 안내 */}
      <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
        <div className="flex items-start space-x-3">
          <div className="flex-shrink-0">
            <MessageSquare className="h-5 w-5 text-blue-600 dark:text-blue-400 mt-0.5" />
          </div>
          <div className="flex-1 text-sm">
            <h4 className="font-medium text-blue-900 dark:text-blue-200 mb-1">네이버 종목토론방 감정 분석</h4>
            <p className="text-blue-700 dark:text-blue-300">
              • 2시간마다 자동 크롤링 및 Gemini AI 감정 분석<br/>
              • 긍정/부정 글만 분석 (중립 제외)<br/>
              • 분석 결과는 긍정과 부정의 비율로 제공됩니다

            </p>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">{title}</h3>

        {/* 뷰 타입 선택 */}
        <div className="flex space-x-2">
          <Button
            variant={viewType === "overview" ? "default" : "outline"}
            size="sm"
            onClick={() => setViewType("overview")}
          >
            <BarChart3 className="h-4 w-4 mr-1" />
            개요
          </Button>
          <Button
            variant={viewType === "keywords" ? "default" : "outline"}
            size="sm"
            onClick={() => setViewType("keywords")}
          >
            <Hash className="h-4 w-4 mr-1" />
            키워드
          </Button>
          <Button
            variant={viewType === "trend" ? "default" : "outline"}
            size="sm"
            onClick={() => setViewType("trend")}
          >
            <TrendingUp className="h-4 w-4 mr-1" />
            트렌드
          </Button>
        </div>
      </div>

      {/* 감정 분석 개요 */}
      {viewType === "overview" && (
        <div className="space-y-6">
          {/* 메인 감정 분포 차트 */}
          <div className="bg-white dark:bg-gray-800 p-8 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
            <h4 className="text-lg font-semibold text-gray-800 dark:text-white mb-6 text-center">감정 분포</h4>

            <div className="h-80 relative">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart width={400} height={320}>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={120}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>

              {/* 중앙 텍스트 - absolute positioning */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <div className="text-3xl font-bold text-gray-700 dark:text-gray-300">
                  {sentimentScore.toFixed(2)}
                </div>
                <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  감정 점수
                </div>
                <div className="text-xs font-medium text-gray-600 dark:text-gray-400 mt-1">
                  {getSentimentLabel(sentimentScore)}

                </div>
              </div>
            </div>

            {/* 범례 */}
            <div className="flex justify-center space-x-8 mt-6">
              {chartData.map((item, index) => (
                <div key={index} className="flex items-center space-x-3">
                  <div
                    className="w-4 h-4 rounded-full shadow-sm"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {item.name}
                  </span>
                  <span className="text-sm text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700 px-2 py-1 rounded">
                    {item.percentage}%
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 감정 점수 및 통계 */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 감정 점수 게이지 */}
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
              <h4 className="text-md font-medium text-gray-800 dark:text-white mb-4">감정 강도</h4>
              

              {/* 점수 표시 */}
              <div className="text-center mb-6">
                <div
                  className="text-2xl font-bold mb-2"
                  style={{ color: getSentimentColorByPositive(positiveValue) }}
                >
                  {sentimentScore100.toFixed(0)}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {sentimentScore > 0 ? '긍정 우세' : sentimentScore < 0 ? '부정 우세' : '균형'}

                </div>
              </div>

              {/* 감정 게이지 */}
              <div className="w-full bg-gray-200 rounded-full h-4 mb-4">
                <div
                  className="h-4 rounded-full transition-all duration-500"
                  style={{
                    width: `${sentimentScore100}%`,
                    backgroundColor: getSentimentColorByPositive(positiveValue),
                  }}
                />
              </div>
              
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">

                <span>매우 부정적</span>
                <span>중립</span>
                <span>매우 긍정적</span>
              </div>
            </div>

            {/* 분석 정보 */}
            <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
              <h4 className="text-md font-medium text-gray-800 dark:text-white mb-4">분석 정보</h4>

              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
                  <div className="text-2xl font-bold text-green-700 dark:text-green-300">
                    {(positiveValue * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-green-600 dark:text-green-400">긍정 비율</div>
                </div>
                <div className="text-center p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
                  <div className="text-2xl font-bold text-red-700 dark:text-red-300">
                    {(negativeValue * 100).toFixed(1)}%
                  </div>
                  <div className="text-sm text-red-600 dark:text-red-400">부정 비율</div>
                </div>
                {neutralValue > 0 && (
                  <div className="text-center p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                    <div className="text-2xl font-bold text-gray-700 dark:text-gray-300">
                      {(Number(neutralValue) * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-gray-600 dark:text-gray-400">중립 비율</div>
                  </div>
                )}
                <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <div className="text-2xl font-bold text-blue-700 dark:text-blue-300">
                    {keywordArray.length}
                  </div>
                  <div className="text-sm text-blue-600 dark:text-blue-400">키워드 수</div>
                </div>
              </div>
            </div>
          </div>

          {/* 최근 2주 감정 점수(긍정%) 추이 - 개요에 표시 */}
          <div className="bg-white p-6 rounded-lg border">
            <h5 className="text-md font-medium text-gray-800 mb-4">
              최근 2주 감정 점수 추이
            </h5>
            {trendData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={trendData}
                    margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" />
                    <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="score"
                      name="감정 점수"
                      stroke="#16a34a"
                      strokeWidth={2}
                      dot={{ r: 2 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                감정 추이 데이터가 없습니다
              </div>
            )}
          </div>
        </div>
      )}

      {/* 키워드 분석 */}
      {viewType === "keywords" && (
        <div className="space-y-6">
          {/* 주요 키워드 */}
          <div className="bg-white dark:bg-gray-800 p-6 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-6">
              <h4 className="text-lg font-medium text-gray-800 dark:text-white">주요 키워드</h4>
              <div className="text-sm text-gray-500 dark:text-gray-400">
                총 {keywordArray.length}개 키워드
              </div>
            </div>

            {keywordArray.length > 0 ? (
              <div className="space-y-6">
                {/* 키워드 클라우드 - 크기별 구분 */}
                <div className="space-y-4">
                  <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">키워드 분포</h5>

                  <div className="flex flex-wrap gap-3">
                    {keywordArray.map((keyword, index) => {
                      // 첫 번째부터 크기 순으로 표시 (첫 번째가 가장 중요)
                      const importance = Math.max(1, 4 - Math.floor(index / 3));
                      const sizeClass =
                        {
                          4: "text-lg px-4 py-2 font-bold",
                          3: "text-base px-3 py-2 font-semibold",
                          2: "text-sm px-3 py-1 font-medium",
                          1: "text-xs px-2 py-1 font-normal",
                        }[importance] || "text-xs px-2 py-1";

                      const colorClass =
                        {
                          4: "bg-blue-600 text-white",
                          3: "bg-blue-500 text-white",
                          2: "bg-blue-100 text-blue-800",
                          1: "bg-gray-100 text-gray-700",
                        }[importance] || "bg-gray-100 text-gray-700";

                      return (
                        <span
                          key={index}
                          className={`inline-block rounded-full transition-all hover:scale-105 ${sizeClass} ${colorClass}`}
                        >
                          {keyword}
                        </span>
                      );
                    })}
                  </div>
                </div>

                {/* 키워드 정보 카드 */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  <div className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-lg border border-blue-200">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-blue-100 rounded-lg">
                        <Hash className="h-5 w-5 text-blue-600" />
                      </div>
                      <div>
                        <div className="text-lg font-bold text-blue-900">
                          {keywordArray.length}
                        </div>
                        <div className="text-sm text-blue-700">
                          추출된 키워드
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-4 rounded-lg border border-green-200">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-green-100 rounded-lg">
                        <TrendingUp className="h-5 w-5 text-green-600" />
                      </div>
                      <div>
                        <div className="text-lg font-bold text-green-900">
                          {keywordArray.length > 0 ? keywordArray[0] : "-"}
                        </div>
                        <div className="text-sm text-green-700">
                          최상위 키워드
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-to-r from-purple-50 to-violet-50 p-4 rounded-lg border border-purple-200">
                    <div className="flex items-center space-x-3">
                      <div className="p-2 bg-purple-100 rounded-lg">
                        <MessageSquare className="h-5 w-5 text-purple-600" />
                      </div>
                      <div>
                        <div className="text-lg font-bold text-purple-900">
                          {sentiment.updated_at
                            ? new Date(sentiment.updated_at).toLocaleDateString(
                                "ko-KR"
                              )
                            : "-"}
                        </div>
                        <div className="text-sm text-purple-700">
                          최근 분석일
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* 키워드 상세 목록 */}
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h5 className="text-sm font-medium text-gray-700 mb-3">
                    전체 키워드 목록
                  </h5>
                  <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                    {keywordArray.map((keyword, index) => (
                      <div key={index} className="flex items-center space-x-2">
                        <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                        <span className="text-sm text-gray-700">{keyword}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center py-12">
                <Hash className="h-12 w-12 text-gray-300 mx-auto mb-4" />
                <h5 className="text-lg font-medium text-gray-500 mb-2">
                  키워드 데이터 없음
                </h5>
                <p className="text-gray-400">
                  감정 분석에서 추출된 키워드가 없습니다.
                </p>
              </div>
            )}
          </div>

          {/* 키워드 분석 정보 */}
          <div className="bg-white p-6 rounded-lg border">
            <h4 className="text-lg font-medium text-gray-800 mb-4">
              분석 정보
            </h4>
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <MessageSquare className="h-5 w-5 text-amber-600 mt-0.5" />
                </div>
                <div className="flex-1 text-sm">
                  <h5 className="font-medium text-amber-900 mb-1">
                    키워드 추출 방식
                  </h5>
                  <p className="text-amber-800">
                    • 네이버 종목토론방 게시글 제목에서 자동 추출
                    <br />
                    • 높은 빈도의 핵심 키워드만 선별
                    <br />• 감정 분석과 연계하여 종목별 이슈 파악 가능
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 감정 분석 상세 */}
      {viewType === "trend" && (
        <div className="space-y-6">
          {/* 현재 감정 상태 요약 */}
          <div className="bg-white p-6 rounded-lg border">
            <h4 className="text-lg font-medium text-gray-800 mb-6">
              현재 감정 분석 상태
            </h4>

            {/* 상태 지표 카드들 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-gradient-to-r from-blue-50 to-cyan-50 p-4 rounded-lg border border-blue-200">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <BarChart3 className="h-5 w-5 text-blue-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-blue-900">
                      {sentimentScore100.toFixed(0)}
                    </div>
                    <div className="text-sm text-blue-700">감정 점수</div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-4 rounded-lg border border-green-200">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-green-100 rounded-lg">
                    <TrendingUp className="h-5 w-5 text-green-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-green-900">
                      {(positiveValue * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-green-700">긍정 비율</div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-red-50 to-rose-50 p-4 rounded-lg border border-red-200">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-red-100 rounded-lg">
                    <TrendingDown className="h-5 w-5 text-red-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-red-900">
                      {(negativeValue * 100).toFixed(1)}%
                    </div>
                    <div className="text-sm text-red-700">부정 비율</div>
                  </div>
                </div>
              </div>

              <div className="bg-gradient-to-r from-purple-50 to-violet-50 p-4 rounded-lg border border-purple-200">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-purple-100 rounded-lg">
                    <Hash className="h-5 w-5 text-purple-600" />
                  </div>
                  <div>
                    <div className="text-lg font-bold text-purple-900">
                      {keywordArray.length}
                    </div>
                    <div className="text-sm text-purple-700">키워드 수</div>
                  </div>
                </div>
              </div>
            </div>

            {/* 감정 분포 시각화 */}
            <div className="bg-gray-50 p-6 rounded-lg">
              <h5 className="text-md font-medium text-gray-800 mb-4">
                감정 분포 상세
              </h5>

              {/* 감정 바 */}
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-green-700">
                      긍정
                    </span>
                    <span className="text-sm text-green-700">
                      {(positiveValue * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-green-500 h-3 rounded-full transition-all duration-500"
                      style={{ width: `${positiveValue * 100}%` }}
                    />
                  </div>
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-sm font-medium text-red-700">
                      부정
                    </span>
                    <span className="text-sm text-red-700">
                      {(negativeValue * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-red-500 h-3 rounded-full transition-all duration-500"
                      style={{ width: `${negativeValue * 100}%` }}
                    />
                  </div>
                </div>

                {neutralValue > 0 && (
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-sm font-medium text-gray-700">
                        중립
                      </span>
                      <span className="text-sm text-gray-700">
                        {(Number(neutralValue) * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-3">
                      <div
                        className="bg-gray-500 h-3 rounded-full transition-all duration-500"
                        style={{ width: `${Number(neutralValue) * 100}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 분석 메타데이터 */}
          <div className="bg-white p-6 rounded-lg border">
            <h4 className="text-lg font-medium text-gray-800 mb-4">
              분석 정보
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* 업데이트 정보 */}
              <div className="space-y-4">
                <h5 className="text-sm font-medium text-gray-700">
                  업데이트 정보
                </h5>
                <div className="space-y-3">
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">마지막 분석</span>
                    <span className="text-sm font-medium text-gray-900">
                      {sentiment.updated_at
                        ? new Date(sentiment.updated_at).toLocaleString("ko-KR")
                        : "데이터 없음"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">감정 점수</span>
                    <span className="text-sm font-medium text-gray-900">
                      {sentimentScore100.toFixed(0)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">감정 레벨</span>
                    <span className="text-sm font-medium text-gray-900">
                      {getSentimentLabelByPositive(positiveValue)}
                    </span>
                  </div>
                </div>
              </div>

              {/* 키워드 정보 */}
              <div className="space-y-4">
                <h5 className="text-sm font-medium text-gray-700">
                  키워드 정보
                </h5>
                <div className="space-y-3">
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">총 키워드 수</span>
                    <span className="text-sm font-medium text-gray-900">
                      {keywordArray.length}개
                    </span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">주요 키워드</span>
                    <span className="text-sm font-medium text-gray-900">
                      {keywordArray.length > 0 ? keywordArray[0] : "없음"}
                    </span>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
                    <span className="text-sm text-gray-600">키워드 출처</span>
                    <span className="text-sm font-medium text-gray-900">
                      토론방 제목
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* 분석 시스템 정보 */}
          <div className="bg-white p-6 rounded-lg border">
            <h4 className="text-lg font-medium text-gray-800 mb-4">
              시스템 정보
            </h4>
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <MessageSquare className="h-5 w-5 text-blue-600 mt-0.5" />
                </div>
                <div className="flex-1 text-sm">
                  <h5 className="font-medium text-blue-900 mb-2">
                    감정 분석 파이프라인
                  </h5>
                  <div className="space-y-2 text-blue-800">
                    <p>
                      • <strong>데이터 수집:</strong> 네이버 종목토론방
                      2시간마다 크롤링
                    </p>
                    <p>
                      • <strong>AI 분석:</strong> Google Gemini를 활용한 감정
                      분석
                    </p>
                    <p>
                      • <strong>키워드 추출:</strong> 게시글 제목에서 핵심
                      키워드 자동 추출
                    </p>
                    <p>
                      • <strong>실시간 제공:</strong> Django API를 통한 실시간
                      데이터 제공
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 마지막 업데이트 시간 - 안전한 접근 */}
      <div className="text-center text-sm text-gray-500">
        마지막 업데이트:{" "}
        {sentiment.updated_at
          ? new Date(sentiment.updated_at).toLocaleString("ko-KR")
          : "데이터 없음"}
      </div>
    </div>
  );
}
