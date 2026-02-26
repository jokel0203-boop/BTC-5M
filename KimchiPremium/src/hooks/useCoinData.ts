import { useState, useEffect, useCallback, useRef } from 'react';
import { CoinPrice, ExchangeRate, SortField, SortOrder } from '../types';
import { getUpbitAllKRW, getBinanceTickers, getIndodaxTickers, getExchangeRates } from '../api';
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

export function useCoinData(refreshInterval: number = 0.1): UseCoinDataReturn {
  const [coins, setCoins] = useState<CoinPrice[]>([]);
  const [exchangeRates, setExchangeRates] = useState<ExchangeRate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [sortField, setSortFieldState] = useState<SortField>('binancePremium');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [searchQuery, setSearchQuery] = useState('');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);

      const [upbitPrices, binancePrices, indodaxPrices, rates] = await Promise.all([
        getUpbitAllKRW(),
        getBinanceTickers(),
        getIndodaxTickers(),
        getExchangeRates(),
      ]);

      setExchangeRates(rates);

      const coinPrices = buildCoinPrices(upbitPrices, binancePrices, indodaxPrices, rates);
      setCoins(coinPrices);
      setLastUpdated(new Date());
    } catch (err: any) {
      setError(err.message || 'Failed to fetch data');
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    await fetchData();
  }, [fetchData]);

  useEffect(() => {
    fetchData();

    intervalRef.current = setInterval(fetchData, refreshInterval * 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
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

  // Sort and filter coins
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
        case 'indodaxPremium':
          aVal = a.indodaxPremium ?? -Infinity;
          bVal = b.indodaxPremium ?? -Infinity;
          break;
        case 'upbitPrice':
          aVal = a.upbitPrice ?? 0;
          bVal = b.upbitPrice ?? 0;
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
