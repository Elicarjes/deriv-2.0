"""
Módulo de Análise Quantitativa de Candlesticks no R_100 (Deriv API Oficial v2/AI).
Baseado nas especificações oficiais de https://developers.deriv.com/docs/ (AI Hub / llms.txt).
Gateway Público: wss://api.derivws.com/trading/v1/options/ws/public

Calcula:
1. Probabilidade condicional de reversão e continuação.
2. Eficiência com Martingale (Entrada Direta, G1, G2, G3 e Loss Total).
3. Balanço financeiro simulado com base no payout real de 95% e multiplicador de 2.2x.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any
import pandas as pd
import numpy as np
from tabulate import tabulate
import websockets

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DerivQuant")

# Endpoint oficial documentado no novo portal developers.deriv.com
DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def fetch_candles_v2(symbol: str = "R_100", total_candles: int = 5000, granularity: int = 60) -> List[Dict[str, Any]]:
    """
    Baixa histórico de candles usando o gateway público da nova arquitetura Deriv API.
    """
    all_candles = []
    end_time = "latest"

    logger.info(f"Conectando ao gateway público oficial: {DERIV_PUBLIC_WS}...")
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        while len(all_candles) < total_candles:
            needed = total_candles - len(all_candles)
            current_batch = min(needed, 5000)

            request = {
                "ticks_history": symbol,
                "adjust_start_time": 1,
                "count": current_batch,
                "end": end_time,
                "style": "candles",
                "granularity": granularity,
                "req_id": 1
            }

            logger.info(f"Solicitando lote de até {current_batch} candles (end={end_time})...")
            await ws.send(json.dumps(request))
            
            raw_response = await ws.recv()
            data = json.loads(raw_response)

            if "error" in data:
                logger.error(f"Erro retornado pela Deriv: {data['error']}")
                break

            candles = data.get("candles", [])
            if not candles:
                logger.warning("Nenhum candle retornado no lote.")
                break

            logger.info(f"Recebidos {len(candles)} candles neste lote.")
            
            if all_candles:
                candles = [c for c in candles if c["epoch"] < all_candles[0]["epoch"]]
                if not candles:
                    break
                all_candles = candles + all_candles
            else:
                all_candles = candles

            if len(candles) > 0:
                # Na nova API o limite por chamada é 1000. Paginamos para trás subtraindo 1s do mais antigo.
                end_time = candles[0]["epoch"] - 1

            if len(candles) < 500: # Se retornou menos de 500, o histórico acabou
                break

    all_candles.sort(key=lambda x: x["epoch"])
    return all_candles[-total_candles:]


def classify_candles(candles: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(candles)
    conditions = [
        df["close"] > df["open"],
        df["close"] < df["open"]
    ]
    choices = ["G", "R"]
    df["direction"] = np.select(conditions, choices, default="D")
    df["datetime"] = pd.to_datetime(df["epoch"], unit="s")
    return df


def evaluate_martingale_strategy(directions: List[str], pattern: str, target_direction: str, max_gales: int = 3):
    """
    Avalia os resultados de uma estratégia que entra em `target_direction` após `pattern`,
    utilizando até `max_gales` níveis de Martingale.
    
    Exemplo:
    pattern = 'GGG' (3 verdes), target_direction = 'R' (reversão para vermelho).
    - Se candle subsequente é 'R': WIN Direto
    - Se é 'G', 'R': WIN no G1
    - Se é 'G', 'G', 'R': WIN no G2
    - Se é 'G', 'G', 'G', 'R': WIN no G3
    - Se é 'G', 'G', 'G', 'G': LOSS TOTAL (Hit)
    """
    pattern_len = len(pattern)
    required_future = 1 + max_gales
    
    results = {
        "direct_win": 0,
        "g1_win": 0,
        "g2_win": 0,
        "g3_win": 0,
        "loss_total": 0,
        "total_triggers": 0
    }

    # Stakes e payouts típicos (Base $1, Gale 2.2x, Payout 95%)
    stakes = [1.0, 2.2, 4.84, 10.65] # Entrada, G1, G2, G3 (Soma total arriscada no ciclo = $18.69)
    payout_rate = 0.95

    total_profit_usd = 0.0

    for i in range(len(directions) - pattern_len - required_future):
        window = "".join(directions[i:i + pattern_len])
        if window == pattern:
            results["total_triggers"] += 1
            future = directions[i + pattern_len : i + pattern_len + required_future]
            
            won_at_step = -1
            for step, outcome in enumerate(future):
                if outcome == target_direction:
                    won_at_step = step
                    break
            
            if won_at_step == 0:
                results["direct_win"] += 1
                # Ganha entrada base: 1 * 0.95 = +0.95
                total_profit_usd += stakes[0] * payout_rate
            elif won_at_step == 1 and max_gales >= 1:
                results["g1_win"] += 1
                # Retorno: 2.2 * 1.95 - (1.0 + 2.2) = +1.09
                profit = (stakes[1] * (1.0 + payout_rate)) - (stakes[0] + stakes[1])
                total_profit_usd += profit
            elif won_at_step == 2 and max_gales >= 2:
                results["g2_win"] += 1
                total_spent = sum(stakes[:3])
                profit = (stakes[2] * (1.0 + payout_rate)) - total_spent
                total_profit_usd += profit
            elif won_at_step == 3 and max_gales >= 3:
                results["g3_win"] += 1
                total_spent = sum(stakes[:4])
                profit = (stakes[3] * (1.0 + payout_rate)) - total_spent
                total_profit_usd += profit
            else:
                results["loss_total"] += 1
                # Perdeu todos os 4 passos seguidos (Hit completo)
                loss_amount = sum(stakes[: 1 + max_gales])
                total_profit_usd -= loss_amount

    results["net_profit_usd"] = total_profit_usd
    return results


def run_full_quant_report(df: pd.DataFrame):
    directions = df["direction"].tolist()
    total = len(directions)
    
    print("\n" + "=" * 95)
    print(f" RELATÓRIO QUANTITATIVO: MARTINGALE (G1, G2, G3) NA DERIV (NOVA API OFICIAL)")
    print(f" Período: {df['datetime'].iloc[0]} até {df['datetime'].iloc[-1]} | Total: {total} Candles de 1m (R_100)")
    print("=" * 95)

    headers = [
        "Estratégia / Padrão",
        "Disparos",
        "Win Direto",
        "Win G1",
        "Win G2",
        "Win G3",
        "Loss Total (Hit)",
        "Taxa Acerto c/ G3",
        "Saldo Líquido ($)"
    ]

    table_data = []

    strategies = [
        # (Nome, Padrão, Direção Alvo)
        ("Aposta REVERSÃO após 1 Verde", "G", "R"),
        ("Aposta REVERSÃO após 2 Verdes", "GG", "R"),
        ("Aposta REVERSÃO após 3 Verdes", "GGG", "R"),
        ("Aposta REVERSÃO após 4 Verdes", "GGGG", "R"),
        ("Aposta CONTINUAÇÃO após 3 Verdes", "GGG", "G"),
        ("Aposta REVERSÃO após 1 Vermelho", "R", "G"),
        ("Aposta REVERSÃO após 2 Vermelhos", "RR", "G"),
        ("Aposta REVERSÃO após 3 Vermelhos", "RRR", "G"),
        ("Aposta REVERSÃO após 4 Vermelhos", "RRRR", "G"),
        ("Aposta CONTINUAÇÃO após 3 Vermelhos", "RRR", "R"),
    ]

    for label, pattern, target in strategies:
        res = evaluate_martingale_strategy(directions, pattern, target, max_gales=3)
        triggers = res["total_triggers"]
        if triggers == 0:
            continue
        
        wins_total = res["direct_win"] + res["g1_win"] + res["g2_win"] + res["g3_win"]
        win_rate = (wins_total / triggers) * 100
        net = res["net_profit_usd"]

        table_data.append([
            label,
            triggers,
            f"{res['direct_win']} ({res['direct_win']/triggers*100:.1f}%)",
            f"{res['g1_win']} ({res['g1_win']/triggers*100:.1f}%)",
            f"{res['g2_win']} ({res['g2_win']/triggers*100:.1f}%)",
            f"{res['g3_win']} ({res['g3_win']/triggers*100:.1f}%)",
            f"{res['loss_total']} ({res['loss_total']/triggers*100:.1f}%)",
            f"{win_rate:.2f}%",
            f"${net:+.2f}"
        ])

    print("\n" + tabulate(table_data, headers=headers, tablefmt="grid"))
    
    print("\n" + "-" * 95)
    print("PARÂMETROS DA SIMULAÇÃO FINANCEIRA:")
    print("  - Entrada Inicial: $1.00 | Gale 1: $2.20 | Gale 2: $4.84 | Gale 3: $10.65")
    print("  - Payout da Deriv: 95% (Retorno de $0.95 por dólar apostado)")
    print("  - Custo de um HIT (Loss Total no G3): -$18.69")
    print("=" * 95 + "\n")


async def main():
    candles = await fetch_candles_v2(symbol="R_100", total_candles=5000, granularity=60)
    if not candles:
        logger.error("Falha ao obter histórico de candles.")
        return

    df = classify_candles(candles)
    run_full_quant_report(df)


if __name__ == "__main__":
    asyncio.run(main())
