import axios from 'axios';
import { UpbitTicker } from '../types';

const UPBIT_API = 'https://api.upbit.com/v1';

export async function getUpbitMarkets(): Promise<string[]> {
  const response = await axios.get(`${UPBIT_API}/market/all`);
  return response.data
    .filter((m: any) => m.market.startsWith('KRW-'))
    .map((m: any) => m.market);
}

export async function getUpbitTickers(markets: string[]): Promise<UpbitTicker[]> {
  const response = await axios.get(`${UPBIT_API}/ticker`, {
    params: { markets: markets.join(',') },
  });
  return response.data;
}

export async function getUpbitAllKRW(): Promise<Map<string, number>> {
  const markets = await getUpbitMarkets();
  const tickers = await getUpbitTickers(markets);
  const priceMap = new Map<string, number>();

  for (const ticker of tickers) {
    const symbol = ticker.market.replace('KRW-', '');
    priceMap.set(symbol, ticker.trade_price);
  }

  return priceMap;
}
