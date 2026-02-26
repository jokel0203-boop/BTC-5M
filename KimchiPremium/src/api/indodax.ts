import axios from 'axios';

const INDODAX_API = 'https://indodax.com/api';

export async function getIndodaxTickers(): Promise<Map<string, number>> {
  const response = await axios.get(`${INDODAX_API}/summaries`);
  const priceMap = new Map<string, number>();
  const tickers = response.data.tickers;

  for (const [pair, data] of Object.entries(tickers)) {
    // Indodax pairs are like "btc_idr", "eth_idr"
    if (pair.endsWith('_idr')) {
      const symbol = pair.replace('_idr', '').toUpperCase();
      priceMap.set(symbol, parseFloat((data as any).last));
    }
  }

  return priceMap;
}
