import { UpbitMarketTicker } from '../types';

const UPBIT_API = 'https://api.upbit.com/v1';

export interface UpbitCoinData {
  price: number;
  changeRate: number;
  changePrice: number;
  tradeVolume24h: number;
}

async function fetchJSON(url: string): Promise<any> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10000);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timeout);
  }
}

async function getUpbitMarkets(): Promise<string[]> {
  const data = await fetchJSON(`${UPBIT_API}/market/all`);
  return data
    .filter((m: any) => m.market.startsWith('KRW-'))
    .map((m: any) => m.market);
}

async function getUpbitTickers(markets: string[]): Promise<UpbitMarketTicker[]> {
  const query = markets.join(',');
  return await fetchJSON(`${UPBIT_API}/ticker?markets=${encodeURIComponent(query)}`);
}

export async function getUpbitAllKRW(): Promise<Map<string, UpbitCoinData>> {
  const markets = await getUpbitMarkets();
  const tickers = await getUpbitTickers(markets);
  const dataMap = new Map<string, UpbitCoinData>();

  for (const ticker of tickers) {
    const symbol = ticker.market.replace('KRW-', '');
    dataMap.set(symbol, {
      price: ticker.trade_price,
      changeRate: ticker.signed_change_rate,
      changePrice: ticker.signed_change_price ?? 0,
      tradeVolume24h: ticker.acc_trade_price_24h,
    });
  }

  return dataMap;
}
