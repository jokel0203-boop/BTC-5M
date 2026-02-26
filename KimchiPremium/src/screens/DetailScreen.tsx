import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { CoinPrice, ExchangeRate } from '../types';
import {
  formatKRW,
  formatUSDT,
  formatIDR,
  formatPremium,
  getPremiumColor,
} from '../utils/premium';

export function DetailScreen({ route }: any) {
  const { coin, exchangeRates } = route.params;

  const binancePriceKrw = coin.binancePrice
    ? coin.binancePrice * exchangeRates.usdKrw
    : null;

  const indodaxPriceKrw = coin.indodaxPrice
    ? coin.indodaxPrice * exchangeRates.idrKrw
    : null;

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.symbol}>{coin.symbol}</Text>
      </View>

      {/* Upbit Price */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>업비트 (KRW)</Text>
        <View style={styles.priceCard}>
          <Text style={styles.priceLabel}>현재가</Text>
          <Text style={styles.priceValue}>
            {coin.upbitPrice ? formatKRW(coin.upbitPrice) : '-'}
          </Text>
        </View>
      </View>

      {/* Binance Comparison */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>바이낸스 (USDT) 비교</Text>
        <View style={styles.priceCard}>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>USDT 가격</Text>
            <Text style={styles.priceValue}>
              {coin.binancePrice ? formatUSDT(coin.binancePrice) : '-'}
            </Text>
          </View>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>KRW 환산가</Text>
            <Text style={styles.priceValue}>
              {binancePriceKrw ? formatKRW(binancePriceKrw) : '-'}
            </Text>
          </View>
          <View style={styles.divider} />
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>김프 (프리미엄)</Text>
            <Text
              style={[
                styles.premiumValue,
                { color: getPremiumColor(coin.binancePremium) },
              ]}
            >
              {formatPremium(coin.binancePremium)}
            </Text>
          </View>
          {coin.binancePremium !== null && coin.upbitPrice && binancePriceKrw && (
            <View style={styles.priceRow}>
              <Text style={styles.priceLabel}>가격 차이</Text>
              <Text style={styles.diffValue}>
                {formatKRW(coin.upbitPrice - binancePriceKrw)}
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Indodax Comparison */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>인도닥스 (IDR) 비교</Text>
        <View style={styles.priceCard}>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>IDR 가격</Text>
            <Text style={styles.priceValue}>
              {coin.indodaxPrice ? formatIDR(coin.indodaxPrice) : '-'}
            </Text>
          </View>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>KRW 환산가</Text>
            <Text style={styles.priceValue}>
              {indodaxPriceKrw ? formatKRW(indodaxPriceKrw) : '-'}
            </Text>
          </View>
          <View style={styles.divider} />
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>김프 (프리미엄)</Text>
            <Text
              style={[
                styles.premiumValue,
                { color: getPremiumColor(coin.indodaxPremium) },
              ]}
            >
              {formatPremium(coin.indodaxPremium)}
            </Text>
          </View>
          {coin.indodaxPremium !== null && coin.upbitPrice && indodaxPriceKrw && (
            <View style={styles.priceRow}>
              <Text style={styles.priceLabel}>가격 차이</Text>
              <Text style={styles.diffValue}>
                {formatKRW(coin.upbitPrice - indodaxPriceKrw)}
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Exchange Rate Info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>환율 정보</Text>
        <View style={styles.priceCard}>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>USD/KRW</Text>
            <Text style={styles.priceValue}>₩{exchangeRates.usdKrw.toFixed(2)}</Text>
          </View>
          <View style={styles.priceRow}>
            <Text style={styles.priceLabel}>IDR/KRW</Text>
            <Text style={styles.priceValue}>₩{exchangeRates.idrKrw.toFixed(6)}</Text>
          </View>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111111',
  },
  header: {
    padding: 20,
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  symbol: {
    fontSize: 32,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  section: {
    padding: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#888888',
    marginBottom: 10,
  },
  priceCard: {
    backgroundColor: '#1A1A1A',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  priceLabel: {
    fontSize: 14,
    color: '#999999',
  },
  priceValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  premiumValue: {
    fontSize: 20,
    fontWeight: '700',
  },
  diffValue: {
    fontSize: 14,
    color: '#AAAAAA',
  },
  divider: {
    height: 1,
    backgroundColor: '#333333',
    marginVertical: 4,
  },
});
