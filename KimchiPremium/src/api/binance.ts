import axios from 'axios';
import { BinanceTicker } from '../types';

const BINANCE_API = 'https://api.binance.com/api/v3';
const TIMEOUT = 10000;

export async function getBinanceTickers(): Promise<Map<string, number>> {
  const response = await axios.get<BinanceTicker[]>(`${BINANCE_API}/ticker/price`, {
    timeout: TIMEOUT,
  });
  const priceMap = new Map<string, number>();

  for (const ticker of response.data) {
    if (ticker.symbol.endsWith('USDT')) {
      const symbol = ticker.symbol.replace('USDT', '');
      priceMap.set(symbol, parseFloat(ticker.price));
    }
  }

  return priceMap;
}
