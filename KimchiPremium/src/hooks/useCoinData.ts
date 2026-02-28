import { useState, useEffect, useCallback, useRef } from 'react';
import { CoinPrice, ExchangeRate, SortField, SortOrder, AppSettings } from '../types';
import { getUpbitAllKRW, fetchProxyData, extractPrices } from '../api';
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

export function useCoinData(settings: AppSettings, refreshInterval: number = 5): UseCoinDataReturn {
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
  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  const fetchData = useCallback(async () => {
    if (isFetchingRef.current) return;
    isFetchingRef.current = true;

    const currentSettings = settingsRef.current;

    try {
      // 1. 업비트 데이터 (폰에서 직접 호출 - 한국이니까 OK)
      let upbitData = new Map();
      try {
        upbitData = await getUpbitAllKRW();
      } catch (e: any) {
        setError('업비트 API 실패: ' + e.message);
        return;
      }

      // 2. 프록시를 통해 해외 데이터 가져오기
      let foreignPrices = new Map<string, number>();
      let rates: ExchangeRate = { usdKrw: 1380, idrKrw: 0.089 };

      if (!currentSettings.proxyUrl) {
        setError('설정에서 프록시 서버 IP를 입력해주세요');
        // 업비트 데이터만이라도 표시
        const coinPrices = buildCoinPrices(upbitData, foreignPrices, rates, currentSettings.foreignExchange);
        setCoins(coinPrices);
        setLastUpdated(new Date());
        setLoading(false);
        isFetchingRef.current = false;
        return;
      }

      try {
        const proxyData = await fetchProxyData(currentSettings.proxyUrl);
        foreignPrices = extractPrices(proxyData, currentSettings.foreignExchange);
        if (proxyData.rates) {
          rates = {
            usdKrw: proxyData.rates.usdKrw || 1380,
            idrKrw: proxyData.rates.idrKrw || 0.089,
          };
        }
        setError(null);
      } catch (e: any) {
        setError('프록시 서버 연결 실패 - IP 확인 필요');
      }

      setExchangeRates(rates);
      const coinPrices = buildCoinPrices(upbitData, foreignPrices, rates, currentSettings.foreignExchange);
      setCoins(coinPrices);
      setLastUpdated(new Date());
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

  // 설정 변경 시 즉시 새로고침
  useEffect(() => {
    isFetchingRef.current = false;
    fetchData();
  }, [settings.proxyUrl, settings.foreignExchange, fetchData]);

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
        case 'premium':
          aVal = a.premium ?? -Infinity;
          bVal = b.premium ?? -Infinity;
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
