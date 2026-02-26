export interface CoinPrice {
  symbol: string;
  name: string;
  upbitPrice: number | null;       // KRW
  binancePrice: number | null;     // USDT
  indodaxPrice: number | null;     // IDR
  binancePremium: number | null;   // %
  indodaxPremium: number | null;   // %
}

export interface ExchangeRate {
  usdKrw: number;
  idrKrw: number;
}

export interface UpbitTicker {
  market: string;
  trade_price: number;
  signed_change_rate: number;
  acc_trade_price_24h: number;
}

export interface BinanceTicker {
  symbol: string;
  price: string;
}

export interface IndodaxTicker {
  [pair: string]: {
    last: string;
    buy: string;
    sell: string;
    vol_base: string;
  };
}

export type SortField = 'symbol' | 'binancePremium' | 'indodaxPremium' | 'upbitPrice';
export type SortOrder = 'asc' | 'desc';

export interface Settings {
  refreshInterval: number; // seconds
  alertThreshold: number;  // premium % to trigger alert
  showOnlyCommon: boolean; // only show coins available on all exchanges
}

export type AlertCondition = 'above' | 'below';
export type AlertExchange = 'binance' | 'indodax';

export interface PremiumAlert {
  id: string;
  symbol: string;          // e.g. "BTC"
  exchange: AlertExchange; // which exchange premium to watch
  condition: AlertCondition; // 'above' = 이상, 'below' = 이하
  threshold: number;       // premium % threshold
  enabled: boolean;
  triggered: boolean;      // has it fired?
  triggeredAt?: Date;
  createdAt: Date;
}

export interface AlertLog {
  id: string;
  alertId: string;
  symbol: string;
  exchange: AlertExchange;
  condition: AlertCondition;
  threshold: number;
  actualPremium: number;
  triggeredAt: Date;
}
