import React, { useMemo, useEffect, useState, useCallback } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Text,
  RefreshControl,
  TouchableOpacity,
} from 'react-native';
import { useCoinData } from '../hooks/useCoinData';
import { useAlerts } from '../hooks/useAlerts';
import { useSettings } from '../contexts/SettingsContext';
import { ExchangeRow } from '../components/ExchangeRow';
import { PremiumRow } from '../components/PremiumRow';
import { SearchBar } from '../components/SearchBar';
import { CoinPrice, SortField } from '../types';
import { getExchangeLabel, getCurrencyUnit } from '../utils/premium';

type TabType = 'exchange' | 'premium';

interface Props {
  navigation: any;
}

export function HomeScreen({ navigation }: Props) {
  const [activeTab, setActiveTab] = useState<TabType>('exchange');
  const { settings } = useSettings();

  const {
    coins,
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
  } = useCoinData(settings, 5);

  const { checkAlerts } = useAlerts();

  useEffect(() => {
    if (coins.length > 0) {
      checkAlerts(coins);
    }
  }, [coins, checkAlerts]);

  const handleCoinPress = useCallback((coin: CoinPrice) => {
    navigation.navigate('Detail', { coin, exchangeRates, foreignExchange: settings.foreignExchange });
  }, [navigation, exchangeRates, settings.foreignExchange]);

  const renderExchangeItem = useCallback(({ item }: { item: CoinPrice }) => (
    <ExchangeRow coin={item} onPress={handleCoinPress} />
  ), [handleCoinPress]);

  const renderPremiumItem = useCallback(({ item }: { item: CoinPrice }) => (
    <PremiumRow coin={item} foreignExchange={settings.foreignExchange} onPress={handleCoinPress} />
  ), [handleCoinPress, settings.foreignExchange]);

  // For premium tab, only show coins that have foreign price
  const premiumCoins = useMemo(() => {
    return coins.filter(c => c.foreignPrice !== null);
  }, [coins]);

  const getSortArrow = (field: SortField) => {
    if (sortField !== field) return '';
    return sortOrder === 'desc' ? ' ▼' : ' ▲';
  };

  const exchangeLabel = getExchangeLabel(settings.foreignExchange);
  const currencyUnit = getCurrencyUnit(settings.foreignExchange);

  if (loading && coins.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>시세 불러오는 중...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Top Tabs */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'exchange' && styles.tabActive]}
          onPress={() => setActiveTab('exchange')}
        >
          <Text style={[styles.tabText, activeTab === 'exchange' && styles.tabTextActive]}>
            거래소
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'premium' && styles.tabActive]}
          onPress={() => setActiveTab('premium')}
        >
          <Text style={[styles.tabText, activeTab === 'premium' && styles.tabTextActive]}>
            프리미엄
          </Text>
        </TouchableOpacity>
      </View>

      {/* Exchange Rate Info Bar - shown on premium tab */}
      {activeTab === 'premium' && (
        <View style={styles.rateBar}>
          <Text style={styles.rateExchange}>업비트 ↔ {exchangeLabel}</Text>
          {exchangeRates && (
            <Text style={styles.rateText}>
              USD/KRW: {exchangeRates.usdKrw.toFixed(0)}
            </Text>
          )}
        </View>
      )}

      {/* Sort Header */}
      {activeTab === 'exchange' ? (
        <View style={styles.sortHeader}>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('symbol')}>
            <Text style={[styles.sortText, sortField === 'symbol' && styles.sortTextActive]}>
              이름{getSortArrow('symbol')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('upbitPrice')}>
            <Text style={[styles.sortText, sortField === 'upbitPrice' && styles.sortTextActive]}>
              가격{getSortArrow('upbitPrice')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('tradeVolume24h')}>
            <Text style={[styles.sortText, sortField === 'tradeVolume24h' && styles.sortTextActive]}>
              거래량{getSortArrow('tradeVolume24h')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.sortBtnRight} onPress={() => setSortField('changeRate')}>
            <Text style={[styles.sortText, sortField === 'changeRate' && styles.sortTextActive]}>
              등락률{getSortArrow('changeRate')}
            </Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.sortHeader}>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('symbol')}>
            <Text style={[styles.sortText, sortField === 'symbol' && styles.sortTextActive]}>
              이름{getSortArrow('symbol')}
            </Text>
          </TouchableOpacity>
          <View style={styles.sortBtn}>
            <Text style={styles.sortText}>{currencyUnit}</Text>
          </View>
          <TouchableOpacity style={styles.sortBtnRight} onPress={() => setSortField('premium')}>
            <Text style={[styles.sortText, sortField === 'premium' && styles.sortTextActive]}>
              프리미엄{getSortArrow('premium')}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Error Banner */}
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText}>{error}</Text>
        </View>
      ) : null}

      {/* Search */}
      <SearchBar value={searchQuery} onChangeText={setSearchQuery} />

      {/* Coin List */}
      {activeTab === 'exchange' ? (
        <FlatList
          data={coins}
          keyExtractor={item => item.symbol}
          renderItem={renderExchangeItem}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={refresh}
              tintColor="#3B82F6"
              colors={['#3B82F6']}
            />
          }
          style={styles.list}
          contentContainerStyle={styles.listContent}
          initialNumToRender={20}
          maxToRenderPerBatch={20}
        />
      ) : (
        <FlatList
          data={premiumCoins}
          keyExtractor={item => item.symbol}
          renderItem={renderPremiumItem}
          ListEmptyComponent={
            !loading ? (
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyText}>
                  {!settings.proxyUrl
                    ? '설정에서 프록시 서버 IP를 입력해주세요'
                    : '해외 거래소 데이터를 불러올 수 없습니다'}
                </Text>
                <Text style={styles.emptySubText}>
                  {!settings.proxyUrl
                    ? '설정 탭 > 프록시 서버에서 VPS IP 입력'
                    : '프록시 서버 연결 상태를 확인하세요'}
                </Text>
              </View>
            ) : null
          }
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={refresh}
              tintColor="#3B82F6"
              colors={['#3B82F6']}
            />
          }
          style={styles.list}
          contentContainerStyle={premiumCoins.length === 0 ? styles.listContentEmpty : styles.listContent}
          initialNumToRender={20}
          maxToRenderPerBatch={20}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0D0D0D',
  },
  loadingText: {
    color: '#666',
    marginTop: 12,
    fontSize: 14,
  },

  // Tabs
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#0D0D0D',
    borderBottomWidth: 0.5,
    borderBottomColor: '#222',
  },
  tab: {
    paddingVertical: 12,
    paddingHorizontal: 20,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#FFFFFF',
  },
  tabText: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },

  // Rate Bar
  rateBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  rateExchange: {
    fontSize: 12,
    color: '#3B82F6',
    fontWeight: '600',
  },
  rateText: {
    fontSize: 11,
    color: '#999',
    fontVariant: ['tabular-nums'],
  },

  // Sort
  sortHeader: {
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  sortBtn: { flex: 1 },
  sortBtnRight: { flex: 1, alignItems: 'flex-end' },
  sortText: { fontSize: 11, color: '#666', fontWeight: '500' },
  sortTextActive: { color: '#3B82F6', fontWeight: '700' },

  // Error
  errorBanner: {
    backgroundColor: '#331111',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  errorBannerText: { color: '#EF4444', fontSize: 12 },

  // Empty
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 80,
    paddingHorizontal: 32,
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 8,
  },
  emptySubText: {
    color: '#555',
    fontSize: 12,
    textAlign: 'center',
  },

  // List
  list: { flex: 1 },
  listContent: { paddingBottom: 20 },
  listContentEmpty: { flexGrow: 1 },
});
