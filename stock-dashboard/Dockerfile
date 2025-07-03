# Next.js KOSPI Dashboard - 멀티스테이지 Docker 빌드
# 
# 🎯 전략: 빌드용 이미지 + 런타임용 이미지 분리
# 📦 결과: 용량 최적화 (1GB → 200MB)

# =============================================
# 📦 Stage 1: Dependencies (의존성 설치)
# =============================================
FROM node:18-alpine AS deps
# 💡 Alpine Linux: 가장 가벼운 Node.js 이미지 (5MB vs 200MB)

# 📝 메타데이터
LABEL stage=deps
LABEL description="Node.js dependencies installation stage"

# 🔧 Alpine Linux 패키지 관리자로 기본 도구 설치
# 💡 최신 Alpine에서는 기본 패키지로 충분함
RUN apk update && apk add --no-cache dumb-init

# 📁 작업 디렉토리 설정
WORKDIR /app

# 📋 package.json과 lock 파일만 먼저 복사 (Docker 레이어 캐싱!)
COPY package.json pnpm-lock.yaml* package-lock.json* yarn.lock* ./
# 💡 캐싱 전략: 의존성이 변경되지 않으면 이 레이어 재사용

# 🛠️ 의존성 설치 (프로덕션 + 개발)
RUN \
  if [ -f pnpm-lock.yaml ]; then \
    npm install -g pnpm && pnpm install --frozen-lockfile; \
  elif [ -f package-lock.json ]; then \
    npm ci; \
  elif [ -f yarn.lock ]; then \
    yarn install --frozen-lockfile; \
  else \
    npm install; \
  fi

# =============================================
# 🏗️ Stage 2: Builder (애플리케이션 빌드)
# =============================================
FROM node:18-alpine AS builder

# 📝 메타데이터
LABEL stage=builder
LABEL description="Next.js application build stage"

# 📁 작업 디렉토리 설정
WORKDIR /app

# 📦 이전 스테이지에서 node_modules 복사
COPY --from=deps /app/node_modules ./node_modules
# 💡 멀티스테이지 핵심: 이전 스테이지의 결과물 활용

# 📁 소스 코드 전체 복사
COPY . .

# 🔧 환경변수 설정 (빌드타임)
# 💡 Next.js 특징: 환경변수가 빌드에 포함됨
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# 🏗️ Next.js 빌드 실행
RUN \
  if [ -f pnpm-lock.yaml ]; then \
    npm install -g pnpm && pnpm build; \
  elif [ -f package-lock.json ]; then \
    npm run build; \
  elif [ -f yarn.lock ]; then \
    yarn build; \
  else \
    npm run build; \
  fi

# =============================================
# 🚀 Stage 3: Runner (프로덕션 실행)
# =============================================
FROM node:18-alpine AS runner

# 📝 메타데이터
LABEL stage=runner
LABEL description="Next.js production runtime"
LABEL maintainer="kospi-project"

# 📁 작업 디렉토리 설정
WORKDIR /app

# 🔧 프로덕션 환경변수 설정
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 👤 보안: 비루트 사용자 생성
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs
# 💡 보안 모범사례: 컨테이너를 루트로 실행하지 않음

# 📦 프로덕션 의존성만 설치
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules

# 📁 빌드된 애플리케이션 복사
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
# 💡 chown: 파일 소유권을 nextjs 사용자에게 할당

# 📁 정적 파일 복사 (public 폴더)
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# 👤 사용자 전환
USER nextjs

# 🌐 포트 노출
EXPOSE 3000
ENV PORT=3000

# 🚀 애플리케이션 실행
CMD ["npm", "start"] 