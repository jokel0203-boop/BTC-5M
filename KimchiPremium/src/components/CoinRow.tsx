import React, { memo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { CoinPrice } from '../types';
import { formatKRW, formatPremium, formatChangeRate, getPremiumColor, getChangeColor } from '../utils/premium';

interface Props {
  coin: CoinPrice;
  onPress: (coin: CoinPrice) => void;
}

export const CoinRow = memo(function CoinRow({ coin, onPress }: Props) {
  return (
    <TouchableOpacity
      style={styles.container}
      onPress={() => onPress(coin)}
      activeOpacity={0.6}
    >
      {/* Left: Symbol */}
      <View style={styles.symbolCol}>
        <Text style={styles.symbol}>{coin.symbol}</Text>
      </View>

      {/* Center: Upbit KRW price + 24h change */}
      <View style={styles.priceCol}>
        <Text style={styles.price}>
          {coin.upbitPrice ? formatKRW(coin.upbitPrice) : '-'}
        </Text>
        <Text style={[styles.changeRate, { color: getChangeColor(coin.changeRate) }]}>
          {formatChangeRate(coin.changeRate)}
        </Text>
      </View>

      {/* Right: Premium */}
      <View style={styles.premiumCol}>
        <Text style={[styles.premium, { color: getPremiumColor(coin.binancePremium) }]}>
          {formatPremium(coin.binancePremium)}
        </Text>
      </View>
    </TouchableOpacity>
  );
});

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 13,
    paddingHorizontal: 16,
    borderBottomWidth: 0.5,
    borderBottomColor: '#1A1A1A',
  },
  symbolCol: {
    width: 70,
  },
  symbol: {
    fontSize: 14,
    fontWeight: '700',
    color: '#E0E0E0',
  },
  priceCol: {
    flex: 1,
    alignItems: 'flex-end',
    paddingRight: 20,
  },
  price: {
    fontSize: 14,
    fontWeight: '600',
    color: '#FFFFFF',
    fontVariant: ['tabular-nums'],
  },
  changeRate: {
    fontSize: 11,
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
  premiumCol: {
    width: 80,
    alignItems: 'flex-end',
  },
  premium: {
    fontSize: 15,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
});
