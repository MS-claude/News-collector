"""
일간 뉴스 리포트 HTML 생성 모듈
- 카테고리별(채용·임원선임·퇴사이직·기타) 기사 정리
- AI 총평 및 주요 트렌드 포함
- 이메일 발송용 HTML 반환
"""
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

_CATEGORY_META = {
    "채용":    {"label": "📋 채용 소식",    "badge_class": "badge-hire"},
    "임원선임": {"label": "👔 임원 선임",    "badge_class": "badge-exec"},
    "퇴사이직": {"label": "🚪 퇴사·이직",   "badge_class": "badge-depart"},
    "기타":    {"label": "📌 기타 HR 뉴스", "badge_class": "badge-other"},
}
_CATEGORY_ORDER = ["채용", "임원선임", "퇴사이직", "기타"]


def generate(articles: list, ai_result: dict) -> tuple[str, str]:
    """
    일간 뉴스 HTML 이메일과 제목(subject) 반환.

    Args:
        articles:  deduplicator가 반환한 신규 기사 목록
        ai_result: summarizer.summarize_daily() 반환 결과

    Returns:
        (subject: str, html_body: str)
    """
    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y년 %m월 %d일 (%a)")
    subject = f"[게임업계 HR 뉴스] {now_kst.strftime('%Y-%m-%d')} · {len(articles)}건"

    # AI 결과와 기사 병합
    enriched = _enrich_articles(articles, ai_result.get("articles", []))

    # 카테고리별 그룹화
    sections = _build_sections(enriched)

    overall_summary = ai_result.get("overall_summary", "")
    key_trends = ai_result.get("key_trends", [])

    html = _render_html(
        date_str=date_str,
        total_count=len(articles),
        overall_summary=overall_summary,
        key_trends=key_trends,
        sections=sections,
        report_type="daily",
    )
    return subject, html


# ------------------------------------------------------------------
# 내부 헬퍼
# ------------------------------------------------------------------

def _enrich_articles(articles: list, ai_articles: list) -> list:
    """AI 분석 결과(카테고리·요약)를 기사 목록에 반영."""
    ai_map = {a["index"]: a for a in ai_articles if "index" in a}
    result = []
    for i, article in enumerate(articles):
        ai = ai_map.get(i, {})
        merged = dict(article)
        merged["category"] = ai.get("category", "기타")
        merged["summary"] = ai.get("summary", article.get("description", "")[:200])
        merged["companies"] = ai.get("companies", [])
        merged["people"] = ai.get("people", [])
        result.append(merged)
    return result


def _build_sections(articles: list) -> list:
    """기사를 카테고리별로 그룹화."""
    grouped: dict = {cat: [] for cat in _CATEGORY_ORDER}
    for a in articles:
        cat = a.get("category", "기타")
        if cat not in grouped:
            cat = "기타"
        grouped[cat].append(a)

    sections = []
    for cat in _CATEGORY_ORDER:
        items = grouped[cat]
        if items:
            sections.append(
                {
                    "category": cat,
                    "label": _CATEGORY_META[cat]["label"],
                    "badge_class": _CATEGORY_META[cat]["badge_class"],
                    "articles": items,
                }
            )
    return sections


