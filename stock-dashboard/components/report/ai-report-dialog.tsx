"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Lightbulb,
  AlertCircle,
  BarChart2,
  TrendingUp,
  Smile,
  Users,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { type AIReport } from "@/lib/api";

interface AIReportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  stockName: string;
  report: AIReport | null;
  loading: boolean;
  error: string | null;
}

const OpinionBadge = ({
  opinion,
}: {
  opinion: AIReport["investment_opinion"];
}) => {
  const styles = {
    "매수 타이밍": "bg-blue-100 text-blue-800 border-blue-300",
    "매도 타이밍": "bg-red-100 text-red-800 border-red-300",
    관망: "bg-gray-100 text-gray-800 border-gray-300",
  };
  return (
    <Badge className={`text-base px-4 py-2 ${styles[opinion]}`}>
      {opinion}
    </Badge>
  );
};

const ReportSection = ({
  title,
  icon,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) => (
  <div className="space-y-2">
    <h3 className="text-lg font-semibold flex items-center gap-2">
      {icon}
      {title}
    </h3>
    <div className="prose prose-sm dark:prose-invert max-w-none text-gray-700 dark:text-gray-300 bg-gray-50 dark:bg-gray-800/50 p-4 rounded-lg border">
      {children}
    </div>
  </div>
);

export function AIReportDialog({
  open,
  onOpenChange,
  stockName,
  report,
  loading,
  error,
}: AIReportDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle className="text-2xl">
            AI 종합 분석 리포트: {stockName}
          </DialogTitle>
          <DialogDescription>
            Gemini AI를 통해 생성된 동적 분석 리포트입니다.
          </DialogDescription>
        </DialogHeader>
        <div className="py-4 max-h-[70vh] overflow-y-auto pr-2 space-y-6">
          {loading && (
            <div className="space-y-4">
              <Skeleton className="h-12 w-1/3 mx-auto" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-24 w-full" />
            </div>
          )}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>오류 발생</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {report && !loading && (
            <div className="space-y-6">
              {/* 최종 투자 의견 */}
              <div className="text-center p-4 bg-gray-100 dark:bg-gray-800 rounded-lg">
                <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                  최종 투자 의견
                </h3>
                <OpinionBadge opinion={report.investment_opinion} />
              </div>

              {/* 상세 분석 */}
              <div className="space-y-4">
                <ReportSection
                  title="재무 분석"
                  icon={<BarChart2 className="h-5 w-5 text-green-500" />}
                >
                  <ReactMarkdown>{report.financial_analysis}</ReactMarkdown>
                </ReportSection>

                <ReportSection
                  title="기술적 분석"
                  icon={<TrendingUp className="h-5 w-5 text-blue-500" />}
                >
                  <ReactMarkdown>{report.technical_analysis}</ReactMarkdown>
                </ReportSection>

                <ReportSection
                  title="감정 분석"
                  icon={<Smile className="h-5 w-5 text-yellow-500" />}
                >
                  <ReactMarkdown>{report.sentiment_analysis}</ReactMarkdown>
                </ReportSection>
              </div>

              {/* 유사 그룹 내 추천 */}
              <ReportSection
                title="유사 그룹 내 유망 주식 추천"
                icon={<Users className="h-5 w-5 text-purple-500" />}
              >
                <div className="font-semibold">
                  {report.recommendation.stock_name}
                </div>
                <ReactMarkdown>{report.recommendation.reason}</ReactMarkdown>
              </ReportSection>

              {/* 예외 처리 안내 */}
              {report.excluded_sections &&
                report.excluded_sections.length > 0 && (
                  <Alert>
                    <Lightbulb className="h-4 w-4" />
                    <AlertTitle>참고</AlertTitle>
                    <AlertDescription>
                      다음 데이터가 부족하여 리포트 생성 시 제외되었습니다:{" "}
                      {report.excluded_sections.join(", ")}.
                    </AlertDescription>
                  </Alert>
                )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
