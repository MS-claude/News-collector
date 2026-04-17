"""
주간 뉴스 리포트 HTML 생성 모듈
- 매주 금요일 9시 KST 발송
- 지난 7일간 수집된 기사를 카테고리별로 정리
- 주간 하이라이트 및 트렌드 분석 포함
"""
from datetime import datetime, timedelta
import pytz

from src.reporters.daily_report import _FONT, _build_sections, _enrich_articles, _render_html, _esc

KST = pytz.timezone("Asia/Seoul")


def generate(articles: list, ai_result: dict) -> tuple[str, str]:
    """
    주간 뉴스 HTML 이메일과 제목(subject) 반환.

    Returns:
        (subject: str, html_body: str)
    """
    now_kst = datetime.now(KST)
    week_start = now_kst - timedelta(days=7)
    period = f"{week_start.strftime('%m/%d')} ~ {now_kst.strftime('%m/%d')}"
    subject = f"[게임업계 HR 주간 리포트] {period} · {len(articles)}건"
    date_str = f"{now_kst.strftime('%Y년 %m월 %d일')} (주간 리포트 · {period})"

    enriched = _enrich_weekly(articles, ai_result.get("articles", []))
    sections = _build_sections(enriched)

    html = _render_html(
        date_str=date_str,
        total_count=len(articles),
        overall_summary=ai_result.get("overall_summary", ""),
        key_trends=ai_result.get("key_trends", []),
        sections=sections,
        report_type="weekly",
        highlights_html=_build_highlights_html(ai_result.get("weekly_highlights", [])),
    )
    return subject, html


# ------------------------------------------------------------------
# 내부 헬퍼
# ------------------------------------------------------------------

def _enrich_weekly(articles: list, ai_articles: list) -> list:
    """AI 분석 결과를 기사 목록에 병합 (DB에 이미 저장된 AI 결과 우선)."""
    ai_map = {a["index"]: a for a in ai_articles if "index" in a}
    result = []
    for i, article in enumerate(articles):
        ai = ai_map.get(i, {})
        merged = dict(article)
        if not merged.get("category"):
            merged["category"] = ai.get("category", "기타")
        if not merged.get("summary"):
            merged["summary"] = ai.get("summary", article.get("description", "")[:200])
        merged.setdefault("companies", [])
        merged.setdefault("people", [])
        result.append(merged)
    return result


def _build_highlights_html(weekly_highlights: list) -> str:
    """주간 주요 이슈 블록 HTML 반환. 없으면 빈 문자열."""
    if not weekly_highlights:
        return ""

    items = "".join(
        f'<li style="margin:6px 0;color:#333333;font-size:13px;'
        f'font-family:{_FONT};">{_esc(h)}</li>'
        for h in weekly_highlights[:5]
    )
    return f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0"
           style="background:#fff8e1;" bgcolor="#fff8e1">
      <tr>
        <td style="padding:16px 20px;border-left:4px solid #ffc107;">
          <p style="margin:0 0 8px;color:#e65100;font-weight:bold;font-size:14px;
                    font-family:{_FONT};">⭐ 이번 주 주요 이슈</p>
          <ul style="margin:0;padding-left:20px;">{items}</ul>
        </td>
      </tr>
    </table>"""
