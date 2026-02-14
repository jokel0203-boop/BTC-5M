"""
재정거래 엔진 - 15분 마켓 실시간 비교

핵심 안전장치:
1. 기준가격(Price to beat) 비교: 양 거래소의 기준가가 다르면 거래 차단
2. 결과 불일치 감지: 두 거래소의 시장가격이 서로 다른 결과를 예측하면 거래 차단
3. 일일 손실 한도: Kalshi 잔고 기반 지출 추적 → 한도 초과 시 봇 중단
4. 거래 에러 즉시 중단: 한쪽이라도 실패하면 봇 즉시 중단
5. 종료 30초 전 긴급 매도: 두 거래소 결과 불일치 시 보유 포지션 전량 매도
6. 15분 쿨다운: 같은 코인은 15분에 1회만 거래
7. 병렬 실행: 양쪽 동시 주문 (감지가 + 슬리피지 캡으로 보호)

비교 조합:
- POLY UP + KALSHI NO
- KALSHI YES + POLY DOWN
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from loguru import logger

from src.polymarket.client import PolymarketClient
from src.kalshi.client import KalshiClient

BUY_THRESHOLD = 90  # 합계 ≤ 90¢
MAX_TRADES_PER_WINDOW = 1  # 15분 윈도우당 1회만 매매
SELL_THRESHOLD = 110  # 익절: 매도 가치 >= 110¢이면 매도 (합 95 매수 → 110 매도 = +15¢ 이익)
MIN_PRICE = 10  # 개별 가격 최소 10¢ (호가 얇아서 손해 방지)
POLY_MIN_ORDER_CENTS = 100  # Polymarket 최소 주문금액 $1 = 100¢
DEFAULT_TRADE_SIZE = 10  # 오더북 없을 때 기본값
MAX_TRADE_SIZE = 10  # 최대 거래 수량
TRADE_WINDOW_SECONDS = 15 * 60  # 15분 윈도우 (거래 횟수 추적 기간)
MIN_TRADE_INTERVAL = 3  # 연속 거래 최소 간격 (초)
STRIKE_DIFF_THRESHOLD = 0.001  # 기준가 차이 허용 범위 (0.1%)
DANGER_ZONE_SELL_SECONDS = 30  # 종료 전 N초 이내 + 결과 불일치 → 긴급 매도
MIN_STRIKE_DISTANCE = int(os.getenv("MIN_STRIKE_DISTANCE", "100"))  # 현재가와 strike 최소 차이 ($)


@dataclass
class ArbitrageOpportunity:
    coin: str
    action: str
    total_cost: float
    poly_price: float
    kalshi_price: float
    trade_size: int
    poly_id: str
    poly_token_id: str  # 실제 CLOB token ID (up_token 또는 down_token)
    kalshi_ticker: str
    side: str
    poly_strike: float = 0
    kalshi_strike: float = 0
    close_time: str = ""  # ISO format UTC


@dataclass
class OpenPosition:
    """보유 포지션 추적 (긴급 매도용)"""
    coin: str
    action: str  # "BUY_POLY_UP_KALSHI_NO" or "BUY_KALSHI_YES_POLY_DOWN"
    poly_token_id: str
    kalshi_ticker: str
    kalshi_yn: str  # "yes" or "no"
    count: int
    poly_strike: float
    kalshi_strike: float
    close_time: datetime  # UTC
    entry_time: float = field(default_factory=time.time)


class ArbitrageEngine:
    def __init__(self, poly_client=None, kalshi_client=None):
        self.polymarket = poly_client or PolymarketClient()
        self.kalshi = kalshi_client or KalshiClient()
        self.bot_mode = os.getenv("BOT_MODE", "test").strip().lower()
        self._connected = False
        self._trade_history = {}  # {coin: [timestamp, ...]} - 15분 윈도우 내 거래 횟수 추적

        # === 병렬 실행용 영구 스레드풀 (매 거래마다 생성/파괴 방지) ===
        self._executor = ThreadPoolExecutor(max_workers=2)

        # === WebSocket 가격 피드 (선택) ===
        self._ws_feed = None  # WebSocketPriceFeed instance

        # === 안전장치 상태 ===
        self._starting_kalshi_balance = None  # 시작 잔고 ($)
        self._trading_halted = False
        self._halt_reason = ""
        self._open_positions: list[OpenPosition] = []
        self._latest_market_data: dict = {}  # {coin: {poly: dict, kalshi: dict}} - 긴급매도용 캐시
        self._sell_retry_after: dict = {}  # {poly_token_id: timestamp} - 매도 실패 후 재시도 대기

    def set_ws_feed(self, feed):
        """WebSocket 가격 피드 설정 (선택)

        설정하면 find_opportunities()에서 WS 캐시 우선 사용.
        WS 데이터 없거나 stale하면 REST 폴백.
        """
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
        poly_ok = self.polymarket.connect()
        kalshi_ok = self.kalshi.connect()
        self._connected = poly_ok and kalshi_ok

        # 시작 잔고 기록
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

    def _check_outcome_mismatch(self, coin: str, poly: dict, kalshi: dict,
                                min_conviction: int = 65) -> bool:
        """두 거래소가 서로 반대 결과를 강하게 예측하는지 체크

        얇은 오더북에서 오판 방지:
        - UP 압도적 → UP ask=0(파는사람없음), DOWN ask=1¢(쓰레기호가)
          → 단순 비교하면 DOWN>UP으로 착각
        - 해결: 양쪽 모두 지배적 가격 ≥min_conviction¢일 때만 방향 판단

        Args:
            min_conviction: 방향 판단 최소 가격 (기본 65¢, 긴급매도 시 50¢)

        Returns:
            True: 확실한 불일치 (양쪽 모두 ≥min_conviction이고 방향 반대)
            False: 판단 불가 또는 일치
        """
        MIN_CONVICTION = min_conviction

        poly_up = poly.get("up_price", 0)
        poly_down = poly.get("down_price", 0)
        kalshi_yes = kalshi.get("yes_ask", 0)
        kalshi_no = kalshi.get("no_ask", 0)

        # Poly 방향: 지배적 가격이 65¢ 이상이어야 판단
        if poly_up >= MIN_CONVICTION and poly_up > poly_down:
            poly_expects_up = True
        elif poly_down >= MIN_CONVICTION and poly_down > poly_up:
            poly_expects_up = False
        else:
            # 양쪽 다 65¢ 미만이거나 가격 없음 → 판단 불가
            return False

        # Kalshi 방향: 동일 기준
        if kalshi_yes >= MIN_CONVICTION and kalshi_yes > kalshi_no:
            kalshi_expects_up = True
        elif kalshi_no >= MIN_CONVICTION and kalshi_no > kalshi_yes:
            kalshi_expects_up = False
        else:
            return False

        if poly_expects_up != kalshi_expects_up:
            logger.warning(
                f"[{coin}] OUTCOME MISMATCH (confirmed)! "
                f"Poly: {'UP' if poly_expects_up else 'DOWN'} (UP={poly_up:.1f} DOWN={poly_down:.1f}) "
                f"vs Kalshi: {'YES' if kalshi_expects_up else 'NO'} (YES={kalshi_yes} NO={kalshi_no})"
            )
            return True

        return False

    def check_emergency_sell(self) -> list:
        """종료 30초 전부터 끝날때까지 감시 → 양쪽 결과 불일치 시 해당 코인 전량매도

        1단계: 30초 이내 포지션의 코인별 결과 불일치 감지 (min_conviction=50)
        2단계: 불일치 감지된 코인의 모든 포지션 전량매도
        """
        if not self._open_positions:
            return []

        now = datetime.now(timezone.utc)
        sold_positions = []
        coins_to_sell = set()  # 전량매도 대상 코인

        # === 1단계: 만료 정리 + 불일치 감지 ===
        for pos in list(self._open_positions):
            time_to_close = (pos.close_time - now).total_seconds()

            # 이미 만료된 포지션 제거 (정산 완료)
            if time_to_close < -60:
                logger.debug(f"[{pos.coin}] 만료된 포지션 제거: {pos.action}")
                self._open_positions.remove(pos)
                continue

            # 종료 30초 전부터 감시
            if 0 < time_to_close <= DANGER_ZONE_SELL_SECONDS:
                # 이미 감지된 코인이면 스킵
                if pos.coin in coins_to_sell:
                    continue

                cached = self._latest_market_data.get(pos.coin)
                if cached and self._check_outcome_mismatch(
                    pos.coin, cached["poly"], cached["kalshi"],
                    min_conviction=50  # 마감 임박 → 낮은 확신 기준
                ):
                    logger.error(
                        f"[EMERGENCY] {pos.coin} 결과 불일치 감지! "
                        f"종료까지 {time_to_close:.0f}초 → 전량매도 예정"
                    )
                    coins_to_sell.add(pos.coin)

        # === 2단계: 불일치 코인 전량매도 ===
        if not coins_to_sell:
            return sold_positions

        for pos in list(self._open_positions):
            if pos.coin not in coins_to_sell:
                continue

            time_to_close = (pos.close_time - now).total_seconds()
            logger.error(
                f"[EMERGENCY] {pos.coin} 전량매도 실행! "
                f"{pos.action} | 수량: {pos.count}주 | "
                f"종료까지 {time_to_close:.0f}초"
            )
            result = self._emergency_sell(pos)
            if result.get("empty_position"):
                logger.error(f"[EMERGENCY] {pos.coin} Poly 잔고 0 → 빈 포지션 제거")
                self._open_positions.remove(pos)
            elif result.get("poly_failed"):
                logger.error(f"[EMERGENCY] {pos.coin} Poly 매도 실패 → 포지션 유지, 재시도 예정")
                # 긴급매도도 5초 대기 (API 스팸 방지)
                self._sell_retry_after[pos.poly_token_id] = time.time() + 5
            else:
                sold_positions.append({"position": pos, "result": result})
                self._open_positions.remove(pos)

        return sold_positions

    def check_profit_sell(self) -> list:
        """이익 실현 매도: 같은 조합의 현재 가격 합이 SELL_THRESHOLD 이상이면 매도

        예: Poly UP 30 + Kalshi NO 65 = 95에 매수 → 현재 Poly UP 40 + Kalshi NO 70 = 110 → 매도

        Returns:
            매도 실행한 포지션 리스트
        """
        if not self._open_positions:
            return []

        sold_positions = []
        now = datetime.now(timezone.utc)

        for pos in list(self._open_positions):
            # 마감된 마켓은 매도 불가 → 제거
            time_to_close = (pos.close_time - now).total_seconds()
            if time_to_close <= 0:
                logger.debug(f"[PROFIT] {pos.coin} 마감됨 → 포지션 제거")
                self._open_positions.remove(pos)
                continue

            cached = self._latest_market_data.get(pos.coin)
            if not cached:
                continue

            poly = cached["poly"]
            kalshi = cached["kalshi"]

            # 같은 조합의 현재 가격 합 계산
            if pos.action == "BUY_POLY_UP_KALSHI_NO":
                poly_price = poly.get("up_price", 0)
                kalshi_price = kalshi.get("no_ask", 0)
            elif pos.action == "BUY_KALSHI_YES_POLY_DOWN":
                poly_price = poly.get("down_price", 0)
                kalshi_price = kalshi.get("yes_ask", 0)
            else:
                continue

            if poly_price <= 0 or kalshi_price <= 0:
                continue

            # 한쪽이 MIN_PRICE 이하면 호가 얇아서 매도 손해
            if poly_price < MIN_PRICE or kalshi_price < MIN_PRICE:
                logger.debug(
                    f"[PROFIT] {pos.coin} 호가 얇음 → 매도 보류 "
                    f"(Poly={poly_price:.1f} Kalshi={kalshi_price})"
                )
                continue

            current_value = poly_price + kalshi_price

            logger.debug(
                f"[PROFIT] {pos.coin} {pos.action}: "
                f"현재={current_value:.1f}¢ (Poly={poly_price:.1f} Kalshi={kalshi_price}) "
                f"threshold={SELL_THRESHOLD}¢"
            )

            if current_value >= SELL_THRESHOLD:
                # 매도 실패 후 재시도 대기 중이면 스킵
                retry_after = self._sell_retry_after.get(pos.poly_token_id, 0)
                if time.time() < retry_after:
                    logger.debug(
                        f"[PROFIT] {pos.coin} 매도 재시도 대기 중 "
                        f"({retry_after - time.time():.1f}s 남음)"
                    )
                    continue

                logger.warning(
                    f"[PROFIT SELL] {pos.coin} 이익 실현! "
                    f"현재={current_value:.1f}¢ >= {SELL_THRESHOLD}¢ | "
                    f"Poly={poly_price:.1f} Kalshi={kalshi_price} | 수량: {pos.count}주"
                )
                result = self._execute_profit_sell(pos)
                if result.get("empty_position"):
                    # Poly 잔고 0 → 빈 포지션 제거
                    logger.warning(f"[PROFIT] {pos.coin} Poly 잔고 0 → 빈 포지션 제거")
                    self._open_positions.remove(pos)
                elif result.get("poly_failed"):
                    # Poly 매도 실패 → 포지션 유지, 5초 후 재시도
                    logger.warning(f"[PROFIT] Poly 매도 실패 → 포지션 유지, 5초 후 재시도")
                else:
                    # 성공이든 Kalshi 실패든 포지션 제거 (Poly는 이미 팔림)
                    sold_positions.append({"position": pos, "result": result, "sell_value": current_value})
                    self._open_positions.remove(pos)
                    # 같은 토큰의 다음 포지션은 3초 후 매도 (슬리피지 방지)
                    self._sell_retry_after[pos.poly_token_id] = time.time() + 3
                    logger.warning(
                        f"[PROFIT] {pos.coin} 매도 완료 → 다음 포지션 3초 대기 "
                        f"(남은 포지션: {sum(1 for p in self._open_positions if p.poly_token_id == pos.poly_token_id)}개)"
                    )

        return sold_positions

    def _execute_profit_sell(self, pos: OpenPosition) -> dict:
        """이익 실현 매도 - 순차 실행 (Poly 먼저 → 성공 시 Kalshi)

        핵심:
        1. Poly 매도 실패 시 Kalshi 매도 안 함 → 한쪽 손실 완전 차단
        2. Poly 매도 수량 = min(actual_balance, pos.count) → 다른 포지션 물량 보호
        3. actual_balance = 0이면 빈 포지션 → 매도 스킵
        """
        t_start = time.monotonic()
        logger.warning(f"[PROFIT SELL] {pos.coin} | {pos.action} | {pos.count}주")

        try:
            # 1) 매도 전 allowance 갱신 (token_id 필수!) + 잔고 확인
            self.polymarket.refresh_conditional_allowance(pos.poly_token_id)
            balance_info = self.polymarket.check_conditional_balance(pos.poly_token_id)
            logger.warning(f"[PROFIT SELL] Poly 잔고: {balance_info}")

            # 실제 보유량 확인 (balance는 raw unit: 1주 = 1,000,000)
            raw_balance = float(balance_info.get("balance", 0))
            actual_balance = int(raw_balance / 1_000_000)

            # 빈 포지션: Poly 잔고 0이면 매도 불가 → 포지션 제거 신호
            if actual_balance <= 0:
                logger.warning(
                    f"[PROFIT SELL] Poly 잔고 0주 (raw={raw_balance:.0f}) → 빈 포지션, 스킵"
                )
                return {"poly": {"skipped": "no_balance"}, "kalshi": {"skipped": "no_balance"}, "empty_position": True}

            # pos.count 이하로만 매도 (다른 포지션 물량 보호!)
            sell_count = min(actual_balance, pos.count)
            logger.warning(f"[PROFIT SELL] 매도 수량: {sell_count}주 (잔고={actual_balance}주, 기록={pos.count}주)")

            # 2) Poly 먼저 매도
            poly_result = self.polymarket.place_market_order(
                token_id=pos.poly_token_id,
                side="SELL",
                size=sell_count,
                price=1
            )
            poly_ok = not (isinstance(poly_result, dict) and "error" in poly_result)
            logger.warning(f"[PROFIT SELL] Poly: {poly_result}")

            if not poly_ok:
                # Poly 매도 실패 → Kalshi 매도 안 함! (한쪽 손실 방지)
                elapsed_ms = (time.monotonic() - t_start) * 1000
                logger.error(
                    f"[PROFIT SELL] Poly 매도 실패 → Kalshi 매도 취소 ({elapsed_ms:.0f}ms) | "
                    f"포지션 유지, 5초 후 재시도"
                )
                # 실패 후 5초 대기 (API 스팸 방지)
                self._sell_retry_after[pos.poly_token_id] = time.time() + 5
                return {"poly": poly_result, "kalshi": {"skipped": "Poly failed"}, "poly_failed": True}

            # 3) Poly 성공 → Kalshi 매도 (Poly와 동일 수량!)
            kalshi_sell_count = sell_count
            kalshi_result = self.kalshi.place_market_order(
                ticker=pos.kalshi_ticker,
                side="sell",
                yes_or_no=pos.kalshi_yn,
                count=kalshi_sell_count,
                price=1
            )
            kalshi_ok = not (isinstance(kalshi_result, dict) and "error" in kalshi_result)
            logger.warning(f"[PROFIT SELL] Kalshi: {kalshi_result}")

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.warning(f"[PROFIT SELL] 완료: {elapsed_ms:.0f}ms")

            # 성공 시 재시도 대기 해제
            self._sell_retry_after.pop(pos.poly_token_id, None)

            if kalshi_ok:
                logger.success(f"[PROFIT SELL] 양쪽 매도 성공! ({sell_count}주)")
                return {"poly": poly_result, "kalshi": kalshi_result, "success": True, "sold_count": sell_count}
            else:
                # Poly 성공 + Kalshi 실패 → 한쪽만 성공, halt
                self._halt_trading(f"이익매도: Poly 성공 but Kalshi 실패")
                return {"poly": poly_result, "kalshi": kalshi_result, "kalshi_failed": True}

        except Exception as e:
            logger.error(f"[PROFIT SELL] 실패: {e}")
            self._sell_retry_after[pos.poly_token_id] = time.time() + 5
            return {"error": str(e)}

    def _emergency_sell(self, pos: OpenPosition) -> dict:
        """긴급 매도 - 순차 실행 (Poly 먼저 → 성공 시 Kalshi)"""
        t_start = time.monotonic()
        logger.error(f"[EMERGENCY SELL] {pos.coin} | {pos.action} | {pos.count}주")

        try:
            # 1) allowance 갱신 (token_id 필수!) + 실제 보유량 확인
            self.polymarket.refresh_conditional_allowance(pos.poly_token_id)
            balance_info = self.polymarket.check_conditional_balance(pos.poly_token_id)
            raw_balance = float(balance_info.get("balance", 0))
            actual_balance = int(raw_balance / 1_000_000)

            # 빈 포지션: Poly 잔고 0이면 매도 불가
            if actual_balance <= 0:
                logger.error(
                    f"[EMERGENCY SELL] Poly 잔고 0주 (raw={raw_balance:.0f}) → 빈 포지션, 스킵"
                )
                return {"poly": {"skipped": "no_balance"}, "kalshi": {"skipped": "no_balance"}, "empty_position": True}

            # pos.count 이하로만 매도 (다른 포지션 물량 보호!)
            sell_count = min(actual_balance, pos.count)
            logger.error(f"[EMERGENCY SELL] 매도 수량: {sell_count}주 (잔고={actual_balance}주, 기록={pos.count}주)")

            # 2) Poly 먼저 매도
            poly_result = self.polymarket.place_market_order(
                token_id=pos.poly_token_id,
                side="SELL",
                size=sell_count,
                price=1
            )
            poly_ok = not (isinstance(poly_result, dict) and "error" in poly_result)
            logger.error(f"[EMERGENCY SELL] Poly: {poly_result}")

            if not poly_ok:
                elapsed_ms = (time.monotonic() - t_start) * 1000
                logger.error(
                    f"[EMERGENCY SELL] Poly 매도 실패 → Kalshi 매도 취소 ({elapsed_ms:.0f}ms)"
                )
                return {"poly": poly_result, "kalshi": {"skipped": "Poly failed"}, "poly_failed": True}

            # 3) Poly 성공 → Kalshi 매도 (Poly와 동일 수량!)
            kalshi_result = self.kalshi.place_market_order(
                ticker=pos.kalshi_ticker,
                side="sell",
                yes_or_no=pos.kalshi_yn,
                count=sell_count,
                price=1
            )
            logger.error(f"[EMERGENCY SELL] Kalshi: {kalshi_result}")

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.error(f"[EMERGENCY SELL] 완료: {elapsed_ms:.0f}ms")

            kalshi_ok = not (isinstance(kalshi_result, dict) and "error" in kalshi_result)
            if not kalshi_ok:
                self._halt_trading(f"긴급매도: Poly 성공 but Kalshi 실패")

            return {"poly": poly_result, "kalshi": kalshi_result, "success": poly_ok and kalshi_ok}
        except Exception as e:
            logger.error(f"[EMERGENCY SELL] 실패: {e}")
            return {"error": str(e)}

    def _get_trade_size(self, poly_ask_size: int, kalshi_ticker: str) -> int:
        """거래 수량 결정 — 시장가 주문이므로 항상 MAX_TRADE_SIZE 사용"""
        return MAX_TRADE_SIZE

    def _get_buy_threshold(self, coin: str) -> int:
        """15분 윈도우 내 거래 횟수에 따른 매수 기준값 반환

        Returns:
            0: 거래 불가 (최대 횟수 도달 또는 최소 간격 미달)
            BUY_THRESHOLD: 매수 가능
        """
        now = time.time()
        # 15분 윈도우 내 거래만 유지
        trades = self._trade_history.get(coin, [])
        trades = [t for t in trades if now - t < TRADE_WINDOW_SECONDS]
        self._trade_history[coin] = trades

        # 최소 거래 간격 체크 (마지막 거래 후 N초 경과 필요)
        if trades and (now - trades[-1]) < MIN_TRADE_INTERVAL:
            logger.debug(f"[{coin}] 최소 거래 간격 미달 ({now - trades[-1]:.1f}s < {MIN_TRADE_INTERVAL}s)")
            return 0

        trade_count = len(trades)
        if trade_count >= MAX_TRADES_PER_WINDOW:
            logger.debug(f"[{coin}] 15분 윈도우 내 {trade_count}회 거래 완료 → 추가 거래 차단")
            return 0

        return BUY_THRESHOLD

    def _check_strike_prices(self, coin: str, poly: dict, kalshi: dict) -> bool:
        """양 거래소의 기준가격(Price to beat) 비교

        기준가가 다르면 양쪽 모두 손실 가능 (진정한 아비트리지가 아님)
        """
        poly_strike = poly.get("strike_price")
        kalshi_strike = kalshi.get("strike_price")

        if poly_strike is None or kalshi_strike is None:
            logger.debug(f"[{coin}] 기준가 비교 불가 (Poly={poly_strike}, Kalshi={kalshi_strike})")
            return True

        if kalshi_strike == 0:
            return True

        diff_pct = abs(poly_strike - kalshi_strike) / kalshi_strike
        if diff_pct > STRIKE_DIFF_THRESHOLD:
            logger.warning(
                f"[{coin}] 기준가 불일치! Poly=${poly_strike:,.2f} vs Kalshi=${kalshi_strike:,.2f} "
                f"(차이: {diff_pct:.3%}) → 거래 차단"
            )
            return False

        logger.debug(f"[{coin}] 기준가 일치: Poly=${poly_strike:,.2f} ≈ Kalshi=${kalshi_strike:,.2f} ({diff_pct:.4%})")
        return True

    def _parse_close_time(self, close_time_val):
        """close_time을 datetime으로 변환 (str, datetime 모두 지원)"""
        if not close_time_val:
            return None
        try:
            # 이미 datetime이면 timezone만 확인
            if isinstance(close_time_val, datetime):
                if close_time_val.tzinfo is None:
                    return close_time_val.replace(tzinfo=timezone.utc)
                return close_time_val
            ct = str(close_time_val).replace("Z", "+00:00")
            return datetime.fromisoformat(ct)
        except Exception:
            return None

    def find_opportunities(self, coin: str) -> list:
        opportunities = []

        # 봇 중단 상태면 스킵
        if self._trading_halted:
            return opportunities

        # Poly requests.Session TCP 연결 유지 (idle 30초 방지)
        self.polymarket.keep_session_warm()

        try:
            # === 시장 데이터 항상 조회 + 캐시 (긴급매도용) ===
            # threshold=0이어도 데이터를 조회해야 check_emergency_sell()이 최신 가격으로 판단 가능
            poly_markets = None
            kalshi_markets = None

            if self._ws_feed:
                poly_data, kalshi_data = self._ws_feed.get_market_data(coin)
                if poly_data and kalshi_data:
                    poly_markets = [poly_data]
                    kalshi_markets = [kalshi_data]
                    logger.debug(f"[{coin}] WS 캐시 사용")
                else:
                    logger.debug(f"[{coin}] WS 캐시 없음/stale → REST 폴백")

            if poly_markets is None:
                poly_markets = self.polymarket.get_crypto_markets(coin)
            if kalshi_markets is None:
                kalshi_markets = self.kalshi.get_crypto_markets(coin)

            if poly_markets and kalshi_markets:
                poly = poly_markets[0]
                kalshi = kalshi_markets[0]
                # 시장 데이터 캐시 갱신 (긴급 매도 체크용) — threshold 체크 전에 항상 실행!
                self._latest_market_data[coin] = {"poly": poly, "kalshi": kalshi}
            else:
                if not poly_markets:
                    logger.debug(f"[{coin}] No Polymarket 15m markets")
                if not kalshi_markets:
                    logger.debug(f"[{coin}] No Kalshi 15m markets")
                return opportunities

            # 15분 윈도우 내 거래 횟수 체크 → 해당 threshold 적용
            current_threshold = self._get_buy_threshold(coin)
            if current_threshold == 0:
                return opportunities

            # 마켓 정보 로그
            poly_slug = poly.get("slug", "unknown")
            kalshi_ticker = kalshi.get("ticker", "unknown")
            logger.debug(f"[{coin}] POLY Slug: {poly_slug} | KALSHI Ticker: {kalshi_ticker}")

            # 기준가격(Price to beat) 비교 - 다르면 거래 차단
            if not self._check_strike_prices(coin, poly, kalshi):
                return opportunities

            # === 마감 시간 파싱 (여러 체크에서 공용) ===
            poly_strike = poly.get("strike_price")
            kalshi_strike = kalshi.get("strike_price")
            close_time_str = kalshi.get("close_time", "")
            close_dt = self._parse_close_time(str(close_time_str)) if close_time_str else None
            remaining = (close_dt - datetime.now(timezone.utc)).total_seconds() if close_dt else 999

            # === 가격 변동 최소 $100 체크 (마감 1분 전부터만 적용) ===
            apply_distance_check = False
            if MIN_STRIKE_DISTANCE > 0 and remaining <= 60:
                apply_distance_check = True
                logger.debug(f"[{coin}] 마감 {remaining:.0f}초 전 → $100 거리 체크 적용")

            if apply_distance_check and poly_strike:
                # 1차: Polymarket API에서 현재가 직접 사용
                current_price = poly.get("current_price")
                if current_price and current_price > 0:
                    distance = abs(current_price - poly_strike)
                    if distance < MIN_STRIKE_DISTANCE:
                        logger.warning(
                            f"[{coin}] 마감 직전 가격 변동 부족: ${distance:.0f} < ${MIN_STRIKE_DISTANCE} "
                            f"(현재=${current_price:,.2f} strike=${poly_strike:,.2f}) → 스킵"
                        )
                        return opportunities
                    logger.debug(f"[{coin}] 가격 변동: ${distance:.0f} >= ${MIN_STRIKE_DISTANCE} ✓ (Poly API)")
                else:
                    # 2차 폴백: 시장 가격(UP/DOWN 비율)으로 거리 추정
                    poly_up = poly.get("up_price", 0)
                    poly_down = poly.get("down_price", 0)
                    dominant = max(poly_up, poly_down)
                    MIN_DOMINANT_PRICE = 65  # 65¢ = ~65% 확률
                    if dominant > 0 and dominant < MIN_DOMINANT_PRICE:
                        logger.warning(
                            f"[{coin}] 마감 직전 가격 변동 부족 (시장가 추정): "
                            f"우세={dominant:.1f}¢ < {MIN_DOMINANT_PRICE}¢ → 스킵"
                        )
                        return opportunities

            # 가격 추출
            poly_up = poly.get("up_price", 0)
            poly_down = poly.get("down_price", 0)
            kalshi_yes = kalshi.get("yes_ask", 0)
            kalshi_no = kalshi.get("no_ask", 0)

            # Kalshi 오더북 비어있으면 stale 가격이므로 전체 스킵
            if kalshi_yes == 0 and kalshi_no == 0:
                logger.debug(f"[{coin}] Kalshi 오더북 비어있음 → 스킵 (stale 가격 폴백 금지)")
                return opportunities
            if poly_up == 0 and poly_down == 0:
                logger.debug(f"[{coin}] Missing Poly prices")
                return opportunities

            # 최소 가격 필터: 개별 가격이 너무 낮으면 유동성 없음 또는 시간대 불일치
            all_prices = [poly_up, poly_down, kalshi_yes, kalshi_no]
            if any(p > 0 and p < MIN_PRICE for p in all_prices):
                logger.debug(
                    f"[{coin}] 최소가격 미달 → 거래 차단 "
                    f"(Poly UP={poly_up:.1f} DOWN={poly_down:.1f} | Kalshi YES={kalshi_yes} NO={kalshi_no})"
                )
                return opportunities

            logger.debug(f"[{coin}] POLY: UP={poly_up:.1f}¢ DOWN={poly_down:.1f}¢ | KALSHI: YES={kalshi_yes}¢ NO={kalshi_no}¢")

            # 오더북 수량
            up_ask_size = poly.get("up_ask_size", 0)
            down_ask_size = poly.get("down_ask_size", 0)
            close_time_str = kalshi.get("close_time", "")

            # === 조합 1: POLY UP + KALSHI NO ===
            combo1 = poly_up + kalshi_no
            logger.debug(f"[{coin}] Combo1 (POLY UP + KALSHI NO) = {combo1:.1f}¢")

            if kalshi_no == 0 or poly_up == 0:
                logger.debug(f"[{coin}] Combo1 스킵: 가격 없음 (Poly UP={poly_up}, Kalshi NO={kalshi_no})")
            elif combo1 > 0 and combo1 <= current_threshold:
                trade_size = self._get_trade_size(up_ask_size, kalshi_ticker)
                poly_order_value = poly_up * trade_size
                if poly_order_value < POLY_MIN_ORDER_CENTS:
                    logger.warning(f"[{coin}] Poly 주문금액 미달: {poly_up:.1f}¢ × {trade_size} = {poly_order_value:.0f}¢ < $1 → 스킵")
                else:
                    trade_n = len(self._trade_history.get(coin, [])) + 1
                    logger.warning(f"[{coin}] *** BUY OPPORTUNITY! #{trade_n} Combo1: {combo1:.1f}¢ ≤ {current_threshold}¢ (Poly UP={poly_up:.1f} + Kalshi NO={kalshi_no}) | Qty: {trade_size} ***")
                    opportunities.append(ArbitrageOpportunity(
                        coin=coin, action="BUY_POLY_UP_KALSHI_NO",
                        total_cost=combo1, poly_price=poly_up, kalshi_price=kalshi_no,
                        trade_size=trade_size, poly_id=poly.get("condition_id", ""),
                        poly_token_id=poly.get("up_token", ""),
                        kalshi_ticker=kalshi_ticker, side="buy",
                        poly_strike=poly_strike or 0,
                        kalshi_strike=kalshi_strike or 0,
                        close_time=close_time_str,
                    ))

            # === 조합 2: KALSHI YES + POLY DOWN ===
            combo2 = kalshi_yes + poly_down
            logger.debug(f"[{coin}] Combo2 (KALSHI YES + POLY DOWN) = {combo2:.1f}¢")

            if kalshi_yes == 0 or poly_down == 0:
                logger.debug(f"[{coin}] Combo2 스킵: 가격 없음 (Kalshi YES={kalshi_yes}, Poly DOWN={poly_down})")
            elif combo2 > 0 and combo2 <= current_threshold:
                trade_size = self._get_trade_size(down_ask_size, kalshi_ticker)
                poly_order_value = poly_down * trade_size
                if poly_order_value < POLY_MIN_ORDER_CENTS:
                    logger.warning(f"[{coin}] Poly 주문금액 미달: {poly_down:.1f}¢ × {trade_size} = {poly_order_value:.0f}¢ < $1 → 스킵")
                else:
                    trade_n = len(self._trade_history.get(coin, [])) + 1
                    logger.warning(f"[{coin}] *** BUY OPPORTUNITY! #{trade_n} Combo2: {combo2:.1f}¢ ≤ {current_threshold}¢ (Kalshi YES={kalshi_yes} + Poly DOWN={poly_down:.1f}) | Qty: {trade_size} ***")
                    opportunities.append(ArbitrageOpportunity(
                        coin=coin, action="BUY_KALSHI_YES_POLY_DOWN",
                        total_cost=combo2, poly_price=poly_down, kalshi_price=kalshi_yes,
                        trade_size=trade_size, poly_id=poly.get("condition_id", ""),
                        poly_token_id=poly.get("down_token", ""),
                        kalshi_ticker=kalshi_ticker, side="buy",
                        poly_strike=poly_strike or 0,
                        kalshi_strike=kalshi_strike or 0,
                        close_time=close_time_str,
                    ))

        except Exception as e:
            logger.error(f"Error [{coin}]: {e}")

        return opportunities

    def execute_trade(self, opp: ArbitrageOpportunity) -> dict:
        # 봇 중단 상태면 실행 안 함
        if self._trading_halted:
            logger.error(f"[HALT] 거래 중단 상태 - 실행 거부: {self._halt_reason}")
            return {"success": False, "error": f"Trading halted: {self._halt_reason}"}

        if self.bot_mode == "test":
            logger.info(f"[TEST] {opp.action} | {opp.coin} | Total: {opp.total_cost:.1f}¢ | Qty: {opp.trade_size}")
            return {"success": True, "simulated": True}

        try:
            t_start = time.monotonic()

            # 주문 파라미터 계산 (최소한의 연산만)
            poly_side = "BUY" if "BUY" in opp.action else "SELL"
            kalshi_side = "buy" if "BUY" in opp.action else "sell"
            kalshi_yn = "no" if "KALSHI_NO" in opp.action else "yes"

            # === 주문 즉시 제출 (로깅보다 먼저!) ===
            poly_future = self._executor.submit(
                self.polymarket.place_market_order,
                token_id=opp.poly_token_id, side=poly_side,
                size=opp.trade_size, price=opp.poly_price
            )
            kalshi_future = self._executor.submit(
                self.kalshi.place_market_order,
                ticker=opp.kalshi_ticker, side=kalshi_side,
                yes_or_no=kalshi_yn, count=opp.trade_size,
                price=int(opp.kalshi_price)
            )

            # 주문 제출 후 로깅 (네트워크 대기 중 병렬)
            logger.warning(
                f"[LIVE] Executing {opp.action} | {opp.coin} | "
                f"Total: {opp.total_cost:.1f}¢ (Poly={opp.poly_price:.1f} Kalshi={opp.kalshi_price:.1f}) | Qty: {opp.trade_size}"
            )
            poly_result = poly_future.result(timeout=10)
            kalshi_result = kalshi_future.result(timeout=10)

            elapsed_ms = (time.monotonic() - t_start) * 1000
            logger.warning(f"[LIVE] 실행 완료 ({elapsed_ms:.0f}ms)")
            logger.warning(f"[LIVE] Poly: {poly_result}")
            logger.warning(f"[LIVE] Kalshi: {kalshi_result}")

            results = {"poly": poly_result, "kalshi": kalshi_result}
            self._trade_history.setdefault(opp.coin, []).append(time.time())

            # 에러 체크: VALUE가 truthy인지 확인 (KEY 존재만 체크하면 안됨!)
            # Kalshi SDK vars()에 error=None 포함 → "error" in dict = True → 거짓 실패!
            poly_ok = not (isinstance(poly_result, dict) and poly_result.get("error"))
            kalshi_ok = not (isinstance(kalshi_result, dict) and kalshi_result.get("error"))

            if poly_ok and kalshi_ok:
                logger.success(f"[LIVE] 양쪽 체결 완료! ({elapsed_ms:.0f}ms)")

                # 매수 직후 Poly 토큰 allowance 승인 (나중에 매도할 때 필요!)
                # ERC-1155은 token_id가 필수 → 여기서 미리 승인
                self.polymarket.approve_token_for_sell(opp.poly_token_id)

                # 포지션 기록 (긴급 매도 + 익절 매도용)
                close_dt = self._parse_close_time(opp.close_time)
                if not close_dt:
                    logger.error(f"[POSITION] close_time 파싱 실패! raw={repr(opp.close_time)} → 포지션 미등록 (긴급매도 불가)")
                if close_dt:
                    self._open_positions.append(OpenPosition(
                        coin=opp.coin,
                        action=opp.action,
                        poly_token_id=opp.poly_token_id,
                        kalshi_ticker=opp.kalshi_ticker,
                        kalshi_yn=kalshi_yn,
                        count=opp.trade_size,
                        poly_strike=opp.poly_strike,
                        kalshi_strike=opp.kalshi_strike,
                        close_time=close_dt,
                    ))
                    logger.warning(
                        f"[POSITION] {opp.coin} 포지션 기록 | "
                        f"종료: {close_dt.strftime('%H:%M:%S')} UTC | "
                        f"보유 포지션 수: {len(self._open_positions)}"
                    )

                return {"success": True, "results": results}
            elif poly_ok != kalshi_ok:
                # === 한쪽만 체결 → 반대쪽 즉시 시장가 매도 후 봇 중단 ===
                failed = "Kalshi" if poly_ok else "Poly"
                logger.error(f"[LIVE] {failed} 실패 ({elapsed_ms:.0f}ms) - 한쪽만 체결! → 반대쪽 즉시 매도")

                try:
                    if poly_ok:
                        # Poly 체결, Kalshi 실패 → Poly 즉시 시장가 매도
                        self.polymarket.approve_token_for_sell(opp.poly_token_id)
                        sell_result = self.polymarket.place_market_order(
                            token_id=opp.poly_token_id, side="SELL",
                            size=opp.trade_size, price=opp.poly_price
                        )
                        logger.warning(f"[RECOVERY] Poly 매도 결과: {sell_result}")
                    else:
                        # Kalshi 체결, Poly 실패 → Kalshi 즉시 시장가 매도
                        sell_result = self.kalshi.place_market_order(
                            ticker=opp.kalshi_ticker, side="sell",
                            yes_or_no=kalshi_yn, count=opp.trade_size,
                            price=int(opp.kalshi_price)
                        )
                        logger.warning(f"[RECOVERY] Kalshi 매도 결과: {sell_result}")
                except Exception as sell_err:
                    logger.error(f"[RECOVERY] 매도 실패! 수동 처리 필요: {sell_err}")

                self._halt_trading(f"한쪽 체결 → 반대쪽 매도 완료 ({failed} 실패)")
                return {"success": False, "results": results, "halted": True}
            else:
                # === 양쪽 다 실패 → 위험 없음, 봇 계속 ===
                logger.warning(f"[LIVE] 양쪽 다 실패 ({elapsed_ms:.0f}ms) → 봇 계속 운영")
                return {"success": False, "results": results}

        except Exception as e:
            logger.error(f"Trade error: {e}")
            self._halt_trading(f"거래 예외: {e}")
            return {"success": False, "error": str(e), "halted": True}
