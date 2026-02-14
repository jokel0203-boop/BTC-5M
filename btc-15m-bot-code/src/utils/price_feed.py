"""현재 코인 가격 조회 (Binance API)"""
import time
import requests
from loguru import logger

_cache = {}  # {coin: (timestamp, price)}
CACHE_TTL = 2  # 2초 캐시 (API 과다 호출 방지)


def get_current_price(coin: str) -> float:
    """Binance에서 현재 코인 가격 조회

    2초 캐시로 같은 스캔 루프 내 중복 호출 방지.
    실패 시 캐시된 가격 반환 (없으면 0).
    """
    now = time.time()
    cached = _cache.get(coin)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1]

    symbol_map = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}
    symbol = symbol_map.get(coin.upper())
    if not symbol:
        return 0.0

    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        r = requests.get(url, timeout=2)
        price = float(r.json()["price"])
        _cache[coin] = (now, price)
        return price
    except Exception as e:
        logger.warning(f"[PRICE] Binance error for {coin}: {e}")
        return cached[1] if cached else 0.0
