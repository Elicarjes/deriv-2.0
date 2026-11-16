"""
Varredura Completa de Barreiras Negativas de Touch (10 Ticks) no R_100.
Calcula para cada barreira:
- Payout oficial da Deriv
- Break-even teórico
- Taxa real de vitórias em 5.000 ticks
- Saldo final líquido acumulado
"""

import asyncio
import json
from tabulate import tabulate
import websockets

DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def fetch_history_ticks(count=5000):
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        all_prices = []
        all_times = []
        end_time = "latest"
        while len(all_prices) < count:
            needed = count - len(all_prices)
            batch = min(needed, 1000)
            req = {"ticks_history": "R_100", "count": batch, "end": end_time, "style": "ticks", "req_id": 1}
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            h = res.get("history", {})
            p, t = h.get("prices", []), h.get("times", [])
            if not p:
                break
            if all_prices:
                p = [price for idx, price in enumerate(p) if t[idx] < all_times[0]]
                t = [time for time in t if time < all_times[0]]
                all_prices = p + all_prices
                all_times = t + all_times
            else:
                all_prices, all_times = p, t
            if t:
                end_time = t[0] - 1
            if len(p) < 500:
                break
        return all_prices[-count:]


async def get_payouts(ws, barriers):
    payouts = {}
    for b in barriers:
        req = {
            "proposal": 1,
            "amount": 1.0,
            "basis": "stake",
            "contract_type": "ONETOUCH",
            "currency": "USD",
            "duration": 10,
            "duration_unit": "t",
            "underlying_symbol": "R_100",
            "barrier": b,
            "req_id": 1
        }
        await ws.send(json.dumps(req))
        res = json.loads(await ws.recv())
        if "proposal" in res:
            payouts[b] = res["proposal"]["payout"]
    return payouts


async def main():
    barriers = ["-0.10", "-0.12", "-0.15", "-0.20", "-0.25", "-0.30", "-0.40", "-0.50"]
    print("Obtendo propostas oficiais da Deriv...")
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        payouts = await get_payouts(ws, barriers)

    print("Obtendo 5.000 ticks históricos...")
    prices = await fetch_history_ticks(5000)
    
    total_samples = len(prices) - 10
    table = []

    for b_str in barriers:
        b_val = float(b_str)
        payout = payouts.get(b_str, 0.0)
        if payout == 0.0:
            continue
        
        be_rate = (1.0 / payout) * 100
        wins = 0
        losses = 0
        net_profit = 0.0

        for i in range(total_samples):
            entry = prices[i]
            target_barrier = entry + b_val
            future = prices[i + 1 : i + 1 + 10]
            
            won = any(p <= target_barrier for p in future)
            if won:
                wins += 1
                net_profit += (payout - 1.0)
            else:
                losses += 1
                net_profit -= 1.0

        win_rate = (wins / total_samples) * 100
        edge = win_rate - be_rate # Diferença entre taxa real e break-even

        table.append([
            b_str,
            f"${payout:.2f}",
            f"{be_rate:.1f}%",
            f"{win_rate:.1f}%",
            f"{edge:+.1f}%",
            f"${net_profit:+.2f}"
        ])

    headers = [
        "Barreira",
        "Payout Deriv",
        "Break-even Necessário",
        "Taxa Real de Vitória",
        "Edge (Vantagem Real)",
        "Saldo em 5.000 Ticks"
    ]

    print("\n" + "=" * 90)
    print(" SCANNER QUANTITATIVO: ONETOUCH PARA BAIXO (10 TICKS) NO R_100")
    print("=" * 90)
    print(tabulate(table, headers=headers, tablefmt="grid"))
    print("\nInterpretação:")
    print("  - Edge Positivo: Você tem vantagem matemática sobre a corretora.")
    print("  - Edge Negativo: A corretora tem vantagem matemática sobre você.")
    print("=" * 90 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
