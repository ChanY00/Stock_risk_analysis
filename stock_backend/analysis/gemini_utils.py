import os
import json
import time
import requests
import logging
from pathlib import Path
from typing import Dict, Optional
from django.conf import settings
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# ===================== 환경 설정 =====================
def load_gemini_api_key():
    """Gemini API 키를 여러 위치에서 로드 시도"""
    # 1. 환경 변수에서 직접 가져오기 (가장 우선순위 높음)
    api_key = os.getenv('GEMINI_API_KEY')
    if api_key:
        logger.info("✅ 환경 변수에서 Gemini API 키 로드 성공")
        return api_key
    else:
        logger.debug(f"환경 변수에서 GEMINI_API_KEY를 찾을 수 없음 (os.getenv('GEMINI_API_KEY') = {repr(api_key)})")
    
    # 2. Django settings에서 가져오기
    try:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if api_key:
            logger.debug("✅ Django settings에서 Gemini API 키 로드 성공")
            return api_key
    except Exception as e:
        logger.debug(f"Django settings 로드 시도 실패: {e}")
    
    # 3. Stock_risk_analysis/.env 파일에서 로드 시도
    try:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        sentiment_env_path = project_root / 'Stock_risk_analysis' / '.env'
        if sentiment_env_path.exists():
            load_dotenv(sentiment_env_path, override=False)
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                logger.info("✅ Stock_risk_analysis/.env 파일에서 Gemini API 키 로드 성공")
                return api_key
            else:
                logger.debug(f"Stock_risk_analysis/.env 파일은 존재하지만 GEMINI_API_KEY가 없습니다.")
        else:
            logger.debug(f"Stock_risk_analysis/.env 파일이 존재하지 않습니다: {sentiment_env_path}")
    except Exception as e:
        logger.debug(f"Stock_risk_analysis/.env 로드 시도 실패 (무시 가능): {e}")
    
    # 4. stock_backend/.env 파일에서 로드 시도
    try:
        backend_env_path = Path(__file__).resolve().parent.parent.parent / '.env'
        if backend_env_path.exists():
            load_dotenv(backend_env_path, override=False)
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                logger.info("✅ stock_backend/.env 파일에서 Gemini API 키 로드 성공")
                return api_key
    except Exception as e:
        logger.debug(f"stock_backend/.env 로드 시도 실패: {e}")
    
    # 5. 기본 .env 파일에서 로드 시도 (프로젝트 루트)
    try:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        root_env_path = project_root / '.env'
        if root_env_path.exists():
            load_dotenv(root_env_path, override=False)
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                logger.info("✅ 프로젝트 루트/.env 파일에서 Gemini API 키 로드 성공")
                return api_key
    except Exception as e:
        logger.debug(f"프로젝트 루트/.env 로드 시도 실패: {e}")
    
    logger.warning("⚠️ 모든 위치에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    return None


# ===================== API 설정 =====================
HEADERS = {"Content-Type": "application/json"}

def get_api_key_and_url():
    """API 키와 URL을 런타임에 가져오기 (매번 재로드)"""
    api_key = load_gemini_api_key()
    if api_key:
        api_url = (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.0-flash:generateContent"
            f"?key={api_key}"
        )
        return api_key, api_url
    return None, None


# ===================== 재시도 대기 시간 추출 =====================
def extract_retry_delay(resp: requests.Response) -> int:
    """API 응답에서 재시도 대기 시간 추출"""
    try:
        details = resp.json().get('error', {}).get('details', [])
        for d in details:
            if d.get('@type', '').endswith('RetryInfo'):
                return int(d['retryDelay'].rstrip('s'))
    except:
        pass
    return 60  # 기본 대기 시간 (초)


# ===================== API 호출 (재시도 로직 포함) =====================
def call_gemini_api(
    payload: Dict,
    max_retries: int = 3,
    timeout: int = 30
) -> requests.Response:
    """
    Gemini API 호출 (재시도 로직 포함)
    
    Args:
        payload: API 요청 페이로드
        max_retries: 최대 재시도 횟수
        timeout: 요청 타임아웃 (초)
    
    Returns:
        Response 객체
    
    Raises:
        ValueError: API 키가 설정되지 않은 경우
        Exception: API 호출 실패 시
    """
    # 런타임에 API 키 로드
    api_key, api_url = get_api_key_and_url()
    
    if not api_key or not api_url:
        # 디버깅을 위한 상세 정보 로깅
        logger.error("=" * 50)
        logger.error("⚠️ GEMINI_API_KEY 로드 실패!")
        logger.error("다음 위치에서 API 키를 찾으려고 시도했습니다:")
        logger.error("1. 환경 변수 (os.getenv('GEMINI_API_KEY'))")
        logger.error("2. Django settings (settings.GEMINI_API_KEY)")
        logger.error("3. Stock_risk_analysis/.env 파일")
        logger.error("4. 기본 .env 파일")
        logger.error("=" * 50)
        error_msg = "GEMINI_API_KEY가 설정되지 않았습니다. 환경 변수 또는 .env 파일에 API 키를 설정해주세요."
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    logger.debug(f"Gemini API 키 로드 성공 (키 길이: {len(api_key)} 문자)")
    
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, headers=HEADERS, json=payload, timeout=timeout)
            
            if response.status_code == 200:
                return response
            
            # 429 Too Many Requests 에러 처리
            if response.status_code == 429:
                delay = extract_retry_delay(response)
                logger.warning(f"[429] Gemini API 요청 한도 초과. {delay}초 후 재시도 ({attempt+1}/{max_retries})")
                time.sleep(delay)
                continue
            
            # 기타 에러
            error_msg = f"Gemini API 호출 실패: {response.status_code} - {response.text}"
            logger.error(error_msg)
            
            if attempt == max_retries - 1:  # 마지막 시도 실패
                raise Exception(error_msg)
            
            # 재시도 전 대기
            time.sleep(3)
            
        except requests.exceptions.Timeout:
            logger.warning(f"[Timeout] Gemini API 요청 타임아웃 ({attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                raise Exception("Gemini API 요청 타임아웃")
            time.sleep(3)
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"[Exception] Gemini API 요청 실패: {e} ({attempt+1}/{max_retries})")
            if attempt == max_retries - 1:
                raise Exception(f"Gemini API 요청 실패: {str(e)}")
            time.sleep(3)
    
    raise Exception("Gemini API 호출 실패: 최대 재시도 횟수 초과")


