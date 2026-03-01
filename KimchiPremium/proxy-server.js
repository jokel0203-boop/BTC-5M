/**
 * 김치프리미엄 프록시 서버
 *
 * VPS에서 실행하면 바이낸스, Indodax 등 해외 거래소 데이터를 가져와서
 * 한국 핸드폰 앱에 중계해줌.
 *
 * 실행: node proxy-server.js
 * 포트: 3001
 */

const http = require('http');
const https = require('https');

const PORT = 3001;
const REFRESH_INTERVAL = 1500; // 1.5초

// --- 캐시 ---
let cache = {
  binanceSpot: {},    // { BTC: 95000, ETH: 3500, ... }
  binanceFutures: {}, // { BTC: 95050, ETH: 3502, ... }
  indodax: {},        // { BTC: 1500000000, ETH: 55000000, ... } (IDR)
  rates: {
    usdKrw: 1380,
    idrKrw: 0.089,
  },
  lastUpdate: 0,
};

// --- HTTPS fetch 헬퍼 ---
function fetchJSON(url, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      req.destroy();
      reject(new Error('timeout'));
    }, timeoutMs);

    const req = https.get(url, { headers: { 'User-Agent': 'KimchiPremium/1.0' } }, (res) => {
      if (res.statusCode !== 200) {
        clearTimeout(timer);
        reject(new Error(`HTTP ${res.statusCode}`));
        res.resume();
        return;
      }
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        clearTimeout(timer);
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(new Error('JSON parse error')); }
      });
    });
    req.on('error', (e) => {
      clearTimeout(timer);
      reject(e);
    });
  });
}

// --- 데이터 가져오기 ---

async function fetchBinanceSpot() {
  const data = await fetchJSON('https://api.binance.com/api/v3/ticker/price');
  const prices = {};
  for (const t of data) {
    if (t.symbol.endsWith('USDT')) {
      prices[t.symbol.replace('USDT', '')] = parseFloat(t.price);
    }
  }
  return prices;
}

async function fetchBinanceFutures() {
  const data = await fetchJSON('https://fapi.binance.com/fapi/v1/ticker/price');
  const prices = {};
  for (const t of data) {
    if (t.symbol.endsWith('USDT')) {
      prices[t.symbol.replace('USDT', '')] = parseFloat(t.price);
    }
  }
  return prices;
}

async function fetchIndodax() {
  const data = await fetchJSON('https://indodax.com/api/ticker_all');
  const prices = {};
  if (data && data.tickers) {
    for (const [pair, info] of Object.entries(data.tickers)) {
      if (pair.endsWith('_idr')) {
        const symbol = pair.replace('_idr', '').toUpperCase();
        prices[symbol] = parseFloat(info.last);
      }
    }
  }
  return prices;
}

function parseNaverRate(data) {
  const result = data && data.result;
  if (!result) return null;
  const price = result.calcPrice || result.closePrice || result.basePrice;
  if (!price) return null;
  const num = typeof price === 'string' ? parseFloat(price.replace(/,/g, '')) : price;
  return num > 0 ? num : null;
}

async function fetchExchangeRates() {
  // 1차: 네이버 증권 환율 API (실시간)
  try {
    const usdData = await fetchJSON('https://m.stock.naver.com/front-api/marketIndex/productDetail?category=exchange&reutersCode=FX_USDKRW', 5000);
    const usdKrw = parseNaverRate(usdData);
    if (usdKrw) {
      let idrKrw = usdKrw / 16000;
      try {
        const idrData = await fetchJSON('https://m.stock.naver.com/front-api/marketIndex/productDetail?category=exchange&reutersCode=FX_IDRKRW', 3000);
        const idrRate = parseNaverRate(idrData);
        if (idrRate) {
          idrKrw = idrRate > 1 ? idrRate / 100 : idrRate;
        }
      } catch {}
      console.log(`[ExchangeRate] 네이버: USD/KRW=${usdKrw}, IDR/KRW=${idrKrw.toFixed(4)}`);
      return { usdKrw, idrKrw };
    }
  } catch (err) {
    console.warn('[ExchangeRate] 네이버 실패:', err.message);
  }

  // 2차: manana.kr (매매기준율)
  try {
    const usdData = await fetchJSON('https://api.manana.kr/exchange/rate/KRW/USD.json', 8000);
    if (Array.isArray(usdData) && usdData.length > 0 && usdData[0].rate) {
      const usdKrw = usdData[0].rate;
      let idrKrw = usdKrw / 16000;
      try {
        const idrData = await fetchJSON('https://api.manana.kr/exchange/rate/KRW/IDR.json', 5000);
        if (Array.isArray(idrData) && idrData.length > 0 && idrData[0].rate) {
          idrKrw = idrData[0].rate;
        }
      } catch {}
      console.log(`[ExchangeRate] manana.kr: USD/KRW=${usdKrw}`);
      return { usdKrw, idrKrw };
    }
  } catch (err) {
    console.warn('[ExchangeRate] manana.kr 실패:', err.message);
  }

  // 3차: Open Exchange Rates (폴백)
  const data = await fetchJSON('https://open.er-api.com/v6/latest/USD', 8000);
  if (data && data.rates) {
    const usdKrw = data.rates.KRW || 1380;
    const usdIdr = data.rates.IDR || 15500;
    return {
      usdKrw,
      idrKrw: usdKrw / usdIdr,
    };
  }
  throw new Error('No rates data');
}

