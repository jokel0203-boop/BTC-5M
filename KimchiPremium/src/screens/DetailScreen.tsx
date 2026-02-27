import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { formatKRW, formatPremium, formatChangeRate, getPremiumColor, getChangeColor } from '../utils/premium';

export function DetailScreen({ route }: any) {
  const { coin, exchangeRates } = route.params;

  const binancePriceKrw = coin.binancePrice && exchangeRates
    ? coin.binancePrice * exchangeRates.usdKrw
    : null;

  const priceDiff = coin.upbitPrice && binancePriceKrw
    ? coin.upbitPrice - binancePriceKrw
    : null;

  return (
    <ScrollView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.symbol}>{coin.symbol}</Text>
        <Text style={[styles.premium, { color: getPremiumColor(coin.binancePremium) }]}>
          {formatPremium(coin.binancePremium)}
        </Text>
      </View>

      {/* Upbit */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>업비트 (Upbit)</Text>
        <View style={styles.row}>
          <Text style={styles.label}>현재가</Text>
          <Text style={styles.value}>
            {coin.upbitPrice ? `${formatKRW(coin.upbitPrice)} KRW` : '-'}
          </Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>24시간 변동</Text>
          <Text style={[styles.value, { color: getChangeColor(coin.changeRate) }]}>
            {formatChangeRate(coin.changeRate)}
          </Text>
        </View>
      </View>

      {/* Binance */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>바이낸스 (Binance)</Text>
        <View style={styles.row}>
          <Text style={styles.label}>USDT 가격</Text>
          <Text style={styles.value}>
            {coin.binancePrice ? `$${coin.binancePrice.toLocaleString('en-US', { maximumFractionDigits: 6 })}` : '-'}
          </Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>KRW 환산</Text>
          <Text style={styles.value}>
            {binancePriceKrw ? `${formatKRW(binancePriceKrw)} KRW` : '-'}
          </Text>
        </View>
      </View>

      {/* Premium */}
      <View style={styles.card}>
        <Text style={styles.cardTitle}>김치프리미엄</Text>
        <View style={styles.row}>
          <Text style={styles.label}>프리미엄</Text>
          <Text style={[styles.bigValue, { color: getPremiumColor(coin.binancePremium) }]}>
            {formatPremium(coin.binancePremium)}
          </Text>
        </View>
        {priceDiff !== null && (
          <View style={styles.row}>
            <Text style={styles.label}>가격 차이</Text>
            <Text style={styles.value}>
              {priceDiff >= 0 ? '+' : ''}{formatKRW(priceDiff)} KRW
            </Text>
          </View>
        )}
      </View>

      {/* Exchange Rate */}
      {exchangeRates && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>환율</Text>
          <View style={styles.row}>
            <Text style={styles.label}>USD/KRW</Text>
            <Text style={styles.value}>{exchangeRates.usdKrw.toFixed(2)}</Text>
          </View>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
  },
  header: {
    padding: 24,
    alignItems: 'center',
    borderBottomWidth: 0.5,
    borderBottomColor: '#222',
  },
  symbol: {
    fontSize: 28,
    fontWeight: '800',
    color: '#FFFFFF',
    marginBottom: 8,
  },
  premium: {
    fontSize: 24,
    fontWeight: '700',
  },
  card: {
    marginHorizontal: 16,
    marginTop: 16,
    backgroundColor: '#141414',
    borderRadius: 12,
    padding: 16,
  },
  cardTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#666',
    marginBottom: 12,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  label: {
    fontSize: 14,
    color: '#888',
  },
  value: {
    fontSize: 15,
    fontWeight: '600',
    color: '#FFF',
    fontVariant: ['tabular-nums'],
  },
  bigValue: {
    fontSize: 20,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
});
