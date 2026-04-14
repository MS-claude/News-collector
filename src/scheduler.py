"""
APScheduler 기반 스케줄러
- 매일 09:00 KST: 일간 뉴스 수집 → AI 요약 → 이메일 발송
- 매주 금요일 09:00 KST: 주간 리포트 생성 → 이메일 발송
- 매일 03:00 KST: 30일 이상 된 기사 DB 정리

수집 전략:
- 게임 전문 매체 RSS: 직접 수집 (인벤·게임동아·게임조선·지디넷)
- 구글/네이버 뉴스: 광범위 검색 후 신뢰 게임 매체 도메인 기사만 통과
"""
import logging
from urllib.parse import urlparse

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from src import database as db
from src.collectors import google_news, naver_news, gaming_media

# 구글·네이버 수집 결과 도메인 허용 목록
TRUSTED_DOMAINS = [
    "game.donga.com",
    "gamefocus.co.kr",
    "gamemeca.com",
    "zdnet.co.kr",
    "gamechosun.co.kr",
    "inven.co.kr",
]
from src.notifiers import email_sender
from src.processors import deduplicator
from src.processors.summarizer import ArticleSummarizer
from src.reporters import daily_report, weekly_report

logger = logging.getLogger(__name__)

KST_TIMEZONE = "Asia/Seoul"
_summarizer = ArticleSummarizer()


# ──────────────────────────────────────────────────────────────────────────────
# 잡 함수
# ──────────────────────────────────────────────────────────────────────────────

def _filter_by_trusted_domain(articles: list) -> list:
    """구글·네이버 수집 기사 중 신뢰 게임 매체 도메인 기사만 반환."""
    result = []
    for article in articles:
        netloc = urlparse(article.get("url", "")).netloc.lower()
        if any(domain in netloc for domain in TRUSTED_DOMAINS):
            result.append(article)
    return result


def daily_job() -> None:
    """
    일간 뉴스 수집 파이프라인
    1. 게임 전문 매체 RSS 직접 수집 (최근 24시간)
    2. 구글·네이버 검색 수집 후 신뢰 도메인 필터링
    3. 중복 제거
    4. DB 저장 + AI 요약
    5. HTML 이메일 생성 및 발송
    """
    logger.info("=== 일간 뉴스 수집 시작 ===")

    try:
        # 1. 게임 전문 매체 RSS 직접 수집
        rss_articles = gaming_media.collect(hours=24)

        # 2. 구글·네이버 수집 후 신뢰 도메인 필터링
        search_raw = google_news.collect(hours=24) + naver_news.collect(hours=24)
        search_articles = _filter_by_trusted_domain(search_raw)
        logger.info(
            "구글·네이버 수집: 전체 %d건 → 도메인 필터 후 %d건",
            len(search_raw), len(search_articles),
        )

        raw_articles = rss_articles + search_articles
        logger.info("수집 완료: 전체 %d건", len(raw_articles))

        # 2. 중복 제거
        new_articles = deduplicator.deduplicate(raw_articles)
        logger.info("신규 기사: %d건", len(new_articles))

        # 3. DB에 원본 저장 (AI 처리 전)
        for article in new_articles:
            db.save_article(article)

        # 4. AI 요약 (신규 기사가 없어도 '뉴스 없음' 결과 반환)
        ai_result = _summarizer.summarize_daily(new_articles)

        # 5. AI 결과로 DB 업데이트
        for i, article in enumerate(new_articles):
            ai_art = next(
                (a for a in ai_result.get("articles", []) if a.get("index") == i), {}
            )
            db.update_article_ai(
                url=article["url"],
                category=ai_art.get("category", "기타"),
                summary=ai_art.get("summary", ""),
                companies=ai_art.get("companies", []),
                people=ai_art.get("people", []),
            )

        # 6. HTML 이메일 생성 및 발송
        subject, html = daily_report.generate(new_articles, ai_result)
        email_sender.send(subject, html)

        logger.info("=== 일간 뉴스 수집 완료 ===")

    except Exception as e:
        logger.exception("일간 뉴스 수집 중 예외 발생: %s", e)


