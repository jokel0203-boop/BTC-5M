"""
Polymarket API - 15분 크립토 마켓 (CLOB 오더북 실시간 가격 사용)

핵심:
- 15분 마켓 slug 패턴: {coin}-updown-15m-{unix_timestamp}
- Gamma API: 마켓 메타데이터 (slug, tokenIds) 조회
- CLOB API: 실시간 오더북에서 bestAsk/bestBid + 수량 조회
- 매 15분마다 새 마켓 생성됨
"""
import base64
import hashlib
import hmac as hmac_mod
import json
import os
import re
import time
import threading
import traceback
import requests
from datetime import datetime, timezone
from loguru import logger

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType, OrderArgs, MarketOrderArgs, OrderType, PartialCreateOrderOptions
    from py_clob_client.order_builder.constants import BUY as CLOB_BUY, SELL as CLOB_SELL
except ImportError:
    ClobClient = None
    ApiCreds = None
    BalanceAllowanceParams = None
    AssetType = None
    OrderArgs = None
    MarketOrderArgs = None
    OrderType = None
    PartialCreateOrderOptions = None
    CLOB_BUY = None
    CLOB_SELL = None

CLOB_URL = "https://clob.polymarket.com"
GAMMA_URL = "https://gamma-api.polymarket.com"
CHAIN_ID = 137


