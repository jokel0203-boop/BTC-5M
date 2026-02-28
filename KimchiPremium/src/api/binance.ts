import { BinanceTicker } from '../types';

const BINANCE_API = 'https://api.binance.com/api/v3';

async function fetchBinancePrices(): Promise<Map<string, number>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(`${BINANCE_API}/ticker/price`, { signal: controller.signal });
    if (!res.ok) throw new Error(`Binance HTTP ${res.status}`);
    const data: BinanceTicker[] = await res.json();
    const priceMap = new Map<string, number>();

    for (const ticker of data) {
      if (ticker.symbol.endsWith('USDT')) {
        const symbol = ticker.symbol.replace('USDT', '');
        priceMap.set(symbol, parseFloat(ticker.price));
      }
    }

    if (priceMap.size === 0) throw new Error('Empty Binance response');
    return priceMap;
  } finally {
    clearTimeout(timeout);
  }
}

async function fetchCoinGeckoPrices(): Promise<Map<string, number>> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(
      'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1',
      { signal: controller.signal }
    );
    if (!res.ok) throw new Error(`CoinGecko HTTP ${res.status}`);
    const data: any[] = await res.json();
    const priceMap = new Map<string, number>();
    for (const coin of data) {
      if (coin.symbol && coin.current_price) {
        priceMap.set(coin.symbol.toUpperCase(), coin.current_price);
      }
    }
    return priceMap;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getBinanceTickers(): Promise<Map<string, number>> {
  try {
    return await fetchBinancePrices();
  } catch (binanceErr) {
    console.warn('Binance API failed, trying CoinGecko fallback:', binanceErr);
    return await fetchCoinGeckoPrices();
  }
}
