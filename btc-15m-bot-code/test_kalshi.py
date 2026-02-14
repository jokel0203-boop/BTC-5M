"""Kalshi API 디버그 테스트 - 오더북 가격 확인"""
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

try:
    import kalshi_python
except ImportError:
    print("ERROR: kalshi-python 패키지 필요 → pip install kalshi-python")
    sys.exit(1)

KALSHI_API_URL = "https://api.elections.kalshi.com/trade-api/v2"


def connect():
    """Kalshi API 연결"""
    key_id = os.getenv("KALSHI_API_KEY_ID")
    key_file = os.getenv("KALSHI_PRIVATE_KEY_FILE")
    if key_file and os.path.exists(key_file):
        with open(key_file, 'r') as f:
            private_key = f.read()
    else:
        private_key = os.getenv("KALSHI_PRIVATE_KEY")

    if not key_id or not private_key:
        print(f"ERROR: API key 미설정 (key_id={'SET' if key_id else 'MISSING'}, pem={'SET' if private_key else 'MISSING'})")
        sys.exit(1)

    config = kalshi_python.Configuration()
    config.host = KALSHI_API_URL
    config.api_key_id = key_id
    config.private_key_pem = private_key
    client = kalshi_python.KalshiClient(configuration=config)

    print(f"  key_id: {key_id[:8]}...")
    return client


def calc_fill_price(sorted_bids, qty):
    """오더북에서 qty 수량의 가중평균 체결가 (센트)"""
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
        return 0, qty - remaining
    return total_cost / qty, qty


def main():
    coins = sys.argv[1:] if len(sys.argv) > 1 else ["BTC", "ETH", "SOL"]
    qty = 10

    print("=== Kalshi API 디버그 테스트 ===")
    print(f"시간: {datetime.now(timezone.utc).isoformat()}")
    print(f"코인: {', '.join(coins)}  |  체결 수량: {qty}")

    # Step 1: 연결
    print("\n--- Step 1: API 연결 ---")
    client = connect()

    # 잔고
    try:
        balance = client.get_balance()
        bal_cents = balance.balance if hasattr(balance, 'balance') else 0
        print(f"  잔고: {bal_cents}¢ (${bal_cents / 100:.2f})")
    except Exception as e:
        print(f"  잔고 조회 실패: {e}")

    # Step 2: 마켓 찾기
    series_map = {"BTC": "KXBTC15M", "ETH": "KXETH15M", "SOL": "KXSOL15M"}
    now = datetime.now(timezone.utc)

    for coin in coins:
        series = series_map.get(coin.upper())
        if not series:
            print(f"\n  [{coin}] 시리즈 미지원")
            continue

        print(f"\n{'=' * 70}")
        print(f"  [{coin}] 시리즈: {series}")
        print(f"{'=' * 70}")

        try:
            response = client.get_markets(status="open", series_ticker=series)
            markets = response.markets if hasattr(response, 'markets') else []
        except Exception as e:
            print(f"  마켓 조회 실패: {e}")
            continue

        if not markets:
            print("  열린 마켓 없음")
            continue

        for m in markets:
            ticker = getattr(m, 'ticker', '?')
            title = getattr(m, 'title', '')
            subtitle = getattr(m, 'subtitle', '')
            close_time = getattr(m, 'close_time', None)
            floor_strike = getattr(m, 'floor_strike', None)
            cap_strike = getattr(m, 'cap_strike', None)
            stale_yes_ask = getattr(m, 'yes_ask', 0) or 0
            stale_no_ask = getattr(m, 'no_ask', 0) or 0

            # 종료 시간 필터
            if close_time:
                try:
                    if isinstance(close_time, str):
                        end_time = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                    elif isinstance(close_time, datetime):
                        end_time = close_time if close_time.tzinfo else close_time.replace(tzinfo=timezone.utc)
                    else:
                        end_time = None
                    if end_time and end_time < now:
                        continue
                except Exception:
                    pass

            print(f"\n  --- {ticker} ---")
            print(f"  제목: {title}")
            print(f"  부제: {subtitle}")
            print(f"  종료: {close_time}")
            print(f"  strike: floor={floor_strike}  cap={cap_strike}")
            print(f"  get_markets 가격 (STALE!): YES={stale_yes_ask}¢  NO={stale_no_ask}¢")

            # Step 3: 오더북 직접 조회
            print(f"\n  [오더북 조회: {ticker}]")
            try:
                ob = client.get_market_orderbook(ticker, depth=20)

                yes_bids = []
                no_bids = []

                inner = getattr(ob, 'orderbook', None)
                if inner is not None:
                    raw_yes = getattr(inner, 'var_true', None) or []
                    raw_no = getattr(inner, 'var_false', None) or []
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

                # dict 폴백
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

                # YES bids (var_true) 표시
                sorted_yes = sorted(yes_bids, key=lambda x: x[0], reverse=True)
                print(f"  YES bids (var_true) [{len(sorted_yes)}개]:")
                if sorted_yes:
                    for price, count in sorted_yes[:10]:
                        print(f"    {price}¢ x {count}")
                else:
                    print("    (비어있음)")

                # NO bids (var_false) 표시
                sorted_no = sorted(no_bids, key=lambda x: x[0], reverse=True)
                print(f"  NO bids (var_false) [{len(sorted_no)}개]:")
                if sorted_no:
                    for price, count in sorted_no[:10]:
                        print(f"    {price}¢ x {count}")
                else:
                    print("    (비어있음)")

                # 가격 계산
                print(f"\n  [가격 계산 (qty={qty})]")

                if sorted_no:
                    yes_ask, yes_filled = calc_fill_price(sorted_no, qty)
                    best_yes_ask = 100 - sorted_no[0][0]
                    print(f"  YES ask = 100 - best NO bid = 100 - {sorted_no[0][0]} = {best_yes_ask}¢  (가중평균: {yes_ask:.1f}¢, {yes_filled}주 체결)")
                else:
                    print("  YES ask = N/A (NO bids 비어있음)")

                if sorted_yes:
                    no_ask, no_filled = calc_fill_price(sorted_yes, qty)
                    best_no_ask = 100 - sorted_yes[0][0]
                    print(f"  NO ask  = 100 - best YES bid = 100 - {sorted_yes[0][0]} = {best_no_ask}¢  (가중평균: {no_ask:.1f}¢, {no_filled}주 체결)")
                else:
                    print("  NO ask  = N/A (YES bids 비어있음)")

                # 합계 (YES + NO)
                if sorted_no and sorted_yes:
                    yes_ask_val, _ = calc_fill_price(sorted_no, qty)
                    no_ask_val, _ = calc_fill_price(sorted_yes, qty)
                    if yes_ask_val > 0 and no_ask_val > 0:
                        combo = yes_ask_val + no_ask_val
                        print(f"\n  YES + NO = {yes_ask_val:.1f} + {no_ask_val:.1f} = {combo:.1f}¢  (100 이하면 차익)")

            except Exception as e:
                print(f"  오더북 조회 실패: {e}")
                import traceback
                traceback.print_exc()

    print(f"\n{'=' * 70}")
    print("=== Done ===")


if __name__ == "__main__":
    main()
