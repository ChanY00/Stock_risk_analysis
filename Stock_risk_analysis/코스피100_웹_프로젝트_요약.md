# 코스피100 주식 분석 웹 프로젝트 요약

## 📌 프로젝트 개요
코스피100 종목 기반의 주식 분석 웹사이트를 구축하는 프로젝트입니다.

- **백엔드**: Django (DRF 기반 REST API)
- **프론트엔드**: React.js + Tailwind CSS
- **데이터베이스**: 개발 시 SQLite, 배포 시 MySQL로 마이그레이션 예정
- **머신러닝 서버**: Flask API (감정 분석 및 클러스터링 기능 제공)

---

## 🔧 주요 기능

- 종목 리스트 조회 (`/api/stocks/`)
- 종목 상세 보기 (`/api/stocks/<code>/`)
- 재무제표 데이터 제공 (`/api/stocks/<code>/financials/`)
- 감정 분석 결과 제공 (`/api/stocks/<code>/sentiment/`)
- 클러스터링 기반 유사 종목 추천 (`/api/stocks/<code>/similar/?criteria_id=1`)
- 실시간 주가 (추후 구현 예정)
- 정기적 데이터 업데이트 기능

---

## ✅ 백엔드 개발 현황

- ✅ Django 프로젝트 구성 완료
- ✅ stocks, financials, sentiment, analysis 앱 분리 구성
- ✅ 주요 API 구현 완료 및 테스트 완료
- ✅ 모델 설계 및 테스트용 샘플 데이터 삽입 완료

---

## 🧠 감정 분석 및 클러스터링 설계

- 감정 분석: Flask 서버에서 네이버 종목토론방 댓글 수집 후 분석
- 클러스터링: Django DB 내 재무 데이터 기반으로 유사 종목 분석
- 결과는 Django DB에 저장되어 사용자에게 제공됨
- 분석 주기: 감정 분석은 1시간마다, 클러스터링은 분기별

---

## 🕒 자동화 흐름

1. `cron` 또는 `Celery`를 통해 주기적 실행
2. Django가 Flask 서버로 분석 요청
3. Flask에서 분석 후 JSON 응답 반환
4. Django에서 결과를 DB에 저장

---

## 📈 과거 가격 데이터 처리 전략

- 서비스 초기: 과거 주가 데이터를 한 번에 수집하여 저장
- 이후: 하루에 한 번 당일 종가만 갱신
- `update_or_create()`를 활용해 중복 없이 저장
- 이미 저장된 경우 `exists()`로 사전 확인 가능
