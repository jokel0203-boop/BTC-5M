import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';

export function SettingsScreen() {
  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>데이터 소스</Text>
        <View style={styles.infoRow}>
          <Text style={styles.label}>국내 거래소</Text>
          <Text style={styles.value}>Upbit</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.label}>해외 거래소</Text>
          <Text style={styles.value}>Binance</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.label}>환율</Text>
          <Text style={styles.value}>Open Exchange Rates</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.label}>새로고침</Text>
          <Text style={styles.value}>5초</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>앱 정보</Text>
        <View style={styles.infoRow}>
          <Text style={styles.label}>버전</Text>
          <Text style={styles.value}>1.0.0</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.disclaimer}>
          * 본 앱은 정보 제공 목적이며, 투자 조언이 아닙니다.{'\n'}
          * 실시간 데이터는 각 거래소 API에서 제공됩니다.{'\n'}
          * 프리미엄은 환율에 따라 변동됩니다.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
  },
  section: {
    padding: 16,
    borderBottomWidth: 0.5,
    borderBottomColor: '#1A1A1A',
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '600',
    color: '#3B82F6',
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
  },
  label: {
    fontSize: 14,
    color: '#888',
  },
  value: {
    fontSize: 14,
    color: '#FFF',
  },
  disclaimer: {
    fontSize: 11,
    color: '#555',
    lineHeight: 18,
  },
});