def generate_stock_report(stock_data: Dict) -> Dict:
    """
    실제 Gemini API를 사용하여 주식 종합 리포트 생성
    
    Args:
        stock_data: 주식 데이터 딕셔너리
            - stock_code, stock_name, sector
            - current_price, market_cap, per, pbr, roe, dividend_yield
            - financials: {revenue, operating_income, net_income, ...}
            - technical: {rsi, macd, ma5, ma20, ma60, ...}
            - sentiment: {sentiment_score, positive_ratio, negative_ratio, top_keywords}
            - similar_stocks: 유사 종목 리스트
    
    Returns:
        리포트 딕셔너리
    """
    try:
        # 프롬프트 생성
        prompt = _build_report_prompt(stock_data)
        
        # Gemini API 호출
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 2048,
            }
        }
        
        logger.info(f"Gemini API 호출 중... (종목: {stock_data.get('stock_name')})")
        response = call_gemini_api(payload, max_retries=3, timeout=30)
        
        # 응답 텍스트 추출
        result = response.json()
        report_text = result['candidates'][0]['content']['parts'][0]['text']
        logger.info("✅ Gemini API 호출 성공")
        
        # JSON 파싱 시도
        try:
            # JSON 형식으로 반환되는 경우
            report_dict = json.loads(report_text)
            return _validate_and_format_report(report_dict, stock_data)
        except json.JSONDecodeError:
            # 텍스트 형식으로 반환되는 경우 파싱
            logger.debug("JSON 형식이 아닌 텍스트 응답, 파싱 시도...")
            return _parse_text_report(report_text, stock_data)
            
    except Exception as e:
        logger.error(f"Gemini API 호출 중 오류 발생: {str(e)}")
        raise


