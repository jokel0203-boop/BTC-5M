import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { SortField, SortOrder } from '../types';

interface Props {
  sortField: SortField;
  sortOrder: SortOrder;
  onSort: (field: SortField) => void;
}

function SortArrow({ field, currentField, order }: { field: SortField; currentField: SortField; order: SortOrder }) {
  if (field !== currentField) return <Text style={styles.arrowInactive}> ↕</Text>;
  return <Text style={styles.arrowActive}>{order === 'desc' ? ' ↓' : ' ↑'}</Text>;
}

export function SortHeader({ sortField, sortOrder, onSort }: Props) {
  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.symbolCol} onPress={() => onSort('symbol')}>
        <Text style={styles.headerText}>
          코인
          <SortArrow field="symbol" currentField={sortField} order={sortOrder} />
        </Text>
      </TouchableOpacity>

      <View style={styles.premiumCols}>
        <TouchableOpacity style={styles.premiumCol} onPress={() => onSort('binancePremium')}>
          <Text style={styles.headerText}>
            Binance
            <SortArrow field="binancePremium" currentField={sortField} order={sortOrder} />
          </Text>
        </TouchableOpacity>

        <TouchableOpacity style={styles.premiumCol} onPress={() => onSort('indodaxPremium')}>
          <Text style={styles.headerText}>
            Indodax
            <SortArrow field="indodaxPremium" currentField={sortField} order={sortOrder} />
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 16,
    backgroundColor: '#1A1A1A',
    borderBottomWidth: 1,
    borderBottomColor: '#333333',
  },
  symbolCol: {
    flex: 1,
  },
  premiumCols: {
    flexDirection: 'row',
    gap: 16,
  },
  premiumCol: {
    alignItems: 'flex-end',
    minWidth: 75,
  },
  headerText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#888888',
  },
  arrowActive: {
    color: '#4A90D9',
  },
  arrowInactive: {
    color: '#444444',
  },
});