// --- 주기적 새로고침 ---

async function refreshAll() {
  const results = await Promise.allSettled([
    fetchBinanceSpot(),
    fetchBinanceFutures(),
    fetchIndodax(),
    fetchExchangeRates(),
  ]);

  if (results[0].status === 'fulfilled') {
    cache.binanceSpot = results[0].value;
    console.log(`[OK] 바이낸스 현물: ${Object.keys(results[0].value).length}개`);
  } else {
    console.log(`[FAIL] 바이낸스 현물: ${results[0].reason?.message}`);
  }

  if (results[1].status === 'fulfilled') {
    cache.binanceFutures = results[1].value;
    console.log(`[OK] 바이낸스 선물: ${Object.keys(results[1].value).length}개`);
  } else {
    // 선물 API 실패(451 등) → 현물 가격으로 대체 (선물/현물 가격은 거의 동일)
    if (Object.keys(cache.binanceSpot).length > 0) {
      cache.binanceFutures = { ...cache.binanceSpot };
      console.log(`[FALLBACK] 바이낸스 선물: 현물 가격으로 대체 (${Object.keys(cache.binanceSpot).length}개) - ${results[1].reason?.message}`);
    } else {
      console.log(`[FAIL] 바이낸스 선물: ${results[1].reason?.message}`);
    }
  }

  if (results[2].status === 'fulfilled') {
    cache.indodax = results[2].value;
    console.log(`[OK] Indodax: ${Object.keys(results[2].value).length}개`);
  } else {
    console.log(`[FAIL] Indodax: ${results[2].reason?.message}`);
  }

  if (results[3].status === 'fulfilled') {
    cache.rates = results[3].value;
    console.log(`[OK] 환율: USD/KRW=${cache.rates.usdKrw}, IDR/KRW=${cache.rates.idrKrw.toFixed(4)}`);
  } else {
    console.log(`[FAIL] 환율: ${results[3].reason?.message}`);
  }

  cache.lastUpdate = Date.now();
  console.log(`--- 업데이트 완료: ${new Date().toLocaleTimeString()} ---\n`);
}

// --- HTTP 서버 ---

const server = http.createServer((req, res) => {
  // CORS 허용
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.url === '/api/data') {
    // 전체 데이터 한번에 전달
    res.writeHead(200);
    res.end(JSON.stringify(cache));
  } else if (req.url === '/api/health') {
    res.writeHead(200);
    res.end(JSON.stringify({
      ok: true,
      lastUpdate: cache.lastUpdate,
      counts: {
        binanceSpot: Object.keys(cache.binanceSpot).length,
        binanceFutures: Object.keys(cache.binanceFutures).length,
        indodax: Object.keys(cache.indodax).length,
      },
    }));
  } else {
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
  }
});

// --- 시작 ---

console.log('=== 김치프리미엄 프록시 서버 ===');
console.log(`포트: ${PORT}`);
console.log(`갱신 주기: ${REFRESH_INTERVAL / 1000}초\n`);

refreshAll();
setInterval(refreshAll, REFRESH_INTERVAL);

server.listen(PORT, '0.0.0.0', () => {
  console.log(`\n서버 시작됨: http://0.0.0.0:${PORT}`);
  console.log(`앱 설정에서 프록시 URL에 VPS IP를 입력하세요`);
  console.log(`예: http://YOUR_VPS_IP:${PORT}\n`);
});
