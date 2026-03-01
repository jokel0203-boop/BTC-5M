/**
 * Indodax API에서 IDR 가격을 직접 가져오기
 * 프록시 없이 직접 호출 가능 (한국 IP 차단 없음)
 */

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

export async function getIndodaxTickers(): Promise<Map<string, number>> {
  const res = await fetchWithTimeout('https://indodax.com/api/ticker_all', 10000);
  const data = await res.json();
  const priceMap = new Map<string, number>();

  if (data && data.tickers) {
    for (const [pair, info] of Object.entries(data.tickers)) {
      if (pair.endsWith('_idr')) {
        const symbol = pair.replace('_idr', '').toUpperCase();
        const price = parseFloat((info as any).last);
        if (!isNaN(price) && price > 0) {
          priceMap.set(symbol, price);
        }
      }
    }
  }

  if (priceMap.size === 0) throw new Error('Empty Indodax response');
  return priceMap;
}
