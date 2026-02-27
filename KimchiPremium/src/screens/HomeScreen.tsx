import React, { useMemo, useEffect } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Text,
  RefreshControl,
} from 'react-native';
import { useCoinData } from '../hooks/useCoinData';
import { useAlerts } from '../hooks/useAlerts';
import { CoinRow } from '../components/CoinRow';
import { SortHeader } from '../components/SortHeader';
import { SearchBar } from '../components/SearchBar';
import { PremiumSummary } from '../components/PremiumSummary';
import { CoinPrice } from '../types';

interface Props {
  navigation: any;
}

export function HomeScreen({ navigation }: Props) {
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

  const btcPremium = useMemo(() => {
    const btc = coins.find(c => c.symbol === 'BTC');
    return btc?.binancePremium ?? null;
  }, [coins]);

  const avgPremium = useMemo(() => {
    const withPremium = coins.filter(c => c.binancePremium !== null);
    if (withPremium.length === 0) return null;
    return withPremium.reduce((sum, c) => sum + (c.binancePremium ?? 0), 0) / withPremium.length;
  }, [coins]);

  const handleCoinPress = (coin: CoinPrice) => {
    navigation.navigate('Detail', { coin, exchangeRates });
  };

  const renderItem = ({ item }: { item: CoinPrice }) => (
    <CoinRow coin={item} onPress={handleCoinPress} />
  );

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
      <PremiumSummary
        btcPremium={btcPremium}
        avgPremium={avgPremium}
        exchangeRates={exchangeRates}
        lastUpdated={lastUpdated}
        coinCount={coins.length}
      />
      <SearchBar value={searchQuery} onChangeText={setSearchQuery} />
      <SortHeader sortField={sortField} sortOrder={sortOrder} onSort={setSortField} />
      <FlatList
        data={coins}
        keyExtractor={item => item.symbol}
        renderItem={renderItem}
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
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 20,
  },
});
