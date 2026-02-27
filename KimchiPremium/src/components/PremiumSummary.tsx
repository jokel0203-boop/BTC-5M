import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { ExchangeRate, CoinPrice } from '../types';
import { getPremiumColor } from '../utils/premium';

interface Props {
  btcPremium: number | null;
  avgPremium: number | null;
  exchangeRates: ExchangeRate | null;
  lastUpdated: Date | null;
  coinCount: number;
}

export function PremiumSummary({
  btcPremium,
  avgPremium,
  exchangeRates,
  lastUpdated,
  coinCount,
}: Props) {
  const formatPct = (val: number | null) => {
    if (val === null) return '-';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  };

  return (
    <View style={styles.container}>
      {/* BTC Premium - main display */}
      <View style={styles.mainRow}>
        <View style={styles.btcSection}>
          <Text style={styles.btcLabel}>BTC 김치프리미엄</Text>
          <Text style={[styles.btcValue, { color: getPremiumColor(btcPremium) }]}>
            {formatPct(btcPremium)}
          </Text>
        </View>
        <View style={styles.avgSection}>
          <Text style={styles.avgLabel}>평균 김프</Text>
          <Text style={[styles.avgValue, { color: getPremiumColor(avgPremium) }]}>
            {formatPct(avgPremium)}
          </Text>
        </View>
      </View>

      {/* Info row */}
      <View style={styles.infoRow}>
        <Text style={styles.infoText}>
          {exchangeRates ? `USD/KRW ${exchangeRates.usdKrw.toFixed(0)}` : '환율 로딩...'}
        </Text>
        <Text style={styles.infoText}>{coinCount}개 코인</Text>
        <Text style={styles.infoText}>
          {lastUpdated ? lastUpdated.toLocaleTimeString('ko-KR') : '...'}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 10,
    backgroundColor: '#0D0D0D',
  },
  mainRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
  },
  btcSection: {
    flex: 1,
  },
  btcLabel: {
    fontSize: 12,
    color: '#777',
    marginBottom: 4,
  },
  btcValue: {
    fontSize: 28,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  avgSection: {
    alignItems: 'flex-end',
  },
  avgLabel: {
    fontSize: 12,
    color: '#777',
    marginBottom: 4,
  },
  avgValue: {
    fontSize: 20,
    fontWeight: '700',
    fontVariant: ['tabular-nums'],
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingTop: 8,
    borderTopWidth: 0.5,
    borderTopColor: '#222',
  },
  infoText: {
    fontSize: 11,
    color: '#555',
    fontVariant: ['tabular-nums'],
  },
});