def _build_report_prompt(stock_data: Dict) -> str:
    """주식 데이터를 기반으로 Gemini API 프롬프트 생성"""
    
    stock_name = stock_data.get('stock_name', '')
    stock_code = stock_data.get('stock_code', '')
    sector = stock_data.get('sector', '')
    current_price = stock_data.get('current_price')
    market_cap = stock_data.get('market_cap')
    per = stock_data.get('per')
    pbr = stock_data.get('pbr')
    roe = stock_data.get('roe')
    dividend_yield = stock_data.get('dividend_yield')
    
    # 재무 데이터
    financials = stock_data.get('financials')
    financial_info = ""
    if financials:
        revenue = financials.get('revenue', 0)
        operating_income = financials.get('operating_income', 0)
        net_income = financials.get('net_income', 0)
        total_assets = financials.get('total_assets')
        total_liabilities = financials.get('total_liabilities')
        total_equity = financials.get('total_equity')
        
        financial_info = f"""
## 재무 정보
- 매출액: {revenue:,}원 (백만원 단위)
- 영업이익: {operating_income:,}원 (백만원 단위)
- 순이익: {net_income:,}원 (백만원 단위)
"""
        if total_assets:
            financial_info += f"- 총자산: {total_assets:,}원 (백만원 단위)\n"
        if total_liabilities:
            financial_info += f"- 총부채: {total_liabilities:,}원 (백만원 단위)\n"
        if total_equity:
            financial_info += f"- 총자본: {total_equity:,}원 (백만원 단위)\n"
        
        # 재무 비율 계산
        if revenue and revenue > 0:
            operating_margin = (operating_income / revenue) * 100
            net_margin = (net_income / revenue) * 100
            financial_info += f"- 영업이익률: {operating_margin:.2f}%\n"
            financial_info += f"- 순이익률: {net_margin:.2f}%\n"
        
        if total_assets and total_assets > 0:
            roa = (net_income / total_assets) * 100
            financial_info += f"- ROA (자산수익률): {roa:.2f}%\n"
        
        if total_equity and total_equity > 0:
            debt_ratio = (total_liabilities / total_equity) * 100 if total_liabilities else 0
            equity_ratio = (total_equity / total_assets) * 100 if total_assets else 0
            financial_info += f"- 부채비율: {debt_ratio:.2f}%\n"
            financial_info += f"- 자기자본비율: {equity_ratio:.2f}%\n"
    
    # 기술적 지표
    technical = stock_data.get('technical')
    technical_info = ""
    if technical:
        rsi = technical.get('rsi')
        macd = technical.get('macd')
        macd_signal = technical.get('macd_signal')
        ma5 = technical.get('ma5')
        ma20 = technical.get('ma20')
        ma60 = technical.get('ma60')
        bollinger_upper = technical.get('bollinger_upper')
        bollinger_lower = technical.get('bollinger_lower')
        
        technical_info = "## 기술적 지표\n"
        if rsi is not None:
            technical_info += f"- RSI(14): {rsi:.2f} "
            if rsi > 70:
                technical_info += "(과매수 구간)\n"
            elif rsi < 30:
                technical_info += "(과매도 구간)\n"
            else:
                technical_info += "(중립 구간)\n"
        
        if macd is not None and macd_signal is not None:
            technical_info += f"- MACD: {macd:.2f}, Signal: {macd_signal:.2f}\n"
            if macd > macd_signal:
                technical_info += "  (상승 추세 가능성)\n"
            else:
                technical_info += "  (하락 추세 가능성)\n"
        
        if ma5 and ma20 and ma60:
            technical_info += f"- 이동평균선: MA5={ma5:,.0f}, MA20={ma20:,.0f}, MA60={ma60:,.0f}\n"
            if current_price:
                if current_price > ma5 > ma20 > ma60:
                    technical_info += "  (강한 상승 추세)\n"
                elif current_price < ma5 < ma20 < ma60:
                    technical_info += "  (강한 하락 추세)\n"
                else:
                    technical_info += "  (횡보 또는 전환 시점)\n"
        
        if bollinger_upper and bollinger_lower and current_price:
            technical_info += f"- 볼린저 밴드: 상단={bollinger_upper:,.0f}, 하단={bollinger_lower:,.0f}\n"
            if current_price > bollinger_upper:
                technical_info += "  (상단 돌파 - 과매수 신호)\n"
            elif current_price < bollinger_lower:
                technical_info += "  (하단 돌파 - 과매도 신호)\n"
    
    # 감정 분석
    sentiment = stock_data.get('sentiment')
    sentiment_info = ""
    if sentiment:
        sentiment_score = sentiment.get('sentiment_score', 0)
        positive_ratio = sentiment.get('positive_ratio', 0)
        negative_ratio = sentiment.get('negative_ratio', 0)
        top_keywords = sentiment.get('top_keywords', '')
        
        sentiment_info = f"""
## 감정 분석
- 감정 점수: {sentiment_score:.2f} ({'긍정적' if sentiment_score > 0 else '부정적' if sentiment_score < 0 else '중립적'})
- 긍정 비율: {positive_ratio:.1%}
- 부정 비율: {negative_ratio:.1%}
- 주요 키워드: {top_keywords}
"""
    
    # 평가 지표
    valuation_info = ""
    if per is not None or pbr is not None or roe is not None:
        valuation_info = "## 밸류에이션 지표\n"
        if per is not None:
            valuation_info += f"- PER(주가수익비율): {per:.2f} "
            if per < 10:
                valuation_info += "(저평가 가능성)\n"
            elif per > 20:
                valuation_info += "(고평가 가능성)\n"
            else:
                valuation_info += "(적정 수준)\n"
        
        if pbr is not None:
            valuation_info += f"- PBR(주가순자산비율): {pbr:.2f} "
            if pbr < 1:
                valuation_info += "(저평가 가능성)\n"
            elif pbr > 2:
                valuation_info += "(고평가 가능성)\n"
            else:
                valuation_info += "(적정 수준)\n"
        
        if roe is not None:
            valuation_info += f"- ROE(자기자본이익률): {roe:.2f}% "
            if roe > 15:
                valuation_info += "(우수한 수익성)\n"
            elif roe < 5:
                valuation_info += "(낮은 수익성)\n"
            else:
                valuation_info += "(보통 수준)\n"
        
        if dividend_yield is not None:
            valuation_info += f"- 배당수익률: {dividend_yield:.2f}%\n"
    
    # 유사 종목
    similar_stocks = stock_data.get('similar_stocks', [])
    similar_info = ""
    if similar_stocks:
        similar_info = "## 유사 종목\n"
        for idx, sim in enumerate(similar_stocks[:3], 1):
            similar_info += f"{idx}. {sim.get('stock_name', '')} (코드: {sim.get('stock_code', '')})\n"
    
    # 현재가와 시가총액 포맷팅 (None 처리)
    current_price_str = f"{current_price:,.0f}원" if current_price else "정보 없음"
    market_cap_str = f"{market_cap:,}원 (백만원 단위)" if market_cap else "정보 없음"
    
    prompt = f"""당신은 전문 주식 애널리스트입니다. 다음 정보를 바탕으로 종합적인 투자 리포트를 작성해주세요.

# 종목 정보
- 종목명: {stock_name}
- 종목코드: {stock_code}
- 섹터: {sector}
- 현재가: {current_price_str}
- 시가총액: {market_cap_str}

{financial_info}

{technical_info}

{sentiment_info}

{valuation_info}

{similar_info}

위 정보를 종합하여 다음 형식의 JSON으로 응답해주세요:
{{
  "investment_opinion": "매수 타이밍" | "매도 타이밍" | "관망",
  "financial_analysis": "재무 상태에 대한 상세 분석 (200자 이상)",
  "technical_analysis": "기술적 지표에 대한 상세 분석 (200자 이상)",
  "sentiment_analysis": "시장 감정에 대한 상세 분석 (200자 이상)"
}}

주의사항:
1. 재무 분석에서는 매출, 영업이익, 순이익 추이와 재무비율(영업이익률, ROA, 부채비율 등)을 종합적으로 평가해주세요.
2. 기술적 분석에서는 RSI, MACD, 이동평균선, 볼린저 밴드 등을 종합하여 현재 추세와 매매 타이밍을 분석해주세요.
3. 감정 분석에서는 감정 점수와 키워드를 바탕으로 시장 심리를 평가해주세요.
4. 투자 의견은 재무 건전성, 기술적 신호, 시장 감정을 모두 고려하여 결정해주세요.
5. 모든 분석은 구체적인 수치와 데이터를 바탕으로 객관적으로 작성해주세요.
6. 반드시 JSON 형식으로만 응답해주세요. 다른 설명이나 텍스트는 포함하지 마세요.
"""
    
    return prompt


