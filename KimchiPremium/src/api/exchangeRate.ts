import { ExchangeRate } from '../types';

export async function getExchangeRates(): Promise<ExchangeRate> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    try {
      const res = await fetch('https://open.er-api.com/v6/latest/USD', {
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      return { usdKrw: data.rates.KRW };
    } finally {
      clearTimeout(timeout);
    }
  } catch {
    return { usdKrw: 1380 };
  }
}
