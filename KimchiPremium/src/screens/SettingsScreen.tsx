import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TextInput,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { useSettings } from '../contexts/SettingsContext';
import { ForeignExchange } from '../types';

const EXCHANGES: { key: ForeignExchange; label: string; desc: string }[] = [
  { key: 'binance_spot', label: '바이낸스 현물', desc: 'Upbit ↔ Binance Spot (USDT)' },
  { key: 'binance_futures', label: '바이낸스 선물', desc: 'Upbit ↔ Binance Futures (USDT)' },
  { key: 'indodax', label: 'Indodax', desc: 'Upbit ↔ Indodax (IDR)' },
];

interface Props {
  navigation: any;
}

export function SettingsScreen({ navigation }: Props) {
  const { settings, setProxyUrl, setForeignExchange } = useSettings();
  const [inputUrl, setInputUrl] = useState(settings.proxyUrl);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  const handleSaveProxy = () => {
    let url = inputUrl.trim();
    // IP만 입력한 경우 http://와 포트 자동 추가
    if (url && !url.startsWith('http')) {
      url = `http://${url}`;
    }
    if (url && !url.includes(':3001') && !url.includes(':80')) {
      url = `${url}:3001`;
    }
    setInputUrl(url);
    setProxyUrl(url);
    setTestResult(null);
  };

  const handleTestProxy = async () => {
    handleSaveProxy();
    setTesting(true);
    setTestResult(null);

    let url = inputUrl.trim();
    if (url && !url.startsWith('http')) url = `http://${url}`;
    if (url && !url.includes(':3001') && !url.includes(':80')) url = `${url}:3001`;

    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 5000);
      const res = await fetch(`${url}/api/health`, { signal: controller.signal });
      clearTimeout(timeout);
      const data = await res.json();
      if (data.ok) {
        setTestResult(`연결 성공! 바이낸스: ${data.counts?.binanceSpot || 0}개, Indodax: ${data.counts?.indodax || 0}개`);
      } else {
        setTestResult('서버 응답이 비정상입니다');
      }
    } catch (e: any) {
      setTestResult(`연결 실패: ${e.message}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* 프록시 서버 설정 */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>프록시 서버</Text>
        <Text style={styles.sectionDesc}>
          VPS IP를 입력하세요. VPS에서 바이낸스 데이터를 가져와 중계합니다.
        </Text>
        <View style={styles.inputRow}>
          <TextInput
            style={styles.textInput}
            value={inputUrl}
            onChangeText={setInputUrl}
            placeholder="VPS IP (예: 123.45.67.89)"
            placeholderTextColor="#555"
            autoCapitalize="none"
            autoCorrect={false}
            onBlur={handleSaveProxy}
          />
        </View>
        <View style={styles.buttonRow}>
          <TouchableOpacity style={styles.saveBtn} onPress={handleSaveProxy}>
            <Text style={styles.saveBtnText}>저장</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.testBtn} onPress={handleTestProxy} disabled={testing}>
            {testing ? (
              <ActivityIndicator size="small" color="#3B82F6" />
            ) : (
              <Text style={styles.testBtnText}>연결 테스트</Text>
            )}
          </TouchableOpacity>
        </View>
        {testResult && (
          <Text style={[styles.testResult, testResult.includes('성공') ? styles.testSuccess : styles.testFail]}>
            {testResult}
          </Text>
        )}
        {!settings.proxyUrl && (
          <View style={styles.warningBox}>
            <Text style={styles.warningText}>
              프록시 미설정 - 프리미엄 데이터를 볼 수 없습니다
            </Text>
          </View>
        )}
      </View>

      {/* 비교 마켓 선택 */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>비교 마켓</Text>
        <Text style={styles.sectionDesc}>
          업비트와 비교할 해외 거래소를 선택하세요.
        </Text>
        {EXCHANGES.map(ex => (
          <TouchableOpacity
            key={ex.key}
            style={[
              styles.exchangeOption,
              settings.foreignExchange === ex.key && styles.exchangeOptionActive,
            ]}
            onPress={() => setForeignExchange(ex.key)}
          >
            <View style={styles.radioOuter}>
              {settings.foreignExchange === ex.key && <View style={styles.radioInner} />}
            </View>
            <View style={styles.exchangeInfo}>
              <Text style={[
                styles.exchangeLabel,
                settings.foreignExchange === ex.key && styles.exchangeLabelActive,
              ]}>
                {ex.label}
              </Text>
              <Text style={styles.exchangeDesc}>{ex.desc}</Text>
            </View>
          </TouchableOpacity>
        ))}
      </View>

      {/* 프리미엄 알람 바로가기 */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>프리미엄 알람</Text>
        <TouchableOpacity
          style={styles.alarmBtn}
          onPress={() => navigation.navigate('알림')}
        >
          <Text style={styles.alarmBtnText}>알람 설정하기</Text>
          <Text style={styles.alarmBtnArrow}>{'>'}</Text>
        </TouchableOpacity>
        <Text style={styles.sectionDesc}>
          특정 코인의 김프가 설정값 이상/이하일 때 알림을 받습니다.
        </Text>
      </View>

      {/* 앱 정보 */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>앱 정보</Text>
        <View style={styles.infoRow}>
          <Text style={styles.label}>국내 거래소</Text>
          <Text style={styles.value}>Upbit (직접 호출)</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.label}>해외 데이터</Text>
          <Text style={styles.value}>VPS 프록시 경유</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.label}>새로고침</Text>
          <Text style={styles.value}>1초</Text>
        </View>
        <View style={styles.infoRow}>
          <Text style={styles.label}>버전</Text>
          <Text style={styles.value}>2.0.0</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.disclaimer}>
          * VPS에서 proxy-server.js를 실행해야 합니다.{'\n'}
          * node proxy-server.js (포트 3001){'\n'}
          * 본 앱은 정보 제공 목적이며 투자 조언이 아닙니다.
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
    fontSize: 13,
    fontWeight: '700',
    color: '#3B82F6',
    marginBottom: 6,
  },
  sectionDesc: {
    fontSize: 12,
    color: '#666',
    marginBottom: 12,
    lineHeight: 18,
  },

  // 프록시 입력
  inputRow: {
    marginBottom: 10,
  },
  textInput: {
    backgroundColor: '#1A1A1A',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 15,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#333',
  },
  buttonRow: {
    flexDirection: 'row',
    gap: 10,
  },
  saveBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#3B82F6',
    alignItems: 'center',
  },
  saveBtnText: { color: '#FFF', fontSize: 14, fontWeight: '600' },
  testBtn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    backgroundColor: '#1A1A1A',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#333',
  },
  testBtnText: { color: '#3B82F6', fontSize: 14, fontWeight: '600' },
  testResult: {
    marginTop: 10,
    fontSize: 12,
    textAlign: 'center',
    paddingVertical: 8,
    borderRadius: 6,
  },
  testSuccess: { color: '#22C55E', backgroundColor: '#0A2612' },
  testFail: { color: '#EF4444', backgroundColor: '#1C0A0A' },
  warningBox: {
    marginTop: 10,
    padding: 10,
    backgroundColor: '#2A1A00',
    borderRadius: 6,
  },
  warningText: { color: '#F59E0B', fontSize: 12, textAlign: 'center' },

  // 마켓 선택
  exchangeOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 10,
    backgroundColor: '#141414',
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#222',
  },
  exchangeOptionActive: {
    borderColor: '#3B82F6',
    backgroundColor: '#0F1A2E',
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#444',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#3B82F6',
  },
  exchangeInfo: { flex: 1 },
  exchangeLabel: {
    fontSize: 15,
    fontWeight: '600',
    color: '#CCC',
  },
  exchangeLabelActive: { color: '#FFF' },
  exchangeDesc: {
    fontSize: 11,
    color: '#666',
    marginTop: 2,
  },

  // 알람 버튼
  alarmBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 16,
    borderRadius: 10,
    backgroundColor: '#141414',
    marginBottom: 10,
    borderWidth: 1,
    borderColor: '#222',
  },
  alarmBtnText: { color: '#FFF', fontSize: 15, fontWeight: '600' },
  alarmBtnArrow: { color: '#666', fontSize: 18 },

  // 앱 정보
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
  },
  label: { fontSize: 14, color: '#888' },
  value: { fontSize: 14, color: '#FFF' },
  disclaimer: {
    fontSize: 11,
    color: '#555',
    lineHeight: 18,
  },
});
