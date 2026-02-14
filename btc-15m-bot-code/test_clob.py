"""CLOB API 디버그 테스트 - 왜 오더북이 안 되는지 확인"""
import time
import requests

GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"

# 1) 현재 BTC 15분 마켓 찾기
now = int(time.time())
interval = 15 * 60
timestamps = [(now // interval) * interval + i * interval for i in range(-1, 2)]

print("=== Step 1: Gamma API에서 BTC 마켓 찾기 ===")
market = None
for ts in timestamps:
    slug = f"btc-updown-15m-{ts}"
    try:
        r = requests.get(f"{GAMMA_URL}/events?slug={slug}", timeout=10)
        data = r.json()
        if data and len(data) > 0:
            event = data[0]
            markets = event.get("markets", [])
            for m in markets:
                if not m.get("closed"):
                    market = m
                    print(f"  Found: {slug}")
                    print(f"  bestAsk: {m.get('bestAsk')}")
                    print(f"  bestBid: {m.get('bestBid')}")
                    print(f"  outcomePrices: {m.get('outcomePrices')}")
                    print(f"  clobTokenIds: {m.get('clobTokenIds')}")
                    break
        if market:
            break
    except Exception as e:
        print(f"  Error: {e}")

if not market:
    print("  No market found!")
    exit()

# 2) Token IDs 확인
tokens = market.get("clobTokenIds", [])
up_token = tokens[0] if len(tokens) > 0 else ""
down_token = tokens[1] if len(tokens) > 1 else ""

print(f"\n=== Step 2: Token IDs ===")
print(f"  UP token:   {up_token}")
print(f"  DOWN token: {down_token}")

if not up_token:
    print("  ERROR: Token IDs are empty!")
    exit()

# 3) CLOB API 직접 호출
print(f"\n=== Step 3: CLOB API 오더북 호출 ===")
for label, token_id in [("UP", up_token), ("DOWN", down_token)]:
    try:
        url = f"{CLOB_URL}/book?token_id={token_id}"
        print(f"\n  [{label}] URL: {url[:80]}...")
        r = requests.get(url, timeout=10)
        print(f"  [{label}] Status: {r.status_code}")
        print(f"  [{label}] Response (first 500 chars): {r.text[:500]}")

        data = r.json()
        asks = data.get("asks", [])
        bids = data.get("bids", [])
        print(f"  [{label}] Asks count: {len(asks)}, Bids count: {len(bids)}")

        if asks:
            sorted_asks = sorted(asks, key=lambda x: float(x.get("price", 0)))
            print(f"  [{label}] Best ask (sorted): {sorted_asks[0]}")
        else:
            print(f"  [{label}] NO ASKS!")

        if bids:
            sorted_bids = sorted(bids, key=lambda x: float(x.get("price", 0)), reverse=True)
            print(f"  [{label}] Best bid (sorted): {sorted_bids[0]}")
        else:
            print(f"  [{label}] NO BIDS!")

    except Exception as e:
        print(f"  [{label}] ERROR: {e}")

print("\n=== Done ===")
