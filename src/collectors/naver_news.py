"""
Naver News API 수집기
- 네이버 뉴스 검색 API를 통해 게임업계 HR 뉴스 수집
- API 키: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET 환경 변수 필요
  https://developers.naver.com 에서 애플리케이션 등록 후 발급
"""
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import quote

import requests

logger = logging.getLogger(__name__)

NAVER_API_URL = "https://openapi.naver.com/v1/search/news.json"
REQUEST_DELAY = 0.5  # 초 (Naver API 요청 간격)
DISPLAY_COUNT = 100  # 요청당 최대 기사 수

SEARCH_QUERIES = [
    "게임사 채용",
    "게임 채용공고",
    "게임업계 채용",
    "게임 임원 선임",
    "게임 대표이사 취임",
    "게임 임원 영입",
    "게임 인사이동",
    "게임 임원 퇴사",
    "게임사 대표 사임",
    "넥슨 인사",
    "엔씨소프트 인사",
    "크래프톤 인사",
    "넷마블 인사",
    "카카오게임즈 인사",
    "펄어비스 인사",
    "스마일게이트 인사",
]


def collect(hours: int = 24) -> list:
    """
    최근 N시간 이내 네이버 뉴스에서 게임업계 HR 기사 수집.

    Returns:
        list of dict: {url, title, source, description, published_at}
    """
    client_id = os.getenv("NAVER_CLIENT_ID")
    client_secret = os.getenv("NAVER_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.warning(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정 → 네이버 뉴스 수집 건너뜀"
        )
        return []

    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }

    articles = []
    seen_urls: set = set()

    for query in SEARCH_QUERIES:
        try:
            params = {
                "query": query,
                "display": DISPLAY_COUNT,
                "start": 1,
                "sort": "date",
            }
            resp = requests.get(NAVER_API_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                url = item.get("originallink") or item.get("link", "")
                if not url or url in seen_urls:
                    continue

                pub_date = _parse_pub_date(item.get("pubDate", ""))
                if pub_date and pub_date < since:
                    continue

                seen_urls.add(url)
                articles.append(
                    {
                        "url": url,
                        "title": _strip_html(item.get("title", "")),
                        "source": _extract_source(url),
                        "description": _strip_html(item.get("description", ""))[:1000],
                        "published_at": pub_date.strftime("%Y-%m-%d %H:%M:%S")
                        if pub_date
                        else "",
                    }
                )

            time.sleep(REQUEST_DELAY)

        except requests.RequestException as e:
            logger.warning("Naver News API 오류 [%s]: %s", query, e)
        except Exception as e:
            logger.warning("Naver News 수집 실패 [%s]: %s", query, e)

    logger.info("Naver News 수집 완료: %d건 (쿼리 %d개)", len(articles), len(SEARCH_QUERIES))
    return articles


def _parse_pub_date(raw: str) -> datetime | None:
    """RFC 2822 형식의 pubDate를 UTC datetime으로 변환."""
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _strip_html(text: str) -> str:
    """HTML 태그 및 엔티티 제거."""

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []

        def handle_data(self, data):
            self.parts.append(data)

    stripper = _Stripper()
    stripper.feed(text)
    return " ".join(stripper.parts).strip()


def _extract_source(url: str) -> str:
    """URL 도메인에서 언론사 이름 추출."""
    try:
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # www. 제거 후 도메인만 반환
        return domain.replace("www.", "").split(".")[0]
    except Exception:
        return ""
