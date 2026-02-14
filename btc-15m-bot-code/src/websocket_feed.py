"""
WebSocket 실시간 가격 피드 매니저

아키텍처:
- 백그라운드 스레드에서 asyncio 이벤트 루프 실행
- 주기적 REST 호출로 시장 발견 (30초마다)
- WebSocket으로 실시간 가격 수신 (Poly + Kalshi)
- 메인 스레드(engine)에서 get_market_data()로 캐시된 가격 읽기

장점:
- 스캔 시간: ~2.8초 → ~0초 (캐시 읽기)
- 가격 지연: ~2.8초 → ~수십ms (WebSocket)
- REST API 호출 최소화 (30초마다 시장 발견만)
"""

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from src.polymarket.websocket_client import PolymarketWebSocket
from src.kalshi.websocket_client import KalshiWebSocket
from src.polymarket.client import PolymarketClient
from src.kalshi.client import KalshiClient


@dataclass
class MarketInfo:
    """시장 메타데이터 (REST에서 조회)"""
    coin: str
    # Polymarket
    poly_slug: str = ""
    poly_condition_id: str = ""
    poly_up_token: str = ""
    poly_down_token: str = ""
    poly_strike: Optional[float] = None
    poly_current_price: Optional[float] = None
    # Kalshi
    kalshi_ticker: str = ""
    kalshi_strike: Optional[float] = None
    kalshi_close_time: str = ""
    # 타임스탬프
    last_discovery: float = 0


@dataclass
class PriceSnapshot:
    """실시간 가격 스냅샷"""
    # Polymarket (센트) — UP/DOWN 개별 타임스탬프!
    # 공유 타임스탬프 사용 시 UP 업데이트가 stale DOWN을 "fresh"로 위장 → 손실 원인
    poly_up_price: float = 0
    poly_down_price: float = 0
    poly_up_ask_size: int = 0
    poly_down_ask_size: int = 0
    poly_up_updated: float = 0    # UP 토큰 마지막 업데이트
    poly_down_updated: float = 0  # DOWN 토큰 마지막 업데이트
    # Kalshi (센트)
    kalshi_yes_ask: float = 0
    kalshi_no_ask: float = 0
    kalshi_updated: float = 0


