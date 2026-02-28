import { ExchangeRate } from '../types';

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

export async function getExchangeRates(): Promise<ExchangeRate> {
  // 1차: Open Exchange Rates
  try {
    const res = await fetchWithTimeout('https://open.er-api.com/v6/latest/USD', 8000);
    const data = await res.json();
    if (data.rates?.KRW) {
      return { usdKrw: data.rates.KRW };
    }
  } catch (err: any) {
    console.warn('[ExchangeRate] open.er-api 실패:', err.message);
  }

  // 2차: ExchangeRate API
  try {
    const res = await fetchWithTimeout('https://api.exchangerate-api.com/v4/latest/USD', 8000);
    const data = await res.json();
    if (data.rates?.KRW) {
      return { usdKrw: data.rates.KRW };
    }
  } catch (err: any) {
    console.warn('[ExchangeRate] exchangerate-api 실패:', err.message);
  }

  // 모두 실패 시 기본값
  console.warn('[ExchangeRate] 모든 API 실패, 기본값 1380 사용');
  return { usdKrw: 1380 };
}
