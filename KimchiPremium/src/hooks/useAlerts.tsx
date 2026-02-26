import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from 'react';
import { Alert, Vibration } from 'react-native';
import { PremiumAlert, AlertLog, AlertCondition, AlertExchange, CoinPrice } from '../types';

interface AlertContextType {
  alerts: PremiumAlert[];
  alertLogs: AlertLog[];
  addAlert: (symbol: string, exchange: AlertExchange, condition: AlertCondition, threshold: number) => void;
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
  // Cooldown: don't re-trigger same alert within 60 seconds
  const cooldownRef = useRef<Map<string, number>>(new Map());

  const addAlert = useCallback(
    (symbol: string, exchange: AlertExchange, condition: AlertCondition, threshold: number) => {
      const newAlert: PremiumAlert = {
        id: generateId(),
        symbol: symbol.toUpperCase(),
        exchange,
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

          // Cooldown check (60s)
          const lastTrigger = cooldownRef.current.get(alert.id);
          if (lastTrigger && now - lastTrigger < 60_000) return alert;

          const coin = coinMap.get(alert.symbol);
          if (!coin) return alert;

          const premium =
            alert.exchange === 'binance' ? coin.binancePremium : coin.indodaxPremium;
          if (premium === null) return alert;

          const shouldTrigger =
            alert.condition === 'above'
              ? premium >= alert.threshold
              : premium <= alert.threshold;

          if (shouldTrigger) {
            changed = true;
            cooldownRef.current.set(alert.id, now);

            // Add to log
            const log: AlertLog = {
              id: generateId(),
              alertId: alert.id,
              symbol: alert.symbol,
              exchange: alert.exchange,
              condition: alert.condition,
              threshold: alert.threshold,
              actualPremium: premium,
              triggeredAt: new Date(),
            };
            setAlertLogs(prevLogs => [log, ...prevLogs].slice(0, 100));

            // Vibrate + system alert
            Vibration.vibrate([0, 200, 100, 200]);
            const condStr = alert.condition === 'above' ? '이상' : '이하';
            const exchStr = alert.exchange === 'binance' ? 'Binance' : 'Indodax';
            Alert.alert(
              `김프 알람 - ${alert.symbol}`,
              `${exchStr} 프리미엄: ${premium.toFixed(2)}%\n조건: ${alert.threshold}% ${condStr}`,
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