class WebSocketPriceFeed:
    """WebSocket 실시간 가격 피드"""

    DISCOVERY_INTERVAL = 30  # 시장 발견 주기 (초)
    STALE_THRESHOLD = 60     # 가격 유효기간 (초) - 15분 마켓은 조용한 구간에 오더북 변화가 드묾

    def __init__(self, poly_client: PolymarketClient, kalshi_client: KalshiClient):
        self.poly_client = poly_client
        self.kalshi_client = kalshi_client

        self.poly_ws = PolymarketWebSocket()
        self.kalshi_ws = KalshiWebSocket()

        # 시장 정보 캐시 (REST에서 주기적 갱신)
        self._markets: dict[str, MarketInfo] = {}
        # 가격 캐시 (WebSocket에서 실시간 갱신)
        self._prices: dict[str, PriceSnapshot] = {}
        # 구독 상태
        self._poly_subs: set = set()
        self._kalshi_subs: set = set()

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._lock = threading.Lock()

        # 연결 상태
        self.poly_ws_connected = False
        self.kalshi_ws_connected = False

    def start(self, coins: list[str]):
        """백그라운드 스레드에서 WebSocket 피드 시작"""
        self._running = True
        self._thread = threading.Thread(
            target=self._run_async_loop,
            args=(coins,),
            daemon=True,
            name="ws-price-feed"
        )
        self._thread.start()
        logger.warning("[WS-FEED] WebSocket 가격 피드 백그라운드 시작")

    def stop(self):
        """피드 중단"""
        self._running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5)
        logger.warning("[WS-FEED] WebSocket 가격 피드 중단")

    @property
    def is_connected(self) -> bool:
        """활성 거래소 WS 연결 상태 (한쪽만 있어도 OK)"""
        if self.poly_client and self.kalshi_client:
            return self.poly_ws_connected and self.kalshi_ws_connected
        elif self.poly_client:
            return self.poly_ws_connected
        elif self.kalshi_client:
            return self.kalshi_ws_connected
        return False

    def get_market_data(self, coin: str):
        """엔진에서 호출: 캐시된 시장 데이터 반환 (thread-safe)

        engine.find_opportunities()와 동일한 형식으로 반환.
        WS 데이터가 없거나 stale하면 None 반환 → 엔진이 REST 폴백.

        Returns:
            (poly_dict, kalshi_dict) or (None, None)
        """
        with self._lock:
            market = self._markets.get(coin)
            prices = self._prices.get(coin)

        if not market or not prices:
            return None, None

        now = time.time()

        # Polymarket 데이터 — UP/DOWN 개별 staleness 체크!
        # UP만 업데이트되고 DOWN이 stale이면 → REST 폴백 (65¢ stale 사고 방지)
        poly_data = None
        poly_up_fresh = prices.poly_up_updated > 0 and (now - prices.poly_up_updated) < self.STALE_THRESHOLD
        poly_down_fresh = prices.poly_down_updated > 0 and (now - prices.poly_down_updated) < self.STALE_THRESHOLD
        if poly_up_fresh and poly_down_fresh:
            poly_data = {
                "coin": coin,
                "slug": market.poly_slug,
                "title": "",
                "condition_id": market.poly_condition_id,
                "up_price": prices.poly_up_price,
                "down_price": prices.poly_down_price,
                "up_token": market.poly_up_token,
                "down_token": market.poly_down_token,
                "up_ask_size": prices.poly_up_ask_size,
                "down_ask_size": prices.poly_down_ask_size,
                "active": True,
                "closed": False,
                "strike_price": market.poly_strike,
                "current_price": market.poly_current_price,
            }

        # Kalshi 데이터
        kalshi_data = None
        if prices.kalshi_updated > 0 and (now - prices.kalshi_updated) < self.STALE_THRESHOLD:
            kalshi_data = {
                "coin": coin,
                "ticker": market.kalshi_ticker,
                "title": "",
                "yes_ask": int(round(prices.kalshi_yes_ask)) if prices.kalshi_yes_ask > 0 else 0,
                "no_ask": int(round(prices.kalshi_no_ask)) if prices.kalshi_no_ask > 0 else 0,
                "yes_bid": 0,
                "no_bid": 0,
                "strike_price": market.kalshi_strike,
                "close_time": market.kalshi_close_time,
            }

        return poly_data, kalshi_data

    # === 백그라운드 asyncio 루프 ===

    def _run_async_loop(self, coins: list[str]):
        """백그라운드 스레드: asyncio 이벤트 루프 실행"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_main(coins))
        except Exception as e:
            logger.error(f"[WS-FEED] 이벤트 루프 에러: {e}")
        finally:
            self._loop.close()

    async def _async_main(self, coins: list[str]):
        """비동기 메인: WS 연결 + 리스너 + 주기적 발견"""
        # WebSocket 연결 (클라이언트가 있는 경우만)
        if self.poly_client:
            self.poly_ws_connected = await self.poly_ws.connect()
            if self.poly_ws_connected:
                logger.warning("[WS-FEED] Polymarket WebSocket 연결 성공")
            else:
                logger.error("[WS-FEED] Polymarket WebSocket 연결 실패 → REST 폴백")
        else:
            logger.warning("[WS-FEED] Polymarket 클라이언트 없음 → 스킵")

        if self.kalshi_client:
            self.kalshi_ws_connected = await self.kalshi_ws.connect()
            if self.kalshi_ws_connected:
                logger.warning("[WS-FEED] Kalshi WebSocket 연결 성공")
            else:
                logger.error("[WS-FEED] Kalshi WebSocket 연결 실패 → REST 폴백")
        else:
            logger.warning("[WS-FEED] Kalshi 클라이언트 없음 → 스킵")

        # 콜백 설정
        self.poly_ws.on_price_update = self._on_poly_price
        self.kalshi_ws.on_price_update = self._on_kalshi_price

        # 초기 시장 발견 (REST) - 가격도 함께 시드
        await self._discover_markets(coins)

        # 병렬 태스크 실행
        tasks = []
        if self.poly_ws_connected:
            tasks.append(asyncio.create_task(self.poly_ws.listen()))
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
                logger.warning(f"[WS-FEED] 시장 발견 에러: {e}")

    async def _discover_markets(self, coins: list[str]):
        """REST API로 시장 발견 + WebSocket 구독"""
        for coin in coins:
            try:
                # REST로 시장 검색 (클라이언트가 있는 경우만)
                loop = asyncio.get_event_loop()
                poly_markets = None
                kalshi_markets = None

                if self.poly_client:
                    poly_markets = await loop.run_in_executor(
                        None, self.poly_client.get_crypto_markets, coin
                    )
                if self.kalshi_client:
                    kalshi_markets = await loop.run_in_executor(
                        None, self.kalshi_client.get_crypto_markets, coin
                    )

                # 활성 거래소 중 하나라도 시장이 있으면 진행
                if not poly_markets and not kalshi_markets:
                    logger.debug(f"[WS-FEED] {coin} 시장 없음")
                    continue

                poly = poly_markets[0] if poly_markets else {}
                kalshi = kalshi_markets[0] if kalshi_markets else {}

                new_market = MarketInfo(
                    coin=coin,
                    poly_slug=poly.get("slug", ""),
                    poly_condition_id=poly.get("condition_id", ""),
                    poly_up_token=poly.get("up_token", ""),
                    poly_down_token=poly.get("down_token", ""),
                    poly_strike=poly.get("strike_price"),
                    poly_current_price=poly.get("current_price"),
                    kalshi_ticker=kalshi.get("ticker", ""),
                    kalshi_strike=kalshi.get("strike_price"),
                    kalshi_close_time=kalshi.get("close_time", ""),
                    last_discovery=time.time(),
                )

                # REST 가격으로 캐시 초기화 (WS가 없거나 stale할 때만!)
                # WS가 정상 수신 중이면 REST 가격(stale)으로 덮어쓰지 않음
                with self._lock:
                    old_market = self._markets.get(coin)

                    prices = self._prices.get(coin, PriceSnapshot())
                    now = time.time()

                    # Poly: UP/DOWN 개별 staleness 체크 (Poly 클라이언트가 있을 때만)
                    if poly:
                        poly_up_fresh = (prices.poly_up_updated > 0 and
                                         (now - prices.poly_up_updated) < self.STALE_THRESHOLD)
                        poly_down_fresh = (prices.poly_down_updated > 0 and
                                           (now - prices.poly_down_updated) < self.STALE_THRESHOLD)
                        if not (poly_up_fresh and poly_down_fresh):
                            prices.poly_up_price = poly.get("up_price", 0)
                            prices.poly_down_price = poly.get("down_price", 0)
                            prices.poly_up_ask_size = poly.get("up_ask_size", 0)
                            prices.poly_down_ask_size = poly.get("down_ask_size", 0)
                            prices.poly_up_updated = now
                            prices.poly_down_updated = now
                            logger.debug(f"[WS-FEED] {coin} Poly REST seed (WS stale: up={poly_up_fresh} down={poly_down_fresh})")

                    # Kalshi: WS 데이터가 stale하면 REST로 시드 (Kalshi 클라이언트가 있을 때만)
                    if kalshi:
                        kalshi_ws_fresh = (prices.kalshi_updated > 0 and
                                           (now - prices.kalshi_updated) < self.STALE_THRESHOLD)
                        if not kalshi_ws_fresh:
                            prices.kalshi_yes_ask = kalshi.get("yes_ask", 0)
                            prices.kalshi_no_ask = kalshi.get("no_ask", 0)
                            prices.kalshi_updated = now
                            logger.debug(f"[WS-FEED] {coin} Kalshi REST seed (WS stale)")

                    self._prices[coin] = prices
                    self._markets[coin] = new_market

                # WebSocket 구독 갱신
                await self._update_subscriptions(coin, old_market, new_market)

                logger.debug(
                    f"[WS-FEED] {coin} 시장 갱신: "
                    f"Poly={new_market.poly_slug} Kalshi={new_market.kalshi_ticker}"
                )

            except Exception as e:
                logger.warning(f"[WS-FEED] {coin} 발견 에러: {e}")

    async def _update_subscriptions(self, coin: str, old: Optional[MarketInfo], new: MarketInfo):
        """WebSocket 구독 갱신 (이전 마켓 구독 해제 + 새 마켓 구독)"""
        # 이전 Poly 토큰 구독 해제
        if old and self.poly_ws_connected:
            if old.poly_up_token and old.poly_up_token != new.poly_up_token:
                await self.poly_ws.unsubscribe(old.poly_up_token)
                self._poly_subs.discard(old.poly_up_token)
            if old.poly_down_token and old.poly_down_token != new.poly_down_token:
                await self.poly_ws.unsubscribe(old.poly_down_token)
                self._poly_subs.discard(old.poly_down_token)

        # 이전 Kalshi 티커 구독 해제
        if old and self.kalshi_ws_connected:
            if old.kalshi_ticker and old.kalshi_ticker != new.kalshi_ticker:
                await self.kalshi_ws.unsubscribe(old.kalshi_ticker)
                self._kalshi_subs.discard(old.kalshi_ticker)

        # 새 Poly 토큰 구독
        if self.poly_ws_connected:
            if new.poly_up_token and new.poly_up_token not in self._poly_subs:
                await self.poly_ws.subscribe(new.poly_up_token)
                self._poly_subs.add(new.poly_up_token)
            if new.poly_down_token and new.poly_down_token not in self._poly_subs:
                await self.poly_ws.subscribe(new.poly_down_token)
                self._poly_subs.add(new.poly_down_token)

        # 새 Kalshi 티커 구독
        if self.kalshi_ws_connected:
            if new.kalshi_ticker and new.kalshi_ticker not in self._kalshi_subs:
                await self.kalshi_ws.subscribe(new.kalshi_ticker)
                self._kalshi_subs.add(new.kalshi_ticker)

    # === WebSocket 콜백 ===

    async def _on_poly_price(self, token_id: str, best_prices: dict):
        """Polymarket 가격 업데이트 콜백 — UP/DOWN 개별 타임스탬프!"""
        with self._lock:
            for coin, market in self._markets.items():
                if token_id == market.poly_up_token:
                    prices = self._prices.setdefault(coin, PriceSnapshot())
                    ask = best_prices.get("ask", 0)
                    prices.poly_up_price = ask * 100 if ask > 0 else 0
                    prices.poly_up_ask_size = best_prices.get("ask_size", 0)
                    prices.poly_up_updated = time.time()
                    logger.debug(
                        f"[WS-FEED] {coin} Poly UP={prices.poly_up_price:.1f}¢ "
                        f"(qty={prices.poly_up_ask_size})"
                    )
                    break
                elif token_id == market.poly_down_token:
                    prices = self._prices.setdefault(coin, PriceSnapshot())
                    ask = best_prices.get("ask", 0)
                    prices.poly_down_price = ask * 100 if ask > 0 else 0
                    prices.poly_down_ask_size = best_prices.get("ask_size", 0)
                    prices.poly_down_updated = time.time()
                    logger.debug(
                        f"[WS-FEED] {coin} Poly DOWN={prices.poly_down_price:.1f}¢ "
                        f"(qty={prices.poly_down_ask_size})"
                    )
                    break

    async def _on_kalshi_price(self, ticker: str, price_data: dict):
        """Kalshi 가격 업데이트 콜백"""
        with self._lock:
            for coin, market in self._markets.items():
                if ticker == market.kalshi_ticker:
                    prices = self._prices.setdefault(coin, PriceSnapshot())
                    prices.kalshi_yes_ask = price_data.get("yes_ask", 0)
                    prices.kalshi_no_ask = price_data.get("no_ask", 0)
                    prices.kalshi_updated = time.time()
                    logger.debug(
                        f"[WS-FEED] {coin} Kalshi YES={prices.kalshi_yes_ask:.1f}¢ "
                        f"NO={prices.kalshi_no_ask:.1f}¢"
                    )
                    break
