"""
Google Gemini AI 뉴스 요약 모듈
- 수집된 기사를 단일 API 호출로 일괄 처리
- 카테고리 분류: 채용 / 임원선임 / 퇴사이직 / 기타
- 기사별 1~2문장 한국어 요약
- 전체 동향 종합 요약 및 주요 트렌드 추출
- API 키: GOOGLE_API_KEY 환경 변수 (Google AI Studio에서 발급)
"""
import json
import logging
import os
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)

MODEL = "gemini-2.0-flash"
MAX_OUTPUT_TOKENS = 4096

_SYSTEM_PROMPT = """당신은 게임업계 채용 전문가를 위한 HR 뉴스 분석 AI입니다.
게임업계의 채용·임원 선임·퇴사·이직 관련 뉴스를 분석하고 한국어로 요약합니다.

## 카테고리 정의
- 채용: 신규 채용 공고, 대규모 채용, 인재 영입 계획
- 임원선임: 대표이사·임원·부사장·전무·상무 등 임원급 신규 선임·취임
- 퇴사이직: 임원·대표이사 사임·퇴사·이직·계약 만료
- 기타: 인사 정책 변화, 조직 개편, 그 외 HR 관련 뉴스

## 응답 원칙
- 모든 응답은 한국어로 작성
- 기사 요약은 핵심 사실만 1~2문장으로 간결하게
- 회사명·인물명은 정확하게 추출
- 확인되지 않은 정보는 추측하지 않음"""


class ArticleSummarizer:
    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise ValueError(
                "GOOGLE_API_KEY 환경 변수가 설정되지 않았습니다. "
                "https://aistudio.google.com 에서 API 키를 발급받으세요."
            )
        genai.configure(api_key=key)
        self._model = genai.GenerativeModel(
            model_name=MODEL,
            system_instruction=_SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )

    def summarize_daily(self, articles: list) -> dict:
        """
        일간 기사 일괄 요약.

        Returns:
            {
              "articles": [
                {"index": int, "category": str, "summary": str,
                 "companies": [str], "people": [str]},
                ...
              ],
              "overall_summary": str,
              "key_trends": [str]
            }
        """
        if not articles:
            return {
                "articles": [],
                "overall_summary": "오늘은 게임업계 HR 관련 주요 뉴스가 없습니다.",
                "key_trends": [],
            }
        return self._call_api(articles, report_type="daily")

    def summarize_weekly(self, articles: list) -> dict:
        """
        주간 기사 일괄 요약.

        Returns:
            summarize_daily()와 동일 구조 + weekly_highlights 필드
        """
        if not articles:
            return {
                "articles": [],
                "overall_summary": "이번 주는 게임업계 HR 관련 주요 뉴스가 없습니다.",
                "key_trends": [],
                "weekly_highlights": [],
            }
        return self._call_api(articles, report_type="weekly")

    # ------------------------------------------------------------------
    # 내부 메서드
    # ------------------------------------------------------------------

    def _call_api(self, articles: list, report_type: str) -> dict:
        articles_text = self._format_articles(articles)

        if report_type == "weekly":
            analysis_instruction = (
                "이번 주 게임업계 HR 동향 전체 요약(4~6문장)과 "
                "주요 하이라이트 3~5개를 추가로 작성해주세요."
            )
            extra_fields = (
                ',\n  "weekly_highlights": ["하이라이트1", "하이라이트2"]'
            )
        else:
            analysis_instruction = "오늘의 게임업계 HR 동향 전체 요약(3~5문장)을 작성해주세요."
            extra_fields = ""

        user_prompt = f"""다음 게임업계 뉴스 기사들을 분석해주세요.

{articles_text}

## 요청 사항
1. 각 기사를 카테고리로 분류하고 핵심 내용을 요약해주세요.
2. {analysis_instruction}

## 응답 형식 (JSON)
{{
  "articles": [
    {{
      "index": 0,
      "category": "채용",
      "summary": "요약 내용 (1~2문장)",
      "companies": ["회사명"],
      "people": ["인물명"]
    }}
  ],
  "overall_summary": "전체 동향 요약",
  "key_trends": ["트렌드1", "트렌드2"]{extra_fields}
}}"""

        try:
            response = self._model.generate_content(user_prompt)
            result = json.loads(response.text)
            self._log_usage(response)
            return result

        except json.JSONDecodeError as e:
            logger.error("AI 응답 JSON 파싱 실패: %s", e)
        except Exception as e:
            logger.error("Gemini API 호출 실패: %s", e)

        return {
            "articles": [],
            "overall_summary": "AI 요약 중 오류가 발생했습니다. 원문을 직접 확인해주세요.",
            "key_trends": [],
        }

    def _format_articles(self, articles: list) -> str:
        """기사 목록을 프롬프트용 텍스트로 변환."""
        parts = []
        for i, a in enumerate(articles):
            desc = a.get("description", "")[:500]
            parts.append(
                f"[기사 {i}]\n"
                f"제목: {a.get('title', '')}\n"
                f"출처: {a.get('source', '')}\n"
                f"날짜: {a.get('published_at', '')}\n"
                f"내용: {desc}\n"
            )
        return "\n".join(parts)

    def _log_usage(self, response) -> None:
        try:
            usage = response.usage_metadata
            logger.debug(
                "Gemini API 사용량 - 입력: %d 토큰, 출력: %d 토큰",
                usage.prompt_token_count,
                usage.candidates_token_count,
            )
        except Exception:
            pass