def _render_html(date_str, total_count, overall_summary, key_trends,
                 sections, report_type="daily") -> str:
    """HTML 이메일 문자열 조립."""

    # ---------- 트렌드 태그 ----------
    trend_tags = ""
    if key_trends:
        tags_html = " ".join(
            f'<span class="trend-tag">#{t}</span>' for t in key_trends[:5]
        )
        trend_tags = f'<div class="trends">{tags_html}</div>'

    # ---------- 섹션 블록 ----------
    sections_html = ""
    for sec in sections:
        articles_html = ""
        for a in sec["articles"]:
            pub = a.get("published_at", "")[:10]
            companies = ", ".join(a.get("companies", []))
            people_str = ", ".join(a.get("people", []))
            meta_extra = ""
            if companies:
                meta_extra += f" · 🏢 {companies}"
            if people_str:
                meta_extra += f" · 👤 {people_str}"

            articles_html += f"""
            <div class="article-card">
              <span class="category-badge {sec['badge_class']}">{sec['category']}</span>
              <div class="article-title">{_esc(a.get('title', ''))}</div>
              <div class="article-meta">{_esc(a.get('source', ''))} · {pub}{_esc(meta_extra)}</div>
              <div class="article-summary">{_esc(a.get('summary', ''))}</div>
              <a href="{_esc(a.get('url', '#'))}" class="article-link" target="_blank">
                기사 원문 보기 →
              </a>
            </div>"""

        sections_html += f"""
        <div class="section">
          <h2 class="section-title">{sec['label']} <span class="count">{len(sec['articles'])}건</span></h2>
          {articles_html}
        </div>"""

    header_title = "🎮 게임업계 HR 뉴스" if report_type == "daily" else "🎮 게임업계 HR 주간 리포트"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{header_title}</title>
<style>
  body {{font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif;background:#f0f2f5;margin:0;padding:20px}}
  .container {{max-width:700px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.1)}}
  .header {{background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:28px 24px}}
  .header h1 {{margin:0 0 6px;font-size:22px}}
  .header p {{margin:0;font-size:13px;opacity:.8}}
  .summary-box {{background:#f0f7ff;border-left:4px solid #2196f3;padding:18px 20px;margin:20px}}
  .summary-box strong {{display:block;margin-bottom:8px;color:#1565c0}}
  .summary-box p {{margin:0;line-height:1.7;color:#333;font-size:14px}}
  .trends {{padding:0 20px 4px}}
  .trend-tag {{display:inline-block;background:#e8eaf6;color:#3949ab;border-radius:20px;padding:3px 10px;font-size:12px;margin:3px 4px 3px 0}}
  .section {{margin:0 20px 24px}}
  .section-title {{font-size:16px;font-weight:700;color:#1a1a2e;border-bottom:2px solid #e3e8f0;padding-bottom:8px;margin-bottom:14px}}
  .section-title .count {{font-size:13px;font-weight:400;color:#888;margin-left:6px}}
  .article-card {{border:1px solid #e8ecf0;border-radius:8px;padding:16px;margin:10px 0;transition:box-shadow .2s}}
  .article-title {{font-weight:600;color:#1a1a2e;font-size:14px;line-height:1.5;margin:6px 0 4px}}
  .article-meta {{color:#888;font-size:12px;margin-bottom:8px}}
  .article-summary {{color:#444;font-size:13px;line-height:1.6;margin-bottom:10px}}
  .article-link {{color:#1976d2;font-size:12px;text-decoration:none}}
  .category-badge {{display:inline-block;padding:2px 8px;border-radius:12px;font-size:11px;font-weight:600;margin-bottom:4px}}
  .badge-hire   {{background:#e8f5e9;color:#2e7d32}}
  .badge-exec   {{background:#e3f2fd;color:#1565c0}}
  .badge-depart {{background:#fce4ec;color:#c62828}}
  .badge-other  {{background:#f3e5f5;color:#6a1b9a}}
  .no-news {{text-align:center;color:#aaa;padding:40px 20px;font-size:14px}}
  .footer {{background:#f5f7fa;padding:16px 20px;text-align:center;color:#aaa;font-size:12px;border-top:1px solid #e8ecf0}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{header_title}</h1>
    <p>{date_str} · 총 {total_count}건</p>
  </div>

  <div class="summary-box">
    <strong>🤖 AI 총평</strong>
    <p>{_esc(overall_summary)}</p>
  </div>

  {trend_tags}

  {sections_html if sections_html else '<div class="no-news">오늘은 새로운 HR 뉴스가 없습니다.</div>'}

  <div class="footer">
    게임업계 HR 뉴스봇 | {date_str}<br>
    본 메일은 자동으로 발송된 뉴스 요약입니다.
  </div>
</div>
</body>
</html>"""


def _esc(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
