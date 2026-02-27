import React, { memo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { CoinPrice } from '../types';
import {
  formatKRW,
  formatChangeRate,
  formatChangePrice,
  formatVolume,
  getChangeColor,
} from '../utils/premium';

interface Props {
  coin: CoinPrice;
  onPress: (coin: CoinPrice) => void;
}

export const ExchangeRow = memo(function ExchangeRow({ coin, onPress }: Props) {
  const changeColor = getChangeColor(coin.changeRate);

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={() => onPress(coin)}
      activeOpacity={0.6}
    >
      {/* Left: Symbol + exchange */}
      <View style={styles.leftCol}>
        <Text style={styles.symbol}>{coin.symbol}/KRW</Text>
        <Text style={styles.exchange}>업비트 (Upbit)</Text>
      </View>

      {/* Center: Price + volume */}
      <View style={styles.centerCol}>
        <Text style={[styles.price, { color: changeColor }]}>
          {coin.upbitPrice ? formatKRW(coin.upbitPrice) : '-'}
        </Text>
        <Text style={styles.volume}>
          {coin.tradeVolume24h ? formatVolume(coin.tradeVolume24h) : '-'}
        </Text>
      </View>

      {/* Right: Change rate + change price */}
      <View style={styles.rightCol}>
        <Text style={[styles.changeRate, { color: changeColor }]}>
          {formatChangeRate(coin.changeRate)}
        </Text>
        <Text style={[styles.changePrice, { color: changeColor }]}>
          {formatChangePrice(coin.changePrice)}
        </Text>
      </View>
    </TouchableOpacity>
  );
});

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 14,
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  leftCol: {
    flex: 1,
  },
  symbol: {
    fontSize: 13,
    fontWeight: '700',
    color: '#E0E0E0',
  },
  exchange: {
    fontSize: 10,
    color: '#666',
    marginTop: 2,
  },
  centerCol: {
    flex: 1,
    alignItems: 'flex-end',
  },
  price: {
    fontSize: 14,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  volume: {
    fontSize: 10,
    color: '#666',
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
  rightCol: {
    width: 90,
    alignItems: 'flex-end',
  },
  changeRate: {
    fontSize: 13,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  changePrice: {
    fontSize: 10,
    marginTop: 2,
    fontVariant: ['tabular-nums'],
  },
});
