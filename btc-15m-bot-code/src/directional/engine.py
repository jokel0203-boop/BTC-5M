"""
방향성 매매 엔진 - 15분 마켓

전략:
- BTC 15분 마켓에서 80~85¢ 범위인 토큰 매수
- 60¢ 이하로 하락 시 손절 매도
- 100¢ 정산 기대 (20¢/주 수익)
- 두 거래소(Polymarket + Kalshi) 독립 매매 → 비교 테스트

안전장치:
1. 거래 에러 → 즉시 중단
2. 15분 윈도우당 1회 매매 (거래소별)
3. 손절 자동 실행 (60¢ 이하)
"""
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from loguru import logger

from src.polymarket.client import PolymarketClient
from src.kalshi.client import KalshiClient

BUY_TRIGGER_PRICE = int(os.getenv("BUY_TRIGGER_PRICE", "80"))  # ASK가 이 가격이면 매수 (¢)
LIMIT_BUY_OFFSET = int(os.getenv("LIMIT_BUY_OFFSET", "1"))  # ASK 대비 -1¢ (지정가 매수 = maker)
STOP_LOSS_PRICE = int(os.getenv("STOP_LOSS_PRICE", "60"))  # 손절 가격 (¢) - 이 이하면 매도
MAX_TRADE_SIZE = 3  # Kalshi 매수 수량
POLY_MIN_TRADE_SIZE = 5  # Polymarket 최소 주문 수량
MAX_TRADES_PER_WINDOW = int(os.getenv("MAX_TRADES_PER_WINDOW", "1"))  # 15분 윈도우당 최대 거래 횟수
TRADE_WINDOW_SECONDS = 15 * 60
MIN_TRADE_INTERVAL = 3  # 최소 거래 간격 (초)
STOPLOSS_COOLDOWN = 120  # 손절 후 매수 금지 시간 (2분)
POLY_MIN_ORDER_CENTS = 100  # Polymarket 최소 주문금액 $1

# 활성 거래소 설정 ("kalshi", "poly")
ENABLED_EXCHANGES = os.getenv("ENABLED_EXCHANGES", "kalshi").strip().lower().split(",")


@dataclass
class TradeOpportunity:
    """매수 기회 (단일 거래소)"""
    coin: str
    exchange: str  # "poly" or "kalshi"
    side: str  # "up"/"down" (poly) or "yes"/"no" (kalshi)
    price: float  # 센트 (ask price)
    trade_size: int
    token_id: str  # poly token_id or kalshi ticker
    close_time: str  # ISO format UTC


@dataclass
class OpenPosition:
    """보유 포지션 (단일 거래소)"""
    coin: str
    exchange: str  # "poly" or "kalshi"
    side: str  # "up"/"down" or "yes"/"no"
    token_id: str  # poly token_id or kalshi ticker
    count: int
    entry_price: float  # 센트
    close_time: datetime  # UTC
    entry_time: float = field(default_factory=time.time)


