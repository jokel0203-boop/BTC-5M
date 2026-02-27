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
    });
  }

  return coins;
}

export function formatKRW(value: number): string {
  if (value >= 1_000_000) {
    return Math.round(value).toLocaleString('ko-KR');
  }
  if (value >= 100) {
    return Math.round(value).toLocaleString('ko-KR');
  }
  if (value >= 1) {
    return value.toFixed(1);
  }
  return value.toFixed(4);
}

export function formatPremium(value: number | null): string {
  if (value === null) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatChangeRate(value: number | null): string {
  if (value === null) return '-';
  const pct = value * 100;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(2)}%`;
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
