"""
텔레그램 실시간 알림 (non-blocking)
"""
import os
import time
import threading
import requests
from datetime import datetime
from loguru import logger


class TelegramNotifier:
    def __init__(self):
        self.token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
        self.chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
        self.enabled = bool(self.token and self.chat_id)

        if self.enabled:
            logger.warning(f"[TELEGRAM] chat_id='{self.chat_id}' (len={len(self.chat_id)}, repr={repr(self.chat_id)})")

        if self.enabled:
            # 실제 API 연결 테스트
            if self._test_connection():
                print("[OK] Telegram notifications enabled (연결 확인됨)")
            else:
                print("[!] Telegram 환경변수 설정됨, API 연결 실패 (토큰/채팅ID 확인)")
        else:
            print("[!] Telegram not configured (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 필요)")

    def _test_connection(self) -> bool:
        """텔레그램 봇 API 연결 + 메시지 전송 테스트"""
        try:
            # 1) 봇 토큰 확인 (getMe)
            url = f"https://api.telegram.org/bot{self.token}/getMe"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200 or not resp.json().get("ok"):
                logger.warning(f"[TELEGRAM] 봇 토큰 무효: {resp.text}")
                return False

            # 2) 실제 메시지 전송 테스트 (chat_id 검증)
            send_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": "🤖 봇 연결 테스트 OK", "parse_mode": "HTML"}
            send_resp = requests.post(send_url, data=data, timeout=5)
            if send_resp.status_code == 200 and send_resp.json().get("ok"):
                return True
            logger.warning(f"[TELEGRAM] 메시지 전송 실패 (chat_id 확인): {send_resp.text}")
            return False
        except Exception as e:
            logger.warning(f"[TELEGRAM] 연결 테스트 에러: {e}")
            return False

    def send(self, message: str):
        """비동기 전송 (백그라운드 스레드) - 거래 실행 차단 안 함"""
        if not self.enabled:
            return
        threading.Thread(target=self._send_sync, args=(message,), daemon=True).start()

    def send_blocking(self, message: str):
        """동기 전송 + 3회 재시도 (중요 알림용: halt 등)"""
        if not self.enabled:
            return
        for attempt in range(3):
            try:
                url = f"https://api.telegram.org/bot{self.token}/sendMessage"
                data = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
                resp = requests.post(url, data=data, timeout=10)
                if resp.status_code == 200:
                    return
                logger.warning(f"[TELEGRAM] 전송 실패 (status={resp.status_code}), 재시도 {attempt+1}/3")
            except Exception as e:
                logger.warning(f"[TELEGRAM] 전송 에러: {e}, 재시도 {attempt+1}/3")
            time.sleep(1)

    def _send_sync(self, message: str):
        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            resp = requests.post(url, data=data, timeout=5)
            if resp.status_code != 200:
                logger.warning(f"[TELEGRAM] 전송 실패 (status={resp.status_code}): {resp.text}")
        except Exception as e:
            logger.warning(f"[TELEGRAM] 백그라운드 전송 실패: {e}")

    def notify_error(self, error_msg):
        msg = f"""⚠️ <b>에러 발생</b>

{error_msg}"""
        self.send(msg)

    def notify_start(self):
        msg = """🤖 <b>BTC 15분 방향성 매매 봇 시작!</b>

📈 전략: 80¢ 매수 → 100¢ 정산
🛑 손절: 60¢ 이하
🔍 스캔 시작..."""
        self.send(msg)
