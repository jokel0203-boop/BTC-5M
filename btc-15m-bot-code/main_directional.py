"""
Crypto Directional Trading Bot

전략: 80¢에 매수, 60¢에 손절
- BTC 15분 마켓 대상
- Polymarket + Kalshi 동시 테스트 (어느 거래소가 더 나은지 비교)
- WebSocket 실시간 가격 + REST 폴백
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
from src.directional.engine import DirectionalEngine, ENABLED_EXCHANGES, MAX_TRADE_SIZE
from src.utils.telegram import TelegramNotifier
from src.websocket_feed import WebSocketPriceFeed

SCAN_INTERVAL = 0.05  # WS 모드: 50ms (캐시 읽기만)
REST_SCAN_INTERVAL = 1.0  # REST 폴백: 기존 간격
SUPPORTED_COINS = ["BTC"]


def main():
    print("=" * 60)
    print("Crypto Directional Trading Bot")
    print("Strategy: Buy ≥80¢, Stop-loss ≤60¢")
    print("=" * 60)

    bot_mode = os.getenv("BOT_MODE", "test").strip().lower()
    use_websocket = os.getenv("USE_WEBSOCKET", "true").strip().lower() != "false"
    print(f"Mode: {bot_mode.upper()}")
    print(f"Price feed: {'WebSocket + REST' if use_websocket else 'REST only'}")
    print(f"Coins: {', '.join(SUPPORTED_COINS)}")
    exchanges_str = ", ".join(e.upper() for e in ENABLED_EXCHANGES)
    print(f"Exchanges: {exchanges_str}")
    print(f"Trade size: {MAX_TRADE_SIZE} contracts")
    print("=" * 60)

    # 텔레그램 알림 초기화
    telegram = TelegramNotifier()

    ws_feed = None

    try:
        poly_client = PolymarketClient() if "poly" in ENABLED_EXCHANGES else None
        kalshi_client = KalshiClient() if "kalshi" in ENABLED_EXCHANGES else None
        engine = DirectionalEngine(poly_client, kalshi_client)

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
                if poly_data or kalshi_data:
                    print(f" OK ({(i+1)*0.5:.1f}s)")
                    break
            else:
                print(" timeout (will use REST fallback)")

            scan_interval = SCAN_INTERVAL
        else:
            scan_interval = REST_SCAN_INTERVAL

        print(f"\nScan interval: {scan_interval}s")
        print("\nStarting scan...\n")

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
                        print(
                            f"\n*** [BUY] {opp.exchange.upper()} {opp.side.upper()} | "
                            f"{opp.coin} | {opp.price:.1f}¢ | Qty: {opp.trade_size} ***"
                        )

                        if bot_mode == "live":
                            telegram.send(
                                f"<b>BUY</b> {opp.exchange.upper()} {opp.side.upper()}\n"
                                f"{opp.coin} | {opp.price:.1f}¢ x{opp.trade_size}"
                            )
                            result = engine.execute_trade(opp)
                            success = result.get("success", False)
                            telegram.send(
                                f"{'✅' if success else '❌'} "
                                f"{opp.exchange.upper()} {opp.side.upper()} "
                                f"{'성공' if success else '실패'}"
                            )

                            if result.get("halted"):
                                telegram.send_blocking(
                                    f"🚨 <b>HALT - 거래 에러</b>\n{engine.halt_reason}"
                                )
                                break
                        else:
                            telegram.send(
                                f"<b>[TEST] BUY</b> {opp.exchange.upper()} {opp.side.upper()}\n"
                                f"{opp.coin} | {opp.price:.1f}¢ x{opp.trade_size}"
                            )
                            engine.execute_trade(opp)

                except Exception as e:
                    print(f"[ERROR] {coin}: {e}")
                    telegram.notify_error(f"{coin}: {e}")

            # === 손절 체크 ===
            try:
                stop_losses = engine.check_stop_loss()
                for s in stop_losses:
                    pos = s["position"]
                    price = s.get("price", 0)
                    print(
                        f"\n*** [STOP-LOSS] {pos.exchange.upper()} {pos.side.upper()} | "
                        f"{pos.coin} | 현재={price:.1f}¢ 진입={pos.entry_price:.1f}¢ | "
                        f"수량: {pos.count} ***"
                    )
                    telegram.send(
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴\n"
                        f"🛑 <b>STOP-LOSS</b>\n"
                        f"{pos.exchange.upper()} {pos.side.upper()}\n"
                        f"{pos.coin} | 현재={price:.1f}¢ 진입={pos.entry_price:.1f}¢\n"
                        f"수량: {pos.count}주\n"
                        f"🔴🔴🔴🔴🔴🔴🔴🔴🔴🔴"
                    )
            except Exception as e:
                logger.error(f"[STOP-LOSS] 체크 실패: {e}")

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
                    f"\r{spin} [{now}] Scan #{scan_count} | {elapsed:.2f}s{ws_status} | "
                    f"No opportunities{pos_info}   ",
                    end="", flush=True
                )
            else:
                print(
                    f"\n[{now}] Scan #{scan_count} | {elapsed:.2f}s{ws_status} | "
                    f"Found {total_opps} opportunities{pos_info}"
                )

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
