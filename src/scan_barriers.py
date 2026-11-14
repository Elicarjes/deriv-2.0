"""
Scanner de Contratos de Barreira: Touches (ONETOUCH) vs No-Touch (NOTOUCH)
e Higher/Lower com Barreira na Nova API Oficial da Deriv.
Endpoint: wss://api.derivws.com/trading/v1/options/ws/public
Documentação: https://developers.deriv.com/docs/ (AI Hub - field: underlying_symbol)
"""

import asyncio
import json
import logging
from tabulate import tabulate
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BarrierScanner")

DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def fetch_spot_price(ws, symbol="R_100"):
    req = {"ticks": symbol}
    await ws.send(json.dumps(req))
    res = json.loads(await ws.recv())
    if "tick" in res:
        return res["tick"]["quote"]
    return None


async def get_proposal(ws, contract_type, symbol, amount, duration, duration_unit, barrier):
    req = {
        "proposal": 1,
        "amount": amount,
        "basis": "stake",
        "contract_type": contract_type,
        "currency": "USD",
        "duration": duration,
        "duration_unit": duration_unit,
        "underlying_symbol": symbol,
        "barrier": barrier,
        "req_id": 1
    }
    await ws.send(json.dumps(req))
    res = json.loads(await ws.recv())
    return res.get("proposal", {})


async def scan_barrier_contracts():
    logger.info(f"Conectando ao gateway público oficial: {DERIV_PUBLIC_WS}...")
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        spot = await fetch_spot_price(ws, "R_100")
        if not spot:
            logger.error("Falha ao obter spot price.")
            return

        logger.info(f"Preço Spot Atual do R_100: {spot} USD")

        durations = [2, 5, 10] # minutos
        barrier_offsets = [0.5, 1.0, 1.5, 2.5, 4.0] # pontos acima do spot
        stake = 10.0 # $10 apostados

        results = []

        for dur in durations:
            for offset in barrier_offsets:
                barrier_str = f"+{offset:.2f}"
                
                # Proposta ONETOUCH
                prop_touch = await get_proposal(ws, "ONETOUCH", "R_100", stake, dur, "m", barrier_str)
                # Proposta NOTOUCH
                prop_notouch = await get_proposal(ws, "NOTOUCH", "R_100", stake, dur, "m", barrier_str)

                # Processa ONETOUCH
                if prop_touch and "payout" in prop_touch:
                    payout_t = prop_touch["payout"]
                    net_t = payout_t - stake
                    roi_t = (net_t / stake) * 100
                    be_t = (stake / payout_t) * 100 # Break-even %
                    touch_info = f"${net_t:+.2f} ({roi_t:+.1f}%)"
                    be_touch_info = f"{be_t:.1f}%"
                else:
                    touch_info = "N/D"
                    be_touch_info = "-"

                # Processa NOTOUCH
                if prop_notouch and "payout" in prop_notouch:
                    payout_nt = prop_notouch["payout"]
                    net_nt = payout_nt - stake
                    roi_nt = (net_nt / stake) * 100
                    be_nt = (stake / payout_nt) * 100
                    notouch_info = f"${net_nt:+.2f} ({roi_nt:+.1f}%)"
                    be_notouch_info = f"{be_nt:.1f}%"
                else:
                    notouch_info = "N/D"
                    be_notouch_info = "-"

                results.append([
                    f"{dur} min",
                    barrier_str,
                    touch_info,
                    be_touch_info,
                    notouch_info,
                    be_notouch_info
                ])

        print("\n" + "=" * 105)
        print(f" RELATÓRIO COMPARATIVO: TOUCHES vs NO-TOUCH (R_100 AO VIVO NA DERIV)")
        print(f" Preço Spot Atual: {spot} USD | Capital de Teste: ${stake:.2f}")
        print("=" * 105)

        headers = [
            "Duração",
            "Barreira",
            "TOUCHES: Lucro (ROI)",
            "TOUCHES: Break-even",
            "NO-TOUCH: Lucro (ROI)",
            "NO-TOUCH: Break-even"
        ]

        print("\n" + tabulate(results, headers=headers, tablefmt="grid"))
        print("\nExplicação Matemática:")
        print("  - Lucro (ROI): Quanto você ganha líquido se a aposta for vitoriosa.")
        print("  - Break-even (%): Taxa de acerto MÍNIMA que o seu bot precisa atingir para ser lucrativo.")
        print("    * Exemplo: Se o Break-even for 35%, acertar apenas 4 em cada 10 trades já dá LUCRO REAL.")
        print("    * No No-Touch, se o Break-even for 85%, errar apenas 2 em cada 10 trades DESTRÓI a banca.")
        print("=" * 105 + "\n")


if __name__ == "__main__":
    asyncio.run(scan_barrier_contracts())
