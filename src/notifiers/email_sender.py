"""
이메일 발송 모듈 (SMTP)
- HTML 이메일 발송
- Gmail 등 SMTP 서버 지원
- 발송 실패 시 로컬 파일에 HTML 저장 (폴백)
"""
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytz

logger = logging.getLogger(__name__)
KST = pytz.timezone("Asia/Seoul")

_FALLBACK_DIR = Path(__file__).parent.parent.parent / "data" / "reports"


def send(subject: str, html_body: str) -> bool:
    """
    HTML 이메일 발송.

    환경 변수:
      EMAIL_SMTP_SERVER   (기본: smtp.gmail.com)
      EMAIL_SMTP_PORT     (기본: 587)
      EMAIL_SENDER        발신자 주소
      EMAIL_SENDER_PASSWORD 발신자 비밀번호(앱 비밀번호)
      EMAIL_RECIPIENTS    수신자 주소 (쉼표 구분)

    Returns:
        True: 발송 성공, False: 발송 실패
    """
    smtp_server = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
    sender = os.getenv("EMAIL_SENDER", "")
    password = os.getenv("EMAIL_SENDER_PASSWORD", "")
    recipients_raw = os.getenv("EMAIL_RECIPIENTS", "")

    if not all([sender, password, recipients_raw]):
        logger.warning(
            "이메일 설정 미완료 (EMAIL_SENDER / EMAIL_SENDER_PASSWORD / EMAIL_RECIPIENTS). "
            "HTML 파일로 저장합니다."
        )
        _save_html_fallback(subject, html_body)
        return False

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        logger.warning("수신자 목록이 비어있습니다.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())

        logger.info(
            "이메일 발송 완료: [%s] → %s", subject, ", ".join(recipients)
        )
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP 인증 실패. Gmail 사용 시 '앱 비밀번호' 설정이 필요합니다."
        )
    except smtplib.SMTPException as e:
        logger.error("SMTP 오류: %s", e)
    except OSError as e:
        logger.error("네트워크 오류: %s", e)

    # 폴백: 로컬 파일 저장
    _save_html_fallback(subject, html_body)
    return False


def _save_html_fallback(subject: str, html_body: str) -> None:
    """이메일 발송 실패 시 HTML 파일로 로컬 저장."""
    _FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
    safe_subject = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject[:40])
    filepath = _FALLBACK_DIR / f"{now}_{safe_subject}.html"
    filepath.write_text(html_body, encoding="utf-8")
    logger.info("HTML 리포트 저장됨: %s", filepath)
