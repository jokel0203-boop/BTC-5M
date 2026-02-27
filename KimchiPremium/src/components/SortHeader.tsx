import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SortField, SortOrder } from '../types';

interface Props {
  sortField: SortField;
  sortOrder: SortOrder;
  onSort: (field: SortField) => void;
}

function Arrow({ field, current, order }: { field: SortField; current: SortField; order: SortOrder }) {
  if (field !== current) return null;
  return <Text style={styles.arrow}>{order === 'desc' ? ' ▼' : ' ▲'}</Text>;
}

export function SortHeader({ sortField, sortOrder, onSort }: Props) {
  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.symbolCol} onPress={() => onSort('symbol')}>
        <Text style={[styles.headerText, sortField === 'symbol' && styles.activeText]}>
          코인명
          <Arrow field="symbol" current={sortField} order={sortOrder} />
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.priceCol} onPress={() => onSort('upbitPrice')}>
        <Text style={[styles.headerText, sortField === 'upbitPrice' && styles.activeText]}>
          현재가(KRW)
          <Arrow field="upbitPrice" current={sortField} order={sortOrder} />
        </Text>
      </TouchableOpacity>

      <TouchableOpacity style={styles.premiumCol} onPress={() => onSort('binancePremium')}>
        <Text style={[styles.headerText, sortField === 'binancePremium' && styles.activeText]}>
          김프
          <Arrow field="binancePremium" current={sortField} order={sortOrder} />
        </Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#222',
  },
  symbolCol: {
    width: 70,
  },
  priceCol: {
    flex: 1,
    alignItems: 'flex-end',
    paddingRight: 20,
  },
  premiumCol: {
    width: 80,
    alignItems: 'flex-end',
  },
  headerText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#666',
  },
  activeText: {
    color: '#999',
  },
  arrow: {
    fontSize: 9,
    color: '#999',
  },
});
