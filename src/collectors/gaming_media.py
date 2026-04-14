"""
게임 전문 매체 RSS 수집기
- 인벤, 게임메카, 게임동아 RSS 피드에서 기사 수집
- HR 관련 키워드(채용·임원·퇴사·이직 등)가 제목에 포함된 기사만 수집
- Google News와 달리 게임 전문 매체이므로 "게임" 키워드 불필요
  → 슈퍼센트처럼 제목에 게임이 없어도 수집 가능
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser

import feedparser

logger = logging.getLogger(__name__)

# 게임 전문 매체 RSS 피드 목록
FEEDS = [
    {"name": "인벤",   "url": "http://feeds.feedburner.com/inven"},
    {"name": "게임메카", "url": "https://www.gamemeca.com/news.php"},
    {"name": "게임동아", "url": "https://game.donga.com/feeds/rss/"},
]

# HR 관련 필터링 키워드 (제목에 하나 이상 포함 시 수집)
HR_KEYWORDS = [
    # 채용
    "채용", "모집", "영입", "채용공고",
    # 임원·선임
    "임원", "대표이사", "대표 선임", "선임", "취임", "사장", "부사장",
    "전무", "상무", "이사", "CTO", "CFO", "COO", "CEO",
    # 퇴사·이직
    "퇴사", "사임", "이직", "퇴임", "사직", "계약 만료",
    # 인사 일반
    "인사이동", "인사 발표", "조직개편",
]

REQUEST_DELAY = 1.5  # 초 (매체별 요청 간격)


def collect(hours: int = 24) -> list:
    """
    최근 N시간 이내 게임 전문 매체 HR 관련 기사 수집.

    Returns:
        list of dict: {url, title, source, description, published_at}
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []
    seen_urls: set = set()

    for feed_info in FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"])
            count = 0

            for entry in feed.entries:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue

                title = entry.get("title", "").strip()

                # HR 키워드 필터링
                if not _has_hr_keyword(title):
                    continue

                pub_date = _parse_published(entry)
                if pub_date and pub_date < since:
                    continue

                seen_urls.add(url)
                articles.append(
                    {
                        "url": url,
                        "title": title,
                        "source": feed_info["name"],
                        "description": _clean_description(
                            entry.get("summary", entry.get("description", ""))
                        ),
                        "published_at": pub_date.strftime("%Y-%m-%d %H:%M:%S")
                        if pub_date
                        else "",
                    }
                )
                count += 1

            logger.debug("%s 수집: %d건", feed_info["name"], count)
            time.sleep(REQUEST_DELAY)

        except Exception as e:
            logger.warning("게임 매체 RSS 수집 실패 [%s]: %s", feed_info["name"], e)

    logger.info(
        "게임 전문 매체 수집 완료: %d건 (매체 %d개)", len(articles), len(FEEDS)
    )
    return articles


# ------------------------------------------------------------------
# 내부 헬퍼
# ------------------------------------------------------------------

def _has_hr_keyword(title: str) -> bool:
    """제목에 HR 관련 키워드가 포함되어 있는지 확인."""
    return any(kw in title for kw in HR_KEYWORDS)


def _parse_published(entry) -> datetime | None:
    """RSS entry에서 발행 시각을 UTC datetime으로 파싱."""
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    for field in ("published_parsed", "updated_parsed"):
        ts = entry.get(field)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _clean_description(text: str) -> str:
    """HTML 태그 제거 및 텍스트 정리."""

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    stripper = _Stripper()
    stripper.feed(text)
    return " ".join(stripper.parts).strip()[:1000]
