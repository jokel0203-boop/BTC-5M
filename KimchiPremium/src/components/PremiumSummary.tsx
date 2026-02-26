import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { ExchangeRate } from '../types';
import { getPremiumColor } from '../utils/premium';

interface Props {
  avgBinancePremium: number | null;
  avgIndodaxPremium: number | null;
  exchangeRates: ExchangeRate | null;
  lastUpdated: Date | null;
  coinCount: number;
}

export function PremiumSummary({
  avgBinancePremium,
  avgIndodaxPremium,
  exchangeRates,
  lastUpdated,
  coinCount,
}: Props) {
  const formatAvg = (val: number | null) => {
    if (val === null) return '-';
    return `${val >= 0 ? '+' : ''}${val.toFixed(2)}%`;
  };

  return (
    <View style={styles.container}>
      <View style={styles.row}>
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Binance 평균 프리미엄</Text>
          <Text style={[styles.cardValue, { color: getPremiumColor(avgBinancePremium) }]}>
            {formatAvg(avgBinancePremium)}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.cardLabel}>Indodax 평균 프리미엄</Text>
          <Text style={[styles.cardValue, { color: getPremiumColor(avgIndodaxPremium) }]}>
            {formatAvg(avgIndodaxPremium)}
          </Text>
        </View>
      </View>

      <View style={styles.infoRow}>
        <Text style={styles.infoText}>
          {exchangeRates ? `USD/KRW: ₩${exchangeRates.usdKrw.toFixed(0)}` : '환율 로딩 중...'}
        </Text>
        <Text style={styles.infoText}>
          {coinCount}개 코인
        </Text>
        <Text style={styles.infoText}>
          {lastUpdated
            ? `${lastUpdated.toLocaleTimeString('ko-KR')} 업데이트`
            : '로딩 중...'}
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    backgroundColor: '#111111',
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  card: {
    flex: 1,
    backgroundColor: '#1A1A1A',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  cardLabel: {
    fontSize: 11,
    color: '#888888',
    marginBottom: 6,
  },
  cardValue: {
    fontSize: 22,
    fontWeight: '700',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10,
    paddingHorizontal: 4,
  },
  infoText: {
    fontSize: 10,
    color: '#555555',
  },
});
