import { BinanceTicker } from '../types';

const BINANCE_API = 'https://api.binance.com/api/v3';

async function fetchWithTimeout(url: string, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res;
  } finally {
    clearTimeout(timeout);
  }
}

// 1차: 바이낸스 공식 API
async function fetchBinancePrices(): Promise<Map<string, number>> {
  const res = await fetchWithTimeout(`${BINANCE_API}/ticker/price`, 8000);
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
}

// 2차: CoinGecko API (무료, 한국에서 접속 가능)
async function fetchCoinGeckoPrices(): Promise<Map<string, number>> {
  const res = await fetchWithTimeout(
    'https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1',
    12000,
  );
  const data: any[] = await res.json();
  const priceMap = new Map<string, number>();
  for (const coin of data) {
    if (coin.symbol && coin.current_price) {
      priceMap.set(coin.symbol.toUpperCase(), coin.current_price);
    }
  }
  if (priceMap.size === 0) throw new Error('Empty CoinGecko response');
  return priceMap;
}

// 3차: CoinCap API (무료, 제한 적음, 한국에서 접속 가능)
async function fetchCoinCapPrices(): Promise<Map<string, number>> {
  const res = await fetchWithTimeout(
    'https://api.coincap.io/v2/assets?limit=250',
    12000,
  );
  const json = await res.json();
  const data: any[] = json.data;
  const priceMap = new Map<string, number>();
  for (const coin of data) {
    if (coin.symbol && coin.priceUsd) {
      priceMap.set(coin.symbol.toUpperCase(), parseFloat(coin.priceUsd));
    }
  }
  if (priceMap.size === 0) throw new Error('Empty CoinCap response');
  return priceMap;
}

// 4차: Kraken API (한국에서 접속 가능)
async function fetchKrakenPrices(): Promise<Map<string, number>> {
  const res = await fetchWithTimeout(
    'https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,XRPUSD,SOLUSD,ADAUSD,DOTUSD,LINKUSD,AVAXUSD,MATICUSD,ATOMUSD',
    10000,
  );
  const json = await res.json();
  const priceMap = new Map<string, number>();

  const krakenSymbolMap: Record<string, string> = {
    XXBTZUSD: 'BTC',
    XETHZUSD: 'ETH',
    XXRPZUSD: 'XRP',
    SOLUSD: 'SOL',
    ADAUSD: 'ADA',
    DOTUSD: 'DOT',
    LINKUSD: 'LINK',
    AVAXUSD: 'AVAX',
    MATICUSD: 'MATIC',
    ATOMUSD: 'ATOM',
  };

  if (json.result) {
    for (const [pair, tickerData] of Object.entries(json.result)) {
      const symbol = krakenSymbolMap[pair];
      if (symbol && (tickerData as any).c) {
        priceMap.set(symbol, parseFloat((tickerData as any).c[0]));
      }
    }
  }

  if (priceMap.size === 0) throw new Error('Empty Kraken response');
  return priceMap;
}

// 순서대로 시도: 바이낸스 → CoinGecko → CoinCap → Kraken
export async function getBinanceTickers(): Promise<Map<string, number>> {
  const sources = [
    { name: 'Binance', fn: fetchBinancePrices },
    { name: 'CoinGecko', fn: fetchCoinGeckoPrices },
    { name: 'CoinCap', fn: fetchCoinCapPrices },
    { name: 'Kraken', fn: fetchKrakenPrices },
  ];

  for (const source of sources) {
    try {
      const result = await source.fn();
      if (result.size > 0) {
        console.log(`[Price] ${source.name} 성공 (${result.size}개 코인)`);
        return result;
      }
    } catch (err: any) {
      console.warn(`[Price] ${source.name} 실패:`, err.message);
    }
  }

  throw new Error('모든 가격 API 접속 실패 - 네트워크 연결을 확인하세요');
}
