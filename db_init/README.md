# 📊 KOSPI 프로젝트 DB 초기화 가이드

## 🎯 목적
팀원들이 프로젝트 시작 시 현재와 동일한 DB 상태로 바로 시작할 수 있도록 DB 덤프를 제공합니다.

## 📁 파일 구조
```
db_init/
├── kospi_db_dump.sql     # 전체 DB 덤프 (스키마 + 데이터)
├── init_db.sh           # DB 초기화 스크립트
└── README.md            # 이 파일
```

## 🚀 사용 방법

### 1. 새로운 환경에서 시작하는 경우
```bash
# 1. 프로젝트 클론
git clone <repository-url>
cd kospi_project

# 2. DB 초기화 (자동)
docker-compose up postgres -d
# 초기화가 자동으로 실행됩니다

# 3. 백엔드 서비스 시작
docker-compose up backend -d

# 4. 전체 서비스 시작
docker-compose up -d
```

### 2. 기존 DB를 리셋하고 싶은 경우
```bash
# 1. 모든 서비스 중지
docker-compose down

# 2. DB 볼륨 삭제 (주의: 모든 데이터 삭제)
docker volume rm kospi_project_postgres_data

# 3. 서비스 재시작 (자동 초기화)
docker-compose up -d
```

### 3. 수동으로 덤프 복원하는 경우
```bash
# PostgreSQL 컨테이너가 실행 중일 때
docker exec -i kospi-postgres psql -U heehyeok -d kospi_db < db_init/kospi_db_dump.sql
```

## 📊 포함된 데이터

### 📈 주식 데이터
- KOSPI 200 종목 기본 정보
- 주가 히스토리 데이터
- 재무제표 데이터

### 🧮 분석 데이터
- 기술적 지표 데이터
- 클러스터링 분석 결과
- 유사 종목 분석 데이터

### 💭 감정 분석 데이터
- 네이버 종목토론방 크롤링 결과
- 감정 분석 점수
- 키워드 분석 결과

### 👥 사용자 데이터
- Django 인증 시스템 테이블
- 관리자 계정 (필요시)

## ⚠️ 주의사항

1. **데이터 크기**: 덤프 파일이 클 수 있으니 Git LFS 사용을 고려하세요
2. **민감 정보**: 실제 사용자 데이터나 API 키는 포함되지 않습니다
3. **버전 관리**: DB 스키마 변경 시 새로운 덤프를 생성해야 합니다

## 🔄 덤프 업데이트 방법

DB에 새로운 데이터가 추가되었거나 스키마가 변경된 경우:

```bash
# 새로운 덤프 생성
docker exec kospi-postgres pg_dump -U heehyeok -d kospi_db --clean --if-exists --create --verbose > db_init/kospi_db_dump.sql

# Git에 커밋
git add db_init/kospi_db_dump.sql
git commit -m "feat: DB 덤프 업데이트 - $(date +%Y%m%d)"
```

## 🛠️ 트러블슈팅

### Q: 초기화가 안 되는 경우
```bash
# PostgreSQL 로그 확인
docker logs kospi-postgres

# 수동 초기화
./db_init/init_db.sh
```

### Q: 권한 에러가 발생하는 경우
```bash
# 스크립트 실행 권한 부여
chmod +x db_init/init_db.sh
```

### Q: 용량이 너무 큰 경우
- Git LFS 사용하거나
- 데이터만 별도 스크립트로 분리 고려 