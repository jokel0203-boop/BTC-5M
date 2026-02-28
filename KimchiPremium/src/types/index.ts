export interface CoinPrice {
  symbol: string;
  upbitPrice: number | null;
  foreignPrice: number | null;      // 해외 거래소 가격 (USDT 또는 IDR)
  foreignPriceKrw: number | null;   // 해외 거래소 가격 (KRW 환산)
  premium: number | null;           // 프리미엄 %
  changeRate: number | null;
  changePrice: number | null;
  tradeVolume24h: number | null;
}

export interface ExchangeRate {
  usdKrw: number;
  idrKrw: number;
}

export type ForeignExchange = 'binance_spot' | 'binance_futures' | 'indodax';

export interface AppSettings {
  proxyUrl: string;
  foreignExchange: ForeignExchange;
}

export interface ProxyData {
  binanceSpot: Record<string, number>;
  binanceFutures: Record<string, number>;
  indodax: Record<string, number>;
  rates: { usdKrw: number; idrKrw: number };
  lastUpdate: number;
}

export interface UpbitMarketTicker {
  market: string;
  trade_price: number;
  signed_change_rate: number;
  signed_change_price: number;
  acc_trade_price_24h: number;
}

export interface BinanceTicker {
  symbol: string;
  price: string;
}

export type SortField = 'symbol' | 'premium' | 'upbitPrice' | 'changeRate' | 'tradeVolume24h';
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
