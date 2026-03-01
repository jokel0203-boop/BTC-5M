import { ExchangeRate } from '../types';

async function fetchWithTimeout(url: string, timeoutMs: number, headers?: Record<string, string>): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal, headers });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getExchangeRates(): Promise<ExchangeRate> {
  // 1차: 두나무(Upbit) 실시간 환율 API - 여러 URL 시도
  const dunamuUrls = [
    'https://quotation-api.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD,FRX.KRWIDR',
    'https://quotation-api-cdn.dunamu.com/v1/forex/recent?codes=FRX.KRWUSD,FRX.KRWIDR',
  ];
  const browserHeaders = { 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0' };
  for (const url of dunamuUrls) {
    try {
      const res = await fetchWithTimeout(url, 5000, browserHeaders);
      const data: Array<{ code: string; basePrice: number; currencyUnit?: number }> = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        let usdKrw = 0;
        let idrKrw = 0;
        for (const item of data) {
          if (item.code === 'FRX.KRWUSD' && item.basePrice) {
            usdKrw = item.basePrice;
          }
          if (item.code === 'FRX.KRWIDR' && item.basePrice) {
            const unit = item.currencyUnit || 100;
            idrKrw = item.basePrice / unit;
          }
        }
        if (usdKrw > 0) {
          if (idrKrw === 0) idrKrw = usdKrw / 16000;
          console.log(`[ExchangeRate] 두나무 성공: USD/KRW=${usdKrw}, IDR/KRW=${idrKrw.toFixed(4)}`);
          return { usdKrw, idrKrw };
        }
      }
    } catch (err: any) {
      console.warn(`[ExchangeRate] 두나무 실패 (${url.includes('-cdn') ? 'CDN' : 'direct'}):`, err.message);
    }
  }

  // 2차: manana.kr (매매기준율 - 하루 1회 갱신)
  try {
    const res = await fetchWithTimeout('https://api.manana.kr/exchange/rate/KRW/USD.json', 8000);
    const data: { date: string; name: string; rate: number }[] = await res.json();
    if (Array.isArray(data) && data.length > 0 && data[0].rate) {
      const usdKrw = data[0].rate;
      console.log(`[ExchangeRate] manana.kr 성공: USD/KRW = ${usdKrw}`);
      let idrKrw = 0.089;
      try {
        const idrRes = await fetchWithTimeout('https://api.manana.kr/exchange/rate/KRW/IDR.json', 5000);
        const idrData: { date: string; name: string; rate: number }[] = await idrRes.json();
        if (Array.isArray(idrData) && idrData.length > 0 && idrData[0].rate) {
          idrKrw = idrData[0].rate;
        }
      } catch {
        idrKrw = usdKrw / 16000;
      }
      return { usdKrw, idrKrw };
    }
  } catch (err: any) {
    console.warn('[ExchangeRate] manana.kr 실패:', err.message);
  }

  // 3차: Open Exchange Rates
  try {
    const res = await fetchWithTimeout('https://open.er-api.com/v6/latest/USD', 8000);
    const data = await res.json();
    if (data.rates?.KRW) {
      return { usdKrw: data.rates.KRW, idrKrw: data.rates.IDR ? data.rates.KRW / data.rates.IDR : 0.089 };
    }
  } catch (err: any) {
    console.warn('[ExchangeRate] open.er-api 실패:', err.message);
  }

  // 4차: ExchangeRate API
  try {
    const res = await fetchWithTimeout('https://api.exchangerate-api.com/v4/latest/USD', 8000);
    const data = await res.json();
    if (data.rates?.KRW) {
      return { usdKrw: data.rates.KRW, idrKrw: data.rates.IDR ? data.rates.KRW / data.rates.IDR : 0.089 };
    }
  } catch (err: any) {
    console.warn('[ExchangeRate] exchangerate-api 실패:', err.message);
  }

  // 모두 실패 시 기본값
  console.warn('[ExchangeRate] 모든 API 실패, 기본값 사용');
  return { usdKrw: 1380, idrKrw: 0.089 };
}
