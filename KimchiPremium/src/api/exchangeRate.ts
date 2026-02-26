import axios from 'axios';
import { ExchangeRate } from '../types';

// Use free exchange rate APIs
export async function getExchangeRates(): Promise<ExchangeRate> {
  try {
    // Using exchangerate-api (free tier)
    const response = await axios.get(
      'https://open.er-api.com/v6/latest/USD'
    );
    const rates = response.data.rates;

    return {
      usdKrw: rates.KRW,
      idrKrw: rates.KRW / rates.IDR, // 1 IDR = X KRW
    };
  } catch (error) {
    // Fallback approximate rates
    console.warn('Exchange rate API failed, using fallback rates');
    return {
      usdKrw: 1350,
      idrKrw: 0.085,
    };
  }
}