def weekly_job() -> None:
    """
    주간 리포트 파이프라인 (스케줄러 자동 실행용)
    1. DB에서 최근 7일 기사 조회 (daily_job이 누적한 데이터 사용)
    2. AI 주간 요약
    3. HTML 이메일 생성 및 발송
    """
    logger.info("=== 주간 리포트 생성 시작 ===")

    try:
        articles = db.get_weekly_articles()
        logger.info("주간 기사 조회: %d건", len(articles))

        ai_result = _summarizer.summarize_weekly(articles)

        subject, html = weekly_report.generate(articles, ai_result)
        email_sender.send(subject, html)

        logger.info("=== 주간 리포트 생성 완료 ===")

    except Exception as e:
        logger.exception("주간 리포트 생성 중 예외 발생: %s", e)


def weekly_collect_job() -> None:
    """
    주간 리포트 파이프라인 (직접 실행용 --weekly)
    1. 최근 7일치 기사 직접 수집 (RSS + 구글·네이버 도메인 필터)
    2. 중복 제거 후 DB 저장
    3. DB에서 최근 7일 기사 전체 조회
    4. AI 주간 요약
    5. HTML 이메일 생성 및 발송
    """
    logger.info("=== 주간 리포트 수집+생성 시작 (직접 실행) ===")

    try:
        # 1. 최근 7일치 직접 수집
        rss_articles = gaming_media.collect(hours=168)

        search_raw = google_news.collect(hours=168) + naver_news.collect(hours=168)
        search_articles = _filter_by_trusted_domain(search_raw)
        logger.info(
            "구글·네이버 수집: 전체 %d건 → 도메인 필터 후 %d건",
            len(search_raw), len(search_articles),
        )

        raw_articles = rss_articles + search_articles
        logger.info("수집 완료: 전체 %d건", len(raw_articles))

        # 2. 중복 제거 후 DB 저장
        new_articles = deduplicator.deduplicate(raw_articles)
        logger.info("신규 기사: %d건", len(new_articles))

        for article in new_articles:
            db.save_article(article)

        # 3. DB에서 최근 7일 기사 전체 조회
        articles = db.get_weekly_articles()
        logger.info("주간 기사 조회: %d건", len(articles))

        # 4. AI 주간 요약
        ai_result = _summarizer.summarize_weekly(articles)

        # 5. HTML 이메일 생성 및 발송
        subject, html = weekly_report.generate(articles, ai_result)
        email_sender.send(subject, html)

        logger.info("=== 주간 리포트 수집+생성 완료 ===")

    except Exception as e:
        logger.exception("주간 리포트 수집+생성 중 예외 발생: %s", e)


def cleanup_job() -> None:
    """30일 이상 된 기사 DB 정리."""
    logger.info("DB 정리 시작")
    try:
        db.cleanup_old_articles(days=30)
    except Exception as e:
        logger.exception("DB 정리 중 예외 발생: %s", e)


# ──────────────────────────────────────────────────────────────────────────────
# 스케줄러 설정 및 실행
# ──────────────────────────────────────────────────────────────────────────────

def run_scheduler() -> None:
    """스케줄러 초기화 후 블로킹 실행."""
    db.init_db()

    scheduler = BlockingScheduler(timezone=KST_TIMEZONE)

    # 매일 09:00 KST 일간 뉴스
    scheduler.add_job(
        daily_job,
        CronTrigger(hour=9, minute=0, timezone=KST_TIMEZONE),
        id="daily_news",
        name="일간 뉴스 수집",
        misfire_grace_time=3600,  # 1시간 이내 실행 누락 허용
    )

    # 매주 금요일 09:00 KST 주간 리포트
    scheduler.add_job(
        weekly_job,
        CronTrigger(day_of_week="fri", hour=9, minute=0, timezone=KST_TIMEZONE),
        id="weekly_report",
        name="주간 리포트",
        misfire_grace_time=3600,
    )

    # 매일 03:00 KST DB 정리
    scheduler.add_job(
        cleanup_job,
        CronTrigger(hour=3, minute=0, timezone=KST_TIMEZONE),
        id="cleanup",
        name="DB 정리",
    )

    logger.info(
        "스케줄러 시작 (KST 기준) — "
        "일간: 매일 09:00 | 주간: 매주 금 09:00 | 정리: 매일 03:00"
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")
