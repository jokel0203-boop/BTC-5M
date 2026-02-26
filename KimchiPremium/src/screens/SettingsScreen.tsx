import React, { useState } from 'react';
import { View, Text, StyleSheet, Switch, ScrollView } from 'react-native';

export function SettingsScreen() {
  const [refreshInterval, setRefreshInterval] = useState(10);
  const [alertEnabled, setAlertEnabled] = useState(false);
  const [showOnlyCommon, setShowOnlyCommon] = useState(false);

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>일반</Text>

        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingLabel}>공통 코인만 표시</Text>
            <Text style={styles.settingDesc}>모든 거래소에 상장된 코인만 보기</Text>
          </View>
          <Switch
            value={showOnlyCommon}
            onValueChange={setShowOnlyCommon}
            trackColor={{ false: '#333333', true: '#4A90D9' }}
            thumbColor="#FFFFFF"
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>알림</Text>

        <View style={styles.settingRow}>
          <View>
            <Text style={styles.settingLabel}>프리미엄 알림</Text>
            <Text style={styles.settingDesc}>김프가 설정값 이상일 때 알림</Text>
          </View>
          <Switch
            value={alertEnabled}
            onValueChange={setAlertEnabled}
            trackColor={{ false: '#333333', true: '#4A90D9' }}
            thumbColor="#FFFFFF"
          />
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>정보</Text>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>데이터 소스</Text>
          <Text style={styles.infoValue}>Upbit, Binance, Indodax</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>환율 소스</Text>
          <Text style={styles.infoValue}>Open Exchange Rates</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>새로고침 간격</Text>
          <Text style={styles.infoValue}>{refreshInterval}초</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>버전</Text>
          <Text style={styles.infoValue}>1.0.0</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.disclaimer}>
          * 본 앱은 정보 제공 목적이며, 투자 조언이 아닙니다.{'\n'}
          * 실시간 데이터는 각 거래소 API에서 제공됩니다.{'\n'}
          * 김치 프리미엄은 환율 변동에 따라 달라질 수 있습니다.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#111111',
  },
  section: {
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: '600',
    color: '#4A90D9',
    marginBottom: 12,
    textTransform: 'uppercase',
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  settingLabel: {
    fontSize: 15,
    color: '#FFFFFF',
    fontWeight: '500',
  },
  settingDesc: {
    fontSize: 12,
    color: '#666666',
    marginTop: 2,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
  },
  infoLabel: {
    fontSize: 14,
    color: '#999999',
  },
  infoValue: {
    fontSize: 14,
    color: '#FFFFFF',
  },
  disclaimer: {
    fontSize: 11,
    color: '#555555',
    lineHeight: 18,
  },
});
