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
  } = useCoinData(0.1);

  const { checkAlerts } = useAlerts();

  // Check alerts whenever coins update
  useEffect(() => {
    if (coins.length > 0) {
      checkAlerts(coins);
    }
  }, [coins, checkAlerts]);

  const avgBinancePremium = useMemo(() => {
    const withPremium = coins.filter(c => c.binancePremium !== null);
    if (withPremium.length === 0) return null;
    return withPremium.reduce((sum, c) => sum + (c.binancePremium ?? 0), 0) / withPremium.length;
  }, [coins]);

  const avgIndodaxPremium = useMemo(() => {
    const withPremium = coins.filter(c => c.indodaxPremium !== null);
    if (withPremium.length === 0) return null;
    return withPremium.reduce((sum, c) => sum + (c.indodaxPremium ?? 0), 0) / withPremium.length;
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
        <ActivityIndicator size="large" color="#4A90D9" />
        <Text style={styles.loadingText}>데이터 불러오는 중...</Text>
      </View>
    );
  }

  if (error && coins.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorText}>오류: {error}</Text>
        <Text style={styles.retryText} onPress={refresh}>
          탭하여 재시도
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <PremiumSummary
        avgBinancePremium={avgBinancePremium}
        avgIndodaxPremium={avgIndodaxPremium}
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
            tintColor="#4A90D9"
            colors={['#4A90D9']}
          />
        }
        style={styles.list}
        contentContainerStyle={styles.listContent}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111111',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#111111',
  },
  loadingText: {
    color: '#888888',
    marginTop: 12,
    fontSize: 14,
  },
  errorText: {
    color: '#FF4444',
    fontSize: 14,
    marginBottom: 8,
  },
  retryText: {
    color: '#4A90D9',
    fontSize: 14,
    textDecorationLine: 'underline',
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 20,
  },
});
