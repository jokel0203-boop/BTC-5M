"""
Polymarket CLOB WebSocket 클라이언트
실시간 오더북 데이터 수신

엔드포인트: wss://ws-subscriptions-clob.polymarket.com/ws/market

프로토콜:
1. 연결 후 초기 핸드셰이크: {"assets_ids": [], "type": "market"}
2. 구독 추가: {"operation": "subscribe", "assets_ids": [token_id]}
3. 구독 해제: {"operation": "unsubscribe", "assets_ids": [token_id]}

주의:
- 응답이 배열(list)일 수 있음 → 개별 처리
- asks/bids 정렬 안됨 → 정렬 필수
- "PONG" 텍스트 메시지 처리
"""

import asyncio
import json
import time
from typing import Callable, Optional
from loguru import logger

try:
    import websockets
except ImportError:
    logger.warning("websockets가 설치되지 않았습니다. pip install websockets")
    websockets = None


WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class PolymarketWebSocket:
    """Polymarket 실시간 WebSocket 클라이언트"""

    def __init__(self):
        self.ws = None
        self.connected = False
        self.subscribed_markets = set()

        self.on_price_update: Optional[Callable] = None

        # 오더북 캐시: {token_id: {"asks": [...], "bids": [...], "timestamp": float}}
        self.orderbooks = {}

    async def connect(self) -> bool:
        if websockets is None:
            logger.error("websockets 라이브러리가 필요합니다")
            return False

        try:
            self.ws = await websockets.connect(WS_URL, ping_interval=30, ping_timeout=10)
            self.connected = True

            # 초기 핸드셰이크 (필수)
            handshake = {"assets_ids": [], "type": "market"}
            await self.ws.send(json.dumps(handshake))

            logger.info("[POLY-WS] 연결 성공")
            return True
        except Exception as e:
            logger.error(f"[POLY-WS] 연결 실패: {e}")
            return False

    async def disconnect(self):
        if self.ws:
            await self.ws.close()
            self.connected = False
            logger.info("[POLY-WS] 연결 종료")

    async def subscribe(self, token_id: str):
        if not self.connected or not self.ws:
            return

        try:
            # Polymarket WS 구독 형식: "operation" 필드 사용
            msg = {
                "operation": "subscribe",
                "assets_ids": [token_id]
            }
            await self.ws.send(json.dumps(msg))
            self.subscribed_markets.add(token_id)
            logger.debug(f"[POLY-WS] 구독: {token_id[:20]}...")
        except Exception as e:
            logger.error(f"[POLY-WS] 구독 실패: {e}")

    async def unsubscribe(self, token_id: str):
        if not self.connected or not self.ws:
            return

        try:
            msg = {
                "operation": "unsubscribe",
                "assets_ids": [token_id]
            }
            await self.ws.send(json.dumps(msg))
            self.subscribed_markets.discard(token_id)
            self.orderbooks.pop(token_id, None)
            logger.debug(f"[POLY-WS] 구독 해제: {token_id[:20]}...")
        except Exception as e:
            logger.error(f"[POLY-WS] 구독 해제 실패: {e}")

    async def listen(self):
        if not self.connected or not self.ws:
            return

        try:
            async for message in self.ws:
                try:
                    # "PONG" 텍스트 처리
                    stripped = message.strip()
                    if stripped.upper() == "PONG":
                        continue

                    parsed = json.loads(message)

                    # 응답이 배열일 수 있음
                    events = parsed if isinstance(parsed, list) else [parsed]
                    for data in events:
                        if isinstance(data, dict):
                            await self._handle_message(data)

                except json.JSONDecodeError:
                    logger.debug(f"[POLY-WS] 비-JSON: {message[:50]}")
                except Exception as e:
                    logger.warning(f"[POLY-WS] 메시지 처리 에러: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("[POLY-WS] 연결 끊김, 재연결 시도...")
            self.connected = False
            await self._reconnect()
        except Exception as e:
            logger.error(f"[POLY-WS] 수신 오류: {e}")
            self.connected = False

    async def _handle_message(self, data: dict):
        # event_type 필드 사용 (Polymarket CLOB WS)
        msg_type = data.get("event_type", "")

        if msg_type == "book":
            token_id = data.get("asset_id", "")
            if not token_id:
                return

            asks_raw = data.get("asks", [])
            bids_raw = data.get("bids", [])

            # asks 오름차순 정렬 (best ask = 최저가)
            asks = sorted(asks_raw, key=lambda x: float(x.get("price", 0)))
            # bids 내림차순 정렬 (best bid = 최고가)
            bids = sorted(bids_raw, key=lambda x: float(x.get("price", 0)), reverse=True)

            self.orderbooks[token_id] = {
                "asks": asks,
                "bids": bids,
                "timestamp": time.time()
            }

            if self.on_price_update:
                best = self.get_best_prices(token_id)
                await self.on_price_update(token_id, best)

        elif msg_type == "price_change":
            # price_changes 배열 안에 asset_id가 있음
            for change in data.get("price_changes", []):
                token_id = change.get("asset_id", "")
                if token_id and self.on_price_update:
                    best = self.get_best_prices(token_id)
                    if best["ask"] > 0:
                        await self.on_price_update(token_id, best)

        elif msg_type == "last_trade_price":
            pass  # 거래 정보 (가격 캐시에 영향 없음)

    async def _reconnect(self):
        # 재연결 중 stale 데이터 거래 방지: 캐시 타임스탬프 무효화
        for token_id in self.orderbooks:
            self.orderbooks[token_id]["timestamp"] = 0
        for attempt in range(5):
            logger.info(f"[POLY-WS] 재연결 {attempt + 1}/5...")
            await asyncio.sleep(min(2 ** attempt, 3))  # 최대 3초 대기 (빠른 복구)
            if await self.connect():
                for token_id in list(self.subscribed_markets):
                    await self.subscribe(token_id)
                asyncio.create_task(self.listen())
                return
        logger.error("[POLY-WS] 재연결 실패 (5회)")

    def _calc_fill_price(self, asks: list, qty: int) -> tuple[float, int]:
        """오더북에서 qty 수량의 가중평균 체결가 계산 (asks 기준)

        asks = [{"price": "0.46", "size": "50"}, ...] (오름차순 정렬됨)
        Returns (weighted_avg_price, total_fillable_qty).
        깊이 부족 시 (0.0, available_qty) 반환.
        """
        if not asks:
            return 0.0, 0
        remaining = qty
        total_cost = 0.0
        total_filled = 0
        for level in asks:
            price = float(level.get("price", 0))
            size = int(float(level.get("size", 0)))
            if price <= 0 or size <= 0:
                continue
            fill = min(remaining, size)
            total_cost += fill * price
            total_filled += fill
            remaining -= fill
            if remaining <= 0:
                break
        if total_filled <= 0:
            return 0.0, 0
        return total_cost / total_filled, total_filled

    def get_best_prices(self, token_id: str, fill_qty: int = 10) -> dict:
        """qty 수량의 가중평균 체결가 (오더북 깊이 반영)"""
        data = self.orderbooks.get(token_id, {})
        asks = data.get("asks", [])
        bids = data.get("bids", [])

        result = {
            "ask": 0.0, "ask_size": 0,
            "bid": 0.0, "bid_size": 0,
            "timestamp": data.get("timestamp", 0)
        }

        if asks:
            avg_price, fillable = self._calc_fill_price(asks, fill_qty)
            result["ask"] = avg_price
            result["ask_size"] = fillable
        if bids:
            result["bid"] = float(bids[0].get("price", 0))
            result["bid_size"] = int(float(bids[0].get("size", 0)))

        return result
