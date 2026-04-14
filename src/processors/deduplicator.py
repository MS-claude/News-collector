"""
중복 기사 제거 모듈
1. DB에 이미 저장된 URL·제목 해시와 대조 → 기존 기사 제거
2. 동일 배치 내 유사 제목 기사 중복 제거 (difflib SequenceMatcher 활용)
"""
import hashlib
import logging
import re
from difflib import SequenceMatcher

from src import database as db

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.85  # 제목 유사도 임계값


def compute_title_hash(title: str) -> str:
    """제목 정규화 후 MD5 해시 반환."""
    normalized = re.sub(r"[^\w가-힣]", "", title.lower())
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def deduplicate(articles: list) -> list:
    """
    수집된 기사 목록에서 중복 제거.

    처리 순서:
      1. 각 기사에 title_hash 추가
      2. DB에 이미 존재하는 기사 제거
      3. 동일 배치 내 유사 제목 기사 제거

    Returns:
        중복이 제거된 새 기사 목록 (title_hash 필드 포함)
    """
    # 1. title_hash 추가
    for article in articles:
        article["title_hash"] = compute_title_hash(article.get("title", ""))

    # 2. DB 기존 기사 제거
    new_articles = [
        a for a in articles
        if not db.is_seen(a["url"], a["title_hash"])
    ]
    removed_by_db = len(articles) - len(new_articles)

    # 3. 배치 내 유사 제목 제거
    unique_articles = _remove_similar_titles(new_articles)
    removed_by_similarity = len(new_articles) - len(unique_articles)

    logger.info(
        "중복 제거: 전체 %d건 → DB 중복 %d건, 유사 제목 %d건 → 신규 %d건",
        len(articles),
        removed_by_db,
        removed_by_similarity,
        len(unique_articles),
    )
    return unique_articles


def _remove_similar_titles(articles: list) -> list:
    """배치 내에서 제목 유사도가 임계값 이상인 기사 중 첫 번째만 유지."""
    unique = []
    for candidate in articles:
        title_c = candidate.get("title", "")
        is_dup = any(
            SequenceMatcher(None, title_c, kept.get("title", "")).ratio()
            >= SIMILARITY_THRESHOLD
            for kept in unique
        )
        if not is_dup:
            unique.append(candidate)
    return unique
