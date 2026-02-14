"""
Polymarket-Kalshi Crypto Arbitrage Bot

15분 크립토 마켓 재정거래 봇
- BTC, ETH, SOL 지원
- WebSocket 실시간 가격 + REST 폴백
- 안전장치: 일일 손실 한도, 거래 에러 즉시 중단, Danger Zone, 긴급 매도
"""
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

# 터미널 로그: WARNING 이상만 표시 (거래/에러만)
logger.remove()
logger.add(sys.stderr, level="WARNING")

from src.polymarket.client import PolymarketClient
from src.kalshi.client import KalshiClient
from src.arbitrage.engine import ArbitrageEngine
from src.utils.telegram import TelegramNotifier
from src.websocket_feed import WebSocketPriceFeed

SCAN_INTERVAL = 0.2  # WS 모드: 빠른 스캔 (가격은 캐시에서 즉시 읽기)
REST_SCAN_INTERVAL = 1.0  # REST 폴백: 기존 간격
SUPPORTED_COINS = ["BTC"]


def main():
    print("=" * 60)
    print("Polymarket-Kalshi Crypto Arbitrage Bot")
    print("=" * 60)

    bot_mode = os.getenv("BOT_MODE", "test").strip().lower()
    use_websocket = os.getenv("USE_WEBSOCKET", "true").strip().lower() != "false"
    print(f"Mode: {bot_mode.upper()}")
    print(f"Price feed: {'WebSocket + REST' if use_websocket else 'REST only'}")
    print(f"Supported coins: {', '.join(SUPPORTED_COINS)}")
    print("=" * 60)

    # 텔레그램 알림 초기화
    telegram = TelegramNotifier()

    ws_feed = None

    try:
        poly_client = PolymarketClient()
        kalshi_client = KalshiClient()
        engine = ArbitrageEngine(poly_client, kalshi_client)

        # API 연결
        if not engine.connect():
            print("[ERROR] API connection failed!")
            telegram.notify_error("API 연결 실패")
            sys.exit(1)

        print("\n[OK] All clients initialized")

        # WebSocket 가격 피드 시작
        if use_websocket:
            print("[WS] Starting WebSocket price feed...")
            ws_feed = WebSocketPriceFeed(poly_client, kalshi_client)
            ws_feed.start(SUPPORTED_COINS)
            engine.set_ws_feed(ws_feed)

            # WS 초기 시장 발견 대기 (최대 10초)
            print("[WS] Waiting for initial market discovery...", end="", flush=True)
            for i in range(20):
                time.sleep(0.5)
                poly_data, kalshi_data = ws_feed.get_market_data(SUPPORTED_COINS[0])
                if poly_data and kalshi_data:
                    print(f" OK ({(i+1)*0.5:.1f}s)")
                    break
            else:
                print(" timeout (will use REST fallback)")

            scan_interval = SCAN_INTERVAL
        else:
            scan_interval = REST_SCAN_INTERVAL

        print(f"\nScan interval: {scan_interval}s")
        print("\nStarting arbitrage scan...\n")

        # 시작 알림
        telegram.notify_start()

        scan_count = 0
        spinner = ['|', '/', '-', '\\']
        while True:
            # === 봇 중단 상태 체크 ===
            if engine.is_halted:
                halt_msg = f"[HALTED] {engine.halt_reason}"
                print(f"\n{halt_msg}")
                telegram.send_blocking(f"🚨 <b>HALT</b>\n{engine.halt_reason}")
                print("봇 중단. 문제 해결 후 재시작하세요.")
                break

            scan_count += 1
            scan_start = time.time()

            total_opps = 0
            for coin in SUPPORTED_COINS:
                try:
                    opportunities = engine.find_opportunities(coin)
                    total_opps += len(opportunities)

                    for opp in opportunities:
                        print(f"\n*** [OPPORTUNITY] {opp.coin} | {opp.action} | "
                              f"Total: {opp.total_cost:.1f}¢ | "
                              f"Poly: {opp.poly_price:.1f}¢ Kalshi: {opp.kalshi_price}¢ | "
                              f"Qty: {opp.trade_size} ***")

                        if bot_mode == "live":
                            # 거래 먼저! (텔레그램은 non-blocking이라 병렬)
                            telegram.notify_opportunity(
                                coin=opp.coin,
                                action=opp.action,
                                total=opp.total_cost,
                                poly_price=opp.poly_price,
                                kalshi_price=opp.kalshi_price,
                                size=opp.trade_size
                            )
                            result = engine.execute_trade(opp)
                            telegram.notify_trade(
                                coin=opp.coin,
                                action=opp.action,
                                success=result.get("success", False)
                            )

                            # 거래 에러로 중단된 경우 즉시 알림 (동기 + 재시도)
                            if result.get("halted"):
                                telegram.send_blocking(
                                    f"🚨 <b>HALT - 거래 에러</b>\n"
                                    f"{engine.halt_reason}"
                                )
                                break  # for 루프 탈출 → while 루프에서 halt 감지 → 봇 종료
                        else:
                            telegram.notify_opportunity(
                                coin=opp.coin,
                                action=opp.action,
                                total=opp.total_cost,
                                poly_price=opp.poly_price,
                                kalshi_price=opp.kalshi_price,
                                size=opp.trade_size
                            )

                except Exception as e:
                    print(f"[ERROR] {coin}: {e}")
                    telegram.notify_error(f"{coin}: {e}")

            # === 긴급 매도 체크 (30초 전~끝, 결과 불일치 시 전량매도) ===
            # 이익매도보다 먼저 실행 → 만료 포지션 제거 전에 긴급매도 우선
            try:
                sold = engine.check_emergency_sell()
                for s in sold:
                    pos = s["position"]
                    telegram.send(
                        f"<b>EMERGENCY SELL</b>\n"
                        f"{pos.coin} | {pos.action}\n"
                        f"수량: {pos.count}주\n"
                        f"사유: 종료 임박 + 결과 불일치 → 전량매도"
                    )
            except Exception as e:
                logger.error(f"[EMERGENCY] 체크 실패: {e}")

            # === 이익 실현 매도 체크 (시장 데이터 캐시 갱신 후) ===
            try:
                profit_sold = engine.check_profit_sell()
                for s in profit_sold:
                    pos = s["position"]
                    sell_value = s.get("sell_value", 0)
                    telegram.send(
                        f"<b>PROFIT SELL</b>\n"
                        f"{pos.coin} | {pos.action}\n"
                        f"수량: {pos.count}주\n"
                        f"매도가치: {sell_value:.1f}¢ (≥{110}¢)"
                    )
                    print(f"\n*** [PROFIT SELL] {pos.coin} | {pos.action} | "
                          f"매도가치: {sell_value:.1f}¢ | 수량: {pos.count} ***")
            except Exception as e:
                logger.error(f"[PROFIT] 체크 실패: {e}")

            elapsed = time.time() - scan_start
            now = datetime.now().strftime("%H:%M:%S")
            pos_count = len(engine.open_positions)
            pos_info = f" | Pos: {pos_count}" if pos_count > 0 else ""

            # WS 상태 표시
            ws_status = ""
            if ws_feed:
                ws_status = " | WS" if ws_feed.is_connected else " | REST"

            if total_opps == 0:
                spin = spinner[scan_count % 4]
                print(f"\r{spin} [{now}] Scan #{scan_count} | {elapsed:.2f}s{ws_status} | No opportunities{pos_info}   ", end="", flush=True)
            else:
                print(f"\n[{now}] Scan #{scan_count} | {elapsed:.2f}s{ws_status} | Found {total_opps} opportunities{pos_info}")

            time.sleep(scan_interval)

    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
        telegram.send_blocking("Bot stopped.")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        telegram.send_blocking(f"⚠️ <b>FATAL ERROR</b>\n{e}")
        sys.exit(1)
    finally:
        if ws_feed:
            ws_feed.stop()


if __name__ == "__main__":
    main()
