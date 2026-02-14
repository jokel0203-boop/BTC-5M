"""
Kalshi 단독 거래 엔진 - 15분 크립토 마켓

전략: Kalshi 내 YES + NO 합이 100¢ 미만이면 양쪽 매수 → 정산 시 100¢ 보장
(교차 거래소 아비트리지와 동일 원리, 단일 거래소 내)

핵심 안전장치:
1. 일일 손실 한도: Kalshi 잔고 기반 지출 추적 → 한도 초과 시 봇 중단
2. 거래 에러 즉시 중단: 한쪽이라도 실패하면 봇 즉시 중단
3. 종료 30초 전 긴급 매도: 오더북 유동성 부족 시 매도
4. 15분 쿨다운: 같은 코인은 15분에 1회만 거래
5. 병렬 실행: YES/NO 동시 주문
6. 이익 실현 매도: 양쪽 매도가치 ≥ SELL_THRESHOLD이면 매도

비교 조합:
- YES ask + NO ask < BUY_THRESHOLD → 양쪽 매수
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from loguru import logger

from src.kalshi.client import KalshiClient

BUY_THRESHOLD = 95  # 합계 ≤ 95¢ (5¢ 이상 이익 보장)
MAX_TRADES_PER_WINDOW = 1  # 15분 윈도우당 1회만 매매
SELL_THRESHOLD = 110  # 익절: 매도 가치 >= 110¢이면 매도
MIN_PRICE = 10  # 개별 가격 최소 10¢ (호가 얇아서 손해 방지)
DEFAULT_TRADE_SIZE = 10  # 기본 거래 수량
MAX_TRADE_SIZE = 10  # 최대 거래 수량
TRADE_WINDOW_SECONDS = 15 * 60  # 15분 윈도우 (거래 횟수 추적 기간)
MIN_TRADE_INTERVAL = 3  # 연속 거래 최소 간격 (초)
DANGER_ZONE_SELL_SECONDS = 30  # 종료 전 N초 이내 → 긴급 매도


@dataclass
class KalshiOpportunity:
    coin: str
    action: str  # "BUY_YES_NO"
    total_cost: float  # YES ask + NO ask (¢)
    yes_price: float  # YES ask (¢)
    no_price: float  # NO ask (¢)
    trade_size: int
    ticker: str
    strike_price: float = 0
    close_time: str = ""  # ISO format UTC


@dataclass
class KalshiPosition:
    """보유 포지션 추적 (긴급 매도 + 이익 실현용)"""
    coin: str
    action: str  # "BUY_YES_NO"
    ticker: str
    yes_count: int
    no_count: int
    strike_price: float
    close_time: datetime  # UTC
    entry_time: float = field(default_factory=time.time)


class KalshiEngine:
    def __init__(self, kalshi_client=None):
        self.kalshi = kalshi_client or KalshiClient()
        self.bot_mode = os.getenv("BOT_MODE", "test").strip().lower()
        self._connected = False
        self._trade_history = {}  # {coin: [timestamp, ...]}

        # === 병렬 실행용 영구 스레드풀 ===
        self._executor = ThreadPoolExecutor(max_workers=2)

        # === WebSocket 가격 피드 (선택) ===
        self._ws_feed = None

        # === 안전장치 상태 ===
        self._starting_balance = None  # 시작 잔고 ($)
        self._trading_halted = False
        self._halt_reason = ""
        self._open_positions: list[KalshiPosition] = []
        self._latest_market_data: dict = {}  # {coin: kalshi_dict}
        self._sell_retry_after: dict = {}  # {ticker: timestamp}

    def set_ws_feed(self, feed):
        """WebSocket 가격 피드 설정 (선택)"""
        self._ws_feed = feed
        logger.warning("[KALSHI-ENGINE] WebSocket 가격 피드 연결됨")

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
        kalshi_ok = self.kalshi.connect()
        self._connected = kalshi_ok

        if self._connected:
            self._init_balance_tracking()

        return self._connected

    def _init_balance_tracking(self):
        """시작 잔고 기록"""
        try:
            bal = self.kalshi.get_balance()
            self._starting_balance = bal
            logger.warning(f"[KALSHI-BALANCE] 시작 잔고: ${bal:.2f}")
        except Exception as e:
            logger.error(f"[KALSHI-BALANCE] 잔고 조회 실패: {e}")

    def _halt_trading(self, reason: str):
        """거래 즉시 중단"""
        self._trading_halted = True
        self._halt_reason = reason
        logger.error(f"[KALSHI-HALT] 거래 중단: {reason}")

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

    def _get_buy_threshold(self, coin: str) -> int:
        """15분 윈도우 내 거래 횟수에 따른 매수 기준값 반환

        Returns:
            0: 거래 불가 (최대 횟수 도달 또는 최소 간격 미달)
            BUY_THRESHOLD: 매수 가능
        """
        now = time.time()
        trades = self._trade_history.get(coin, [])
        trades = [t for t in trades if now - t < TRADE_WINDOW_SECONDS]
        self._trade_history[coin] = trades

        if trades and (now - trades[-1]) < MIN_TRADE_INTERVAL:
            logger.debug(f"[{coin}] 최소 거래 간격 미달 ({now - trades[-1]:.1f}s < {MIN_TRADE_INTERVAL}s)")
            return 0

        trade_count = len(trades)
        if trade_count >= MAX_TRADES_PER_WINDOW:
            logger.debug(f"[{coin}] 15분 윈도우 내 {trade_count}회 거래 완료 → 추가 거래 차단")
            return 0

        return BUY_THRESHOLD

    def check_emergency_sell(self) -> list:
        """종료 30초 전부터 끝날때까지 감시 → 유동성 부족 시 전량매도"""
        if not self._open_positions:
            return []

        now = datetime.now(timezone.utc)
        sold_positions = []

        for pos in list(self._open_positions):
            time_to_close = (pos.close_time - now).total_seconds()

            # 이미 만료된 포지션 제거
            if time_to_close < -60:
                logger.debug(f"[{pos.coin}] 만료된 포지션 제거: {pos.action}")
                self._open_positions.remove(pos)
                continue

            # 종료 30초 전부터 감시
            if 0 < time_to_close <= DANGER_ZONE_SELL_SECONDS:
                cached = self._latest_market_data.get(pos.coin)
                if not cached:
                    continue

                # 유동성 체크: 양쪽 모두 가격이 있는지 확인
                yes_ask = cached.get("yes_ask", 0)
                no_ask = cached.get("no_ask", 0)

                # 한쪽이라도 가격 없으면 (유동성 부족) → 긴급 매도
                if yes_ask == 0 or no_ask == 0:
                    logger.error(
                        f"[KALSHI-EMERGENCY] {pos.coin} 유동성 부족! "
                        f"YES={yes_ask}¢ NO={no_ask}¢ | "
                        f"종료까지 {time_to_close:.0f}초 → 전량매도"
                    )
                    result = self._emergency_sell(pos)
                    if result.get("success"):
                        sold_positions.append({"position": pos, "result": result})
                        self._open_positions.remove(pos)
                    elif result.get("error"):
                        logger.error(f"[KALSHI-EMERGENCY] 매도 실패: {result}")
                        self._sell_retry_after[pos.ticker] = time.time() + 5

        return sold_positions

    def check_profit_sell(self) -> list:
        """이익 실현 매도: 양쪽 매도 가치 ≥ SELL_THRESHOLD이면 매도

        매도 가치 = YES bid + NO bid (양쪽을 되팔았을 때 받는 금액)
        매수 시 YES ask + NO ask < 95에 샀으므로, 110에 팔면 +15¢ 이익
        """
        if not self._open_positions:
            return []

        sold_positions = []
        now = datetime.now(timezone.utc)

        for pos in list(self._open_positions):
            time_to_close = (pos.close_time - now).total_seconds()
            if time_to_close <= 0:
                logger.debug(f"[KALSHI-PROFIT] {pos.coin} 마감됨 → 포지션 제거")
                self._open_positions.remove(pos)
                continue

            cached = self._latest_market_data.get(pos.coin)
            if not cached:
                continue

            yes_ask = cached.get("yes_ask", 0)
            no_ask = cached.get("no_ask", 0)

            if yes_ask <= 0 or no_ask <= 0:
                continue

            # 매도 가치 = 200 - (상대방 combo ask)
            # 하지만 단일 거래소에서는 직접 계산: 양쪽 다 되팔면
            # YES 매도가 = YES bid, NO 매도가 = NO bid
            # YES bid = 100 - NO ask, NO bid = 100 - YES ask
            # 매도 가치 = (100 - NO ask) + (100 - YES ask) = 200 - (YES ask + NO ask)
            sell_value = 200 - (yes_ask + no_ask)

            if yes_ask < MIN_PRICE or no_ask < MIN_PRICE:
                logger.debug(
                    f"[KALSHI-PROFIT] {pos.coin} 호가 얇음 → 매도 보류 "
                    f"(YES={yes_ask} NO={no_ask})"
                )
                continue

            logger.debug(
                f"[KALSHI-PROFIT] {pos.coin}: "
                f"매도가치={sell_value:.1f}¢ (YES={yes_ask} NO={no_ask}) "
                f"threshold={SELL_THRESHOLD}¢"
            )

            if sell_value >= SELL_THRESHOLD:
                # 재시도 대기 체크
                retry_after = self._sell_retry_after.get(pos.ticker, 0)
                if time.time() < retry_after:
                    logger.debug(
                        f"[KALSHI-PROFIT] {pos.coin} 매도 재시도 대기 중 "
                        f"({retry_after - time.time():.1f}s 남음)"
                    )
                    continue

                logger.warning(
                    f"[KALSHI-PROFIT SELL] {pos.coin} 이익 실현! "
                    f"매도가치={sell_value:.1f}¢ >= {SELL_THRESHOLD}¢ | "
                    f"YES={yes_ask} NO={no_ask} | 수량: YES={pos.yes_count} NO={pos.no_count}"
                )
                result = self._execute_profit_sell(pos)
                if result.get("success"):
                    sold_positions.append({"position": pos, "result": result, "sell_value": sell_value})
                    self._open_positions.remove(pos)
                    self._sell_retry_after[pos.ticker] = time.time() + 3
                elif result.get("error"):
                    self._sell_retry_after[pos.ticker] = time.time() + 5

        return sold_positions

    def _execute_profit_sell(self, pos: KalshiPosition) -> dict:
        """이익 실현 매도 - YES와 NO 순차 매도"""
        t_start = time.monotonic()
        logger.warning(f"[KALSHI-PROFIT SELL] {pos.coin} | YES={pos.yes_count} NO={pos.no_count}")

        try:
            # YES 매도
            yes_result = self.kalshi.place_market_order(
                ticker=pos.ticker,
                side="sell",
                yes_or_no="yes",
                count=pos.yes_count,
                price=1  # 빠른 매도
            )
            yes_ok = not (isinstance(yes_result, dict) and yes_result.get("error"))
            logger.warning(f"[KALSHI-PROFIT SELL] YES: {yes_result}")

            if not yes_ok:
                logger.error(f"[KALSHI-PROFIT SELL] YES 매도 실패 → NO 매도 취소")
                return {"yes": yes_result, "no": {"skipped": "YES failed"}, "error": True}

            # YES 성공 → NO 매도
            no_result = self.kalshi.place_market_order(
                ticker=pos.ticker,
                side="sell",
                yes_or_no="no",
                count=pos.no_count,
                price=1
            )
            no_ok = not (isinstance(no_result, dict) and no_result.get("error"))
            logger.warning(f"[KALSHI-PROFIT SELL] NO: {no_result}")

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.warning(f"[KALSHI-PROFIT SELL] 완료: {elapsed_ms:.0f}ms")

            if no_ok:
                logger.success(f"[KALSHI-PROFIT SELL] 양쪽 매도 성공!")
                return {"yes": yes_result, "no": no_result, "success": True}
            else:
                self._halt_trading(f"이익매도: YES 성공 but NO 실패")
                return {"yes": yes_result, "no": no_result, "no_failed": True}

        except Exception as e:
            logger.error(f"[KALSHI-PROFIT SELL] 실패: {e}")
            self._sell_retry_after[pos.ticker] = time.time() + 5
            return {"error": str(e)}

    def _emergency_sell(self, pos: KalshiPosition) -> dict:
        """긴급 매도 - YES/NO 순차 매도"""
        t_start = time.monotonic()
        logger.error(f"[KALSHI-EMERGENCY SELL] {pos.coin} | YES={pos.yes_count} NO={pos.no_count}")

        try:
            # YES 매도
            yes_result = self.kalshi.place_market_order(
                ticker=pos.ticker,
                side="sell",
                yes_or_no="yes",
                count=pos.yes_count,
                price=1
            )
            yes_ok = not (isinstance(yes_result, dict) and yes_result.get("error"))
            logger.error(f"[KALSHI-EMERGENCY SELL] YES: {yes_result}")

            if not yes_ok:
                logger.error(f"[KALSHI-EMERGENCY SELL] YES 매도 실패")
                return {"yes": yes_result, "no": {"skipped": "YES failed"}, "error": True}

            # NO 매도
            no_result = self.kalshi.place_market_order(
                ticker=pos.ticker,
                side="sell",
                yes_or_no="no",
                count=pos.no_count,
                price=1
            )
            no_ok = not (isinstance(no_result, dict) and no_result.get("error"))
            logger.error(f"[KALSHI-EMERGENCY SELL] NO: {no_result}")

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.error(f"[KALSHI-EMERGENCY SELL] 완료: {elapsed_ms:.0f}ms")

            if not no_ok:
                self._halt_trading(f"긴급매도: YES 성공 but NO 실패")

            return {"yes": yes_result, "no": no_result, "success": yes_ok and no_ok}

        except Exception as e:
            logger.error(f"[KALSHI-EMERGENCY SELL] 실패: {e}")
            return {"error": str(e)}

    def find_opportunities(self, coin: str) -> list:
        """기회 탐색: YES ask + NO ask < BUY_THRESHOLD → 양쪽 매수"""
        opportunities = []

        if self._trading_halted:
            return opportunities

        try:
            # === 시장 데이터 조회 + 캐시 ===
            kalshi_markets = None

            if self._ws_feed:
                kalshi_data = self._ws_feed.get_market_data(coin)
                if kalshi_data:
                    kalshi_markets = [kalshi_data]
                    logger.debug(f"[{coin}] WS 캐시 사용")
                else:
                    logger.debug(f"[{coin}] WS 캐시 없음/stale → REST 폴백")

            if kalshi_markets is None:
                kalshi_markets = self.kalshi.get_crypto_markets(coin)

            if not kalshi_markets:
                logger.debug(f"[{coin}] No Kalshi 15m markets")
                return opportunities

            kalshi = kalshi_markets[0]
            self._latest_market_data[coin] = kalshi

            # 15분 윈도우 내 거래 횟수 체크
            current_threshold = self._get_buy_threshold(coin)
            if current_threshold == 0:
                return opportunities

            ticker = kalshi.get("ticker", "unknown")
            logger.debug(f"[{coin}] KALSHI Ticker: {ticker}")

            # === 마감 시간 파싱 ===
            close_time_str = kalshi.get("close_time", "")
            close_dt = self._parse_close_time(str(close_time_str)) if close_time_str else None
            remaining = (close_dt - datetime.now(timezone.utc)).total_seconds() if close_dt else 999

            # 가격 추출
            yes_ask = kalshi.get("yes_ask", 0)
            no_ask = kalshi.get("no_ask", 0)

            # 오더북 비어있으면 스킵
            if yes_ask == 0 and no_ask == 0:
                logger.debug(f"[{coin}] Kalshi 오더북 비어있음 → 스킵")
                return opportunities
            if yes_ask == 0 or no_ask == 0:
                logger.debug(f"[{coin}] 한쪽 가격 없음 (YES={yes_ask} NO={no_ask}) → 스킵")
                return opportunities

            # 최소 가격 필터
            if yes_ask < MIN_PRICE or no_ask < MIN_PRICE:
                logger.debug(
                    f"[{coin}] 최소가격 미달 → 거래 차단 "
                    f"(YES={yes_ask} NO={no_ask})"
                )
                return opportunities

            logger.debug(f"[{coin}] KALSHI: YES={yes_ask}¢ NO={no_ask}¢")

            # === YES + NO 합계 체크 ===
            combo = yes_ask + no_ask
            logger.debug(f"[{coin}] Combo (YES + NO) = {combo}¢")

            if combo > 0 and combo <= current_threshold:
                trade_size = MAX_TRADE_SIZE

                trade_n = len(self._trade_history.get(coin, [])) + 1
                logger.warning(
                    f"[{coin}] *** BUY OPPORTUNITY! #{trade_n} "
                    f"Combo: {combo}¢ ≤ {current_threshold}¢ "
                    f"(YES={yes_ask} + NO={no_ask}) | Qty: {trade_size} ***"
                )
                opportunities.append(KalshiOpportunity(
                    coin=coin,
                    action="BUY_YES_NO",
                    total_cost=combo,
                    yes_price=yes_ask,
                    no_price=no_ask,
                    trade_size=trade_size,
                    ticker=ticker,
                    strike_price=kalshi.get("strike_price") or 0,
                    close_time=close_time_str,
                ))

        except Exception as e:
            logger.error(f"Error [{coin}]: {e}")

        return opportunities

    def execute_trade(self, opp: KalshiOpportunity) -> dict:
        """거래 실행: YES + NO 병렬 매수"""
        if self._trading_halted:
            logger.error(f"[KALSHI-HALT] 거래 중단 상태 - 실행 거부: {self._halt_reason}")
            return {"success": False, "error": f"Trading halted: {self._halt_reason}"}

        if self.bot_mode == "test":
            logger.info(
                f"[KALSHI-TEST] {opp.action} | {opp.coin} | "
                f"Total: {opp.total_cost:.1f}¢ | Qty: {opp.trade_size}"
            )
            return {"success": True, "simulated": True}

        try:
            t_start = time.monotonic()

            # === YES + NO 병렬 매수 ===
            yes_future = self._executor.submit(
                self.kalshi.place_market_order,
                ticker=opp.ticker, side="buy",
                yes_or_no="yes", count=opp.trade_size,
                price=int(opp.yes_price)
            )
            no_future = self._executor.submit(
                self.kalshi.place_market_order,
                ticker=opp.ticker, side="buy",
                yes_or_no="no", count=opp.trade_size,
                price=int(opp.no_price)
            )

            logger.warning(
                f"[KALSHI-LIVE] Executing {opp.action} | {opp.coin} | "
                f"Total: {opp.total_cost:.1f}¢ (YES={opp.yes_price} NO={opp.no_price}) | "
                f"Qty: {opp.trade_size}"
            )
            yes_result = yes_future.result(timeout=10)
            no_result = no_future.result(timeout=10)

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.warning(f"[KALSHI-LIVE] 실행 완료 ({elapsed_ms:.0f}ms)")
            logger.warning(f"[KALSHI-LIVE] YES: {yes_result}")
            logger.warning(f"[KALSHI-LIVE] NO: {no_result}")

            results = {"yes": yes_result, "no": no_result}
            self._trade_history.setdefault(opp.coin, []).append(time.time())

            yes_ok = not (isinstance(yes_result, dict) and yes_result.get("error"))
            no_ok = not (isinstance(no_result, dict) and no_result.get("error"))

            if yes_ok and no_ok:
                logger.success(f"[KALSHI-LIVE] 양쪽 체결 완료! ({elapsed_ms:.0f}ms)")

                # 포지션 기록
                close_dt = self._parse_close_time(opp.close_time)
                if close_dt:
                    self._open_positions.append(KalshiPosition(
                        coin=opp.coin,
                        action=opp.action,
                        ticker=opp.ticker,
                        yes_count=opp.trade_size,
                        no_count=opp.trade_size,
                        strike_price=opp.strike_price,
                        close_time=close_dt,
                    ))
                    logger.warning(
                        f"[KALSHI-POSITION] {opp.coin} 포지션 기록 | "
                        f"종료: {close_dt.strftime('%H:%M:%S')} UTC | "
                        f"보유 포지션 수: {len(self._open_positions)}"
                    )

                return {"success": True, "results": results}

            elif yes_ok != no_ok:
                # 한쪽만 체결 → 반대쪽 즉시 시장가 매도 후 봇 중단
                failed = "NO" if yes_ok else "YES"
                logger.error(
                    f"[KALSHI-LIVE] {failed} 실패 ({elapsed_ms:.0f}ms) - 한쪽만 체결! "
                    f"→ 반대쪽 즉시 매도"
                )

                try:
                    if yes_ok:
                        # YES 체결, NO 실패 → YES 즉시 매도
                        sell_result = self.kalshi.place_market_order(
                            ticker=opp.ticker, side="sell",
                            yes_or_no="yes", count=opp.trade_size,
                            price=int(opp.yes_price)
                        )
                        logger.warning(f"[KALSHI-RECOVERY] YES 매도 결과: {sell_result}")
                    else:
                        # NO 체결, YES 실패 → NO 즉시 매도
                        sell_result = self.kalshi.place_market_order(
                            ticker=opp.ticker, side="sell",
                            yes_or_no="no", count=opp.trade_size,
                            price=int(opp.no_price)
                        )
                        logger.warning(f"[KALSHI-RECOVERY] NO 매도 결과: {sell_result}")
                except Exception as sell_err:
                    logger.error(f"[KALSHI-RECOVERY] 매도 실패! 수동 처리 필요: {sell_err}")

                self._halt_trading(f"한쪽 체결 → 반대쪽 매도 완료 ({failed} 실패)")
                return {"success": False, "results": results, "halted": True}

            else:
                # 양쪽 다 실패 → 위험 없음
                logger.warning(f"[KALSHI-LIVE] 양쪽 다 실패 ({elapsed_ms:.0f}ms) → 봇 계속 운영")
                return {"success": False, "results": results}

        except Exception as e:
            logger.error(f"Trade error: {e}")
            self._halt_trading(f"거래 예외: {e}")
            return {"success": False, "error": str(e), "halted": True}
