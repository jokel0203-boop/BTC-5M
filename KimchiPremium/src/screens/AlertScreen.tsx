import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  TextInput,
  Switch,
  Modal,
} from 'react-native';
import { useAlerts } from '../hooks/useAlerts';
import { PremiumAlert, AlertCondition, AlertExchange, AlertLog } from '../types';

export function AlertScreen() {
  const { alerts, alertLogs, addAlert, removeAlert, toggleAlert, clearLogs } = useAlerts();
  const [showAddModal, setShowAddModal] = useState(false);
  const [showLogs, setShowLogs] = useState(false);

  // Add form state
  const [newSymbol, setNewSymbol] = useState('BTC');
  const [newExchange, setNewExchange] = useState<AlertExchange>('binance');
  const [newCondition, setNewCondition] = useState<AlertCondition>('above');
  const [newThreshold, setNewThreshold] = useState('3.0');

  const handleAdd = () => {
    const threshold = parseFloat(newThreshold);
    if (isNaN(threshold)) return;
    addAlert(newSymbol.trim(), newExchange, newCondition, threshold);
    setShowAddModal(false);
    setNewSymbol('BTC');
    setNewThreshold('3.0');
  };

  const renderAlert = ({ item }: { item: PremiumAlert }) => {
    const condStr = item.condition === 'above' ? '이상' : '이하';
    const exchStr = item.exchange === 'binance' ? 'Binance' : 'Indodax';
    return (
      <View style={styles.alertRow}>
        <View style={styles.alertInfo}>
          <Text style={styles.alertSymbol}>{item.symbol}</Text>
          <Text style={styles.alertDetail}>
            {exchStr} 프리미엄 {item.threshold}% {condStr}
          </Text>
          {item.triggered && item.triggeredAt && (
            <Text style={styles.triggeredText}>
              마지막 알림: {new Date(item.triggeredAt).toLocaleTimeString('ko-KR')}
            </Text>
          )}
        </View>
        <View style={styles.alertActions}>
          <Switch
            value={item.enabled}
            onValueChange={() => toggleAlert(item.id)}
            trackColor={{ false: '#333', true: '#4A90D9' }}
            thumbColor="#FFF"
          />
          <TouchableOpacity onPress={() => removeAlert(item.id)} style={styles.deleteBtn}>
            <Text style={styles.deleteText}>삭제</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  };

  const renderLog = ({ item }: { item: AlertLog }) => {
    const condStr = item.condition === 'above' ? '이상' : '이하';
    const exchStr = item.exchange === 'binance' ? 'Binance' : 'Indodax';
    return (
      <View style={styles.logRow}>
        <Text style={styles.logSymbol}>{item.symbol}</Text>
        <Text style={styles.logDetail}>
          {exchStr} {item.actualPremium.toFixed(2)}% (조건: {item.threshold}% {condStr})
        </Text>
        <Text style={styles.logTime}>
          {new Date(item.triggeredAt).toLocaleString('ko-KR')}
        </Text>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      {/* Tab Toggle */}
      <View style={styles.tabRow}>
        <TouchableOpacity
          style={[styles.tab, !showLogs && styles.tabActive]}
          onPress={() => setShowLogs(false)}
        >
          <Text style={[styles.tabText, !showLogs && styles.tabTextActive]}>
            알람 설정 ({alerts.length})
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, showLogs && styles.tabActive]}
          onPress={() => setShowLogs(true)}
        >
          <Text style={[styles.tabText, showLogs && styles.tabTextActive]}>
            알림 기록 ({alertLogs.length})
          </Text>
        </TouchableOpacity>
      </View>

      {!showLogs ? (
        <>
          <FlatList
            data={alerts}
            keyExtractor={item => item.id}
            renderItem={renderAlert}
            ListEmptyComponent={
              <View style={styles.empty}>
                <Text style={styles.emptyText}>설정된 알람이 없습니다</Text>
                <Text style={styles.emptySubtext}>+ 버튼으로 김프 알람을 추가하세요</Text>
              </View>
            }
            style={styles.list}
          />
          <TouchableOpacity style={styles.fab} onPress={() => setShowAddModal(true)}>
            <Text style={styles.fabText}>+</Text>
          </TouchableOpacity>
        </>
      ) : (
        <>
          <FlatList
            data={alertLogs}
            keyExtractor={item => item.id}
            renderItem={renderLog}
            ListEmptyComponent={
              <View style={styles.empty}>
                <Text style={styles.emptyText}>알림 기록이 없습니다</Text>
              </View>
            }
            style={styles.list}
          />
          {alertLogs.length > 0 && (
            <TouchableOpacity style={styles.clearBtn} onPress={clearLogs}>
              <Text style={styles.clearText}>기록 전체 삭제</Text>
            </TouchableOpacity>
          )}
        </>
      )}

      {/* Add Alert Modal */}
      <Modal visible={showAddModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>김프 알람 추가</Text>

            {/* Symbol */}
            <Text style={styles.fieldLabel}>코인 심볼</Text>
            <TextInput
              style={styles.textInput}
              value={newSymbol}
              onChangeText={setNewSymbol}
              placeholder="BTC"
              placeholderTextColor="#666"
              autoCapitalize="characters"
            />

            {/* Exchange */}
            <Text style={styles.fieldLabel}>거래소</Text>
            <View style={styles.toggleRow}>
              <TouchableOpacity
                style={[styles.toggleBtn, newExchange === 'binance' && styles.toggleActive]}
                onPress={() => setNewExchange('binance')}
              >
                <Text style={[styles.toggleText, newExchange === 'binance' && styles.toggleTextActive]}>
                  Binance
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.toggleBtn, newExchange === 'indodax' && styles.toggleActive]}
                onPress={() => setNewExchange('indodax')}
              >
                <Text style={[styles.toggleText, newExchange === 'indodax' && styles.toggleTextActive]}>
                  Indodax
                </Text>
              </TouchableOpacity>
            </View>

            {/* Condition */}
            <Text style={styles.fieldLabel}>조건</Text>
            <View style={styles.toggleRow}>
              <TouchableOpacity
                style={[styles.toggleBtn, newCondition === 'above' && styles.toggleActive]}
                onPress={() => setNewCondition('above')}
              >
                <Text style={[styles.toggleText, newCondition === 'above' && styles.toggleTextActive]}>
                  {'이상 (>=)'}
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.toggleBtn, newCondition === 'below' && styles.toggleActive]}
                onPress={() => setNewCondition('below')}
              >
                <Text style={[styles.toggleText, newCondition === 'below' && styles.toggleTextActive]}>
                  {'이하 (<=)'}
                </Text>
              </TouchableOpacity>
            </View>

            {/* Threshold */}
            <Text style={styles.fieldLabel}>프리미엄 기준값 (%)</Text>
            <TextInput
              style={styles.textInput}
              value={newThreshold}
              onChangeText={setNewThreshold}
              placeholder="3.0"
              placeholderTextColor="#666"
              keyboardType="decimal-pad"
            />

            {/* Preview */}
            <View style={styles.previewBox}>
              <Text style={styles.previewText}>
                {newSymbol.toUpperCase()} {newExchange === 'binance' ? 'Binance' : 'Indodax'} 프리미엄이{' '}
                {newThreshold}% {newCondition === 'above' ? '이상' : '이하'}이면 알림
              </Text>
            </View>

            {/* Buttons */}
            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setShowAddModal(false)}>
                <Text style={styles.cancelBtnText}>취소</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.addBtn} onPress={handleAdd}>
                <Text style={styles.addBtnText}>추가</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#111111' },
  tabRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  tab: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#4A90D9',
  },
  tabText: { fontSize: 14, color: '#666' },
  tabTextActive: { color: '#4A90D9', fontWeight: '600' },
  list: { flex: 1 },
  alertRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    borderBottomWidth: 0.5,
    borderBottomColor: '#2A2A2A',
  },
  alertInfo: { flex: 1 },
  alertSymbol: { fontSize: 18, fontWeight: '700', color: '#FFF' },
  alertDetail: { fontSize: 13, color: '#AAA', marginTop: 2 },
  triggeredText: { fontSize: 11, color: '#FF8800', marginTop: 4 },
  alertActions: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  deleteBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: '#331111',
  },
  deleteText: { color: '#FF4444', fontSize: 12, fontWeight: '600' },
  empty: { alignItems: 'center', paddingTop: 80 },
  emptyText: { color: '#666', fontSize: 16 },
  emptySubtext: { color: '#444', fontSize: 13, marginTop: 8 },
  fab: {
    position: 'absolute',
    right: 20,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#4A90D9',
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 4,
    shadowColor: '#4A90D9',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
  },
  fabText: { fontSize: 28, color: '#FFF', fontWeight: '300', marginTop: -2 },
  logRow: {
    padding: 14,
    borderBottomWidth: 0.5,
    borderBottomColor: '#2A2A2A',
  },
  logSymbol: { fontSize: 15, fontWeight: '700', color: '#FFF' },
  logDetail: { fontSize: 12, color: '#AAA', marginTop: 2 },
  logTime: { fontSize: 11, color: '#555', marginTop: 4 },
  clearBtn: {
    padding: 14,
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#2A2A2A',
  },
  clearText: { color: '#FF4444', fontSize: 14 },
  // Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#1A1A1A',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 20,
    textAlign: 'center',
  },
  fieldLabel: {
    fontSize: 13,
    color: '#888',
    marginBottom: 6,
    marginTop: 12,
  },
  textInput: {
    backgroundColor: '#222',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 16,
    color: '#FFF',
    borderWidth: 1,
    borderColor: '#333',
  },
  toggleRow: {
    flexDirection: 'row',
    gap: 10,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: '#222',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#333',
  },
  toggleActive: {
    backgroundColor: '#1A3355',
    borderColor: '#4A90D9',
  },
  toggleText: { fontSize: 14, color: '#888' },
  toggleTextActive: { color: '#4A90D9', fontWeight: '600' },
  previewBox: {
    marginTop: 16,
    padding: 12,
    backgroundColor: '#222',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#333',
  },
  previewText: { fontSize: 13, color: '#CCC', textAlign: 'center' },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#222',
    alignItems: 'center',
  },
  cancelBtnText: { color: '#888', fontSize: 16, fontWeight: '600' },
  addBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: '#4A90D9',
    alignItems: 'center',
  },
  addBtnText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
});
