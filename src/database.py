"""
SQLite 데이터베이스 관리 모듈
- 수집된 기사 저장 (중복 방지)
- 과거 기사 조회 (주간 리포트용)
- 30일 이상 된 기사 자동 정리
"""
import sqlite3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "news.db")


def _get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """DB 초기화: 테이블 및 인덱스 생성."""
    with _get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                url           TEXT UNIQUE NOT NULL,
                title_hash    TEXT NOT NULL,
                title         TEXT NOT NULL,
                source        TEXT,
                description   TEXT,
                published_at  TEXT,
                category      TEXT,
                summary       TEXT,
                companies     TEXT,
                people        TEXT,
                created_at    TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_articles_title_hash ON articles(title_hash)"
        )
        conn.commit()
    logger.info("DB 초기화 완료: %s", DB_PATH)


def is_seen(url: str, title_hash: str) -> bool:
    """URL 또는 제목 해시 기준으로 이미 저장된 기사인지 확인."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM articles WHERE url = ? OR title_hash = ?",
            (url, title_hash),
        ).fetchone()
    return row is not None


def save_article(article: dict) -> bool:
    """기사를 DB에 저장. 이미 존재하면 무시."""
    try:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO articles
                    (url, title_hash, title, source, description, published_at,
                     category, summary, companies, people)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    article.get("url", ""),
                    article.get("title_hash", ""),
                    article.get("title", ""),
                    article.get("source", ""),
                    article.get("description", ""),
                    article.get("published_at", ""),
                    article.get("category", ""),
                    article.get("summary", ""),
                    ",".join(article.get("companies", [])),
                    ",".join(article.get("people", [])),
                ),
            )
            conn.commit()
        return True
    except sqlite3.Error as e:
        logger.error("기사 저장 실패: %s", e)
        return False


def update_article_ai(url: str, category: str, summary: str,
                      companies: list, people: list) -> None:
    """AI 처리 결과(카테고리, 요약, 관련 회사/인물)로 기사 업데이트."""
    with _get_connection() as conn:
        conn.execute(
            """
            UPDATE articles
            SET category = ?, summary = ?, companies = ?, people = ?
            WHERE url = ?
            """,
            (
                category,
                summary,
                ",".join(companies),
                ",".join(people),
                url,
            ),
        )
        conn.commit()


def get_recent_articles(hours: int = 24) -> list:
    """최근 N시간 이내 수집된 기사 목록 반환."""
    since = (datetime.utcnow() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM articles WHERE created_at >= ? ORDER BY created_at DESC",
            (since,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_weekly_articles() -> list:
    """최근 7일간 수집된 기사 목록 반환 (주간 리포트용)."""
    return get_recent_articles(hours=168)


def cleanup_old_articles(days: int = 30) -> None:
    """N일 이상 된 기사를 DB에서 삭제."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    with _get_connection() as conn:
        deleted = conn.execute(
            "DELETE FROM articles WHERE created_at < ?", (cutoff,)
        ).rowcount
        conn.commit()
    if deleted > 0:
        logger.info("%d건의 오래된 기사 정리 완료", deleted)
