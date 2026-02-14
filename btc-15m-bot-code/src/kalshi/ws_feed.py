"""
Kalshi 전용 WebSocket 실시간 가격 피드 매니저

아키텍처 (websocket_feed.py와 동일 패턴):
- 백그라운드 스레드에서 asyncio 이벤트 루프 실행
- 주기적 REST 호출로 시장 발견 (30초마다)
- WebSocket으로 실시간 가격 수신 (Kalshi only)
- 메인 스레드(engine)에서 get_market_data()로 캐시된 가격 읽기
"""

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from src.kalshi.websocket_client import KalshiWebSocket
from src.kalshi.client import KalshiClient


@dataclass
class KalshiMarketInfo:
    """시장 메타데이터 (REST에서 조회)"""
    coin: str
    ticker: str = ""
    title: str = ""
    strike_price: Optional[float] = None
    close_time: str = ""
    last_discovery: float = 0


@dataclass
class KalshiPriceSnapshot:
    """실시간 가격 스냅샷"""
    yes_ask: float = 0
    no_ask: float = 0
    updated: float = 0


class KalshiWebSocketFeed:
    """Kalshi 전용 WebSocket 실시간 가격 피드"""

    DISCOVERY_INTERVAL = 30  # 시장 발견 주기 (초)
    STALE_THRESHOLD = 15     # 가격 유효기간 (초) - WS 끊김 감지

    def __init__(self, kalshi_client: KalshiClient):
        self.kalshi_client = kalshi_client
        self.kalshi_ws = KalshiWebSocket()

        # 시장 정보 캐시 (REST에서 주기적 갱신)
        self._markets: dict[str, KalshiMarketInfo] = {}
        # 가격 캐시 (WebSocket에서 실시간 갱신)
        self._prices: dict[str, KalshiPriceSnapshot] = {}
        # 구독 상태
        self._kalshi_subs: set = set()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()

        # 연결 상태
        self.kalshi_ws_connected = False

    def start(self, coins: list[str]):
        """백그라운드 스레드에서 WebSocket 피드 시작"""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_async_loop,
            args=(coins,),
            daemon=True,
            name="kalshi-ws-feed"
        )
        self._thread.start()
        logger.warning("[KALSHI-FEED] WebSocket 가격 피드 백그라운드 시작")

    def stop(self):
        """피드 중단"""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        logger.warning("[KALSHI-FEED] WebSocket 가격 피드 중단")

    @property
    def is_connected(self) -> bool:
        """WS 연결 상태"""
        return self.kalshi_ws_connected

    def get_market_data(self, coin: str):
        """엔진에서 호출: 캐시된 시장 데이터 반환 (thread-safe)

        Returns:
            kalshi_dict or None
        """
        with self._lock:
            market = self._markets.get(coin)
            prices = self._prices.get(coin)

        if not market or not prices:
            return None

        now = time.time()

        # staleness 체크
        if prices.updated > 0 and (now - prices.updated) < self.STALE_THRESHOLD:
            return {
                "coin": coin,
                "ticker": market.ticker,
                "title": market.title,
                "yes_ask": int(round(prices.yes_ask)) if prices.yes_ask > 0 else 0,
                "no_ask": int(round(prices.no_ask)) if prices.no_ask > 0 else 0,
                "yes_bid": 0,
                "no_bid": 0,
                "strike_price": market.strike_price,
                "close_time": market.close_time,
            }

        return None

    # === 백그라운드 asyncio 루프 ===

    def _run_async_loop(self, coins: list[str]):
        """백그라운드 스레드: asyncio 이벤트 루프 실행"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main(coins))
        except Exception as e:
            logger.error(f"[KALSHI-FEED] 이벤트 루프 에러: {e}")
        finally:
            self._loop.close()

    async def _async_main(self, coins: list[str]):
        """비동기 메인: WS 연결 + 리스너 + 주기적 발견"""
        # WebSocket 연결
        self.kalshi_ws_connected = await self.kalshi_ws.connect()

        if self.kalshi_ws_connected:
            logger.warning("[KALSHI-FEED] Kalshi WebSocket 연결 성공")
        else:
            logger.error("[KALSHI-FEED] Kalshi WebSocket 연결 실패 → REST 폴백")

        # 콜백 설정
        self.kalshi_ws.on_price_update = self._on_kalshi_price

        # 초기 시장 발견 (REST)
        await self._discover_markets(coins)

        # 병렬 태스크 실행
        tasks = []
        if self.kalshi_ws_connected:
            tasks.append(asyncio.create_task(self.kalshi_ws.listen()))
        tasks.append(asyncio.create_task(self._periodic_discovery(coins)))

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    async def _periodic_discovery(self, coins: list[str]):
        """주기적 시장 발견 + 구독 갱신"""
        while self._running:
            await asyncio.sleep(self.DISCOVERY_INTERVAL)
            try:
                await self._discover_markets(coins)
            except Exception as e:
                logger.warning(f"[KALSHI-FEED] 시장 발견 에러: {e}")

    async def _discover_markets(self, coins: list[str]):
        """REST API로 시장 발견 + WebSocket 구독"""
        for coin in coins:
            try:
                loop = asyncio.get_event_loop()
                kalshi_markets = await loop.run_in_executor(
                    None, self.kalshi_client.get_crypto_markets, coin
                )

                if not kalshi_markets:
                    logger.debug(f"[KALSHI-FEED] {coin} 시장 없음")
                    continue

                kalshi = kalshi_markets[0]

                new_market = KalshiMarketInfo(
                    coin=coin,
                    ticker=kalshi.get("ticker", ""),
                    title=kalshi.get("title", ""),
                    strike_price=kalshi.get("strike_price"),
                    close_time=kalshi.get("close_time", ""),
                    last_discovery=time.time(),
                )

                with self._lock:
                    old_market = self._markets.get(coin)

                    prices = self._prices.get(coin, KalshiPriceSnapshot())
                    now = time.time()

                    # WS 데이터가 stale하면 REST로 시드
                    ws_fresh = (prices.updated > 0 and
                                (now - prices.updated) < self.STALE_THRESHOLD)
                    if not ws_fresh:
                        prices.yes_ask = kalshi.get("yes_ask", 0)
                        prices.no_ask = kalshi.get("no_ask", 0)
                        prices.updated = now
                        logger.debug(f"[KALSHI-FEED] {coin} REST seed (WS stale)")

                    self._prices[coin] = prices
                    self._markets[coin] = new_market

                # WebSocket 구독 갱신
                await self._update_subscriptions(coin, old_market, new_market)

                logger.debug(
                    f"[KALSHI-FEED] {coin} 시장 갱신: "
                    f"Kalshi={new_market.ticker}"
                )

            except Exception as e:
                logger.warning(f"[KALSHI-FEED] {coin} 발견 에러: {e}")

    async def _update_subscriptions(self, coin: str, old: Optional[KalshiMarketInfo], new: KalshiMarketInfo):
        """WebSocket 구독 갱신"""
        # 이전 티커 구독 해제
        if old and self.kalshi_ws_connected:
            if old.ticker and old.ticker != new.ticker:
                await self.kalshi_ws.unsubscribe(old.ticker)
                self._kalshi_subs.discard(old.ticker)

        # 새 티커 구독
        if self.kalshi_ws_connected:
            if new.ticker and new.ticker not in self._kalshi_subs:
                await self.kalshi_ws.subscribe(new.ticker)
                self._kalshi_subs.add(new.ticker)

    # === WebSocket 콜백 ===

    async def _on_kalshi_price(self, ticker: str, price_data: dict):
        """Kalshi 가격 업데이트 콜백"""
        with self._lock:
            for coin, market in self._markets.items():
                if ticker == market.ticker:
                    prices = self._prices.setdefault(coin, KalshiPriceSnapshot())
                    prices.yes_ask = price_data.get("yes_ask", 0)
                    prices.no_ask = price_data.get("no_ask", 0)
                    prices.updated = time.time()
                    logger.debug(
                        f"[KALSHI-FEED] {coin} YES={prices.yes_ask:.1f}¢ "
                        f"NO={prices.no_ask:.1f}¢"
                    )
                    break
