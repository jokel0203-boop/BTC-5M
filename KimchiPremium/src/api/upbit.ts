import axios from 'axios';
import { UpbitMarketTicker } from '../types';

const UPBIT_API = 'https://api.upbit.com/v1';
const TIMEOUT = 10000;

export interface UpbitCoinData {
  price: number;
  changeRate: number;
}

async function getUpbitMarkets(): Promise<string[]> {
  const response = await axios.get(`${UPBIT_API}/market/all`, { timeout: TIMEOUT });
  return response.data
    .filter((m: any) => m.market.startsWith('KRW-'))
    .map((m: any) => m.market);
}

async function getUpbitTickers(markets: string[]): Promise<UpbitMarketTicker[]> {
  const response = await axios.get(`${UPBIT_API}/ticker`, {
    params: { markets: markets.join(',') },
    timeout: TIMEOUT,
  });
  return response.data;
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
    });
  }

  return dataMap;
}
