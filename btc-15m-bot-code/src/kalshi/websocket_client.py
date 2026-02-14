"""
Kalshi WebSocket 클라이언트
실시간 오더북 데이터 수신

인증: HTTP 헤더에 RSA-PSS 서명 (연결 시 전달)
엔드포인트: wss://api.elections.kalshi.com/trade-api/ws/v2

오더북 구조 (REST와 동일):
- "yes" 배열 = YES bids (YES 매수 주문)
- "no" 배열 = NO bids (NO 매수 주문)
- YES ask = 100 - best NO bid
- NO ask = 100 - best YES bid
"""

import asyncio
import json
import time
import base64
import os
from typing import Callable, Optional
from loguru import logger

try:
    import websockets
except ImportError:
    logger.warning("websockets가 설치되지 않았습니다. pip install websockets")
    websockets = None


# Kalshi WebSocket 엔드포인트 (공식 starter code 기준)
WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
WS_DEMO_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"
WS_PATH = "/trade-api/ws/v2"


class KalshiWebSocket:
    """Kalshi 실시간 WebSocket 클라이언트"""

    def __init__(self, demo_mode: bool = False):
        self.key_id = os.getenv("KALSHI_API_KEY_ID")
        self.demo_mode = demo_mode

        # 프라이빗 키 로드 (파일 또는 환경변수)
        key_file = os.getenv("KALSHI_PRIVATE_KEY_FILE")
        if key_file and os.path.exists(key_file):
            with open(key_file, 'r') as f:
                self.private_key_pem = f.read()
        else:
            self.private_key_pem = os.getenv("KALSHI_PRIVATE_KEY")

        # RSA 키 로드
        self._private_key = None
        if self.private_key_pem:
            try:
                from cryptography.hazmat.primitives import serialization
                self._private_key = serialization.load_pem_private_key(
                    self.private_key_pem.encode(), password=None
                )
            except Exception as e:
                logger.error(f"[KALSHI-WS] RSA 키 로드 실패: {e}")

        self.ws = None
        self.connected = False
        self.subscribed_markets = set()
        self._msg_id = 1
        # Kalshi returns sid on subscribe → required for unsubscribe
        self._ticker_to_sid: dict[str, int] = {}  # ticker → sid
        self._pending_subs: dict[int, str] = {}   # msg_id → ticker (subscribe 응답 매칭용)

        # 콜백 함수
        self.on_price_update: Optional[Callable] = None

        # 오더북 캐시
        self._orderbooks = {}
        self.prices = {}

    def _get_ws_url(self) -> str:
        return WS_DEMO_URL if self.demo_mode else WS_URL

    def _build_auth_headers(self) -> dict:
        """RSA-PSS 서명으로 인증 헤더 생성 (HTTP 핸드셰이크용)"""
        if not self.key_id or not self._private_key:
            return {}

        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding

            timestamp_ms = str(int(time.time() * 1000))
            msg_string = f"{timestamp_ms}GET{WS_PATH}"

            signature = self._private_key.sign(
                msg_string.encode('utf-8'),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            signature_b64 = base64.b64encode(signature).decode('utf-8')

            return {
                "KALSHI-ACCESS-KEY": self.key_id,
                "KALSHI-ACCESS-SIGNATURE": signature_b64,
                "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            }
        except Exception as e:
            logger.error(f"[KALSHI-WS] 인증 헤더 생성 실패: {e}")
            return {}

    async def connect(self) -> bool:
        """WebSocket 연결 (인증 헤더를 HTTP 핸드셰이크에 포함)"""
        if websockets is None:
            logger.error("websockets 라이브러리가 필요합니다")
            return False

        try:
            # 인증 헤더 생성
            auth_headers = self._build_auth_headers()
            if not auth_headers:
                logger.error("[KALSHI-WS] 인증 헤더 없음 (API 키 확인)")
                return False

            self.ws = await websockets.connect(
                self._get_ws_url(),
                additional_headers=auth_headers,
                ping_interval=30,
                ping_timeout=10
            )

            self.connected = True
            logger.info("[KALSHI-WS] 연결+인증 성공")
            return True

        except Exception as e:
            logger.error(f"[KALSHI-WS] 연결 실패: {e}")
            return False

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("[KALSHI-WS] 연결 종료")

    async def subscribe(self, ticker: str):
        if not self.connected or not self.ws:
            return

        try:
            self._msg_id += 1
            msg = {
                "id": self._msg_id,
                "cmd": "subscribe",
                "params": {
                    "channels": ["orderbook_delta"],
                    "market_tickers": [ticker]
                }
            }
            await self.ws.send(json.dumps(msg))
            self._pending_subs[self._msg_id] = ticker
            self.subscribed_markets.add(ticker)
            logger.debug(f"[KALSHI-WS] 구독 요청: {ticker} (msg_id={self._msg_id})")
        except Exception as e:
            logger.error(f"[KALSHI-WS] 구독 실패: {e}")

    async def unsubscribe(self, ticker: str):
        if not self.connected or not self.ws:
            return

        sid = self._ticker_to_sid.get(ticker)
        if sid is None:
            logger.warning(f"[KALSHI-WS] 구독 해제 스킵 (sid 없음): {ticker}")
            self.subscribed_markets.discard(ticker)
            return

        try:
            self._msg_id += 1
            msg = {
                "id": self._msg_id,
                "cmd": "unsubscribe",
                "params": {
                    "sids": [sid]
                }
            }
            await self.ws.send(json.dumps(msg))
            self.subscribed_markets.discard(ticker)
            self._ticker_to_sid.pop(ticker, None)
            self._orderbooks.pop(ticker, None)
            self.prices.pop(ticker, None)
            logger.debug(f"[KALSHI-WS] 구독 해제: {ticker} (sid={sid})")
        except Exception as e:
            logger.error(f"[KALSHI-WS] 구독 해제 실패: {e}")

    async def listen(self):
        if not self.connected or not self.ws:
            return

        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.debug(f"[KALSHI-WS] 비-JSON: {message[:50]}")
                except Exception as e:
                    logger.warning(f"[KALSHI-WS] 메시지 처리 에러: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("[KALSHI-WS] 연결 끊김, 재연결 시도...")
            self.connected = False
            await self._reconnect()
        except Exception as e:
            logger.error(f"[KALSHI-WS] 수신 오류: {e}")
            self.connected = False

    async def _handle_message(self, data: dict):
        msg_type = data.get("type", "")
        msg = data.get("msg", {})

        if msg_type == "orderbook_snapshot":
            ticker = msg.get("market_ticker", "")
            if ticker:
                self._apply_snapshot(ticker, msg)
                self._compute_prices(ticker)

        elif msg_type == "orderbook_delta":
            ticker = msg.get("market_ticker", "")
            if not ticker:
                return
            if "yes" in msg or "no" in msg:
                self._apply_snapshot(ticker, msg)
            elif "price" in msg and "delta" in msg and "side" in msg:
                self._apply_delta(ticker, msg)
            else:
                return
            self._compute_prices(ticker)

        elif msg_type == "subscribed":
            # 구독 응답에서 sid 추적
            resp_id = data.get("id")
            sid = msg.get("sid") if isinstance(msg, dict) else None
            if sid is None:
                sid = data.get("sid")
            if sid is not None and resp_id in self._pending_subs:
                ticker = self._pending_subs.pop(resp_id)
                self._ticker_to_sid[ticker] = sid
                logger.info(f"[KALSHI-WS] 구독 확인: {ticker} → sid={sid}")
            elif sid is not None:
                logger.debug(f"[KALSHI-WS] 구독 응답 sid={sid} (매칭 안됨, id={resp_id})")

        elif msg_type == "error":
            logger.error(f"[KALSHI-WS] 오류: {data}")

    def _apply_snapshot(self, ticker: str, msg: dict):
        yes_bids = {}
        no_bids = {}

        for item in (msg.get("yes") or []):
            if isinstance(item, list) and len(item) >= 2:
                price, qty = int(item[0]), int(item[1])
                if qty > 0:
                    yes_bids[price] = qty
            elif isinstance(item, dict):
                price = int(item.get("price", 0))
                qty = int(item.get("quantity", item.get("count", 0)))
                if qty > 0:
                    yes_bids[price] = qty

        for item in (msg.get("no") or []):
            if isinstance(item, list) and len(item) >= 2:
                price, qty = int(item[0]), int(item[1])
                if qty > 0:
                    no_bids[price] = qty
            elif isinstance(item, dict):
                price = int(item.get("price", 0))
                qty = int(item.get("quantity", item.get("count", 0)))
                if qty > 0:
                    no_bids[price] = qty

        self._orderbooks[ticker] = {
            "yes_bids": yes_bids,
            "no_bids": no_bids,
            "timestamp": time.time()
        }

    def _apply_delta(self, ticker: str, msg: dict):
        if ticker not in self._orderbooks:
            return

        book = self._orderbooks[ticker]
        side = msg.get("side", "")
        price = int(msg.get("price", 0))
        delta = int(msg.get("delta", 0))

        if side == "yes":
            bids = book["yes_bids"]
        elif side == "no":
            bids = book["no_bids"]
        else:
            return

        current = bids.get(price, 0)
        new_qty = current + delta
        if new_qty <= 0:
            bids.pop(price, None)
        else:
            bids[price] = new_qty
        book["timestamp"] = time.time()

    def _calc_fill_price(self, bids: dict, qty: int) -> float:
        """오더북에서 qty 수량의 가중평균 체결가 계산

        bids = {price: count, ...}
        체결가 = 100 - bid_price (complement)
        Returns 0 if insufficient depth.
        """
        if not bids:
            return 0.0
        sorted_bids = sorted(bids.items(), key=lambda x: x[0], reverse=True)
        remaining = qty
        total_cost = 0
        for bid_price, available in sorted_bids:
            fill = min(remaining, available)
            ask_price = 100 - bid_price
            total_cost += fill * ask_price
            remaining -= fill
            if remaining <= 0:
                break
        if remaining > 0:
            return 0.0  # 오더북 깊이 부족
        return total_cost / qty

    def _compute_prices(self, ticker: str, fill_qty: int = 3):
        """YES/NO ask 가격 계산 — qty 수량의 가중평균 체결가

        fill_qty=3: MAX_TRADE_SIZE와 동일 (10이면 가격 왜곡 심함).
        오더북 깊이가 부족하면 0 반환 (거래 차단).
        """
        book = self._orderbooks.get(ticker)
        if not book:
            return

        # YES ask = 100 - NO bids (가중평균)
        yes_ask = self._calc_fill_price(book["no_bids"], fill_qty)
        # NO ask = 100 - YES bids (가중평균)
        no_ask = self._calc_fill_price(book["yes_bids"], fill_qty)

        self.prices[ticker] = {
            "yes_ask": yes_ask,
            "no_ask": no_ask,
            "timestamp": time.time()
        }

        if self.on_price_update:
            asyncio.ensure_future(
                self.on_price_update(ticker, self.prices[ticker])
            )

    async def _reconnect(self):
        # 재연결 시 sid 매핑 초기화 (서버에서 새 sid 발급)
        self._ticker_to_sid.clear()
        self._pending_subs.clear()
        for attempt in range(5):
            logger.info(f"[KALSHI-WS] 재연결 {attempt + 1}/5...")
            await asyncio.sleep(2 ** attempt)
            if await self.connect():
                for ticker in list(self.subscribed_markets):
                    await self.subscribe(ticker)
                asyncio.create_task(self.listen())
                return
        logger.error("[KALSHI-WS] 재연결 실패 (5회)")

    def get_price(self, ticker: str) -> dict:
        return self.prices.get(ticker, {"yes_ask": 0, "no_ask": 0, "timestamp": 0})
