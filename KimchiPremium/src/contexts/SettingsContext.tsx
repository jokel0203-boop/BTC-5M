import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppSettings, ForeignExchange } from '../types';

const STORAGE_KEY = 'kimchi_settings';

interface SettingsContextType {
  settings: AppSettings;
  setProxyUrl: (url: string) => void;
  setForeignExchange: (exchange: ForeignExchange) => void;
  loaded: boolean;
}

const defaultSettings: AppSettings = {
  proxyUrl: '',
  foreignExchange: 'binance_spot',
};

const SettingsContext = createContext<SettingsContextType | null>(null);

export function useSettings() {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error('useSettings must be used within SettingsProvider');
  return ctx;
}

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings);
  const [loaded, setLoaded] = useState(false);

  // 앱 시작 시 저장된 설정 불러오기
  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY).then(raw => {
      if (raw) {
        try {
          const saved = JSON.parse(raw);
          setSettings(prev => ({ ...prev, ...saved }));
        } catch {}
      }
      setLoaded(true);
    }).catch(() => setLoaded(true));
  }, []);

  // 설정 변경 시 AsyncStorage에 저장
  const persist = useCallback((newSettings: AppSettings) => {
    AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings)).catch(() => {});
  }, []);

  const setProxyUrl = useCallback((url: string) => {
    setSettings(prev => {
      const next = { ...prev, proxyUrl: url.trim() };
      persist(next);
      return next;
    });
  }, [persist]);

  const setForeignExchange = useCallback((exchange: ForeignExchange) => {
    setSettings(prev => {
      const next = { ...prev, foreignExchange: exchange };
      persist(next);
      return next;
    });
  }, [persist]);

  return (
    <SettingsContext.Provider value={{ settings, setProxyUrl, setForeignExchange, loaded }}>
      {children}
    </SettingsContext.Provider>
  );
}