def _parse_text_report(report_text: str, stock_data: Dict) -> Dict:
    """텍스트 형식의 리포트를 파싱하여 구조화"""
    # JSON 블록 찾기 시도
    try:
        import re
        # ```json ... ``` 형식 찾기
        json_match = re.search(r'```json\s*(.*?)\s*```', report_text, re.DOTALL)
        if json_match:
            report_dict = json.loads(json_match.group(1))
            return _validate_and_format_report(report_dict, stock_data)
        
        # { ... } 형식 찾기
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', report_text, re.DOTALL)
        if json_match:
            report_dict = json.loads(json_match.group(0))
            return _validate_and_format_report(report_dict, stock_data)
    except Exception as e:
        logger.debug(f"JSON 파싱 실패: {e}")
    
    # 파싱 실패 시 텍스트를 섹션별로 분리
    sections = {
        'financial_analysis': '',
        'technical_analysis': '',
        'sentiment_analysis': ''
    }
    
    lines = report_text.split('\n')
    current_section = None
    
    for line in lines:
        if '재무' in line or 'financial' in line.lower():
            current_section = 'financial_analysis'
        elif '기술' in line or 'technical' in line.lower():
            current_section = 'technical_analysis'
        elif '감정' in line or 'sentiment' in line.lower():
            current_section = 'sentiment_analysis'
        
        if current_section and line.strip() and not line.strip().startswith('#'):
            sections[current_section] += line.strip() + '\n'
    
    # 투자 의견 추출
    opinion = "관망"
    if '매수' in report_text and '매도' not in report_text:
        opinion = "매수 타이밍"
    elif '매도' in report_text:
        opinion = "매도 타이밍"
    
    # 유사 종목 추천 생성 (텍스트 파싱 경로)
    recommendation_stock = "추천 종목 없음"
    recommendation_reason = "유사한 주식이 없습니다."
    recommendations = []
    
    similar_stocks = stock_data.get('similar_stocks', [])
    if similar_stocks and len(similar_stocks) > 0:
        for sim in similar_stocks[:3]:  # 최대 3개
            name = sim.get('stock_name', '추천 종목')
            stock_code = sim.get('stock_code', '')
            reasons = []
            if sim.get('per') is not None and sim.get('per') < 15:
                reasons.append("합리적인 밸류에이션")
            if sim.get('roe') is not None and sim.get('roe') > 10:
                reasons.append("우수한 수익성")
            if sim.get('pbr') is not None and sim.get('pbr') < 1.5:
                reasons.append("안정적인 자산가치")
            reason_text = ", ".join(reasons) if reasons else "유사 그룹 내 우수한 재무지표"
            recommendations.append({
                'stock_name': name,
                'stock_code': stock_code,
                'reason': f"{name}은(는) {reason_text}을 보이고 있습니다."
            })
        if recommendations:
            recommendation_stock = recommendations[0]['stock_name']
            recommendation_reason = recommendations[0]['reason']
    
    return {
        "investment_opinion": opinion,
        "financial_analysis": sections['financial_analysis'] or f"{stock_data.get('stock_name')}의 재무 상태를 분석한 결과입니다.",
        "technical_analysis": sections['technical_analysis'] or "기술적 지표를 분석한 결과입니다.",
        "sentiment_analysis": sections['sentiment_analysis'] or "시장 감정을 분석한 결과입니다.",
        "recommendation": {
            "stock_name": recommendation_stock,
            "reason": recommendation_reason
        },
        "recommendations": recommendations,
        "excluded_sections": stock_data.get('excluded_sections', [])
    }


