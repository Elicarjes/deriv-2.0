"""
Backtest Quantitativo: Touch para Baixo (ONETOUCH, barreira -0.12, 10 ticks).
Compara:
1. Entrada Cega (em todos os ticks).
2. Entrada com Filtro de Momentum (só entra se o último tick caiu).
3. Entrada com Filtro de Vela de Baixa (se o candle de 1m anterior fechou vermelho).
"""

import asyncio
import json
import logging
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TouchBacktest")

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


def run_touch_backtest(prices, barrier_offset=-0.12, duration_ticks=10, stake=1.0, payout=1.46):
    total_samples = len(prices) - duration_ticks - 2
    
    # 1. Sem filtro (Entrada cega)
    wins_blind = 0
    losses_blind = 0
    profit_blind = 0.0

    # 2. Com filtro de queda no tick anterior
    wins_filter_tick = 0
    losses_filter_tick = 0
    profit_filter_tick = 0.0
    triggers_tick = 0

    # 3. Com filtro de 2 ticks consecutivos de queda
    wins_filter_2ticks = 0
    losses_filter_2ticks = 0
    profit_filter_2ticks = 0.0
    triggers_2ticks = 0

    for i in range(2, total_samples):
        entry_price = prices[i]
        barrier = entry_price + barrier_offset # Ex: 570.36 + (-0.12) = 570.24
        future_ticks = prices[i + 1 : i + 1 + duration_ticks]
        
        # Para vencer no ONETOUCH com barreira negativa: qualquer tick futuro <= barrier
        won = any(p <= barrier for p in future_ticks)

        # 1. Cego
        if won:
            wins_blind += 1
            profit_blind += (payout - stake)
        else:
            losses_blind += 1
            profit_blind -= stake

        # 2. Filtro 1 tick de queda (prices[i] < prices[i-1])
        if prices[i] < prices[i - 1]:
            triggers_tick += 1
            if won:
                wins_filter_tick += 1
                profit_filter_tick += (payout - stake)
            else:
                losses_filter_tick += 1
                profit_filter_tick -= stake

        # 3. Filtro 2 ticks de queda (prices[i] < prices[i-1] < prices[i-2])
        if prices[i] < prices[i - 1] < prices[i - 2]:
            triggers_2ticks += 1
            if won:
                wins_filter_2ticks += 1
                profit_filter_2ticks += (payout - stake)
            else:
                losses_filter_2ticks += 1
                profit_filter_2ticks -= stake

    be_rate = (stake / payout) * 100

    print("\n" + "=" * 85)
    print(f" RELATÓRIO: ONETOUCH (BARREIRA {barrier_offset:.2f}, {duration_ticks} TICKS) NO R_100")
    print(f" Payout Oficial: ${payout:.2f} (Lucro: +${payout-stake:.2f}) | Break-even Mínimo: {be_rate:.2f}%")
    print(f" Total de Ticks Analisados: {total_samples}")
    print("=" * 85)

    def print_mode(name, wins, losses, triggers, profit):
        if triggers == 0:
            return
        rate = (wins / triggers) * 100
        ev = profit / triggers
        print(f"\n[{name}]")
        print(f"  Entradas Disparadas: {triggers}")
        print(f"  Vitórias: {wins} ({rate:.2f}%) | Derrotas: {losses} ({100-rate:.2f}%)")
        print(f"  Taxa Real de Acerto : {rate:.2f}% (Break-even necessário: {be_rate:.2f}%)")
        print(f"  Saldo Financeiro    : ${profit:+.2f}")
        print(f"  Expectativa/Trade   : ${ev:+.4f} por aposta")

    print_mode("MODO 1: ENTRADA CEGA (Sem nenhum filtro)", wins_blind, losses_blind, total_samples - 2, profit_blind)
    print_mode("MODO 2: FILTRO 1 TICK DE QUEDA (Momentum Imediato)", wins_filter_tick, losses_filter_tick, triggers_tick, profit_filter_tick)
    print_mode("MODO 3: FILTRO 2 TICKS CONSECUTIVOS DE QUEDA (Tendência)", wins_filter_2ticks, losses_filter_2ticks, triggers_2ticks, profit_filter_2ticks)
    print("\n" + "=" * 85 + "\n")


async def main():
    prices, times = await fetch_history_ticks(count=5000)
    run_touch_backtest(prices, barrier_offset=-0.12, duration_ticks=10, stake=1.0, payout=1.46)


if __name__ == "__main__":
    asyncio.run(main())
