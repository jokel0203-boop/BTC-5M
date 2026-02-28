import { useState, useEffect, useCallback, useRef } from 'react';
import { CoinPrice, ExchangeRate, SortField, SortOrder } from '../types';
import { getUpbitAllKRW, getBinanceTickers, getExchangeRates } from '../api';
import { buildCoinPrices } from '../utils/premium';

interface UseCoinDataReturn {
  coins: CoinPrice[];
  exchangeRates: ExchangeRate | null;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
  refresh: () => Promise<void>;
  sortField: SortField;
  sortOrder: SortOrder;
  setSortField: (field: SortField) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
}

export function useCoinData(refreshInterval: number = 5): UseCoinDataReturn {
  const [coins, setCoins] = useState<CoinPrice[]>([]);
  const [exchangeRates, setExchangeRates] = useState<ExchangeRate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [sortField, setSortFieldState] = useState<SortField>('tradeVolume24h');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isFetchingRef = useRef(false);

  const fetchData = useCallback(async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    try {
      const [upbitResult, binanceResult, ratesResult] = await Promise.allSettled([
        getUpbitAllKRW(),
        getBinanceTickers(),
        getExchangeRates(),
      ]);

      const errors: string[] = [];

      if (ratesResult.status === 'rejected') {
        errors.push(`환율: ${ratesResult.reason?.message || '실패'}`);
      }
      if (upbitResult.status === 'rejected') {
        errors.push(`업비트: ${upbitResult.reason?.message || '실패'}`);
      }
      if (binanceResult.status === 'rejected') {
        errors.push(`바이낸스: ${binanceResult.reason?.message || '실패'}`);
      }

      const rates = ratesResult.status === 'fulfilled'
        ? ratesResult.value
        : { usdKrw: 1380 } as ExchangeRate;

      const upbitData = upbitResult.status === 'fulfilled'
        ? upbitResult.value
        : new Map();

      const binancePrices = binanceResult.status === 'fulfilled'
        ? binanceResult.value
        : new Map();

      setExchangeRates(rates);
      const coinPrices = buildCoinPrices(upbitData, binancePrices, rates);
      setCoins(coinPrices);
      setLastUpdated(new Date());

      // Only set error if there are failures, never clear previous error on retry start
      if (errors.length > 0) {
        setError(errors.join(' | '));
      } else {
        setError(null);
      }
    } catch (err: any) {
      setError(err.message || '알 수 없는 에러');
    } finally {
      setLoading(false);
      isFetchingRef.current = false;
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    isFetchingRef.current = false;
    await fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, refreshInterval * 1000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchData, refreshInterval]);

  const setSortField = useCallback((field: SortField) => {
    setSortFieldState(prev => {
      if (prev === field) {
        setSortOrder(o => (o === 'desc' ? 'asc' : 'desc'));
        return prev;
      }
      setSortOrder('desc');
      return field;
    });
  }, []);

  const processedCoins = coins
    .filter(coin => {
      if (!searchQuery) return true;
      return coin.symbol.toLowerCase().includes(searchQuery.toLowerCase());
    })
    .sort((a, b) => {
      let aVal: number;
      let bVal: number;

      switch (sortField) {
        case 'symbol':
          return sortOrder === 'asc'
            ? a.symbol.localeCompare(b.symbol)
            : b.symbol.localeCompare(a.symbol);
        case 'binancePremium':
          aVal = a.binancePremium ?? -Infinity;
          bVal = b.binancePremium ?? -Infinity;
          break;
        case 'upbitPrice':
          aVal = a.upbitPrice ?? 0;
          bVal = b.upbitPrice ?? 0;
          break;
        case 'changeRate':
          aVal = a.changeRate ?? -Infinity;
          bVal = b.changeRate ?? -Infinity;
          break;
        case 'tradeVolume24h':
          aVal = a.tradeVolume24h ?? 0;
          bVal = b.tradeVolume24h ?? 0;
          break;
        default:
          return 0;
      }

      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });

  return {
    coins: processedCoins,
    exchangeRates,
    loading,
    error,
    lastUpdated,
    refresh,
    sortField,
    sortOrder,
    setSortField,
    searchQuery,
    setSearchQuery,
  };
}
