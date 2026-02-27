import { CoinPrice, ExchangeRate } from '../types';
import { UpbitCoinData } from '../api/upbit';

export function calculatePremium(
  upbitPriceKrw: number,
  binancePriceUsdt: number,
  usdKrw: number
): number {
  const binancePriceKrw = binancePriceUsdt * usdKrw;
  if (binancePriceKrw === 0) return 0;
  return ((upbitPriceKrw - binancePriceKrw) / binancePriceKrw) * 100;
}

export function buildCoinPrices(
  upbitData: Map<string, UpbitCoinData>,
  binancePrices: Map<string, number>,
  exchangeRates: ExchangeRate
): CoinPrice[] {
  const coins: CoinPrice[] = [];

  for (const [symbol, data] of upbitData) {
    const binancePrice = binancePrices.get(symbol) ?? null;

    const binancePremium =
      binancePrice !== null
        ? calculatePremium(data.price, binancePrice, exchangeRates.usdKrw)
        : null;

    coins.push({
      symbol,
      upbitPrice: data.price,
      binancePrice,
      binancePremium,
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

export function formatUSDT(value: number): string {
  if (value >= 1) {
    return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  }
  return value.toFixed(6);
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
  const sign = value >= 0 ? '+ ' : '- ';
  return `${sign}${Math.abs(value).toFixed(2)}%`;
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
