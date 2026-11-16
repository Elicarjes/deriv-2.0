"""
Backtest Quantitativo Real: No-Touch (+0.33, 10 ticks) no R_100.
Testa a cada tick do histórico se nos 10 ticks seguintes o preço tocou na barreira (+0.33).
"""

import asyncio
import json
import logging
import pandas as pd
import numpy as np
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("NoTouchBacktest")

DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def fetch_history_ticks(count=5000):
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        all_prices = []
        all_times = []
        end_time = "latest"
        
        while len(all_prices) < count:
            needed = count - len(all_prices)
            batch = min(needed, 1000)
            req = {
                "ticks_history": "R_100",
                "count": batch,
                "end": end_time,
                "style": "ticks",
                "req_id": 1
            }
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            h = res.get("history", {})
            p = h.get("prices", [])
            t = h.get("times", [])
            if not p:
                break
            if all_prices:
                p = [price for idx, price in enumerate(p) if t[idx] < all_times[0]]
                t = [time for time in t if time < all_times[0]]
                all_prices = p + all_prices
                all_times = t + all_times
            else:
                all_prices = p
                all_times = t
            if t:
                end_time = t[0] - 1
            if len(p) < 500:
                break
        return all_prices[-count:], all_times[-count:]


def backtest_notouch(prices, barrier_offset=0.33, duration_ticks=10, stake=1.0, payout=1.50):
    total_samples = len(prices) - duration_ticks
    wins = 0
    losses = 0

    net_profit = 0.0

    for i in range(total_samples):
        entry_price = prices[i]
        barrier = entry_price + barrier_offset
        future_ticks = prices[i + 1 : i + 1 + duration_ticks]
        
        # Se algum tick nos próximos 10 ticks foi >= barrier, TOCOU (Perde no No-Touch)
        touched = any(p >= barrier for p in future_ticks)
        
        if not touched:
            wins += 1
            net_profit += (payout - stake) # +$0.50
        else:
            losses += 1
            net_profit -= stake # -$1.00

    win_rate = (wins / total_samples) * 100
    loss_rate = (losses / total_samples) * 100
    expected_value_per_trade = net_profit / total_samples

    print("\n" + "=" * 80)
    print(f" BACKTEST REAL: NO-TOUCH (+{barrier_offset}, {duration_ticks} TICKS) NO R_100")
    print(f" Amostras de Ticks Analisadas: {total_samples}")
    print("=" * 80)
    print(f"  Stake por Operação : ${stake:.2f}")
    print(f"  Payout por Vitória : ${payout:.2f} (Lucro: +${payout - stake:.2f})")
    print(f"  Prejuízo por Derrota: -${stake:.2f}")
    print("-" * 80)
    print(f"  Vitórias (Não tocou): {wins} ({win_rate:.2f}%)")
    print(f"  Derrotas (Tocou)    : {losses} ({loss_rate:.2f}%)")
    print(f"  Taxa de Break-even  : {(stake / payout) * 100:.2f}%")
    print("-" * 80)
    print(f"  Resultado Financeiro Total: ${net_profit:+.2f}")
    print(f"  Expectativa por Trade (EV): ${expected_value_per_trade:+.4f} por aposta")
    print("=" * 80 + "\n")


async def main():
    prices, times = await fetch_history_ticks(count=5000)
    if not prices:
        print("Erro ao baixar ticks.")
        return
    backtest_notouch(prices, barrier_offset=0.33, duration_ticks=10, stake=1.0, payout=1.50)


if __name__ == "__main__":
    asyncio.run(main())
