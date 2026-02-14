# 크립토 재정거래 봇 프로젝트 요약

## 프로젝트 목적
Polymarket과 Kalshi 간의 15분 크립토 마켓 재정거래 기회 감지

## 지원 코인
BTC, ETH, SOL

## 매매 조건
- **매수**: 합계 <= 95센트
- **매도**: 합계 >= 105센트

## 비교 조합
1. POLY UP + KALSHI NO
2. KALSHI YES + POLY DOWN

## 현재 문제점 (해결 필요)
1. **가격이 실제와 다름**: bestAsk/bestBid 대신 outcomePrices 사용 중
2. **수량이 항상 10**: 오더북 기반 최소 수량 로직 미적용

## API 정보
- Polymarket Gamma API: `https://gamma-api.polymarket.com/events?slug={coin}-updown-15m-{timestamp}`
- Kalshi 시리즈: KXBTC15M, KXETH15M, KXSOL15M

## 가격 계산 공식 (수정 필요)
- UP 가격 = bestAsk × 100
- DOWN 가격 = (1 - bestBid) × 100

## 주요 파일
- main.py: 메인 실행 파일
- src/polymarket/client.py: Polymarket API 클라이언트
- src/kalshi/client.py: Kalshi API 클라이언트
- src/arbitrage/engine.py: 재정거래 엔진
- src/utils/telegram.py: 텔레그램 알림

## 환경 변수 (.env)
- KALSHI_API_KEY, KALSHI_PRIVATE_KEY_PATH
- TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
- BOT_MODE=test

## 새 대화에서 요청할 내용
"크립토 재정거래 봇의 가격이 실제 웹사이트와 다릅니다. Polymarket에서 bestAsk/bestBid를 사용하도록 수정하고, 수량도 오더북 기반으로 계산해주세요."
