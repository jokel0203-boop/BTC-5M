import axios from 'axios';
import { BinanceTicker } from '../types';

const BINANCE_API = 'https://api.binance.com/api/v3';

export async function getBinanceTickers(): Promise<Map<string, number>> {
  const response = await axios.get<BinanceTicker[]>(`${BINANCE_API}/ticker/price`);
  const priceMap = new Map<string, number>();

  for (const ticker of response.data) {
    // Only get USDT pairs
    if (ticker.symbol.endsWith('USDT')) {
      const symbol = ticker.symbol.replace('USDT', '');
      priceMap.set(symbol, parseFloat(ticker.price));
    }
  }

  return priceMap;
}
