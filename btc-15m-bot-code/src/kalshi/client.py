"""
Kalshi API - 15분 크립토 마켓

핵심:
- 15분 마켓 시리즈: KXBTC15M, KXETH15M, KXSOL15M
- get_markets()의 yes_ask/no_ask는 **stale(지연)** → 오더북 직접 조회 필수
- get_market_orderbook(ticker): 실시간 오더북에서 정확한 가격 계산
- SDK 응답 구조: ob.orderbook.var_true (YES bids) / var_false (NO bids)
  각 항목은 OrderbookLevel(price, count) 객체
- YES ask = 100 - best "false" bid, NO ask = 100 - best "true" bid
"""
import os
import re
from datetime import datetime, timezone
from loguru import logger

try:
    import kalshi_python
except ImportError:
    kalshi_python = None

KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2"


class KalshiClient:
    def __init__(self):
        self.key_id = os.getenv("KALSHI_API_KEY_ID")

        key_file = os.getenv("KALSHI_PRIVATE_KEY_FILE")
        if key_file and os.path.exists(key_file):
            with open(key_file, 'r') as f:
                self.private_key = f.read()
        else:
            self.private_key = os.getenv("KALSHI_PRIVATE_KEY")

        self.client = None
        self._initialized = False

    def connect(self) -> bool:
        if kalshi_python is None:
            logger.error("kalshi-python required")
            return False
        try:
            config = kalshi_python.Configuration()
            config.host = KALSHI_API_URL

            if self.key_id and self.private_key:
                # 진단 로그: key_id 앞 8자 표시 (대시보드와 대조용)
                logger.warning(f"[KALSHI] Auth key_id={self.key_id[:8]}... pem_len={len(self.private_key)}")
                config.api_key_id = self.key_id
                config.private_key_pem = self.private_key
                self.client = kalshi_python.KalshiClient(configuration=config)
                self._initialized = True
                # HTTP 연결 pre-warm (첫 주문 시 TCP/TLS 지연 제거)
                try:
                    self.client.get_balance()
                except Exception as e:
                    logger.warning(f"[KALSHI] Pre-warm balance call failed: {e}")
                logger.info("Kalshi connected")
                return True
            else:
                logger.error(f"Kalshi API key not set (key_id={'SET' if self.key_id else 'MISSING'}, pem={'SET' if self.private_key else 'MISSING'})")
                return False
        except Exception as e:
            logger.error(f"Kalshi error: {e}")
            return False

    def _get_orderbook_prices(self, ticker: str, qty: int = 3) -> dict:
        """오더북에서 실시간 가격 조회 (get_markets보다 정확)

        qty=3: MAX_TRADE_SIZE와 동일 (10이면 가격 왜곡 심함).

        가격 계산:
        - YES ask = 100 - best NO bid (= best "false" bid)
        - NO ask = 100 - best YES bid (= best "true" bid)
        """
        result = {"yes_ask": 0, "no_ask": 0}
        try:
            ob = self.client.get_market_orderbook(ticker, depth=20)

            # SDK v2.1.4: ob.orderbook.var_true / var_false (Pydantic 모델)
            yes_bids = []
            no_bids = []

            # 1차: Pydantic 모델 구조 (ob.orderbook.var_true/var_false)
            inner = getattr(ob, 'orderbook', None)
            if inner is not None:
                raw_yes = getattr(inner, 'var_true', None) or []
                raw_no = getattr(inner, 'var_false', None) or []
                # OrderbookLevel 객체 → [price, count] 변환
                for level in raw_yes:
                    p = getattr(level, 'price', None)
                    c = getattr(level, 'count', None)
                    if p is not None and c is not None:
                        yes_bids.append([int(p), int(c)])
                for level in raw_no:
                    p = getattr(level, 'price', None)
                    c = getattr(level, 'count', None)
                    if p is not None and c is not None:
                        no_bids.append([int(p), int(c)])

            # 2차 폴백: dict 구조
            if not yes_bids and not no_bids and isinstance(ob, dict):
                orderbook = ob.get('orderbook', ob)
                for item in (orderbook.get('true', []) or orderbook.get('yes', []) or []):
                    if isinstance(item, list):
                        yes_bids.append([int(item[0]), int(item[1])])
                    elif isinstance(item, dict):
                        yes_bids.append([int(item['price']), int(item['count'])])
                for item in (orderbook.get('false', []) or orderbook.get('no', []) or []):
                    if isinstance(item, list):
                        no_bids.append([int(item[0]), int(item[1])])
                    elif isinstance(item, dict):
                        no_bids.append([int(item['price']), int(item['count'])])

            logger.debug(f"[KALSHI-OB] {ticker}: yes_bids={yes_bids[:3]} no_bids={no_bids[:3]}")

            # YES ask = 100 - NO bids (NO bid 높은 순 → YES ask 낮은 순)
            if no_bids:
                sorted_no = sorted(no_bids, key=lambda x: x[0], reverse=True)
                result["yes_ask"] = self._calc_fill_price(sorted_no, qty)

            # NO ask = 100 - YES bids (YES bid 높은 순 → NO ask 낮은 순)
            if yes_bids:
                sorted_yes = sorted(yes_bids, key=lambda x: x[0], reverse=True)
                result["no_ask"] = self._calc_fill_price(sorted_yes, qty)

            if result["yes_ask"] == 0 and result["no_ask"] == 0:
                logger.debug(f"[KALSHI-OB] {ticker}: 오더북 비어있음")

        except Exception as e:
            logger.warning(f"[KALSHI] Orderbook error for {ticker}: {e}")
        return result

    def _calc_fill_price(self, sorted_bids: list, qty: int) -> float:
        """오더북에서 qty 수량의 가중평균 체결가 계산

        bids = [[price, count], ...] (내림차순 정렬됨)
        체결가 = 100 - bid_price (complement)
        """
        remaining = qty
        total_cost = 0

        for bid in sorted_bids:
            bid_price = bid[0]
            available = bid[1]
            fill = min(remaining, available)
            ask_price = 100 - bid_price  # 실제 체결가

            total_cost += fill * ask_price
            remaining -= fill
            if remaining <= 0:
                break

        if remaining > 0:
            logger.debug(f"[KALSHI-OB] 오더북 깊이 부족: {qty - remaining}/{qty} 체결 가능")
            return 0

        return total_cost / qty  # 가중평균 (센트)

    def get_crypto_markets(self, coin: str = None) -> list:
        """15분 크립토 마켓 조회 - KXBTC15M, KXETH15M 시리즈"""
        if not self._initialized:
            return []

        try:
            # 코인별 시리즈 티커
            series_map = {
                "BTC": "KXBTC15M",
                "ETH": "KXETH15M",
                "SOL": "KXSOL15M"
            }

            target_coins = [coin.upper()] if coin else ["BTC", "ETH", "SOL"]
            all_markets = []

            for c in target_coins:
                series_ticker = series_map.get(c)
                if not series_ticker:
                    continue

                try:
                    response = self.client.get_markets(status="open", series_ticker=series_ticker)
                    markets = response.markets if hasattr(response, 'markets') else []
                except Exception as e:
                    logger.debug(f"Series {series_ticker} not found: {e}")
                    markets = []

                now = datetime.now(timezone.utc)

                for m in markets:
                    ticker = getattr(m, 'ticker', '?')
                    # 종료 시간 확인 (str 또는 datetime 모두 처리)
                    close_time = getattr(m, 'close_time', None)
                    check_time = close_time or getattr(m, 'expiration_time', None)
                    if check_time:
                        try:
                            if isinstance(check_time, str):
                                end_time = datetime.fromisoformat(check_time.replace("Z", "+00:00"))
                            elif isinstance(check_time, datetime):
                                end_time = check_time if check_time.tzinfo else check_time.replace(tzinfo=timezone.utc)
                            else:
                                end_time = None

                            if end_time and end_time < now:
                                continue
                        except Exception:
                            pass

                    yes_ask = getattr(m, 'yes_ask', 0) or 0
                    no_ask = getattr(m, 'no_ask', 0) or 0
                    yes_bid = getattr(m, 'yes_bid', 0) or 0
                    no_bid = getattr(m, 'no_bid', 0) or 0

                    ticker = getattr(m, 'ticker', '')
                    title = getattr(m, 'title', '')
                    subtitle = getattr(m, 'subtitle', '')
                    floor_strike = getattr(m, 'floor_strike', None)
                    cap_strike = getattr(m, 'cap_strike', None)

                    # Price to beat 추출 (floor_strike 또는 subtitle에서)
                    strike_price = None
                    if floor_strike is not None:
                        try:
                            strike_price = float(floor_strike)
                        except (ValueError, TypeError):
                            pass
                    if strike_price is None and subtitle:
                        match = re.search(r'\$?([\d,]+\.?\d*)', str(subtitle))
                        if match:
                            try:
                                strike_price = float(match.group(1).replace(',', ''))
                            except ValueError:
                                pass

                    # 오더북에서 실시간 가격 조회
                    ob_prices = self._get_orderbook_prices(ticker)
                    real_yes_ask = ob_prices["yes_ask"]
                    real_no_ask = ob_prices["no_ask"]

                    # 오더북 가격만 사용 (get_markets 폴백 금지! → 한쪽 체결 사고 원인)
                    yes_ask = int(round(real_yes_ask)) if real_yes_ask > 0 else 0
                    no_ask = int(round(real_no_ask)) if real_no_ask > 0 else 0

                    market_data = {
                        "coin": c,
                        "ticker": ticker,
                        "title": title,
                        "yes_ask": yes_ask,
                        "no_ask": no_ask,
                        "yes_bid": yes_bid,
                        "no_bid": no_bid,
                        "strike_price": strike_price,
                        "close_time": str(close_time) if close_time else "",
                    }
                    all_markets.append(market_data)
                    logger.debug(
                        f"[KALSHI] {c} | {ticker} | YES={yes_ask}¢ NO={no_ask}¢ "
                        f"(OB: YES={real_yes_ask:.1f}¢ NO={real_no_ask:.1f}¢)"
                    )

            return all_markets

        except Exception as e:
            logger.error(f"Kalshi market error: {e}")
            return []

    def place_market_order(self, ticker: str, side: str, yes_or_no: str, count: int, price: int = 0) -> dict:
        """Kalshi 지정가 주문

        Args:
            ticker: 마켓 티커
            side: "buy" or "sell"
            yes_or_no: "yes" or "no"
            count: 수량
            price: 주문 가격 (센트). 0이면 주문 거부 (빈 오더북 방어)
        """

        if not self._initialized:
            logger.error("[KALSHI] Client not initialized")
            return {"error": "Client not initialized"}

        if price <= 0:
            logger.error(f"[KALSHI] 가격 미지정 → 주문 거부 (빈 오더북 방어): {ticker}")
            return {"error": "No detected price - refusing blind order"}

        try:
            if side == "buy":
                # 매수: 지정가 (80¢)
                order_type = "limit"
                order_price = price
                price_label = f"{price}¢ LIMIT"
            else:
                # 매도(손절): 시장가 (1¢)
                order_type = "market"
                order_price = 1
                price_label = "MARKET (1¢)"

            order_params = {
                "ticker": ticker,
                "action": side,
                "side": yes_or_no,
                "type": order_type,
                "count": count,
            }
            if yes_or_no == "yes":
                order_params["yes_price"] = order_price
            else:
                order_params["no_price"] = order_price

            logger.warning(f"[KALSHI] Order: {side} {yes_or_no} x{count} @ {price_label} on {ticker}")
            response = self.client.create_order(**order_params)
            logger.warning(f"[KALSHI] Order response: {response}")
            if hasattr(response, '__dict__'):
                d = vars(response)
                # SDK 응답이 {'order': Order(...)} 구조일 때 → 내부 Order를 flat dict로 변환
                if 'order' in d and hasattr(d['order'], '__dict__'):
                    return vars(d['order'])
                return d
            return response if isinstance(response, dict) else {"response": str(response)}
        except Exception as e:
            logger.error(f"[KALSHI] Order error: {e}")
            return {"error": str(e)}

    def cancel_order(self, order_id: str) -> dict:
        """미체결 주문 취소"""
        if not self._initialized:
            return {"error": "Client not initialized"}
        try:
            response = self.client.cancel_order(order_id)
            logger.warning(f"[KALSHI] 주문 취소 완료: {order_id}")
            if hasattr(response, '__dict__'):
                return vars(response)
            return response if isinstance(response, dict) else {"response": str(response)}
        except Exception as e:
            logger.warning(f"[KALSHI] 주문 취소 실패: {order_id} → {e}")
            return {"error": str(e)}

    def get_balance(self) -> float:
        if not self._initialized:
            return 0.0
        try:
            balance = self.client.get_balance()
            return balance.balance / 100 if hasattr(balance, 'balance') else 0.0
        except Exception as e:
            logger.error(f"[KALSHI] Balance error: {e}")
            return 0.0
