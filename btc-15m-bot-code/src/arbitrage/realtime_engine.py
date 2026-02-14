"""
[DEPRECATED] 이전 WebSocket 전용 엔진.
현재는 engine.py + websocket_feed.py 하이브리드 방식 사용.
안전장치가 없으므로 사용 금지.
"""

import asyncio
import os
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from src.polymarket.websocket_client import PolymarketWebSocket
from src.polymarket.client import PolymarketClient
from src.kalshi.websocket_client import KalshiWebSocket
from src.kalshi.client import KalshiClient


# 매매 조건 (센트 기준)
BUY_THRESHOLD = 95   # 합계 95 이하면 매수
SELL_THRESHOLD = 105  # 합계 105 이상이면 매도


@dataclass
class MarketPair:
    """시장 쌍 정보"""
    coin: str
    poly_token_id: str
    kalshi_ticker: str


@dataclass
class ArbitrageOpportunity:
    """재정거래 기회"""
    coin: str
    action: str
    total_cost: float
    poly_price: float
    kalshi_price: float
    trade_size: int
    poly_token_id: str
    kalshi_ticker: str
    side: str


class RealtimeArbitrageEngine:
    """실시간 재정거래 엔진"""

    def __init__(self):
        # WebSocket 클라이언트
        self.poly_ws = PolymarketWebSocket()
        self.kalshi_ws = KalshiWebSocket()

        # REST API 클라이언트 (주문용)
        self.poly_client = PolymarketClient()
        self.kalshi_client = KalshiClient()

        # 설정
        self.bot_mode = os.getenv("BOT_MODE", "test")

        # 모니터링 중인 시장 쌍
        self.market_pairs: list[MarketPair] = []

        # 잔액
        self.poly_balance = 0.0
        self.kalshi_balance = 0.0

        # 통계
        self.opportunity_count = 0
        self.trade_count = 0

    async def connect(self) -> bool:
        """모든 연결 초기화"""
        # REST API 연결 (주문용)
        poly_rest_ok = self.poly_client.connect()
        kalshi_rest_ok = self.kalshi_client.connect()

        # WebSocket 연결
        poly_ws_ok = await self.poly_ws.connect()
        kalshi_ws_ok = await self.kalshi_ws.connect()

        if poly_ws_ok and kalshi_ws_ok:
            logger.info("모든 WebSocket 연결 완료")

            # 가격 업데이트 콜백 설정
            self.poly_ws.on_price_update = self._on_poly_price_update
            self.kalshi_ws.on_price_update = self._on_kalshi_price_update

            # 잔액 조회
            self.kalshi_balance = self.kalshi_client.get_balance()
            logger.info(f"Kalshi 잔액: ${self.kalshi_balance:.2f}")

            return True

        logger.error("WebSocket 연결 실패")
        return False

    async def disconnect(self):
        """모든 연결 종료"""
        await self.poly_ws.disconnect()
        await self.kalshi_ws.disconnect()
        logger.info("모든 연결 종료")

    async def subscribe_markets(self, coins: list[str]):
        """
        시장 구독

        Args:
            coins: 모니터링할 코인 목록 (BTC, ETH, XRP)
        """
        logger.info(f"시장 구독 중: {coins}")

        for coin in coins:
            # Polymarket 시장 찾기
            poly_markets = self.poly_client.get_crypto_markets(coin)
            # Kalshi 시장 찾기
            kalshi_markets = self.kalshi_client.get_crypto_markets(coin)

            if poly_markets and kalshi_markets:
                poly_market = poly_markets[0]
                kalshi_market = kalshi_markets[0]

                pair = MarketPair(
                    coin=coin,
                    poly_token_id=poly_market.get("token_id", ""),
                    kalshi_ticker=kalshi_market.get("ticker", "")
                )
                self.market_pairs.append(pair)

                # WebSocket 구독
                await self.poly_ws.subscribe(pair.poly_token_id)
                await self.kalshi_ws.subscribe(pair.kalshi_ticker)

                logger.info(f"{coin} 시장 구독 완료")
            else:
                logger.warning(f"{coin} 시장을 찾을 수 없음")

    async def _on_poly_price_update(self, token_id: str, data: dict):
        """Polymarket 가격 업데이트 콜백"""
        await self._check_arbitrage(token_id=token_id)

    async def _on_kalshi_price_update(self, ticker: str, data: dict):
        """Kalshi 가격 업데이트 콜백"""
        await self._check_arbitrage(ticker=ticker)

    async def _check_arbitrage(self, token_id: str = None, ticker: str = None):
        """
        재정거래 기회 확인 및 실행

        가격이 업데이트될 때마다 호출됨
        """
        for pair in self.market_pairs:
            # 해당 시장인지 확인
            if token_id and pair.poly_token_id != token_id:
                continue
            if ticker and pair.kalshi_ticker != ticker:
                continue

            # 양쪽 가격 조회
            poly_prices = self.poly_ws.get_best_prices(pair.poly_token_id)
            kalshi_prices = self.kalshi_ws.get_price(pair.kalshi_ticker)

            # 가격 변환 (0-1 → 센트)
            poly_up_ask = poly_prices["ask"] * 100
            poly_up_size = poly_prices["ask_size"]
            poly_down_ask = (1 - poly_prices["ask"]) * 100
            poly_down_size = poly_up_size

            kalshi_yes_ask = kalshi_prices.get("yes_ask", 0)
            kalshi_yes_size = kalshi_prices.get("yes_ask_size", 0)
            kalshi_no_ask = kalshi_prices.get("no_ask", 0)
            kalshi_no_size = kalshi_prices.get("no_ask_size", 0)

            # 조합 1: POLY UP + KALSHI NO
            combo1_total = poly_up_ask + kalshi_no_ask
            combo1_size = min(poly_up_size, kalshi_no_size) if poly_up_size and kalshi_no_size else 0

            if combo1_total <= BUY_THRESHOLD and combo1_size > 0:
                opp = ArbitrageOpportunity(
                    coin=pair.coin,
                    action="BUY_POLY_UP_KALSHI_NO",
                    total_cost=combo1_total,
                    poly_price=poly_up_ask,
                    kalshi_price=kalshi_no_ask,
                    trade_size=combo1_size,
                    poly_token_id=pair.poly_token_id,
                    kalshi_ticker=pair.kalshi_ticker,
                    side="buy"
                )
                await self._execute_opportunity(opp)

            elif combo1_total >= SELL_THRESHOLD and combo1_size > 0:
                opp = ArbitrageOpportunity(
                    coin=pair.coin,
                    action="SELL_POLY_UP_KALSHI_NO",
                    total_cost=combo1_total,
                    poly_price=poly_up_ask,
                    kalshi_price=kalshi_no_ask,
                    trade_size=combo1_size,
                    poly_token_id=pair.poly_token_id,
                    kalshi_ticker=pair.kalshi_ticker,
                    side="sell"
                )
                await self._execute_opportunity(opp)

            # 조합 2: KALSHI YES + POLY DOWN
            combo2_total = kalshi_yes_ask + poly_down_ask
            combo2_size = min(kalshi_yes_size, poly_down_size) if kalshi_yes_size and poly_down_size else 0

            if combo2_total <= BUY_THRESHOLD and combo2_size > 0:
                opp = ArbitrageOpportunity(
                    coin=pair.coin,
                    action="BUY_KALSHI_YES_POLY_DOWN",
                    total_cost=combo2_total,
                    poly_price=poly_down_ask,
                    kalshi_price=kalshi_yes_ask,
                    trade_size=combo2_size,
                    poly_token_id=pair.poly_token_id,
                    kalshi_ticker=pair.kalshi_ticker,
                    side="buy"
                )
                await self._execute_opportunity(opp)

            elif combo2_total >= SELL_THRESHOLD and combo2_size > 0:
                opp = ArbitrageOpportunity(
                    coin=pair.coin,
                    action="SELL_KALSHI_YES_POLY_DOWN",
                    total_cost=combo2_total,
                    poly_price=poly_down_ask,
                    kalshi_price=kalshi_yes_ask,
                    trade_size=combo2_size,
                    poly_token_id=pair.poly_token_id,
                    kalshi_ticker=pair.kalshi_ticker,
                    side="sell"
                )
                await self._execute_opportunity(opp)

    async def _execute_opportunity(self, opp: ArbitrageOpportunity):
        """재정거래 기회 실행"""
        self.opportunity_count += 1

        logger.success(
            f"[기회 #{self.opportunity_count}] {opp.coin} | "
            f"합계:{opp.total_cost:.1f} | "
            f"수량:{opp.trade_size}주 | "
            f"{opp.action}"
        )

        # 증거금 확인
        required = (opp.total_cost / 100) * opp.trade_size
        if required > self.kalshi_balance + self.poly_balance:
            logger.warning(f"증거금 부족! 필요: ${required:.2f}")
            return

        if self.bot_mode == "test":
            logger.info(f"  [테스트] 거래 시뮬레이션")
            return

        # 실제 거래 실행
        try:
            if "POLY_UP" in opp.action or "POLY_DOWN" in opp.action:
                self.poly_client.place_market_order(
                    token_id=opp.poly_token_id,
                    side="BUY" if opp.side == "buy" else "SELL",
                    size=opp.trade_size,
                    price=opp.poly_price
                )

            if "KALSHI_YES" in opp.action:
                self.kalshi_client.place_market_order(
                    ticker=opp.kalshi_ticker,
                    side=opp.side,
                    yes_or_no="yes",
                    count=opp.trade_size,
                    price=int(opp.kalshi_price)
                )

            if "KALSHI_NO" in opp.action:
                self.kalshi_client.place_market_order(
                    ticker=opp.kalshi_ticker,
                    side=opp.side,
                    yes_or_no="no",
                    count=opp.trade_size,
                    price=int(opp.kalshi_price)
                )

            self.trade_count += 1
            logger.success(f"  거래 완료! (총 {self.trade_count}건)")

            # 잔액 업데이트
            self.kalshi_balance = self.kalshi_client.get_balance()

        except Exception as e:
            logger.error(f"거래 실행 실패: {e}")

    async def run(self, coins: list[str] = None):
        """
        봇 실행

        Args:
            coins: 모니터링할 코인 목록
        """
        if coins is None:
            coins = ["BTC", "ETH", "XRP"]

        # 시장 구독
        await self.subscribe_markets(coins)

        logger.info("=" * 50)
        logger.info("실시간 재정거래 봇 시작")
        logger.info(f"모드: {self.bot_mode.upper()}")
        logger.info(f"매수 조건: 합계 <= {BUY_THRESHOLD}")
        logger.info(f"매도 조건: 합계 >= {SELL_THRESHOLD}")
        logger.info("=" * 50)

        # WebSocket 리스너 실행
        await asyncio.gather(
            self.poly_ws.listen(),
            self.kalshi_ws.listen()
        )
