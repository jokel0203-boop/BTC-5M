import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { Alert, Vibration } from 'react-native';
import { PremiumAlert, AlertLog, AlertCondition, CoinPrice } from '../types';

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

export function AlertProvider({ children }: { children: React.ReactNode }) {
  const [alerts, setAlerts] = useState<PremiumAlert[]>([]);
  const [alertLogs, setAlertLogs] = useState<AlertLog[]>([]);
  const cooldownRef = useRef<Map<string, number>>(new Map());

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
      setAlerts(prev => [...prev, newAlert]);
    },
    []
  );

  const removeAlert = useCallback((id: string) => {
    setAlerts(prev => prev.filter(a => a.id !== id));
    cooldownRef.current.delete(id);
  }, []);

  const toggleAlert = useCallback((id: string) => {
    setAlerts(prev =>
      prev.map(a => (a.id === id ? { ...a, enabled: !a.enabled, triggered: false } : a))
    );
    cooldownRef.current.delete(id);
  }, []);

  const clearLogs = useCallback(() => {
    setAlertLogs([]);
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

          const premium = coin.premium;
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
            setAlertLogs(prevLogs => [log, ...prevLogs].slice(0, 100));

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
