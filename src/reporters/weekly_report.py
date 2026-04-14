"""
주간 뉴스 리포트 HTML 생성 모듈
- 매주 월요일 9시 KST 발송
- 지난 7일간 수집된 기사를 카테고리별로 정리
- 주간 하이라이트 및 트렌드 분석 포함
"""
from datetime import datetime, timedelta
import pytz

from src.reporters.daily_report import _build_sections, _render_html, _esc

KST = pytz.timezone("Asia/Seoul")


def generate(articles: list, ai_result: dict) -> tuple[str, str]:
    """
    주간 뉴스 HTML 이메일과 제목(subject) 반환.

    Args:
        articles:  DB에서 조회한 최근 7일 기사 목록
        ai_result: summarizer.summarize_weekly() 반환 결과

    Returns:
        (subject: str, html_body: str)
    """
    now_kst = datetime.now(KST)
    week_start = now_kst - timedelta(days=7)
    period = (
        f"{week_start.strftime('%m/%d')} ~ {now_kst.strftime('%m/%d')}"
    )
    subject = (
        f"[게임업계 HR 주간 리포트] {period} · {len(articles)}건"
    )
    date_str = f"{now_kst.strftime('%Y년 %m월 %d일')} (주간 리포트 · {period})"

    # AI 결과와 기사 병합
    ai_articles = ai_result.get("articles", [])
    enriched = _enrich_weekly(articles, ai_articles)

    # 카테고리별 섹션
    sections = _build_sections(enriched)

    overall_summary = ai_result.get("overall_summary", "")
    key_trends = ai_result.get("key_trends", [])
    weekly_highlights = ai_result.get("weekly_highlights", [])

    html = _render_weekly_html(
        date_str=date_str,
        period=period,
        total_count=len(articles),
        overall_summary=overall_summary,
        key_trends=key_trends,
        weekly_highlights=weekly_highlights,
        sections=sections,
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
        # DB에 이미 카테고리가 있으면 그걸 우선 사용
        if not merged.get("category"):
            merged["category"] = ai.get("category", "기타")
        if not merged.get("summary"):
            merged["summary"] = ai.get("summary", article.get("description", "")[:200])
        merged.setdefault("companies", [])
        merged.setdefault("people", [])
        result.append(merged)
    return result


def _render_weekly_html(date_str, period, total_count, overall_summary,
                        key_trends, weekly_highlights, sections) -> str:
    """주간 리포트 전용 HTML 생성."""

    # 하이라이트 블록
    highlights_html = ""
    if weekly_highlights:
        items = "".join(
            f'<li style="margin:6px 0;color:#333;font-size:13px;">{_esc(h)}</li>'
            for h in weekly_highlights[:5]
        )
        highlights_html = f"""
        <div style="background:#fff8e1;border-left:4px solid #ffc107;padding:16px 20px;margin:0 20px 20px;">
          <strong style="color:#e65100;display:block;margin-bottom:8px;">⭐ 이번 주 주요 이슈</strong>
          <ul style="margin:0;padding-left:20px;">{items}</ul>
        </div>"""

    # 트렌드 태그
    trend_tags = ""
    if key_trends:
        tags = " ".join(
            f'<span style="display:inline-block;background:#e8eaf6;color:#3949ab;border-radius:20px;'
            f'padding:3px 10px;font-size:12px;margin:3px 4px 3px 0">#{_esc(t)}</span>'
            for t in key_trends[:5]
        )
        trend_tags = f'<div style="padding:0 20px 8px">{tags}</div>'

    # 섹션 HTML (daily_report._render_html 재사용)
    from src.reporters.daily_report import _render_html as base_render
    base_html = base_render(
        date_str=date_str,
        total_count=total_count,
        overall_summary=overall_summary,
        key_trends=key_trends,
        sections=sections,
        report_type="weekly",
    )

    # 하이라이트 블록을 summary-box 뒤에 삽입
    if highlights_html:
        insert_marker = "</div>\n\n  {trend_tags}"
        base_html = base_html.replace(
            "</div>\n\n  {trend_tags}",
            f"</div>\n{highlights_html}\n  {{trend_tags}}",
        )

    return base_html
