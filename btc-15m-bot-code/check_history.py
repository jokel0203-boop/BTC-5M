"""거래 내역 조회 스크립트 - Kalshi + Polymarket"""
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

from src.polymarket.client import PolymarketClient
from src.kalshi.client import KalshiClient


def check_kalshi_history(client):
    print("\n" + "=" * 70)
    print("KALSHI 거래 내역")
    print("=" * 70)

    # 잔고
    try:
        balance = client.client.get_balance()
        print(f"\n잔고: {balance}")
    except Exception as e:
        print(f"잔고 조회 실패: {e}")

    # 포지션
    print("\n--- 현재 포지션 ---")
    try:
        positions = client.client.get_positions()
        if hasattr(positions, 'market_positions'):
            for p in positions.market_positions:
                print(f"  {p}")
        elif hasattr(positions, 'positions'):
            for p in positions.positions:
                print(f"  {p}")
        else:
            print(f"  Raw: {positions}")
    except Exception as e:
        print(f"  포지션 조회 실패: {e}")

    # 주문 내역 (최근)
    print("\n--- 최근 주문 ---")
    try:
        orders = client.client.get_orders()
        order_list = []
        if hasattr(orders, 'orders'):
            order_list = orders.orders
        elif isinstance(orders, dict):
            order_list = orders.get('orders', [])

        if not order_list:
            print("  주문 없음")
        else:
            # 최근 20개만 표시
            for o in order_list[:20]:
                if hasattr(o, '__dict__'):
                    d = vars(o)
                    ticker = d.get('ticker', '?')
                    side = d.get('side', '?')
                    action = d.get('action', '?')
                    status = d.get('status', '?')
                    yes_price = d.get('yes_price', '?')
                    no_price = d.get('no_price', '?')
                    count = d.get('count', '?')
                    remaining = d.get('remaining_count', '?')
                    created = d.get('created_time', '?')
                    print(f"  {created} | {ticker} | {action} {side} x{count} (remain:{remaining}) | YES={yes_price}¢ NO={no_price}¢ | {status}")
                else:
                    print(f"  {o}")
    except Exception as e:
        print(f"  주문 조회 실패: {e}")

    # 체결 내역
    print("\n--- 체결 내역 (fills) ---")
    try:
        fills = client.client.get_fills()
        fill_list = []
        if hasattr(fills, 'fills'):
            fill_list = fills.fills
        elif isinstance(fills, dict):
            fill_list = fills.get('fills', [])

        if not fill_list:
            print("  체결 없음")
        else:
            for f in fill_list[:30]:
                if hasattr(f, '__dict__'):
                    d = vars(f)
                    ticker = d.get('ticker', '?')
                    side = d.get('side', '?')
                    action = d.get('action', '?')
                    yes_price = d.get('yes_price', d.get('price', '?'))
                    no_price = d.get('no_price', '?')
                    count = d.get('count', '?')
                    created = d.get('created_time', '?')
                    print(f"  {created} | {ticker} | {action} {side} x{count} | YES={yes_price}¢ NO={no_price}¢")
                else:
                    print(f"  {f}")
    except Exception as e:
        print(f"  체결 조회 실패: {e}")

    # 정산 내역
    print("\n--- 정산 내역 (settlements) ---")
    try:
        settlements = client.client.get_settlements()
        settle_list = []
        if hasattr(settlements, 'settlements'):
            settle_list = settlements.settlements
        elif isinstance(settlements, dict):
            settle_list = settlements.get('settlements', [])

        if not settle_list:
            print("  정산 없음")
        else:
            for s in settle_list[:20]:
                if hasattr(s, '__dict__'):
                    d = vars(s)
                    ticker = d.get('ticker', d.get('market_ticker', '?'))
                    revenue = d.get('revenue', d.get('settlement_value', '?'))
                    result = d.get('result', d.get('market_result', '?'))
                    no_count = d.get('no_total_cost', '?')
                    yes_count = d.get('yes_total_cost', '?')
                    settled_time = d.get('settled_time', d.get('settlement_time', '?'))
                    print(f"  {settled_time} | {ticker} | result={result} | revenue={revenue}¢ | YES_cost={yes_count} NO_cost={no_count}")
                else:
                    print(f"  {s}")
    except Exception as e:
        print(f"  정산 조회 실패: {e}")


def check_polymarket_history(client):
    print("\n" + "=" * 70)
    print("POLYMARKET 거래 내역")
    print("=" * 70)

    # 잔고 (USDC)
    try:
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        balance = client.client.get_balance_allowance(
            params=BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        print(f"\nUSDC 잔고/allowance: {balance}")
    except Exception as e:
        print(f"잔고 조회 실패: {e}")

    # 주문 내역
    print("\n--- 최근 주문 ---")
    try:
        orders_resp = client.client.get_orders()
        if isinstance(orders_resp, dict):
            orders = orders_resp.get('data', orders_resp.get('orders', []))
        elif hasattr(orders_resp, 'data'):
            orders = orders_resp.data
        else:
            orders = orders_resp if isinstance(orders_resp, list) else [orders_resp]

        if not orders:
            print("  주문 없음")
        else:
            for o in orders[:20]:
                if isinstance(o, dict):
                    oid = o.get('id', '?')[:12]
                    side = o.get('side', '?')
                    price = o.get('price', '?')
                    size = o.get('original_size', o.get('size_matched', '?'))
                    matched = o.get('size_matched', '?')
                    asset_id = o.get('asset_id', '?')[:16] if o.get('asset_id') else '?'
                    status = o.get('status', '?')
                    ts = o.get('created_at', o.get('timestamp', '?'))
                    otype = o.get('type', '?')
                    print(f"  {ts} | {side} x{size} (filled:{matched}) @ {price} | {otype} {status} | token={asset_id}...")
                else:
                    print(f"  {o}")
    except Exception as e:
        print(f"  주문 조회 실패: {e}")

    # 체결 내역
    print("\n--- 체결 내역 (trades) ---")
    try:
        trades_resp = client.client.get_trades()
        if isinstance(trades_resp, dict):
            trades = trades_resp.get('data', trades_resp.get('trades', []))
        elif hasattr(trades_resp, 'data'):
            trades = trades_resp.data
        else:
            trades = trades_resp if isinstance(trades_resp, list) else [trades_resp]

        if not trades:
            print("  체결 없음")
        else:
            for t in trades[:30]:
                if isinstance(t, dict):
                    side = t.get('side', '?')
                    price = t.get('price', '?')
                    size = t.get('size', '?')
                    asset_id = t.get('asset_id', '?')[:16] if t.get('asset_id') else '?'
                    ts = t.get('created_at', t.get('match_time', '?'))
                    fee = t.get('fee_rate_bps', '?')
                    print(f"  {ts} | {side} x{size} @ {price} | fee={fee}bps | token={asset_id}...")
                else:
                    print(f"  {t}")
    except Exception as e:
        print(f"  체결 조회 실패: {e}")


def main():
    print("거래 내역 조회 중...")
    print(f"시간: {datetime.now(timezone.utc).isoformat()}")

    # Kalshi
    kalshi = KalshiClient()
    if kalshi.connect():
        check_kalshi_history(kalshi)
    else:
        print("[ERROR] Kalshi 연결 실패")

    # Polymarket
    poly = PolymarketClient()
    if poly.connect():
        check_polymarket_history(poly)
    else:
        print("[ERROR] Polymarket 연결 실패")


if __name__ == "__main__":
    main()
