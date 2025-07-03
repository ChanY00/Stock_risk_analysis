# 📈 KOSPI 실시간 주식 대시보드

> **AI 기반 실시간 주식 분석 플랫폼**  
> 한국 주식 시장의 실시간 데이터와 AI 감정 분석을 통한 스마트 투자 인사이트 제공

![Next.js](https://img.shields.io/badge/Next.js-15-black)
![Django](https://img.shields.io/badge/Django-4.x-green)
![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue)
![Docker](https://img.shields.io/badge/Docker-Compose-blue)

---

## 🎯 프로젝트 소개

**KOSPI 실시간 주식 대시보드**는 한국 주식 시장의 복잡한 데이터를 직관적이고 아름다운 인터페이스로 제공하는 종합 투자 분석 플랫폼입니다.

### 💡 **핵심 가치**
- 📊 **통합된 정보**: 주가, 재무제표, 뉴스, 감정 분석을 한 곳에서
- 🤖 **AI 기반 인사이트**: 네이버 종목토론방 크롤링을 통한 실시간 감정 분석  
- 📱 **직관적인 UX**: 복잡한 금융 데이터를 누구나 쉽게 이해할 수 있게
- ⚡ **실시간 업데이트**: WebSocket 기반 실시간 주가 및 지표 업데이트

---

## ✨ 주요 기능

### 📈 **실시간 주가 모니터링**
- KOSPI 200 종목 실시간 주가 추적
- 기간별 필터링 및 선형/캔들스틱 차트
- WebSocket 기반 실시간 업데이트

### 🧠 **AI 감정 분석**
- 네이버 종목토론방 자동 크롤링
- Google Gemini AI 기반 감정 분석
- 긍정/부정/중립 감정 점수 및 키워드 추출

### 📊 **기술적 분석**
- 이동평균선, RSI, MACD, 볼린저 밴드
- 거래량 분석 및 패턴 인식

### 💰 **재무 분석**
- 실시간 재무제표 데이터
- PER, PBR, ROE 등 주요 투자 지표
- 섹터별 비교 분석

### 🎯 **포트폴리오 관리**
- 개인 관심종목 관리
- 포트폴리오 수익률 추적 및 리스크 분석

### 🔬 **클러스터링 분석**
- 머신러닝 기반 유사 종목 그룹핑
- 투자 스타일별 종목 추천

---

## 🚀 실행 방법

### 🐳 **Docker로 한 번에 실행 (권장)**

```bash
# 1. 프로젝트 클론
git clone <repository-url>
cd kospi_project

# 2. 환경 변수 설정 (선택사항)
cp stock_backend/.env.example stock_backend/.env
cp stock-dashboard/.env.local.example stock-dashboard/.env.local

# 3. 전체 시스템 실행
docker-compose up -d

# 4. 브라우저에서 접속
# 🌐 http://localhost:3000
```

**⏱️ 약 2-3분 후 모든 서비스가 준비됩니다!**

### 📱 **접속 주소**
- **📊 메인 대시보드**: http://localhost:3000
- **🔧 API 서버**: http://localhost:8000  
- **💭 감정분석 API**: http://localhost:5001
- **👨‍💼 관리자 페이지**: http://localhost:8000/admin

---

## 🏗️ 기술 스택

- **프론트엔드**: Next.js 15 + TypeScript + Tailwind CSS
- **백엔드**: Django REST Framework + PostgreSQL + Redis
- **AI 분석**: Flask + Google Gemini AI + scikit-learn
- **인프라**: Docker Compose + WebSocket

---

## 🎁 포함된 데이터

프로젝트에는 즉시 체험 가능한 실제 데이터가 포함되어 있습니다:

- ✅ **KOSPI 200 종목** 기본 정보
- ✅ **12개월 주가 히스토리** (일봉 데이터)  
- ✅ **재무제표 데이터** (최근 4분기)
- ✅ **기술적 지표** (이동평균, RSI, MACD 등)
- ✅ **감정 분석 샘플** (네이버 종목토론방)
- ✅ **클러스터링 결과** (유사 종목 그룹)

---

**Happy Trading! 📈** 