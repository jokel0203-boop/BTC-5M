import { ProxyData, ForeignExchange } from '../types';

/**
 * VPS 프록시 서버에서 해외 거래소 데이터를 가져옴.
 * 폰에서 직접 바이낸스를 호출하면 한국 IP 차단으로 실패하므로,
 * VPS가 대신 데이터를 가져와서 중계해주는 구조.
 */
export async function fetchProxyData(proxyUrl: string): Promise<ProxyData> {
  const url = proxyUrl.replace(/\/$/, '');
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const res = await fetch(`${url}/api/data`, { signal: controller.signal });
    if (!res.ok) throw new Error(`Proxy HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * 프록시 데이터에서 선택한 거래소의 가격 맵을 추출
 */
export function extractPrices(
  data: ProxyData,
  exchange: ForeignExchange
): Map<string, number> {
  let source: Record<string, number>;
  switch (exchange) {
    case 'binance_spot':
      source = data.binanceSpot || {};
      break;
    case 'binance_futures':
      source = data.binanceFutures || {};
      // 선물 데이터가 비어있으면 현물 가격으로 대체 (선물/현물 가격은 거의 동일)
      if (Object.keys(source).length === 0) {
        source = data.binanceSpot || {};
      }
      break;
    case 'indodax':
      source = data.indodax || {};
      break;
  }
  return new Map(Object.entries(source));
}
