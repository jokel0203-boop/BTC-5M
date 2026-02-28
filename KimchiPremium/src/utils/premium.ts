import { CoinPrice, ExchangeRate, ForeignExchange } from '../types';
import { UpbitCoinData } from '../api/upbit';

/**
 * 프리미엄 계산
 * upbitPriceKrw: 업비트 원화 가격
 * foreignPrice: 해외 거래소 가격 (USDT 또는 IDR)
 * conversionRate: 해외 화폐 → KRW 변환 비율
 */
export function calculatePremium(
  upbitPriceKrw: number,
  foreignPrice: number,
  conversionRate: number,
): number {
  const foreignPriceKrw = foreignPrice * conversionRate;
  if (foreignPriceKrw === 0) return 0;
  return ((upbitPriceKrw - foreignPriceKrw) / foreignPriceKrw) * 100;
}

/**
 * 거래소 선택에 따른 환산 비율 반환
 * - binance_spot / binance_futures: USDT(≈USD) → KRW
 * - indodax: IDR → KRW
 */
export function getConversionRate(
  exchange: ForeignExchange,
  rates: ExchangeRate,
): number {
  if (exchange === 'indodax') return rates.idrKrw;
  return rates.usdKrw; // binance_spot, binance_futures
}

/**
 * 코인 가격 목록 생성
 */
export function buildCoinPrices(
  upbitData: Map<string, UpbitCoinData>,
  foreignPrices: Map<string, number>,
  rates: ExchangeRate,
  exchange: ForeignExchange,
): CoinPrice[] {
  const coins: CoinPrice[] = [];
  const convRate = getConversionRate(exchange, rates);

  for (const [symbol, data] of upbitData) {
    const foreignPrice = foreignPrices.get(symbol) ?? null;

    let premium: number | null = null;
    let foreignPriceKrw: number | null = null;
    if (foreignPrice !== null) {
      foreignPriceKrw = foreignPrice * convRate;
      premium = calculatePremium(data.price, foreignPrice, convRate);
    }

    coins.push({
      symbol,
      upbitPrice: data.price,
      foreignPrice,
      foreignPriceKrw,
      premium,
      changeRate: data.changeRate,
      changePrice: data.changePrice,
      tradeVolume24h: data.tradeVolume24h,
    });
  }

  return coins;
}

export function formatKRW(value: number): string {
  return Math.round(value).toLocaleString('ko-KR');
}

export function formatForeignPrice(value: number, exchange: ForeignExchange): string {
  if (exchange === 'indodax') {
    // IDR: 큰 숫자, 소수점 없음
    return Math.round(value).toLocaleString('id-ID') + ' IDR';
  }
  // USDT
  if (value >= 1) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 }) + ' USDT';
  }
  return value.toFixed(6) + ' USDT';
}

export function formatVolume(value: number): string {
  if (value >= 1_0000_0000_0000) {
    return `${Math.round(value / 1_0000_0000_0000).toLocaleString()} 조원`;
  }
  if (value >= 1_0000_0000) {
    return `${Math.round(value / 1_0000_0000).toLocaleString()} 억원`;
  }
  if (value >= 1_0000) {
    return `${Math.round(value / 1_0000).toLocaleString()} 만원`;
  }
  return `${Math.round(value).toLocaleString()} 원`;
}

export function formatPremium(value: number | null): string {
  if (value === null) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatChangeRate(value: number | null): string {
  if (value === null) return '-';
  const pct = value * 100;
  const arrow = pct > 0 ? '▲ ' : pct < 0 ? '▼ ' : '';
  return `${arrow}${Math.abs(pct).toFixed(2)}%`;
}

export function formatChangePrice(value: number | null): string {
  if (value === null) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${Math.round(value).toLocaleString('ko-KR')}`;
}

export function getPremiumColor(value: number | null): string {
  if (value === null) return '#888888';
  if (value > 0) return '#EF4444';
  if (value < 0) return '#3B82F6';
  return '#888888';
}

export function getChangeColor(value: number | null): string {
  if (value === null) return '#888888';
  if (value > 0) return '#EF4444';
  if (value < 0) return '#3B82F6';
  return '#888888';
}

export function getExchangeLabel(exchange: ForeignExchange): string {
  switch (exchange) {
    case 'binance_spot': return '바이낸스 현물';
    case 'binance_futures': return '바이낸스 선물';
    case 'indodax': return 'Indodax';
  }
}

export function getCurrencyUnit(exchange: ForeignExchange): string {
  return exchange === 'indodax' ? 'IDR' : 'USDT';
}
