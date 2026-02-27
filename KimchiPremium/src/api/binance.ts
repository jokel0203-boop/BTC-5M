import { BinanceTicker } from '../types';

const BINANCE_API = 'https://api.binance.com/api/v3';

export async function getBinanceTickers(): Promise<Map<string, number>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${BINANCE_API}/ticker/price`, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data: BinanceTicker[] = await res.json();
    const priceMap = new Map<string, number>();

    for (const ticker of data) {
      if (ticker.symbol.endsWith('USDT')) {
        const symbol = ticker.symbol.replace('USDT', '');
        priceMap.set(symbol, parseFloat(ticker.price));
      }
    }

    return priceMap;
  } finally {
    clearTimeout(timeout);
  }
}