class DirectionalEngine:
    def __init__(self, poly_client=None, kalshi_client=None):
        self.polymarket = poly_client or PolymarketClient()
        self.kalshi = kalshi_client or KalshiClient()
        self.bot_mode = os.getenv("BOT_MODE", "test").strip().lower()
        self._connected = False
        self._trade_history = {}  # {exchange:coin: [timestamp, ...]}

        # WebSocket 가격 피드 (선택)
        self._ws_feed = None

        # 안전장치 상태
        self._starting_kalshi_balance = None
        self._trading_halted = False
        self._halt_reason = ""
        self._open_positions: list[OpenPosition] = []
        self._latest_market_data: dict = {}  # {coin: {poly: dict, kalshi: dict}}
        self._sell_retry_after: dict = {}  # {token_id: timestamp}
        self._pending_poly_orders: dict = {}  # {token_id: order_id} GTC 미체결 주문 추적
        self._stoploss_cooldown: dict = {}  # {exchange:coin: timestamp} 손절 후 쿨다운

    def set_ws_feed(self, feed):
        """WebSocket 가격 피드 설정"""
        self._ws_feed = feed
        logger.warning("[ENGINE] WebSocket 가격 피드 연결됨")

    @property
    def is_halted(self) -> bool:
        return self._trading_halted

    @property
    def halt_reason(self) -> str:
        return self._halt_reason

    @property
    def open_positions(self) -> list:
        return self._open_positions

    def connect(self) -> bool:
        poly_ok = True
        kalshi_ok = True

        if "poly" in ENABLED_EXCHANGES:
            poly_ok = self.polymarket.connect()
        if "kalshi" in ENABLED_EXCHANGES:
            kalshi_ok = self.kalshi.connect()

        self._connected = poly_ok and kalshi_ok

        if self._connected:
            self._init_balance_tracking()

        return self._connected

    def _init_balance_tracking(self):
        """시작 잔고 기록 (로그용)"""
        try:
            bal = self.kalshi.get_balance()
            self._starting_kalshi_balance = bal
            logger.warning(f"[BALANCE] 시작 Kalshi 잔고: ${bal:.2f}")
        except Exception as e:
            logger.error(f"[BALANCE] 잔고 조회 실패: {e}")

    def _halt_trading(self, reason: str):
        """거래 즉시 중단"""
        self._trading_halted = True
        self._halt_reason = reason
        logger.error(f"[HALT] 거래 중단: {reason}")

    def _parse_close_time(self, close_time_val):
        """close_time을 datetime으로 변환 (str, datetime 모두 지원)"""
        if not close_time_val:
            return None
        try:
            if isinstance(close_time_val, datetime):
                if close_time_val.tzinfo is None:
                    return close_time_val.replace(tzinfo=timezone.utc)
                return close_time_val
            ct = str(close_time_val).replace("Z", "+00:00")
            return datetime.fromisoformat(ct)
        except Exception:
            return None

    def _get_buy_threshold(self, key: str, ticker: str = "") -> int:
        """거래소:마켓별 매수 가능 여부 반환

        15분 마켓은 매 15분 리셋 → 마켓 티커 기반으로 거래 횟수 관리.
        같은 마켓(같은 ticker)에서만 MAX_TRADES_PER_WINDOW 적용.

        Returns:
            0: 매수 불가 (최대 횟수 도달 or 최소 간격 미달)
            BUY_TRIGGER_PRICE: 매수 가능
        """
        now = time.time()

        # 손절 후 쿨다운 체크 (2분)
        cooldown_until = self._stoploss_cooldown.get(key, 0)
        if now < cooldown_until:
            remaining = cooldown_until - now
            logger.debug(f"[{key}] 손절 쿨다운 중 ({remaining:.0f}초 남음)")
            return 0

        # 최소 거래 간격 (거래소:코인 단위 — 연속 중복 주문 방지)
        trades_all = self._trade_history.get(key, [])
        trades_all = [t for t in trades_all if now - t < TRADE_WINDOW_SECONDS]
        self._trade_history[key] = trades_all

        if trades_all and (now - trades_all[-1]) < MIN_TRADE_INTERVAL:
            logger.debug(f"[{key}] 최소 거래 간격 미달 ({now - trades_all[-1]:.1f}s < {MIN_TRADE_INTERVAL}s)")
            return 0

        # 15분 윈도우당 총 거래 횟수 제한 (Yes/No 합산)
        if len(trades_all) >= MAX_TRADES_PER_WINDOW:
            logger.debug(f"[{key}] 총 {len(trades_all)}회 거래 완료 → 추가 차단")
            return 0

        return BUY_TRIGGER_PRICE

    def find_opportunities(self, coin: str) -> list:
        """80~85¢ 범위인 토큰을 찾아서 매수 기회 반환

        양 거래소 독립 체크:
        - Polymarket: UP/DOWN 80~85¢ → 매수
        - Kalshi: YES/NO 80~85¢ → 매수
        - 85¢ 초과 → 스킵 (리스크 대비 수익 불량)
        """
        opportunities = []

        if self._trading_halted:
            return opportunities

        self.polymarket.keep_session_warm()

        try:
            # === 시장 데이터 조회 ===
            poly_markets = kalshi_markets = None

            if self._ws_feed:
                poly_data, kalshi_data = self._ws_feed.get_market_data(coin)
                if poly_data:
                    poly_markets = [poly_data]
                if kalshi_data:
                    kalshi_markets = [kalshi_data]
                if poly_data or kalshi_data:
                    logger.debug(f"[{coin}] WS 캐시 (poly={'O' if poly_data else 'X'} kalshi={'O' if kalshi_data else 'X'})")

            if poly_markets is None and "poly" in ENABLED_EXCHANGES:
                poly_markets = self.polymarket.get_crypto_markets(coin)
            if kalshi_markets is None and "kalshi" in ENABLED_EXCHANGES:
                kalshi_markets = self.kalshi.get_crypto_markets(coin)

            poly = poly_markets[0] if poly_markets else None
            kalshi = kalshi_markets[0] if kalshi_markets else None

            if not poly and not kalshi:
                return opportunities

            # 시장 데이터 캐시 (손절 체크용)
            self._latest_market_data[coin] = {"poly": poly, "kalshi": kalshi}

            # close_time (Kalshi에서 가져옴, 없으면 Poly slug에서 추출)
            close_time_str = ""
            if kalshi:
                close_time_str = kalshi.get("close_time", "")
            if not close_time_str and poly:
                # slug: btc-updown-15m-1707900000 → close = timestamp + 900초
                slug = poly.get("slug", "")
                parts = slug.rsplit("-", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    ts = int(parts[1])
                    close_time_str = datetime.fromtimestamp(ts + 900, tz=timezone.utc).isoformat()

            # 이미 보유중인 거래소 체크 (만료된 마켓 포지션은 제외!)
            now_utc = datetime.now(timezone.utc)
            has_poly_pos = any(
                p.exchange == "poly" and p.coin == coin and p.close_time > now_utc
                for p in self._open_positions
            )
            has_kalshi_pos = any(
                p.exchange == "kalshi" and p.coin == coin and p.close_time > now_utc
                for p in self._open_positions
            )

            # === Polymarket 체크 ===
            if poly and not has_poly_pos and "poly" in ENABLED_EXCHANGES:
                poly_up = poly.get("up_price", 0)
                poly_down = poly.get("down_price", 0)
                poly_slug = poly.get("slug", "")

                threshold_key = f"poly:{coin}"
                if self._get_buy_threshold(threshold_key, ticker=poly_slug) > 0:
                    trade_size = max(MAX_TRADE_SIZE, POLY_MIN_TRADE_SIZE)  # Poly 최소 5주
                    if poly_up == BUY_TRIGGER_PRICE:
                        order_value = poly_up * trade_size
                        if order_value >= POLY_MIN_ORDER_CENTS:
                            logger.warning(
                                f"[{coin}] POLY UP = {poly_up:.1f}¢ == {BUY_TRIGGER_PRICE}¢ → 매수!"
                            )
                            opportunities.append(TradeOpportunity(
                                coin=coin, exchange="poly", side="up",
                                price=poly_up, trade_size=trade_size,
                                token_id=poly.get("up_token", ""),
                                close_time=close_time_str,
                            ))
                    elif poly_down == BUY_TRIGGER_PRICE:
                        order_value = poly_down * trade_size
                        if order_value >= POLY_MIN_ORDER_CENTS:
                            logger.warning(
                                f"[{coin}] POLY DOWN = {poly_down:.1f}¢ == {BUY_TRIGGER_PRICE}¢ → 매수!"
                            )
                            opportunities.append(TradeOpportunity(
                                coin=coin, exchange="poly", side="down",
                                price=poly_down, trade_size=trade_size,
                                token_id=poly.get("down_token", ""),
                                close_time=close_time_str,
                            ))

                logger.debug(f"[{coin}] POLY: UP={poly_up:.1f}¢ DOWN={poly_down:.1f}¢")

            # === Kalshi 체크 ===
            if kalshi and not has_kalshi_pos and "kalshi" in ENABLED_EXCHANGES:
                kalshi_yes = kalshi.get("yes_ask", 0)
                kalshi_no = kalshi.get("no_ask", 0)
                kalshi_ticker = kalshi.get("ticker", "")

                threshold_key = f"kalshi:{coin}"
                if self._get_buy_threshold(threshold_key, ticker=kalshi_ticker) > 0:
                    if kalshi_yes == BUY_TRIGGER_PRICE:
                        logger.warning(
                            f"[{coin}] KALSHI YES = {kalshi_yes}¢ == {BUY_TRIGGER_PRICE}¢ → 매수!"
                        )
                        opportunities.append(TradeOpportunity(
                            coin=coin, exchange="kalshi", side="yes",
                            price=kalshi_yes, trade_size=MAX_TRADE_SIZE,
                            token_id=kalshi_ticker,
                            close_time=close_time_str,
                        ))
                    elif kalshi_no == BUY_TRIGGER_PRICE:
                        logger.warning(
                            f"[{coin}] KALSHI NO = {kalshi_no}¢ == {BUY_TRIGGER_PRICE}¢ → 매수!"
                        )
                        opportunities.append(TradeOpportunity(
                            coin=coin, exchange="kalshi", side="no",
                            price=kalshi_no, trade_size=MAX_TRADE_SIZE,
                            token_id=kalshi_ticker,
                            close_time=close_time_str,
                        ))

                logger.debug(f"[{coin}] KALSHI: YES={kalshi_yes}¢ NO={kalshi_no}¢")

        except Exception as e:
            logger.error(f"Error [{coin}]: {e}")

        return opportunities

    def execute_trade(self, opp: TradeOpportunity) -> dict:
        """단일 거래소 매수 실행"""
        if self._trading_halted:
            logger.error(f"[HALT] 거래 중단 상태 - 실행 거부: {self._halt_reason}")
            return {"success": False, "error": f"Trading halted: {self._halt_reason}"}

        if self.bot_mode == "test":
            logger.info(
                f"[TEST] {opp.exchange.upper()} {opp.side.upper()} | "
                f"{opp.coin} | {opp.price:.1f}¢ | Qty: {opp.trade_size}"
            )
            # 테스트 모드에서도 포지션 기록 (손절 시뮬레이션용)
            close_dt = self._parse_close_time(opp.close_time)
            if not close_dt:
                close_dt = datetime.now(timezone.utc) + timedelta(minutes=15)
            self._open_positions.append(OpenPosition(
                coin=opp.coin, exchange=opp.exchange, side=opp.side,
                token_id=opp.token_id, count=opp.trade_size,
                entry_price=opp.price, close_time=close_dt,
            ))
            self._trade_history.setdefault(f"{opp.exchange}:{opp.coin}", []).append(time.time())
            return {"success": True, "simulated": True}

        try:
            t_start = time.monotonic()

            limit_price = BUY_TRIGGER_PRICE - LIMIT_BUY_OFFSET  # 79¢ maker

            if opp.exchange == "poly":
                result = self.polymarket.place_market_order(
                    token_id=opp.token_id, side="BUY",
                    size=opp.trade_size, price=limit_price
                )
            else:  # kalshi
                result = self.kalshi.place_market_order(
                    ticker=opp.token_id, side="buy",
                    yes_or_no=opp.side, count=opp.trade_size,
                    price=limit_price
                )

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.warning(f"[{opp.exchange.upper()}] 실행 완료 ({elapsed_ms:.0f}ms): {result}")

            ok = not (isinstance(result, dict) and result.get("error"))

            if ok:
                # Polymarket GTC 주문: 즉시 포지션 등록 (체결 여부 무관)
                # 손절 시 실제 잔고 확인 후 전량 매도
                if opp.exchange == "poly" and isinstance(result, dict):
                    poly_order_id = result.get("orderID")
                    poly_status = str(result.get("status", "")).upper()
                    if poly_order_id:
                        self._pending_poly_orders[opp.token_id] = poly_order_id
                        logger.warning(
                            f"[POLY] GTC 주문 ({poly_status}): {opp.trade_size}주 @ {limit_price}¢ → 즉시 포지션 등록"
                        )

                logger.success(
                    f"[{opp.exchange.upper()}] {opp.side.upper()} 매수 성공! "
                    f"{opp.coin} {opp.price:.1f}¢ x{opp.trade_size} ({elapsed_ms:.0f}ms)"
                )

                # Poly: 매도를 위한 allowance 즉시 승인
                if opp.exchange == "poly":
                    self.polymarket.approve_token_for_sell(opp.token_id)

                # 포지션 기록 (양 거래소 모두 maker 지정가에 매수)
                entry = BUY_TRIGGER_PRICE - LIMIT_BUY_OFFSET  # 79¢
                close_dt = self._parse_close_time(opp.close_time)
                if not close_dt:
                    close_dt = datetime.now(timezone.utc) + timedelta(minutes=15)
                self._open_positions.append(OpenPosition(
                    coin=opp.coin, exchange=opp.exchange, side=opp.side,
                    token_id=opp.token_id, count=opp.trade_size,
                    entry_price=entry, close_time=close_dt,
                ))
                logger.warning(
                    f"[POSITION] {opp.exchange} {opp.side} {opp.coin} 포지션 기록 | "
                    f"진입={entry}¢ | 종료: {close_dt.strftime('%H:%M:%S')} UTC | "
                    f"보유: {len(self._open_positions)}개"
                )

                now_ts = time.time()
                self._trade_history.setdefault(f"{opp.exchange}:{opp.coin}", []).append(now_ts)
                # 마켓 티커별 거래 기록 (새 15분 장은 별도 카운트)
                self._trade_history.setdefault(f"{opp.exchange}:{opp.coin}:{opp.token_id}", []).append(now_ts)
                return {"success": True, "result": result}
            else:
                error_str = str(result)
                logger.error(f"[{opp.exchange.upper()}] 매수 실패: {result}")
                # 잔고/allowance 부족은 해당 거래소만 스킵 (봇 중단 안 함)
                if "balance" in error_str.lower() or "allowance" in error_str.lower():
                    logger.warning(f"[{opp.exchange.upper()}] 잔고 부족 → 이 거래소 스킵 (봇 계속)")
                    return {"success": False, "result": result}
                self._halt_trading(f"{opp.exchange} 매수 실패: {result}")
                return {"success": False, "result": result, "halted": True}

        except Exception as e:
            error_str = str(e)
            logger.error(f"Trade error: {e}")
            if "balance" in error_str.lower() or "allowance" in error_str.lower():
                logger.warning(f"[{opp.exchange.upper()}] 잔고 부족 → 이 거래소 스킵 (봇 계속)")
                return {"success": False, "error": error_str}
            self._halt_trading(f"거래 예외: {e}")
            return {"success": False, "error": str(e), "halted": True}

    def check_stop_loss(self) -> list:
        """보유 포지션 손절 체크: 현재가 ≤ 60¢이면 매도

        Returns:
            매도 실행한 포지션 리스트
        """
        if not self._open_positions:
            return []

        sold = []
        now = datetime.now(timezone.utc)

        for pos in list(self._open_positions):
            time_to_close = (pos.close_time - now).total_seconds()

            # 마감된 마켓: 매도 시도 불가 (409 market_closed 방지)
            if time_to_close <= 0:
                if time_to_close < -60:
                    logger.debug(f"[{pos.coin}] 만료 포지션 제거: {pos.exchange} {pos.side}")
                    # Poly GTC 미체결 주문 취소
                    pending_oid = self._pending_poly_orders.pop(pos.token_id, None)
                    if pending_oid:
                        self.polymarket.cancel_order(pending_oid)
                    self._open_positions.remove(pos)
                    # 만료 후 거래 기록 초기화 → 새 마켓 매수 가능
                    ticker_key = f"{pos.exchange}:{pos.coin}:{pos.token_id}"
                    self._trade_history.pop(ticker_key, None)
                else:
                    logger.debug(
                        f"[{pos.coin}] 마감됨 → 정산 대기 ({-time_to_close:.0f}초 전 마감) | "
                        f"{pos.exchange} {pos.side}"
                    )
                continue

            # 현재 가격 조회
            cached = self._latest_market_data.get(pos.coin)
            if not cached:
                continue

            current_price = self._get_position_price(pos, cached)
            if current_price <= 0:
                continue

            logger.debug(
                f"[STOP-LOSS] {pos.coin} {pos.exchange} {pos.side}: "
                f"현재={current_price:.1f}¢ 진입={pos.entry_price:.1f}¢ "
                f"손절={STOP_LOSS_PRICE}¢"
            )

            if current_price <= STOP_LOSS_PRICE:
                # 매도 실패 후 재시도 대기
                retry_after = self._sell_retry_after.get(pos.token_id, 0)
                if time.time() < retry_after:
                    continue

                logger.warning(
                    f"[STOP-LOSS] {pos.coin} {pos.exchange} {pos.side} 손절! "
                    f"현재={current_price:.1f}¢ ≤ {STOP_LOSS_PRICE}¢ | "
                    f"진입={pos.entry_price:.1f}¢ | 수량={pos.count}"
                )

                if self.bot_mode == "test":
                    logger.warning(
                        f"[TEST STOP-LOSS] {pos.exchange} {pos.side} {pos.coin} 손절 시뮬레이션"
                    )
                    sold.append({"position": pos, "price": current_price})
                    self._open_positions.remove(pos)
                    ticker_key = f"{pos.exchange}:{pos.coin}:{pos.token_id}"
                    self._trade_history.pop(ticker_key, None)
                    cooldown_key = f"{pos.exchange}:{pos.coin}"
                    self._stoploss_cooldown[cooldown_key] = time.time() + STOPLOSS_COOLDOWN
                    continue

                result = self._execute_sell(pos)
                if result.get("success"):
                    sold.append({"position": pos, "result": result, "price": current_price})
                    self._open_positions.remove(pos)
                    # 손절 후 거래 기록 초기화 → 재매수 가능
                    ticker_key = f"{pos.exchange}:{pos.coin}:{pos.token_id}"
                    self._trade_history.pop(ticker_key, None)
                    # 손절 후 2분 쿨다운
                    cooldown_key = f"{pos.exchange}:{pos.coin}"
                    self._stoploss_cooldown[cooldown_key] = time.time() + STOPLOSS_COOLDOWN
                    logger.warning(f"[STOP-LOSS] 손절 완료 → {STOPLOSS_COOLDOWN}초 쿨다운: {cooldown_key}")
                elif result.get("empty_position"):
                    self._open_positions.remove(pos)
                    ticker_key = f"{pos.exchange}:{pos.coin}:{pos.token_id}"
                    self._trade_history.pop(ticker_key, None)
                else:
                    self._sell_retry_after[pos.token_id] = time.time() + 5

        return sold

    def _get_position_price(self, pos: OpenPosition, cached: dict) -> float:
        """포지션의 현재 가격 조회 (ask 기준)"""
        if pos.exchange == "poly":
            poly = cached.get("poly")
            if not poly:
                return 0
            if pos.side == "up":
                return poly.get("up_price", 0)
            else:
                return poly.get("down_price", 0)
        else:  # kalshi
            kalshi = cached.get("kalshi")
            if not kalshi:
                return 0
            if pos.side == "yes":
                return kalshi.get("yes_ask", 0)
            else:
                return kalshi.get("no_ask", 0)

    def _execute_sell(self, pos: OpenPosition) -> dict:
        """손절 매도 실행"""
        if pos.exchange == "poly":
            return self._sell_poly(pos)
        else:
            return self._sell_kalshi(pos)

    def _sell_poly(self, pos: OpenPosition) -> dict:
        """Polymarket 손절 매도 - 실제 잔고 전량 매도"""
        try:
            # 미체결 GTC 주문 취소 (추가 체결 방지)
            pending_order_id = self._pending_poly_orders.pop(pos.token_id, None)
            if pending_order_id:
                logger.warning(f"[SELL] Poly 미체결 GTC 주문 취소: {pending_order_id[:16]}...")
                self.polymarket.cancel_order(pending_order_id)

            self.polymarket.refresh_conditional_allowance(pos.token_id)
            balance_info = self.polymarket.check_conditional_balance(pos.token_id)
            raw_balance = float(balance_info.get("balance", 0))
            actual_balance = int(raw_balance / 1_000_000)

            if actual_balance <= 0:
                logger.warning(f"[SELL] Poly 잔고 0 → 빈 포지션 제거")
                return {"empty_position": True}

            sell_count = actual_balance  # 전량 매도
            logger.warning(f"[SELL] Poly {pos.side} 전량 매도: {sell_count}주")

            result = self.polymarket.place_market_order(
                token_id=pos.token_id, side="SELL",
                size=sell_count, price=1
            )
            ok = not (isinstance(result, dict) and result.get("error"))
            if ok:
                logger.success(f"[SELL] Poly {pos.side} 매도 성공: {sell_count}주")
                return {"success": True, "result": result, "sold_count": sell_count}
            else:
                logger.error(f"[SELL] Poly 매도 실패: {result}")
                return {"error": result}
        except Exception as e:
            logger.error(f"[SELL] Poly 매도 예외: {e}")
            return {"error": str(e)}

    def _sell_kalshi(self, pos: OpenPosition) -> dict:
        """Kalshi 손절 매도"""
        try:
            result = self.kalshi.place_market_order(
                ticker=pos.token_id, side="sell",
                yes_or_no=pos.side, count=pos.count,
                price=1
            )
            ok = not (isinstance(result, dict) and result.get("error"))
            if ok:
                logger.success(f"[SELL] Kalshi {pos.side} 매도 성공: {pos.count}주")
                return {"success": True, "result": result, "sold_count": pos.count}
            else:
                logger.error(f"[SELL] Kalshi 매도 실패: {result}")
                return {"error": result}
        except Exception as e:
            logger.error(f"[SELL] Kalshi 매도 예외: {e}")
            return {"error": str(e)}