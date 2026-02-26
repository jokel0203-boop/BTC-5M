import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { CoinPrice } from '../types';
import { formatKRW, formatPremium, getPremiumColor } from '../utils/premium';

interface Props {
  coin: CoinPrice;
  onPress: (coin: CoinPrice) => void;
}

export function CoinRow({ coin, onPress }: Props) {
  return (
    <TouchableOpacity style={styles.container} onPress={() => onPress(coin)}>
      <View style={styles.symbolContainer}>
        <Text style={styles.symbol}>{coin.symbol}</Text>
        <Text style={styles.price}>{coin.upbitPrice ? formatKRW(coin.upbitPrice) : '-'}</Text>
      </View>

      <View style={styles.premiumContainer}>
        <View style={styles.premiumItem}>
          <Text style={styles.exchangeLabel}>Binance</Text>
          <Text style={[styles.premiumValue, { color: getPremiumColor(coin.binancePremium) }]}>
            {formatPremium(coin.binancePremium)}
          </Text>
        </View>

        <View style={styles.premiumItem}>
          <Text style={styles.exchangeLabel}>Indodax</Text>
          <Text style={[styles.premiumValue, { color: getPremiumColor(coin.indodaxPremium) }]}>
            {formatPremium(coin.indodaxPremium)}
          </Text>
        </View>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderBottomWidth: 0.5,
    borderBottomColor: '#2A2A2A',
  },
  symbolContainer: {
    flex: 1,
  },
  symbol: {
    fontSize: 16,
    fontWeight: '700',
    color: '#FFFFFF',
  },
  price: {
    fontSize: 12,
    color: '#AAAAAA',
    marginTop: 2,
  },
  premiumContainer: {
    flexDirection: 'row',
    gap: 16,
  },
  premiumItem: {
    alignItems: 'flex-end',
    minWidth: 75,
  },
  exchangeLabel: {
    fontSize: 10,
    color: '#666666',
    marginBottom: 2,
  },
  premiumValue: {
    fontSize: 15,
    fontWeight: '600',
  },
});