def _validate_and_format_report(report_dict: Dict, stock_data: Dict) -> Dict:
    """리포트 딕셔너리 검증 및 포맷팅"""
    # 필수 필드 확인 및 기본값 설정
    investment_opinion = report_dict.get('investment_opinion', '관망')
    if investment_opinion not in ['매수 타이밍', '매도 타이밍', '관망']:
        # 유사 단어 매칭
        if '매수' in str(investment_opinion):
            investment_opinion = '매수 타이밍'
        elif '매도' in str(investment_opinion):
            investment_opinion = '매도 타이밍'
        else:
            investment_opinion = '관망'
    
    # 유사 종목 추천 생성 (유사도 순위 3까지만)
    recommendation_stock = "추천 종목 없음"
    recommendation_reason = "유사한 주식이 없습니다."
    recommendations = []
    
    similar_stocks = stock_data.get('similar_stocks', [])
    # similar_stocks가 None이 아니고 빈 리스트가 아닐 때만 처리
    if similar_stocks and len(similar_stocks) > 0:
        for sim in similar_stocks[:3]:  # 최대 3개
            name = sim.get('stock_name', '추천 종목')
            stock_code = sim.get('stock_code', '')
            reasons = []
            if sim.get('per') is not None and sim.get('per') < 15:
                reasons.append("합리적인 밸류에이션")
            if sim.get('roe') is not None and sim.get('roe') > 10:
                reasons.append("우수한 수익성")
            if sim.get('pbr') is not None and sim.get('pbr') < 1.5:
                reasons.append("안정적인 자산가치")
            reason_text = ", ".join(reasons) if reasons else "유사 그룹 내 우수한 재무지표"
            recommendations.append({
                'stock_name': name,
                'stock_code': stock_code,
                'reason': f"{name}은(는) {reason_text}을 보이고 있습니다."
            })
        if recommendations:
            recommendation_stock = recommendations[0]['stock_name']
            recommendation_reason = recommendations[0]['reason']
    else:
        # 유사한 주식이 없는 경우
        recommendation_stock = "추천 종목 없음"
        recommendation_reason = "유사한 주식이 없습니다."
    
    return {
        "investment_opinion": investment_opinion,
        "financial_analysis": report_dict.get('financial_analysis', f"{stock_data.get('stock_name')}의 재무 상태를 분석한 결과입니다."),
        "technical_analysis": report_dict.get('technical_analysis', "기술적 지표를 분석한 결과입니다."),
        "sentiment_analysis": report_dict.get('sentiment_analysis', "시장 감정을 분석한 결과입니다."),
        "recommendation": {
            "stock_name": recommendation_stock,
            "reason": recommendation_reason
        },
        "recommendations": recommendations,
        "excluded_sections": stock_data.get('excluded_sections', [])
    } 