"""
일간 뉴스 리포트 HTML 생성 모듈
- 카테고리별(채용·임원선임·퇴사이직·기타) 기사 정리
- AI 총평 및 주요 트렌드 포함
- Outlook 호환: 테이블 레이아웃 + 전체 인라인 스타일
"""
from datetime import datetime
import pytz

KST = pytz.timezone("Asia/Seoul")

_FONT = "'Malgun Gothic','Apple SD Gothic Neo',Arial,sans-serif"

_CATEGORY_META = {
    "채용":    {"label": "📋 채용 소식",    "badge_style": "background:#e8f5e9;color:#2e7d32;"},
    "임원선임": {"label": "👔 임원 선임",    "badge_style": "background:#e3f2fd;color:#1565c0;"},
    "퇴사이직": {"label": "🚪 퇴사·이직",   "badge_style": "background:#fce4ec;color:#c62828;"},
    "기타":    {"label": "📌 기타 HR 뉴스", "badge_style": "background:#f3e5f5;color:#6a1b9a;"},
}
_CATEGORY_ORDER = ["채용", "임원선임", "퇴사이직", "기타"]


def generate(articles: list, ai_result: dict) -> tuple[str, str]:
    """
    일간 뉴스 HTML 이메일과 제목(subject) 반환.

    Returns:
        (subject: str, html_body: str)
    """
    now_kst = datetime.now(KST)
    date_str = now_kst.strftime("%Y년 %m월 %d일 (%a)")
    subject = f"[게임업계 HR 뉴스] {now_kst.strftime('%Y-%m-%d')} · {len(articles)}건"

    enriched = _enrich_articles(articles, ai_result.get("articles", []))
    sections = _build_sections(enriched)

    html = _render_html(
        date_str=date_str,
        total_count=len(articles),
        overall_summary=ai_result.get("overall_summary", ""),
        key_trends=ai_result.get("key_trends", []),
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

    return [
        {
            "category": cat,
            "label": _CATEGORY_META[cat]["label"],
            "badge_style": _CATEGORY_META[cat]["badge_style"],
            "articles": grouped[cat],
        }
        for cat in _CATEGORY_ORDER
        if grouped[cat]
    ]


def _render_html(date_str, total_count, overall_summary, key_trends,
                 sections, report_type="daily", highlights_html="") -> str:
    """
    Outlook 호환 HTML 이메일 조립.
    highlights_html: 주간 리포트의 '이번 주 주요 이슈' 블록 (선택)
    """
    header_title = "게임업계 HR 뉴스" if report_type == "daily" else "게임업계 HR 주간 리포트"

    # 트렌드 태그 행
    trend_row = ""
    if key_trends:
        tags = "".join(
            f'<span style="display:inline-block;background:#e8eaf6;color:#3949ab;'
            f'padding:3px 10px;font-size:12px;margin:3px 4px 3px 0;'
            f'font-family:{_FONT};">#{_esc(t)}</span>'
            for t in key_trends[:5]
        )
        trend_row = f'<tr><td style="padding:12px 20px 4px;">{tags}</td></tr>'

    # 하이라이트 행 (주간 리포트)
    highlights_row = (
        f'<tr><td style="padding:0 20px;">{highlights_html}</td></tr>'
        if highlights_html else ""
    )

    # 섹션 행들
    sections_rows = _build_sections_rows(sections)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<!--[if mso]><noscript><xml><o:OfficeDocumentSettings>
<o:PixelsPerInch>96</o:PixelsPerInch>
</o:OfficeDocumentSettings></xml></noscript><![endif]-->
</head>
<body style="margin:0;padding:0;background:#f0f2f5;" bgcolor="#f0f2f5">
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background:#f0f2f5;" bgcolor="#f0f2f5">
  <tr>
    <td align="center" style="padding:20px 10px;">
      <!--[if mso]><table width="700" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->
      <table width="700" cellpadding="0" cellspacing="0" border="0"
             style="background:#ffffff;max-width:700px;width:100%;" bgcolor="#ffffff">

        <!-- 헤더 -->
        <tr>
          <td style="background:#1a1a2e;padding:28px 24px;" bgcolor="#1a1a2e">
            <p style="margin:0 0 6px;font-size:22px;color:#ffffff;font-weight:bold;
                      font-family:{_FONT};">{_esc(header_title)}</p>
            <p style="margin:0;font-size:13px;color:#cccccc;
                      font-family:{_FONT};">{_esc(date_str)} · 총 {total_count}건</p>
          </td>
        </tr>

        <!-- AI 총평 -->
        <tr>
          <td style="padding:20px 20px 0 20px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="background:#f0f7ff;" bgcolor="#f0f7ff">
              <tr>
                <td style="padding:18px 20px;border-left:4px solid #2196f3;">
                  <p style="margin:0 0 8px;color:#1565c0;font-weight:bold;font-size:14px;
                            font-family:{_FONT};">AI 총평</p>
                  <p style="margin:0;line-height:1.7;color:#333333;font-size:14px;
                            font-family:{_FONT};">{_esc(overall_summary)}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        {highlights_row}
        {trend_row}
        {sections_rows}

        <!-- 푸터 -->
        <tr>
          <td style="background:#f5f7fa;padding:16px 20px;text-align:center;
                     color:#aaaaaa;font-size:12px;border-top:1px solid #e8ecf0;
                     font-family:{_FONT};" bgcolor="#f5f7fa">
            게임업계 HR 뉴스봇 | {_esc(date_str)}<br>
            본 메일은 자동으로 발송된 뉴스 요약입니다.
          </td>
        </tr>

      </table>
      <!--[if mso]></td></tr></table><![endif]-->
    </td>
  </tr>
</table>
</body>
</html>"""


def _build_sections_rows(sections: list) -> str:
    """섹션 목록을 <tr> 블록 문자열로 변환."""
    if not sections:
        return (
            f'<tr><td style="text-align:center;color:#aaaaaa;padding:40px 20px;'
            f'font-size:14px;font-family:{_FONT};">오늘은 새로운 HR 뉴스가 없습니다.</td></tr>'
        )

    rows = ""
    for sec in sections:
        cards = ""
        for a in sec["articles"]:
            pub = a.get("published_at", "")[:10]
            meta_parts = [_esc(a.get("source", "")), pub]
            companies = ", ".join(a.get("companies", []))
            people_str = ", ".join(a.get("people", []))
            if companies:
                meta_parts.append(f"🏢 {_esc(companies)}")
            if people_str:
                meta_parts.append(f"👤 {_esc(people_str)}")
            meta_str = " · ".join(meta_parts)

            cards += f"""
              <tr>
                <td style="padding:0 0 10px 0;">
                  <table width="100%" cellpadding="0" cellspacing="0" border="0"
                         style="border:1px solid #e8ecf0;border-collapse:collapse;">
                    <tr>
                      <td style="padding:16px;">
                        <span style="display:inline-block;{sec['badge_style']}
                                     padding:2px 8px;font-size:11px;font-weight:600;
                                     font-family:{_FONT};">{_esc(sec['category'])}</span>
                        <p style="margin:6px 0 4px;font-weight:600;color:#1a1a2e;
                                  font-size:14px;line-height:1.5;
                                  font-family:{_FONT};">{_esc(a.get('title', ''))}</p>
                        <p style="margin:0 0 8px;color:#888888;font-size:12px;
                                  font-family:{_FONT};">{meta_str}</p>
                        <p style="margin:0 0 10px;color:#444444;font-size:13px;
                                  line-height:1.6;font-family:{_FONT};">{_esc(a.get('summary', ''))}</p>
                        <a href="{_esc(a.get('url', '#'))}"
                           style="color:#1976d2;font-size:12px;text-decoration:none;
                                  font-family:{_FONT};" target="_blank">기사 원문 보기 →</a>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>"""

        rows += f"""
        <tr>
          <td style="padding:20px 20px 4px 20px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="padding-bottom:8px;border-bottom:2px solid #e3e8f0;">
                  <span style="font-size:16px;font-weight:700;color:#1a1a2e;
                               font-family:{_FONT};">{sec['label']}</span>
                  <span style="font-size:13px;font-weight:400;color:#888888;
                               margin-left:6px;font-family:{_FONT};">{len(sec['articles'])}건</span>
                </td>
              </tr>
              <tr>
                <td style="padding-top:14px;">
                  <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    {cards}
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>"""

    return rows


def _esc(text: str) -> str:
    """HTML 특수문자 이스케이프."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
