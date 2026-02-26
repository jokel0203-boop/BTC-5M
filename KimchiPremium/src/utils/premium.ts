import { CoinPrice, ExchangeRate } from '../types';

/**
 * Calculate kimchi premium percentage
 * Premium = ((Upbit KRW price - Foreign price in KRW) / Foreign price in KRW) * 100
 */
export function calculatePremium(
  upbitPriceKrw: number,
  foreignPrice: number,
  exchangeRateToKrw: number
): number {
  const foreignPriceInKrw = foreignPrice * exchangeRateToKrw;
  if (foreignPriceInKrw === 0) return 0;
  return ((upbitPriceKrw - foreignPriceInKrw) / foreignPriceInKrw) * 100;
}

export function buildCoinPrices(
  upbitPrices: Map<string, number>,
  binancePrices: Map<string, number>,
  indodaxPrices: Map<string, number>,
  exchangeRates: ExchangeRate
): CoinPrice[] {
  const coins: CoinPrice[] = [];

  for (const [symbol, upbitPrice] of upbitPrices) {
    const binancePrice = binancePrices.get(symbol) ?? null;
    const indodaxPrice = indodaxPrices.get(symbol) ?? null;

    const binancePremium =
      binancePrice !== null
        ? calculatePremium(upbitPrice, binancePrice, exchangeRates.usdKrw)
        : null;

    const indodaxPremium =
      indodaxPrice !== null
        ? calculatePremium(upbitPrice, indodaxPrice, exchangeRates.idrKrw)
        : null;

    coins.push({
      symbol,
      name: symbol, // Could map to full names later
      upbitPrice,
      binancePrice,
      indodaxPrice,
      binancePremium,
      indodaxPremium,
    });
  }

  return coins;
}

export function formatKRW(value: number): string {
  if (value >= 1_000_000) {
    return `₩${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `₩${Math.round(value).toLocaleString()}`;
  }
  if (value >= 1) {
    return `₩${value.toFixed(1)}`;
  }
  return `₩${value.toFixed(4)}`;
}

export function formatUSDT(value: number): string {
  if (value >= 1000) {
    return `$${Math.round(value).toLocaleString()}`;
  }
  if (value >= 1) {
    return `$${value.toFixed(2)}`;
  }
  return `$${value.toFixed(6)}`;
}

export function formatIDR(value: number): string {
  return `Rp${Math.round(value).toLocaleString()}`;
}

export function formatPremium(value: number | null): string {
  if (value === null) return '-';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function getPremiumColor(value: number | null): string {
  if (value === null) return '#888888';
  if (value > 3) return '#FF4444';     // High premium - red
  if (value > 0) return '#FF8800';     // Low premium - orange
  if (value > -1) return '#888888';    // Near zero - gray
  return '#44BB44';                    // Discount - green
}
