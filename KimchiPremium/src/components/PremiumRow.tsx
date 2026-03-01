import React, { memo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { CoinPrice, ForeignExchange } from '../types';
import { formatKRW, formatForeignPrice, formatPremium, getPremiumColor } from '../utils/premium';

interface Props {
  coin: CoinPrice;
  foreignExchange: ForeignExchange;
  onPress: (coin: CoinPrice) => void;
  onAlarmPress?: (coin: CoinPrice) => void;
}

export const PremiumRow = memo(function PremiumRow({ coin, foreignExchange, onPress, onAlarmPress }: Props) {
  const premiumColor = getPremiumColor(coin.premium);

  return (
    <TouchableOpacity
      style={styles.container}
      onPress={() => onPress(coin)}
      activeOpacity={0.6}
    >
      {/* Left: Symbol + Upbit */}
      <View style={styles.leftCol}>
        <Text style={styles.symbol}>{coin.symbol}</Text>
        <Text style={styles.price}>
          {coin.upbitPrice ? `${formatKRW(coin.upbitPrice)}` : '-'}
        </Text>
      </View>

      {/* Center: Foreign price */}
      <View style={styles.centerCol}>
        <Text style={styles.foreignPrice}>
          {coin.foreignPrice ? formatForeignPrice(coin.foreignPrice, foreignExchange) : '-'}
        </Text>
      </View>

      {/* Right: Premium */}
      <View style={styles.rightCol}>
        <Text style={[styles.premiumValue, { color: premiumColor }]}>
          {formatPremium(coin.premium)}
        </Text>
      </View>

      {/* Alarm Button */}
      {onAlarmPress && (
        <TouchableOpacity
          style={styles.alarmBtn}
          onPress={() => onAlarmPress(coin)}
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <Text style={styles.alarmIcon}>{'\u{1F514}'}</Text>
        </TouchableOpacity>
      )}
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
    flex: 3,
  },
  centerCol: {
    flex: 3,
    alignItems: 'center',
  },
  rightCol: {
    flex: 3,
    alignItems: 'flex-end',
  },
  symbol: {
    fontSize: 14,
    fontWeight: '700',
    color: '#FFFFFF',
    marginBottom: 2,
  },
  price: {
    fontSize: 12,
    color: '#999',
    fontVariant: ['tabular-nums'],
  },
  foreignPrice: {
    fontSize: 12,
    color: '#888',
    fontVariant: ['tabular-nums'],
  },
  premiumValue: {
    fontSize: 17,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  alarmBtn: {
    width: 32,
    height: 32,
    justifyContent: 'center',
    alignItems: 'center',
    marginLeft: 4,
  },
  alarmIcon: {
    fontSize: 16,
  },
});
