"""
Google News RSS 수집기
- 게임업계 채용·임원 선임·퇴사 관련 뉴스를 Google News RSS로 수집
- 검색어별로 피드를 파싱, 최근 N시간 이내 기사만 반환
"""
import logging
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser

logger = logging.getLogger(__name__)

# 검색 쿼리 목록 (게임업계 HR 뉴스 타겟팅)
SEARCH_QUERIES = [
    # 채용
    "게임사 채용",
    "게임 채용공고",
    "게임업계 채용",
    # 임원 선임
    "게임 임원 선임",
    "게임 대표이사 취임",
    "게임 임원 영입",
    "게임사 대표 선임",
    # 퇴사·이직
    "게임 임원 퇴사",
    "게임사 대표 사임",
    "게임 인사이동",
    # 주요 게임사 인사
    "넥슨 인사",
    "엔씨소프트 인사",
    "크래프톤 인사",
    "넷마블 인사",
    "카카오게임즈 인사",
]

GOOGLE_NEWS_RSS_URL = (
    "https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
)
REQUEST_DELAY = 1.5  # 초 (Google 요청 간격)


def collect(hours: int = 24) -> list:
    """
    최근 N시간 이내 게임업계 HR 관련 Google News 기사 수집.

    Returns:
        list of dict: {url, title, source, description, published_at}
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    articles = []
    seen_urls: set = set()

    for query in SEARCH_QUERIES:
        try:
            feed_url = GOOGLE_NEWS_RSS_URL.format(query=quote_plus(query))
            feed = feedparser.parse(feed_url)

            for entry in feed.entries:
                url = entry.get("link", "")
                if not url or url in seen_urls:
                    continue

                # 발행 시각 파싱
                pub_date = _parse_published(entry)
                if pub_date and pub_date < since:
                    continue  # 범위 밖 기사 스킵

                seen_urls.add(url)
                articles.append(
                    {
                        "url": url,
                        "title": entry.get("title", "").strip(),
                        "source": _extract_source(entry),
                        "description": _clean_description(
                            entry.get("summary", entry.get("description", ""))
                        ),
                        "published_at": pub_date.strftime("%Y-%m-%d %H:%M:%S")
                        if pub_date
                        else "",
                    }
                )

            time.sleep(REQUEST_DELAY)

        except Exception as e:
            logger.warning("Google News 수집 실패 [%s]: %s", query, e)

    logger.info("Google News 수집 완료: %d건 (쿼리 %d개)", len(articles), len(SEARCH_QUERIES))
    return articles


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
    # feedparser가 time_struct을 파싱했을 경우
    for field in ("published_parsed", "updated_parsed"):
        ts = entry.get(field)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _extract_source(entry) -> str:
    """RSS entry에서 언론사 이름 추출."""
    # Google News RSS는 제목에 " - 언론사명" 형식으로 포함
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    source = entry.get("source", {})
    if isinstance(source, dict):
        return source.get("title", "")
    return str(source) if source else ""


def _clean_description(text: str) -> str:
    """HTML 태그 제거 및 텍스트 정리."""
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    stripper = _Stripper()
    stripper.feed(text)
    return " ".join(stripper.parts).strip()[:1000]