class PolymarketClient:
    def __init__(self):
        self.api_key = os.getenv("POLYMARKET_API_KEY")
        self.api_secret = os.getenv("POLYMARKET_SECRET")
        self.passphrase = os.getenv("POLYMARKET_PASSPHRASE")
        self.private_key = os.getenv("POLYMARKET_PRIVATE_KEY")
        self.funder = os.getenv("POLYMARKET_FUNDER_ADDRESS")
        self.client = None
        self._initialized = False
        self._warmed_tokens = set()  # SDK 캐시 pre-warm 완료 토큰
        self._last_session_warm = 0  # requests.Session 마지막 활성 시간
        # HTTP 세션 (연결 재사용 → TCP/TLS 핸드셰이크 1회만)
        self._session = requests.Session()
        self._session.headers.update({"Connection": "keep-alive"})

    def connect(self) -> bool:
        try:
            if not ClobClient:
                logger.error("py_clob_client not installed")
                return False
            if not self.private_key:
                logger.error("POLYMARKET_PRIVATE_KEY not set")
                return False

            # 프록시 지갑 사용 (Polymarket 웹사이트 가입 사용자)
            if self.funder:
                # funder 주소 정리: 공백/따옴표/특수문자 제거
                import re
                clean_funder = self.funder.strip().strip('"').strip("'").strip()
                # 0x + 40 hex chars 추출
                match = re.search(r'(0x[0-9a-fA-F]{40})', clean_funder)
                if not match:
                    logger.error(f"[POLY] Invalid funder address (len={len(clean_funder)}): {repr(self.funder)}")
                    return False
                clean_funder = match.group(1)
                logger.info(f"[POLY] Proxy wallet: {clean_funder}")

                # signature_type=1 (POLY_PROXY) - 프록시 지갑에 적합
                self.client = ClobClient(
                    host=CLOB_URL, chain_id=CHAIN_ID,
                    key=self.private_key,
                    signature_type=1,
                    funder=clean_funder
                )
                new_creds = self.client.create_or_derive_api_creds()
            else:
                logger.warning("[POLY] POLYMARKET_FUNDER_ADDRESS 미설정 → EOA 모드")
                self.client = ClobClient(
                    host=CLOB_URL, chain_id=CHAIN_ID,
                    key=self.private_key, signature_type=0
                )
                new_creds = self.client.derive_api_key()

            self.client.set_api_creds(new_creds)
            self._setup_allowances()
            self._initialized = True
            # SDK httpx 타임아웃 확장 (기본 5초 → 15초, ReadTimeout 방지)
            try:
                from py_clob_client.http_helpers.helpers import _http_client
                import httpx
                _http_client._transport = httpx.HTTPTransport(http2=True)
                _http_client._timeout = httpx.Timeout(15.0)
            except Exception:
                pass
            # HTTP 연결 pre-warm (TCP/TLS 핸드셰이크 1회 → 이후 재사용)
            try:
                self._session.get(f"{CLOB_URL}/time", timeout=3)
            except Exception:
                pass
            # POST /order 경로도 pre-warm (requests.Session은 host별 연결 풀이지만 확실히)
            self._last_session_warm = time.monotonic()
            logger.info(f"Polymarket connected (proxy={'yes' if self.funder else 'no'})")
            return True

        except Exception as e:
            logger.error(f"Polymarket error: {e}")
            logger.error(f"[POLY] Connect traceback:\n{traceback.format_exc()}")
            return False

    def _setup_allowances(self):
        """USDC allowance 승인 (거래 전 필수)

        조건부 토큰(CONDITIONAL)은 ERC-1155이므로 특정 token_id 필요.
        → 매수 후 approve_token_for_sell()에서 개별 승인.
        """
        if not self.client or not BalanceAllowanceParams:
            return
        try:
            # USDC (collateral) 승인 → 매수 시 필요
            self.client.update_balance_allowance(
                params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            logger.info("[POLY] USDC allowance approved")
        except Exception as e:
            logger.warning(f"[POLY] USDC allowance error: {e}")

    def approve_token_for_sell(self, token_id: str):
        """특정 조건부 토큰의 allowance 승인 (매도 전 필수!)

        ERC-1155은 token_id가 필수. 일반 CONDITIONAL 호출은 assetId=-1로 실패.
        매수 직후 + 매도 직전에 호출하여 매도 가능하도록 보장.
        """
        if not self.client or not BalanceAllowanceParams or not token_id:
            return
        try:
            self.client.update_balance_allowance(
                params=BalanceAllowanceParams(
                    asset_type=AssetType.CONDITIONAL,
                    token_id=token_id
                )
            )
            logger.info(f"[POLY] Token allowance approved: {token_id[:16]}...")
        except Exception as e:
            logger.warning(f"[POLY] Token allowance error ({token_id[:16]}...): {e}")

    def check_conditional_balance(self, token_id: str) -> dict:
        """조건부 토큰 잔고 및 allowance 확인 (매도 전 디버깅용)"""
        if not self.client or not BalanceAllowanceParams:
            return {}
        try:
            params = BalanceAllowanceParams(
                asset_type=AssetType.CONDITIONAL,
                token_id=token_id
            )
            result = self.client.get_balance_allowance(params)
            logger.warning(f"[POLY] Balance/allowance for {token_id[:16]}...: {result}")
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as e:
            logger.warning(f"[POLY] Balance check error: {e}")
            return {"error": str(e)}

    def refresh_conditional_allowance(self, token_id: str = ""):
        """조건부 토큰 allowance 갱신 (매도 전 호출)

        ERC-1155은 token_id 필수! token_id 없으면 assetId=-1로 API 거부됨.
        """
        if not self.client or not BalanceAllowanceParams:
            return
        if not token_id:
            logger.warning("[POLY] refresh_conditional_allowance: token_id 없음 → 스킵")
            return
        try:
            self.client.update_balance_allowance(
                params=BalanceAllowanceParams(
                    asset_type=AssetType.CONDITIONAL,
                    token_id=token_id
                )
            )
            logger.info(f"[POLY] Token allowance refreshed: {token_id[:16]}...")
        except Exception as e:
            logger.warning(f"[POLY] Allowance refresh error: {e}")

    def keep_session_warm(self):
        """requests.Session TCP 연결 유지 (30초 이상 idle 방지)

        스캔 루프에서 주기적 호출 → POST /order 시 TCP 재연결 방지.
        _get_book_prices()가 매 스캔마다 호출되므로 보통 불필요하지만,
        WS 모드에서 REST 호출 빈도가 낮을 때 유용.
        """
        now = time.monotonic()
        if hasattr(self, '_last_session_warm') and (now - self._last_session_warm) < 25:
            return  # 25초 이내 → 아직 warm
        try:
            self._session.get(f"{CLOB_URL}/time", timeout=2)
            self._last_session_warm = now
        except Exception:
            pass

    def _post_order_fast(self, signed_order, order_type="FOK"):
        """SDK httpx 우회 → requests.Session으로 직접 POST /order

        requests.Session은 market discovery(_get_book_prices) 시
        clob.polymarket.com에 이미 TCP/TLS 연결이 warm 상태.
        SDK httpx는 별도 연결 풀 → 주문 시 cold connection 가능 → 추가 지연.
        이 메서드로 ~200-500ms 절약 가능.
        """
        # 1. Body 생성 (SDK order_to_json과 동일)
        body = {
            "order": signed_order.dict(),
            "owner": self.client.creds.api_key,
            "orderType": order_type,
            "postOnly": False,
        }
        serialized = json.dumps(body, separators=(",", ":"), ensure_ascii=False)

        # 2. HMAC 서명 (SDK build_hmac_signature와 동일)
        timestamp = str(int(time.time()))
        message = timestamp + "POST" + "/order" + serialized
        secret_bytes = base64.urlsafe_b64decode(self.client.creds.api_secret)
        sig = base64.urlsafe_b64encode(
            hmac_mod.new(secret_bytes, message.encode("utf-8"), hashlib.sha256).digest()
        ).decode("utf-8")

        # 3. Level 2 인증 헤더
        headers = {
            "POLY_ADDRESS": self.client.signer.address(),
            "POLY_SIGNATURE": sig,
            "POLY_TIMESTAMP": timestamp,
            "POLY_API_KEY": self.client.creds.api_key,
            "POLY_PASSPHRASE": self.client.creds.api_passphrase,
            "Content-Type": "application/json",
            "User-Agent": "py_clob_client",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }

        # 4. requests.Session으로 POST (warm TCP/TLS 연결 재사용)
        r = self._session.post(
            f"{CLOB_URL}/order",
            data=serialized.encode("utf-8"),
            headers=headers,
            timeout=10,
        )

        if r.status_code != 200:
            raise Exception(f"POST /order HTTP {r.status_code}: {r.text[:300]}")

        return r.json()

    def _pre_warm_sdk_cache(self, token_id: str):
        """SDK 내부 캐시 pre-warm (주문 시 tick_size/neg_risk/fee_rate HTTP 호출 제거)"""
        if not self.client or not token_id or token_id in self._warmed_tokens:
            return
        try:
            self.client.get_tick_size(token_id)
            self.client.get_neg_risk(token_id)
            self.client.get_fee_rate_bps(token_id)
            self._warmed_tokens.add(token_id)
        except Exception:
            pass

    def _get_current_timestamps(self):
        """현재 15분 슬롯과 주변 timestamp 반환 (현재 슬롯 우선)"""
        now = int(time.time())
        interval = 15 * 60  # 15분
        current = (now // interval) * interval
        # 현재 → 다음 → 이전 순서 (만기 직전 마켓 방지)
        return [current, current + interval, current - interval]

    def _get_book_prices(self, token_id: str, qty: int = 10) -> dict:
        """CLOB 오더북에서 qty 수량의 가중평균 체결가 조회

        qty만큼 체결했을 때의 평균 가격을 계산 (오더북 깊이 반영).
        주의: CLOB API는 asks/bids를 정렬 없이 반환하므로 정렬 필수.
        """
        result = {"best_ask": 0, "best_bid": 0, "ask_size": 0, "bid_size": 0}
        if not token_id:
            return result
        try:
            url = f"{CLOB_URL}/book?token_id={token_id}"
            logger.debug(f"[CLOB] Fetching book: {token_id[:16]}...")
            r = self._session.get(url, timeout=5)
            if r.status_code != 200:
                logger.warning(f"[CLOB] HTTP {r.status_code} for {token_id[:16]}...")
                return result
            data = r.json()
            asks = data.get("asks", [])
            bids = data.get("bids", [])
            logger.debug(f"[CLOB] token={token_id[:16]}... asks={len(asks)} bids={len(bids)}")
            if asks:
                sorted_asks = sorted(asks, key=lambda x: float(x.get("price", 0)))
                # qty 수량의 가중평균 체결가 계산
                remaining = qty
                total_cost = 0.0
                total_filled = 0
                for level in sorted_asks:
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
                if total_filled > 0:
                    result["best_ask"] = total_cost / total_filled
                    result["ask_size"] = total_filled
            if bids:
                sorted_bids = sorted(bids, key=lambda x: float(x.get("price", 0)), reverse=True)
                result["best_bid"] = float(sorted_bids[0].get("price", 0))
                result["bid_size"] = int(float(sorted_bids[0].get("size", 0)))
        except Exception as e:
            logger.warning(f"[POLY] Book price error for {token_id}: {e}")
        return result

    def get_crypto_markets(self, coin: str = None) -> list:
        """15분 크립토 마켓 조회 - CLOB 오더북에서 실시간 가격 사용"""
        try:
            coins = [coin.upper()] if coin else ["BTC", "ETH", "SOL"]
            all_markets = []
            timestamps = self._get_current_timestamps()

            for c in coins:
                prefix = c.lower()

                for ts in timestamps:
                    slug = f"{prefix}-updown-15m-{ts}"

                    try:
                        url = f"{GAMMA_URL}/events?slug={slug}"
                        logger.debug(f"[POLY] Checking slug: {slug}")
                        r = self._session.get(url, timeout=5)
                        data = r.json()

                        if not data or len(data) == 0:
                            logger.debug(f"[POLY] Slug not found: {slug}")
                            continue

                        event = data[0] if isinstance(data, list) else data
                        markets = event.get("markets", [])

                        # 이벤트 description에서 기준가격(Price to beat) 추출
                        poly_strike = None
                        for text_field in [event.get("description", ""), event.get("title", "")]:
                            if text_field:
                                price_match = re.search(r'\$?([\d,]+\.?\d*)', str(text_field))
                                if price_match:
                                    try:
                                        val = float(price_match.group(1).replace(',', ''))
                                        if val > 100:  # 코인 가격은 최소 $100 이상
                                            poly_strike = val
                                            break
                                    except ValueError:
                                        pass

                        # 현재 코인 가격 추출 (Polymarket 이벤트 데이터에서)
                        poly_current_price = None
                        for field_name in ['currentPrice', 'current_price', 'oraclePrice',
                                           'oracle_price', 'startingPrice', 'starting_price',
                                           'referencePrice', 'reference_price', 'price']:
                            val = event.get(field_name)
                            if val is not None:
                                try:
                                    fval = float(val)
                                    if fval > 100:  # 코인 가격 (>$100)
                                        poly_current_price = fval
                                        logger.debug(f"[POLY] 현재가 발견: {field_name}={fval}")
                                        break
                                except (ValueError, TypeError):
                                    pass

                        for m in markets:
                            if m.get("closed"):
                                continue

                            # 마켓에서도 현재가 추출 시도
                            if poly_current_price is None:
                                for field_name in ['currentPrice', 'current_price', 'oraclePrice',
                                                   'oracle_price', 'startingPrice', 'price']:
                                    val = m.get(field_name)
                                    if val is not None:
                                        try:
                                            fval = float(val)
                                            if fval > 100:
                                                poly_current_price = fval
                                                logger.debug(f"[POLY] 현재가 발견 (market): {field_name}={fval}")
                                                break
                                        except (ValueError, TypeError):
                                            pass

                            # 마켓 description에서도 기준가격 추출 시도
                            if poly_strike is None:
                                for mfield in [m.get("question", ""), m.get("description", "")]:
                                    if mfield:
                                        price_match = re.search(r'\$?([\d,]+\.?\d*)', str(mfield))
                                        if price_match:
                                            try:
                                                val = float(price_match.group(1).replace(',', ''))
                                                if val > 100:
                                                    poly_strike = val
                                                    break
                                            except ValueError:
                                                pass

                            # 토큰 ID 추출 (CLOB 오더북 조회용)
                            # Gamma API가 clobTokenIds를 JSON 문자열로 반환할 수 있음
                            tokens = m.get("clobTokenIds", [])
                            if isinstance(tokens, str):
                                tokens = json.loads(tokens)
                            up_token = tokens[0] if len(tokens) > 0 else ""
                            down_token = tokens[1] if len(tokens) > 1 else ""

                            # SDK 캐시 pre-warm (동기 - 시장 발견 시 300ms 블로킹하여 주문 경로 0ms 보장)
                            self._pre_warm_sdk_cache(up_token)
                            self._pre_warm_sdk_cache(down_token)

                            # CLOB 오더북에서 실시간 가격 조회
                            logger.debug(f"[POLY] Token IDs - UP: {up_token[:16]}... DOWN: {down_token[:16]}..." if up_token else "[POLY] Token IDs EMPTY!")
                            up_book = self._get_book_prices(up_token)
                            down_book = self._get_book_prices(down_token)

                            up_ask = up_book["best_ask"]
                            down_ask = down_book["best_ask"]
                            up_ask_size = up_book["ask_size"]
                            down_ask_size = down_book["ask_size"]

                            # 각 토큰의 오더북에서 직접 가격 사용 (asks 없으면 매수 불가 = 0)
                            up_price = up_ask * 100 if up_ask > 0 else 0
                            down_price = down_ask * 100 if down_ask > 0 else 0

                            # CLOB 실패 시 Gamma API bestAsk/bestBid로 폴백
                            if up_price == 0 and down_price == 0:
                                best_ask = m.get("bestAsk")
                                best_bid = m.get("bestBid")
                                if best_ask:
                                    up_price = float(best_ask) * 100
                                if best_bid:
                                    down_price = (1 - float(best_bid)) * 100
                                logger.warning(
                                    f"[POLY] CLOB 실패, Gamma 폴백: "
                                    f"UP={up_price:.1f}¢ DOWN={down_price:.1f}¢"
                                )

                            if up_price == 0 and down_price == 0:
                                logger.warning(f"[POLY] {c} | {slug} | 가격 조회 실패 (CLOB+Gamma 모두 0)")
                                continue

                            market_data = {
                                "coin": c,
                                "slug": slug,
                                "title": event.get("title", ""),
                                "condition_id": m.get("conditionId", ""),
                                "up_price": up_price,
                                "down_price": down_price,
                                "up_token": up_token,
                                "down_token": down_token,
                                "up_ask_size": up_ask_size,
                                "down_ask_size": down_ask_size,
                                "active": m.get("active", True),
                                "closed": m.get("closed", False),
                                "strike_price": poly_strike,
                                "current_price": poly_current_price,
                            }
                            all_markets.append(market_data)
                            logger.debug(
                                f"[POLY] {c} | Slug: {slug} | "
                                f"UP={up_price:.1f}¢ (qty:{up_ask_size}) "
                                f"DOWN={down_price:.1f}¢ (qty:{down_ask_size})"
                            )
                            break

                    except Exception as e:
                        logger.warning(f"[POLY] Error for {slug}: {e}")
                        continue

                    if any(m["coin"] == c for m in all_markets):
                        break

            return all_markets

        except Exception as e:
            logger.error(f"Polymarket error: {e}")
            return []

    def get_orderbook(self, token_id: str) -> dict:
        """오더북 조회 - 수량 확인용"""
        if not token_id:
            return {"asks": [], "bids": []}
        try:
            url = f"{CLOB_URL}/book?token_id={token_id}"
            r = self._session.get(url, timeout=5)
            data = r.json()
            return {
                "asks": data.get("asks", []),
                "bids": data.get("bids", [])
            }
        except Exception as e:
            logger.debug(f"Orderbook error: {e}")
            return {"asks": [], "bids": []}

    def cancel_order(self, order_id: str) -> dict:
        """주문 취소 (GTC resting 주문용)"""
        if not self.client or not order_id:
            return {"error": "client or order_id missing"}
        try:
            result = self.client.cancel(order_id)
            logger.warning(f"[POLY] 주문 취소: {order_id[:16]}... → {result}")
            return result if isinstance(result, dict) else {"result": str(result)}
        except Exception as e:
            logger.warning(f"[POLY] 취소 실패: {order_id[:16]}... → {e}")
            return {"error": str(e)}

    def place_market_order(self, token_id: str, side: str, size: int, price: float = 0, is_no: bool = False) -> dict:
        """Polymarket 마켓 주문 (SDK create_market_order 사용)

        웹사이트 Market 주문과 동일 방식:
        - BUY: amount = USDC 예산 (감지가 × 수량), SDK가 오더북에서 최적가 자동 계산
        - SELL: amount = 매도 수량 (주), SDK가 오더북에서 최적가 자동 계산
        - FOK (Fill or Kill): 전량 체결 또는 전량 취소

        Args:
            token_id: CLOB token ID
            side: "BUY" or "SELL"
            size: 거래 수량 (주)
            price: 감지 가격 (센트). BUY 시 USDC 예산 계산에 사용
            is_no: 미사용
        """
        if not self.client:
            logger.error("[POLY] Client not initialized")
            return {"error": "Client not initialized"}

        try:
            order_side = CLOB_BUY if side.upper() == "BUY" else CLOB_SELL

            if price > 0:
                price_decimal = price / 100.0
            else:
                book = self._get_book_prices(token_id)
                price_decimal = book["best_ask"] if order_side == CLOB_BUY else book["best_bid"]
                if price_decimal <= 0:
                    return {"error": "No price available"}

            # BUY: 지정가 주문 (FOK) - 정확히 price_decimal에 매수 (시장가 아님!)
            # SELL: 시장가 주문 (FOK) - 빠른 손절
            t_sign_start = time.monotonic()
            if order_side == CLOB_BUY:
                # 지정가: price_decimal(예: 0.80)에 size주 매수
                order_args = OrderArgs(
                    price=price_decimal,
                    size=size,
                    side=order_side,
                    token_id=token_id,
                )
                signed_order = self.client.create_order(order_args)
            else:
                # 매도: 시장가 (빠른 손절)
                market_order = MarketOrderArgs(
                    token_id=token_id,
                    amount=float(size),
                    price=0.01,
                    side=order_side,
                )
                signed_order = self.client.create_market_order(market_order)
            t_sign_end = time.monotonic()

            # BUY: GTC (maker 주문, resting 가능) / SELL: FOK (즉시 체결)
            post_order_type = "GTC" if order_side == CLOB_BUY else "FOK"

            # Fast path: requests.Session으로 직접 POST (warm TCP 재사용)
            # SDK httpx는 별도 연결 풀 → cold connection 시 +500ms
            try:
                response = self._post_order_fast(signed_order, order_type=post_order_type)
                t_post_end = time.monotonic()
                logger.warning(
                    f"[POLY] FAST POST: sign={int((t_sign_end-t_sign_start)*1000)}ms "
                    f"post={int((t_post_end-t_sign_end)*1000)}ms "
                    f"total={int((t_post_end-t_sign_start)*1000)}ms"
                )
            except Exception as fast_err:
                logger.warning(f"[POLY] Fast POST failed ({fast_err}), falling back to SDK...")
                sdk_order_type = OrderType.GTC if order_side == CLOB_BUY else OrderType.FOK
                response = self.client.post_order(signed_order, sdk_order_type)
                t_post_end = time.monotonic()
                logger.warning(
                    f"[POLY] SDK POST: sign={int((t_sign_end-t_sign_start)*1000)}ms "
                    f"post={int((t_post_end-t_sign_end)*1000)}ms"
                )

            order_desc = f"{size}주 @ {price_decimal:.2f}" if order_side == CLOB_BUY else f"{size}주 매도"
            logger.warning(
                f"[POLY] LIMIT {side}: {order_desc} "
                f"(detected={price_decimal:.4f}) → {response.get('status', 'unknown') if isinstance(response, dict) else 'ok'}"
            )
            return response if isinstance(response, dict) else {"response": str(response)}

        except Exception as e:
            logger.error(f"[POLY] Order error: {e}")
            logger.error(f"[POLY] Traceback:\n{traceback.format_exc()}")
            return {"error": str(e)}
