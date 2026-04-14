"""
게임업계 HR 뉴스봇 진입점

실행:
    python main.py              # 스케줄러 상시 실행 (운영 모드)
    python main.py --now        # 즉시 일간 뉴스 수집 후 종료 (테스트용)
    python main.py --weekly     # 즉시 주간 리포트 생성 후 종료 (테스트용)
"""
import argparse
import logging
import os
import sys

from dotenv import load_dotenv

# .env 파일 로드 (있을 경우)
load_dotenv()

# 로그 설정
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="게임업계 HR 뉴스봇")
    parser.add_argument(
        "--now",
        action="store_true",
        help="즉시 일간 뉴스 수집 실행 후 종료",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="즉시 주간 리포트 생성 후 종료",
    )
    args = parser.parse_args()

    from src import database as db
    db.init_db()

    if args.now:
        logger.info("즉시 실행 모드: 일간 뉴스 수집")
        from src.scheduler import daily_job
        daily_job()
        return

    if args.weekly:
        logger.info("즉시 실행 모드: 주간 리포트 (7일치 직접 수집)")
        from src.scheduler import weekly_collect_job
        weekly_collect_job()
        return

    # 기본: 스케줄러 상시 실행
    from src.scheduler import run_scheduler
    run_scheduler()


if __name__ == "__main__":
    main()
