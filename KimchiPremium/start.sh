#!/bin/bash
# 김치프리미엄 앱 + 프록시 서버 동시 실행
echo "=== 김치프리미엄 시작 ==="

# 프록시 서버 백그라운드 실행
echo "[1/2] 프록시 서버 시작 (포트 3001)..."
node proxy-server.js &
PROXY_PID=$!

# 잠시 대기
sleep 2

# Expo 시작
echo "[2/2] Expo 앱 서버 시작..."
npx expo start --tunnel

# Expo 종료 시 프록시도 종료
kill $PROXY_PID 2>/dev/null
echo "종료됨"
