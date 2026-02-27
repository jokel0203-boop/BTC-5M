import React, { memo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { CoinPrice, ExchangeRate } from '../types';
import { formatKRW, formatUSDT, formatPremium, getPremiumColor } from '../utils/premium';

interface Props {
  coin: CoinPrice;
  exchangeRates: ExchangeRate | null;
  onPress: (coin: CoinPrice) => void;
}

export const PremiumRow = memo(function PremiumRow({ coin, exchangeRates, onPress }: Props) {
  const premiumColor = getPremiumColor(coin.binancePremium);

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={() => onPress(coin)}
      activeOpacity={0.6}
    >
      {/* Left: Upbit */}
      <View style={styles.leftCol}>
        <Text style={styles.exchangeLabel}>업비트 (Upbit)</Text>
        <Text style={styles.pair}>{coin.symbol}/KRW</Text>
        <Text style={styles.price}>
          {coin.upbitPrice ? `${formatKRW(coin.upbitPrice)} KRW` : '-'}
        </Text>
      </View>

      {/* Center: Binance */}
      <View style={styles.centerCol}>
        <Text style={styles.exchangeLabel}>바이낸스 (Binance)</Text>
        <Text style={styles.pair}>{coin.symbol}/USDT</Text>
        <Text style={styles.price}>
          {coin.binancePrice ? `${formatUSDT(coin.binancePrice)} USDT` : '-'}
        </Text>
      </View>

      {/* Right: Premium */}
      <View style={styles.rightCol}>
        <Text style={styles.premiumLabel}>프리미엄</Text>
        <Text style={[styles.premiumValue, { color: premiumColor }]}>
          {formatPremium(coin.binancePremium)}
        </Text>
      </View>
    </TouchableOpacity>
  );
});

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  leftCol: {
    flex: 4,
  },
  centerCol: {
    flex: 4,
    alignItems: 'center',
  },
  rightCol: {
    flex: 3,
    alignItems: 'flex-end',
    justifyContent: 'center',
  },
  exchangeLabel: {
    fontSize: 9,
    color: '#666',
    marginBottom: 2,
  },
  pair: {
    fontSize: 12,
    fontWeight: '700',
    color: '#D0D0D0',
    marginBottom: 2,
  },
  price: {
    fontSize: 11,
    color: '#999',
    fontVariant: ['tabular-nums'],
  },
  premiumLabel: {
    fontSize: 9,
    color: '#666',
    marginBottom: 4,
  },
  premiumValue: {
    fontSize: 16,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
});
