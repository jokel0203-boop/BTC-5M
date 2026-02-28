import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { Alert, Vibration } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { PremiumAlert, AlertLog, AlertCondition, CoinPrice } from '../types';

const ALERTS_KEY = '@kimchi_alerts';
const LOGS_KEY = '@kimchi_alert_logs';

interface AlertContextType {
  alerts: PremiumAlert[];
  alertLogs: AlertLog[];
  addAlert: (symbol: string, condition: AlertCondition, threshold: number) => void;
  removeAlert: (id: string) => void;
  toggleAlert: (id: string) => void;
  clearLogs: () => void;
  checkAlerts: (coins: CoinPrice[]) => void;
}

const AlertContext = createContext<AlertContextType | null>(null);

export function useAlerts() {
  const ctx = useContext(AlertContext);
  if (!ctx) throw new Error('useAlerts must be used within AlertProvider');
  return ctx;
}

let nextId = 1;
function generateId() {
  return `alert_${Date.now()}_${nextId++}`;
}

// AsyncStorage 헬퍼
async function saveAlerts(alerts: PremiumAlert[]) {
  try {
    await AsyncStorage.setItem(ALERTS_KEY, JSON.stringify(alerts));
  } catch (e) {
    console.warn('알람 저장 실패:', e);
  }
}

async function saveLogs(logs: AlertLog[]) {
  try {
    await AsyncStorage.setItem(LOGS_KEY, JSON.stringify(logs));
  } catch (e) {
    console.warn('로그 저장 실패:', e);
  }
}

async function loadAlerts(): Promise<PremiumAlert[]> {
  try {
    const data = await AsyncStorage.getItem(ALERTS_KEY);
    if (data) {
      const parsed = JSON.parse(data);
      return parsed.map((a: any) => ({
        ...a,
        createdAt: new Date(a.createdAt),
        triggeredAt: a.triggeredAt ? new Date(a.triggeredAt) : undefined,
      }));
    }
  } catch (e) {
    console.warn('알람 로드 실패:', e);
  }
  return [];
}

async function loadLogs(): Promise<AlertLog[]> {
  try {
    const data = await AsyncStorage.getItem(LOGS_KEY);
    if (data) {
      const parsed = JSON.parse(data);
      return parsed.map((l: any) => ({
        ...l,
        triggeredAt: new Date(l.triggeredAt),
      }));
    }
  } catch (e) {
    console.warn('로그 로드 실패:', e);
  }
  return [];
}

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<PremiumAlert[]>([]);
  const [alertLogs, setAlertLogs] = useState<AlertLog[]>([]);
  const cooldownRef = useRef<Map<string, number>>(new Map());
  const loadedRef = useRef(false);

  // 앱 시작 시 저장된 데이터 로드
  useEffect(() => {
    if (loadedRef.current) return;
    loadedRef.current = true;
    (async () => {
      const [savedAlerts, savedLogs] = await Promise.all([loadAlerts(), loadLogs()]);
      if (savedAlerts.length > 0) setAlerts(savedAlerts);
      if (savedLogs.length > 0) setAlertLogs(savedLogs);
    })();
  }, []);

  const addAlert = useCallback(
    (symbol: string, condition: AlertCondition, threshold: number) => {
      const newAlert: PremiumAlert = {
        id: generateId(),
        symbol: symbol.toUpperCase(),
        condition,
        threshold,
        enabled: true,
        triggered: false,
        createdAt: new Date(),
      };
      setAlerts(prev => {
        const updated = [...prev, newAlert];
        saveAlerts(updated);
        return updated;
      });
    },
    []
  );

  const removeAlert = useCallback((id: string) => {
    setAlerts(prev => {
      const updated = prev.filter(a => a.id !== id);
      saveAlerts(updated);
      return updated;
    });
    cooldownRef.current.delete(id);
  }, []);

  const toggleAlert = useCallback((id: string) => {
    setAlerts(prev => {
      const updated = prev.map(a =>
        a.id === id ? { ...a, enabled: !a.enabled, triggered: false } : a
      );
      saveAlerts(updated);
      return updated;
    });
    cooldownRef.current.delete(id);
  }, []);

  const clearLogs = useCallback(() => {
    setAlertLogs([]);
    saveLogs([]);
  }, []);

  const checkAlerts = useCallback(
    (coins: CoinPrice[]) => {
      const now = Date.now();
      const coinMap = new Map(coins.map(c => [c.symbol, c]));

      setAlerts(prev => {
        let changed = false;
        const updated = prev.map(alert => {
          if (!alert.enabled) return alert;

          const lastTrigger = cooldownRef.current.get(alert.id);
          if (lastTrigger && now - lastTrigger < 60_000) return alert;

          const coin = coinMap.get(alert.symbol);
          if (!coin) return alert;

          const premium = coin.binancePremium;
          if (premium === null) return alert;

          const shouldTrigger =
            alert.condition === 'above'
              ? premium >= alert.threshold
              : premium <= alert.threshold;

          if (shouldTrigger) {
            changed = true;
            cooldownRef.current.set(alert.id, now);

            const log: AlertLog = {
              id: generateId(),
              alertId: alert.id,
              symbol: alert.symbol,
              condition: alert.condition,
              threshold: alert.threshold,
              actualPremium: premium,
              triggeredAt: new Date(),
            };
            setAlertLogs(prevLogs => {
              const updated = [log, ...prevLogs].slice(0, 100);
              saveLogs(updated);
              return updated;
            });

            Vibration.vibrate([0, 200, 100, 200]);
            const condStr = alert.condition === 'above' ? '이상' : '이하';
            Alert.alert(
              `김프 알람 - ${alert.symbol}`,
              `프리미엄: ${premium.toFixed(2)}%\n조건: ${alert.threshold}% ${condStr}`,
              [{ text: '확인' }]
            );

            return { ...alert, triggered: true, triggeredAt: new Date() };
          }

          return alert;
        });

        if (changed) {
          saveAlerts(updated);
        }
        return changed ? updated : prev;
      });
    },
    []
  );

  return (
    <AlertContext.Provider
      value={{ alerts, alertLogs, addAlert, removeAlert, toggleAlert, clearLogs, checkAlerts }}
    >
      {children}
    </AlertContext.Provider>
  );
}
