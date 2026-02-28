import React, { createContext, useContext, useState, useCallback } from 'react';
import { AppSettings, ForeignExchange } from '../types';

interface SettingsContextType {
  settings: AppSettings;
  setProxyUrl: (url: string) => void;
  setForeignExchange: (exchange: ForeignExchange) => void;
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

  const setProxyUrl = useCallback((url: string) => {
    setSettings(prev => ({ ...prev, proxyUrl: url.trim() }));
  }, []);

  const setForeignExchange = useCallback((exchange: ForeignExchange) => {
    setSettings(prev => ({ ...prev, foreignExchange: exchange }));
  }, []);

  return (
    <SettingsContext.Provider value={{ settings, setProxyUrl, setForeignExchange }}>
      {children}
    </SettingsContext.Provider>
  );
}
