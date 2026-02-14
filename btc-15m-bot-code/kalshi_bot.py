"""
Kalshi 단독 거래 봇

15분 크립토 마켓 단일 거래소 아비트리지:
- YES ask + NO ask < 95¢ → 양쪽 매수 → 정산 시 100¢ 보장
- WebSocket 실시간 가격 + REST 폴백
- 안전장치: 일일 손실 한도, 거래 에러 즉시 중단, 긴급 매도, 이익 실현 매도
"""
import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

load_dotenv(override=True)

# 터미널 로그: WARNING 이상만 표시
logger.remove()
logger.add(sys.stderr, level="WARNING")

from src.kalshi.client import KalshiClient
from src.kalshi.engine import KalshiEngine
from src.kalshi.ws_feed import KalshiWebSocketFeed
from src.utils.telegram import TelegramNotifier

SCAN_INTERVAL = 0.2  # WS 모드: 빠른 스캔
REST_SCAN_INTERVAL = 1.0  # REST 폴백
SUPPORTED_COINS = ["BTC"]


def main():
    print("=" * 60)
    print("Kalshi Standalone Crypto Trading Bot")
    print("=" * 60)

    bot_mode = os.getenv("BOT_MODE", "test").strip().lower()
    use_websocket = os.getenv("USE_WEBSOCKET", "true").strip().lower() != "false"
    print(f"Mode: {bot_mode.upper()}")
    print(f"Price feed: {'WebSocket + REST' if use_websocket else 'REST only'}")
    print(f"Supported coins: {', '.join(SUPPORTED_COINS)}")
    print("=" * 60)

    telegram = TelegramNotifier()

    ws_feed = None

    try:
        kalshi_client = KalshiClient()
        engine = KalshiEngine(kalshi_client)

        if not engine.connect():
            print("[ERROR] Kalshi API connection failed!")
            telegram.notify_error("Kalshi API 연결 실패")
            sys.exit(1)

        print("\n[OK] Kalshi client initialized")

        # WebSocket 가격 피드 시작
        if use_websocket:
            print("[WS] Starting Kalshi WebSocket price feed...")
            ws_feed = KalshiWebSocketFeed(kalshi_client)
            ws_feed.start(SUPPORTED_COINS)
            engine.set_ws_feed(ws_feed)

            # WS 초기 시장 발견 대기 (최대 10초)
            print("[WS] Waiting for initial market discovery...", end="", flush=True)
            for i in range(20):
                time.sleep(0.5)
                data = ws_feed.get_market_data(SUPPORTED_COINS[0])
                if data:
                    print(f" OK ({(i+1)*0.5:.1f}s)")
                    break
            else:
                print(" timeout (will use REST fallback)")

            scan_interval = SCAN_INTERVAL
        else:
            scan_interval = REST_SCAN_INTERVAL

        print(f"\nScan interval: {scan_interval}s")
        print("\nStarting Kalshi scan...\n")

        # 시작 알림
        telegram.send("🤖 <b>Kalshi 단독 봇 시작!</b>\n\n✅ Kalshi 연결됨\n🔍 스캔 시작...")

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
                        print(
                            f"\n*** [OPPORTUNITY] {opp.coin} | {opp.action} | "
                            f"Total: {opp.total_cost:.1f}¢ | "
                            f"YES: {opp.yes_price}¢ NO: {opp.no_price}¢ | "
                            f"Qty: {opp.trade_size} ***"
                        )

                        if bot_mode == "live":
                            # 텔레그램 알림 (non-blocking)
                            telegram.send(
                                f"🚨 <b>Kalshi 기회 발견!</b>\n"
                                f"🪙 {opp.coin}\n"
                                f"💰 합계: <b>{opp.total_cost:.1f}¢</b>\n"
                                f"   YES: {opp.yes_price}¢ / NO: {opp.no_price}¢\n"
                                f"📦 수량: {opp.trade_size}주"
                            )
                            result = engine.execute_trade(opp)
                            status = "✅ 성공" if result.get("success") else "❌ 실패"
                            telegram.send(
                                f"{status} | {opp.coin} {opp.action}\n"
                                f"합계: {opp.total_cost:.1f}¢"
                            )

                            if result.get("halted"):
                                telegram.send_blocking(
                                    f"🚨 <b>HALT - 거래 에러</b>\n"
                                    f"{engine.halt_reason}"
                                )
                                break
                        else:
                            telegram.send(
                                f"🔍 <b>Kalshi 기회 (TEST)</b>\n"
                                f"🪙 {opp.coin}\n"
                                f"💰 합계: <b>{opp.total_cost:.1f}¢</b>\n"
                                f"   YES: {opp.yes_price}¢ / NO: {opp.no_price}¢\n"
                                f"📦 수량: {opp.trade_size}주"
                            )

                except Exception as e:
                    print(f"[ERROR] {coin}: {e}")
                    telegram.notify_error(f"Kalshi {coin}: {e}")

            # === 긴급 매도 체크 ===
            try:
                sold = engine.check_emergency_sell()
                for s in sold:
                    pos = s["position"]
                    telegram.send(
                        f"⚡ <b>KALSHI EMERGENCY SELL</b>\n"
                        f"{pos.coin} | {pos.action}\n"
                        f"수량: YES={pos.yes_count} NO={pos.no_count}\n"
                        f"사유: 종료 임박 + 유동성 부족 → 전량매도"
                    )
            except Exception as e:
                logger.error(f"[KALSHI-EMERGENCY] 체크 실패: {e}")

            # === 이익 실현 매도 체크 ===
            try:
                profit_sold = engine.check_profit_sell()
                for s in profit_sold:
                    pos = s["position"]
                    sell_value = s.get("sell_value", 0)
                    telegram.send(
                        f"💰 <b>KALSHI PROFIT SELL</b>\n"
                        f"{pos.coin} | {pos.action}\n"
                        f"수량: YES={pos.yes_count} NO={pos.no_count}\n"
                        f"매도가치: {sell_value:.1f}¢ (≥{110}¢)"
                    )
                    print(
                        f"\n*** [PROFIT SELL] {pos.coin} | {pos.action} | "
                        f"매도가치: {sell_value:.1f}¢ | "
                        f"YES={pos.yes_count} NO={pos.no_count} ***"
                    )
            except Exception as e:
                logger.error(f"[KALSHI-PROFIT] 체크 실패: {e}")

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
                print(
                    f"\r{spin} [{now}] Scan #{scan_count} | "
                    f"{elapsed:.2f}s{ws_status} | No opportunities{pos_info}   ",
                    end="", flush=True
                )
            else:
                print(
                    f"\n[{now}] Scan #{scan_count} | "
                    f"{elapsed:.2f}s{ws_status} | Found {total_opps} opportunities{pos_info}"
                )

            time.sleep(scan_interval)

    except KeyboardInterrupt:
        print("\n\nBot stopped by user")
        telegram.send_blocking("Kalshi Bot stopped.")
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        telegram.send_blocking(f"⚠️ <b>FATAL ERROR</b>\n{e}")
        sys.exit(1)
    finally:
        if ws_feed:
            ws_feed.stop()


if __name__ == "__main__":
    main()
