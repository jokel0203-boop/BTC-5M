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
import { ExchangeRow } from '../components/ExchangeRow';
import { PremiumRow } from '../components/PremiumRow';
import { SearchBar } from '../components/SearchBar';
import { CoinPrice, SortField } from '../types';

type TabType = 'exchange' | 'premium';

interface Props {
  navigation: any;
}

export function HomeScreen({ navigation }: Props) {
  const [activeTab, setActiveTab] = useState<TabType>('exchange');

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
  } = useCoinData(5);

  const { checkAlerts } = useAlerts();

  useEffect(() => {
    if (coins.length > 0) {
      checkAlerts(coins);
    }
  }, [coins, checkAlerts]);

  const handleCoinPress = useCallback((coin: CoinPrice) => {
    navigation.navigate('Detail', { coin, exchangeRates });
  }, [navigation, exchangeRates]);

  const renderExchangeItem = useCallback(({ item }: { item: CoinPrice }) => (
    <ExchangeRow coin={item} onPress={handleCoinPress} />
  ), [handleCoinPress]);

  const renderPremiumItem = useCallback(({ item }: { item: CoinPrice }) => (
    <PremiumRow coin={item} exchangeRates={exchangeRates} onPress={handleCoinPress} />
  ), [handleCoinPress, exchangeRates]);

  // For premium tab, only show coins that have binance price
  const premiumCoins = useMemo(() => {
    return coins.filter(c => c.binancePrice !== null);
  }, [coins]);

  const getSortArrow = (field: SortField) => {
    if (sortField !== field) return '';
    return sortOrder === 'desc' ? ' ▼' : ' ▲';
  };

  if (loading && coins.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>시세 불러오는 중...</Text>
      </View>
    );
  }

  if (error && coins.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>{error}</Text>
        <Text style={styles.retryText} onPress={refresh}>
          탭하여 재시도
        </Text>
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
          <Text style={styles.rateText}>
            USD/KRW : {exchangeRates ? exchangeRates.usdKrw.toFixed(2) : '-'}
          </Text>
          <Text style={styles.rateSep}>  </Text>
          <Text style={styles.rateText}>USDT/USD : 1.0</Text>
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
            <Text style={styles.sortText}>바이낸스</Text>
          </View>
          <TouchableOpacity style={styles.sortBtnRight} onPress={() => setSortField('binancePremium')}>
            <Text style={[styles.sortText, sortField === 'binancePremium' && styles.sortTextActive]}>
              프리미엄{getSortArrow('binancePremium')}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Status Banner */}
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText}>{error}</Text>
        </View>
      ) : null}
      {!loading && coins.length === 0 && !error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText}>데이터 없음 - 당겨서 새로고침</Text>
        </View>
      )}

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
                <Text style={styles.emptyIcon}>!</Text>
                <Text style={styles.emptyText}>
                  바이낸스 데이터를 불러올 수 없습니다
                </Text>
                <Text style={styles.emptySubText}>
                  아래로 당겨서 새로고침 해주세요
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
  errorText: {
    color: '#EF4444',
    fontSize: 14,
    marginBottom: 12,
    paddingHorizontal: 32,
    textAlign: 'center',
  },
  retryText: {
    color: '#3B82F6',
    fontSize: 14,
  },

  // Top Tabs
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

  // Exchange Rate Bar
  rateBar: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  rateText: {
    fontSize: 11,
    color: '#999',
    fontVariant: ['tabular-nums'],
  },
  rateSep: {
    fontSize: 11,
    color: '#333',
  },

  // Sort Header
  sortHeader: {
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  sortBtn: {
    flex: 1,
  },
  sortBtnRight: {
    flex: 1,
    alignItems: 'flex-end',
  },
  sortText: {
    fontSize: 11,
    color: '#666',
    fontWeight: '500',
  },
  sortTextActive: {
    color: '#3B82F6',
    fontWeight: '700',
  },

  // Error Banner
  errorBanner: {
    backgroundColor: '#331111',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  errorBannerText: {
    color: '#EF4444',
    fontSize: 12,
  },

  // Empty State
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 80,
    paddingHorizontal: 32,
  },
  emptyIcon: {
    fontSize: 40,
    color: '#333',
    marginBottom: 16,
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
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 20,
  },
  listContentEmpty: {
    flexGrow: 1,
  },
});
