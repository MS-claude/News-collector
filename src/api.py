"""
FastAPI 기반 HTTP API 서버
n8n 등 외부 스케줄러에서 HTTP 요청으로 수집 작업을 트리거할 때 사용.

엔드포인트:
    GET  /health        - 서버 상태 확인
    POST /run/daily     - 일간 뉴스 수집 트리거
    POST /run/weekly    - 주간 리포트 수집+생성 트리거

인증:
    모든 POST 요청에 X-API-Key 헤더 필요 (API_KEY 환경변수 값)
"""
import logging
import os

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Header

from src import database as db
from src.scheduler import daily_job, weekly_collect_job

logger = logging.getLogger(__name__)

app = FastAPI(title="뉴스봇 API")


@app.on_event("startup")
async def startup():
    db.init_db()


def _verify_api_key(x_api_key: str = Header(...)):
    expected = os.getenv("API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=500, detail="API_KEY 환경변수가 설정되지 않았습니다"
        )
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="유효하지 않은 API 키")


@app.get("/health")
async def health():
    """서버 상태 확인 (인증 불필요)."""
    return {"status": "ok"}


@app.post("/run/daily", dependencies=[Depends(_verify_api_key)])
async def run_daily(background_tasks: BackgroundTasks):
    """일간 뉴스 수집을 백그라운드로 실행."""
    background_tasks.add_task(daily_job)
    logger.info("일간 수집 작업 트리거됨")
    return {"status": "started", "job": "daily"}


@app.post("/run/weekly", dependencies=[Depends(_verify_api_key)])
async def run_weekly(background_tasks: BackgroundTasks):
    """주간 리포트 수집+생성을 백그라운드로 실행."""
    background_tasks.add_task(weekly_collect_job)
    logger.info("주간 수집 작업 트리거됨")
    return {"status": "started", "job": "weekly"}
