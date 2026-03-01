import React, { useMemo, useEffect, useState, useCallback } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Text,
  RefreshControl,
  TouchableOpacity,
  Modal,
  TextInput,
  ScrollView,
} from 'react-native';
import { useCoinData } from '../hooks/useCoinData';
import { useAlerts } from '../hooks/useAlerts';
import { useSettings } from '../contexts/SettingsContext';
import { ExchangeRow } from '../components/ExchangeRow';
import { PremiumRow } from '../components/PremiumRow';
import { SearchBar } from '../components/SearchBar';
import { CoinPrice, SortField, ForeignExchange, AlertCondition } from '../types';
import { getExchangeLabel, getCurrencyUnit } from '../utils/premium';

type TabType = 'exchange' | 'premium';

const EXCHANGE_TABS: { key: ForeignExchange; label: string; short: string }[] = [
  { key: 'binance_spot', label: '바이낸스 현물', short: '현물' },
  { key: 'binance_futures', label: '바이낸스 선물', short: '선물' },
  { key: 'indodax', label: 'Indodax', short: 'IDX' },
];

interface Props {
  navigation: any;
}

export function HomeScreen({ navigation }: Props) {
  const [activeTab, setActiveTab] = useState<TabType>('exchange');
  const { settings, setForeignExchange } = useSettings();

  const {
    coins,
    exchangeRates,
    loading,
    error,
    lastUpdated,
    refresh,
    sortField,
    sortOrder,
    setSortField,
    searchQuery,
    setSearchQuery,
    dataSource,
  } = useCoinData(settings, 5);

  const { checkAlerts, addAlert } = useAlerts();

  // Alarm modal state
  const [showAlarmModal, setShowAlarmModal] = useState(false);
  const [alarmCoin, setAlarmCoin] = useState<CoinPrice | null>(null);
  const [alarmCondition, setAlarmCondition] = useState<AlertCondition>('above');
  const [alarmThreshold, setAlarmThreshold] = useState('3.0');

  useEffect(() => {
    if (coins.length > 0) {
      checkAlerts(coins);
    }
  }, [coins, checkAlerts]);

  const handleCoinPress = useCallback((coin: CoinPrice) => {
    navigation.navigate('Detail', { coin, exchangeRates, foreignExchange: settings.foreignExchange });
  }, [navigation, exchangeRates, settings.foreignExchange]);

  const handleAlarmPress = useCallback((coin: CoinPrice) => {
    setAlarmCoin(coin);
    setAlarmCondition('above');
    setAlarmThreshold('3.0');
    setShowAlarmModal(true);
  }, []);

  const handleAddAlarm = useCallback(() => {
    if (!alarmCoin) return;
    const threshold = parseFloat(alarmThreshold);
    if (isNaN(threshold)) return;
    addAlert(alarmCoin.symbol, alarmCondition, threshold);
    setShowAlarmModal(false);
  }, [alarmCoin, alarmCondition, alarmThreshold, addAlert]);

  const renderExchangeItem = useCallback(({ item }: { item: CoinPrice }) => (
    <ExchangeRow coin={item} onPress={handleCoinPress} />
  ), [handleCoinPress]);

  const renderPremiumItem = useCallback(({ item }: { item: CoinPrice }) => (
    <PremiumRow
      coin={item}
      foreignExchange={settings.foreignExchange}
      onPress={handleCoinPress}
      onAlarmPress={handleAlarmPress}
    />
  ), [handleCoinPress, handleAlarmPress, settings.foreignExchange]);

  // For premium tab, only show coins that have foreign price
  const premiumCoins = useMemo(() => {
    return coins.filter(c => c.foreignPrice !== null);
  }, [coins]);

  const getSortArrow = (field: SortField) => {
    if (sortField !== field) return '';
    return sortOrder === 'desc' ? ' ▼' : ' ▲';
  };

  const exchangeLabel = getExchangeLabel(settings.foreignExchange);
  const currencyUnit = getCurrencyUnit(settings.foreignExchange);

  if (loading && coins.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#3B82F6" />
        <Text style={styles.loadingText}>시세 불러오는 중...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {/* Top Tabs */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'exchange' && styles.tabActive]}
          onPress={() => setActiveTab('exchange')}
        >
          <Text style={[styles.tabText, activeTab === 'exchange' && styles.tabTextActive]}>
            거래소
          </Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.tab, activeTab === 'premium' && styles.tabActive]}
          onPress={() => setActiveTab('premium')}
        >
          <Text style={[styles.tabText, activeTab === 'premium' && styles.tabTextActive]}>
            프리미엄
          </Text>
        </TouchableOpacity>
      </View>

      {/* Premium Tab: Exchange Selector + Info Bar */}
      {activeTab === 'premium' && (
        <>
          {/* Exchange selector tabs */}
          <View style={styles.exchangeTabBar}>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.exchangeTabScroll}>
              {EXCHANGE_TABS.map(ex => (
                <TouchableOpacity
                  key={ex.key}
                  style={[
                    styles.exchangeTab,
                    settings.foreignExchange === ex.key && styles.exchangeTabActive,
                  ]}
                  onPress={() => setForeignExchange(ex.key)}
                >
                  <Text style={[
                    styles.exchangeTabText,
                    settings.foreignExchange === ex.key && styles.exchangeTabTextActive,
                  ]}>
                    {ex.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </ScrollView>
          </View>

          {/* Exchange rate info bar */}
          <View style={styles.rateBar}>
            <Text style={styles.rateExchange}>
              업비트 ↔ {exchangeLabel}
            </Text>
            <View style={styles.rateRight}>
              {dataSource !== 'none' && (
                <View style={[styles.sourceBadge, dataSource === 'proxy' ? styles.sourceBadgeProxy : styles.sourceBadgeDirect]}>
                  <Text style={styles.sourceBadgeText}>
                    {dataSource === 'proxy' ? '프록시' : '직접'}
                  </Text>
                </View>
              )}
              {exchangeRates && (
                <Text style={styles.rateText}>
                  {settings.foreignExchange === 'indodax'
                    ? `IDR/KRW: ${exchangeRates.idrKrw.toFixed(4)}`
                    : `USD/KRW: ${exchangeRates.usdKrw.toFixed(2)}`}
                </Text>
              )}
            </View>
          </View>
        </>
      )}

      {/* Sort Header */}
      {activeTab === 'exchange' ? (
        <View style={styles.sortHeader}>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('symbol')}>
            <Text style={[styles.sortText, sortField === 'symbol' && styles.sortTextActive]}>
              이름{getSortArrow('symbol')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('upbitPrice')}>
            <Text style={[styles.sortText, sortField === 'upbitPrice' && styles.sortTextActive]}>
              가격{getSortArrow('upbitPrice')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('tradeVolume24h')}>
            <Text style={[styles.sortText, sortField === 'tradeVolume24h' && styles.sortTextActive]}>
              거래량{getSortArrow('tradeVolume24h')}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.sortBtnRight} onPress={() => setSortField('changeRate')}>
            <Text style={[styles.sortText, sortField === 'changeRate' && styles.sortTextActive]}>
              등락률{getSortArrow('changeRate')}
            </Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.sortHeader}>
          <TouchableOpacity style={styles.sortBtn} onPress={() => setSortField('symbol')}>
            <Text style={[styles.sortText, sortField === 'symbol' && styles.sortTextActive]}>
              이름{getSortArrow('symbol')}
            </Text>
          </TouchableOpacity>
          <View style={styles.sortBtn}>
            <Text style={styles.sortText}>{currencyUnit}</Text>
          </View>
          <TouchableOpacity style={styles.sortBtnRight} onPress={() => setSortField('premium')}>
            <Text style={[styles.sortText, sortField === 'premium' && styles.sortTextActive]}>
              프리미엄{getSortArrow('premium')}
            </Text>
          </TouchableOpacity>
          <View style={{ width: 36 }} />
        </View>
      )}

      {/* Error Banner */}
      {error ? (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText}>{error}</Text>
        </View>
      ) : null}

      {/* Search */}
      <SearchBar value={searchQuery} onChangeText={setSearchQuery} />

      {/* Coin List */}
      {activeTab === 'exchange' ? (
        <FlatList
          data={coins}
          keyExtractor={item => item.symbol}
          renderItem={renderExchangeItem}
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={refresh}
              tintColor="#3B82F6"
              colors={['#3B82F6']}
            />
          }
          style={styles.list}
          contentContainerStyle={styles.listContent}
          initialNumToRender={20}
          maxToRenderPerBatch={20}
        />
      ) : (
        <FlatList
          data={premiumCoins}
          keyExtractor={item => item.symbol}
          renderItem={renderPremiumItem}
          ListEmptyComponent={
            !loading ? (
              <View style={styles.emptyContainer}>
                <Text style={styles.emptyText}>
                  {dataSource === 'none'
                    ? '해외 거래소 데이터를 불러올 수 없습니다'
                    : '데이터를 불러오는 중...'}
                </Text>
                <Text style={styles.emptySubText}>
                  {dataSource === 'none'
                    ? '네트워크 연결을 확인하거나 새로고침 해주세요'
                    : '잠시만 기다려주세요'}
                </Text>
              </View>
            ) : null
          }
          refreshControl={
            <RefreshControl
              refreshing={loading}
              onRefresh={refresh}
              tintColor="#3B82F6"
              colors={['#3B82F6']}
            />
          }
          style={styles.list}
          contentContainerStyle={premiumCoins.length === 0 ? styles.listContentEmpty : styles.listContent}
          initialNumToRender={20}
          maxToRenderPerBatch={20}
        />
      )}

      {/* Alarm Quick-Add Modal */}
      <Modal visible={showAlarmModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>
              {alarmCoin?.symbol} 프리미엄 알람
            </Text>

            {alarmCoin?.premium !== null && alarmCoin?.premium !== undefined && (
              <View style={styles.currentPremiumBox}>
                <Text style={styles.currentPremiumLabel}>현재 프리미엄</Text>
                <Text style={styles.currentPremiumValue}>
                  {alarmCoin.premium >= 0 ? '+' : ''}{alarmCoin.premium.toFixed(2)}%
                </Text>
              </View>
            )}

            <Text style={styles.fieldLabel}>조건</Text>
            <View style={styles.toggleRow}>
              <TouchableOpacity
                style={[styles.toggleBtn, alarmCondition === 'above' && styles.toggleActive]}
                onPress={() => setAlarmCondition('above')}
              >
                <Text style={[styles.toggleText, alarmCondition === 'above' && styles.toggleTextActive]}>
                  이상
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.toggleBtn, alarmCondition === 'below' && styles.toggleActive]}
                onPress={() => setAlarmCondition('below')}
              >
                <Text style={[styles.toggleText, alarmCondition === 'below' && styles.toggleTextActive]}>
                  이하
                </Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.fieldLabel}>프리미엄 (%)</Text>
            <TextInput
              style={styles.textInput}
              value={alarmThreshold}
              onChangeText={setAlarmThreshold}
              placeholder="3.0"
              placeholderTextColor="#555"
              keyboardType="decimal-pad"
            />

            <View style={styles.previewBox}>
              <Text style={styles.previewText}>
                {alarmCoin?.symbol} 김프가 {alarmThreshold}% {alarmCondition === 'above' ? '이상' : '이하'}이면 알림
              </Text>
            </View>

            <View style={styles.modalButtons}>
              <TouchableOpacity style={styles.cancelBtn} onPress={() => setShowAlarmModal(false)}>
                <Text style={styles.cancelBtnText}>취소</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.addBtn} onPress={handleAddAlarm}>
                <Text style={styles.addBtnText}>알람 추가</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0D0D0D',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#0D0D0D',
  },
  loadingText: {
    color: '#666',
    marginTop: 12,
    fontSize: 14,
  },

  // Main Tabs
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#0D0D0D',
    borderBottomWidth: 0.5,
    borderBottomColor: '#222',
  },
  tab: {
    paddingVertical: 12,
    paddingHorizontal: 20,
  },
  tabActive: {
    borderBottomWidth: 2,
    borderBottomColor: '#FFFFFF',
  },
  tabText: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },

  // Exchange Tabs (within premium)
  exchangeTabBar: {
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  exchangeTabScroll: {
    flexDirection: 'row',
    paddingHorizontal: 10,
    paddingVertical: 8,
    gap: 6,
  },
  exchangeTab: {
    paddingVertical: 6,
    paddingHorizontal: 14,
    borderRadius: 16,
    backgroundColor: '#1A1A1A',
    borderWidth: 1,
    borderColor: '#333',
  },
  exchangeTabActive: {
    backgroundColor: '#1E3A5F',
    borderColor: '#3B82F6',
  },
  exchangeTabText: {
    fontSize: 12,
    color: '#888',
    fontWeight: '500',
  },
  exchangeTabTextActive: {
    color: '#3B82F6',
    fontWeight: '700',
  },

  // Rate Bar
  rateBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  rateExchange: {
    fontSize: 12,
    color: '#3B82F6',
    fontWeight: '600',
  },
  rateRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  rateText: {
    fontSize: 11,
    color: '#999',
    fontVariant: ['tabular-nums'],
  },
  sourceBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  sourceBadgeProxy: {
    backgroundColor: '#0A2612',
  },
  sourceBadgeDirect: {
    backgroundColor: '#2A1A00',
  },
  sourceBadgeText: {
    fontSize: 9,
    color: '#F59E0B',
    fontWeight: '600',
  },

  // Sort
  sortHeader: {
    flexDirection: 'row',
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: '#111',
    borderBottomWidth: 0.5,
    borderBottomColor: '#1C1C1C',
  },
  sortBtn: { flex: 1 },
  sortBtnRight: { flex: 1, alignItems: 'flex-end' },
  sortText: { fontSize: 11, color: '#666', fontWeight: '500' },
  sortTextActive: { color: '#3B82F6', fontWeight: '700' },

  // Error
  errorBanner: {
    backgroundColor: '#331111',
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  errorBannerText: { color: '#EF4444', fontSize: 12 },

  // Empty
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 80,
    paddingHorizontal: 32,
  },
  emptyText: {
    color: '#888',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 8,
  },
  emptySubText: {
    color: '#555',
    fontSize: 12,
    textAlign: 'center',
  },

  // List
  list: { flex: 1 },
  listContent: { paddingBottom: 20 },
  listContentEmpty: { flexGrow: 1 },

  // Alarm Modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.7)',
    justifyContent: 'flex-end',
  },
  modalContent: {
    backgroundColor: '#141414',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 24,
    paddingBottom: 40,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#FFF',
    marginBottom: 12,
    textAlign: 'center',
  },
  currentPremiumBox: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#1A1A1A',
    borderRadius: 8,
    padding: 10,
    marginBottom: 16,
  },
  currentPremiumLabel: {
    fontSize: 13,
    color: '#888',
  },
  currentPremiumValue: {
    fontSize: 16,
    fontWeight: '700',
    color: '#3B82F6',
    fontVariant: ['tabular-nums'],
  },
  fieldLabel: {
    fontSize: 12,
    color: '#777',
    marginBottom: 6,
    marginTop: 12,
  },
  textInput: {
    backgroundColor: '#1A1A1A',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: '#FFF',
  },
  toggleRow: {
    flexDirection: 'row',
    gap: 10,
  },
  toggleBtn: {
    flex: 1,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#1A1A1A',
    alignItems: 'center',
  },
  toggleActive: {
    backgroundColor: '#1E3A5F',
  },
  toggleText: { fontSize: 14, color: '#666' },
  toggleTextActive: { color: '#3B82F6', fontWeight: '600' },
  previewBox: {
    marginTop: 16,
    padding: 12,
    backgroundColor: '#1A1A1A',
    borderRadius: 8,
  },
  previewText: { fontSize: 13, color: '#AAA', textAlign: 'center' },
  modalButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 20,
  },
  cancelBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#1A1A1A',
    alignItems: 'center',
  },
  cancelBtnText: { color: '#888', fontSize: 16, fontWeight: '600' },
  addBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 10,
    backgroundColor: '#3B82F6',
    alignItems: 'center',
  },
  addBtnText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
});
