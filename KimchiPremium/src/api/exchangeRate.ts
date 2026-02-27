import axios from 'axios';
import { ExchangeRate } from '../types';

export async function getExchangeRates(): Promise<ExchangeRate> {
  try {
    const response = await axios.get('https://open.er-api.com/v6/latest/USD', {
      timeout: 8000,
    });
    const rates = response.data.rates;
    return { usdKrw: rates.KRW };
  } catch (error) {
    console.warn('Exchange rate API failed, using fallback');
    return { usdKrw: 1380 };
  }
}
