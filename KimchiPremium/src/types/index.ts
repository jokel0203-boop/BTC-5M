export interface CoinPrice {
  symbol: string;
  upbitPrice: number | null;
  binancePrice: number | null;
  binancePremium: number | null;
  changeRate: number | null;
}

export interface ExchangeRate {
  usdKrw: number;
}

export interface UpbitMarketTicker {
  market: string;
  trade_price: number;
  signed_change_rate: number;
  acc_trade_price_24h: number;
}

export interface BinanceTicker {
  symbol: string;
  price: string;
}

export type SortField = 'symbol' | 'binancePremium' | 'upbitPrice' | 'changeRate';
export type SortOrder = 'asc' | 'desc';

export type AlertCondition = 'above' | 'below';

export interface PremiumAlert {
  id: string;
  symbol: string;
  condition: AlertCondition;
  threshold: number;
  enabled: boolean;
  triggered: boolean;
  triggeredAt?: Date;
  createdAt: Date;
}

export interface AlertLog {
  id: string;
  alertId: string;
  symbol: string;
  condition: AlertCondition;
  threshold: number;
  actualPremium: number;
  triggeredAt: Date;
}
