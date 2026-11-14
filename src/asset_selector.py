"""
Módulo de Seleção Dinâmica do Ativo Mais Seguro para Acumuladores (ACCU).
Consulta periodicamente a API oficial da Deriv para todos os índices de volatilidade,
analisa o histórico de sobrevivência dos últimos 100 contratos de cada um e elege
o ativo que possui a maior probabilidade de sobrevivência no alvo de ticks (ex: 2 ticks).
"""

import asyncio
import json
import logging
from typing import Tuple, List, Dict
import websockets

logger = logging.getLogger("AssetSelector")

CANDIDATE_SYMBOLS = [
    ("R_10", "Volatility 10"),
    ("1HZ50V", "Volatility 50 (1s)"),
    ("R_25", "Volatility 25"),
    ("1HZ100V", "Volatility 100 (1s)"),
    ("1HZ30V", "Volatility 30 (1s)"),
    ("1HZ10V", "Volatility 10 (1s)"),
    ("R_50", "Volatility 50"),
    ("1HZ15V", "Volatility 15 (1s)"),
    ("R_75", "Volatility 75"),
    ("1HZ75V", "Volatility 75 (1s)"),
    ("1HZ90V", "Volatility 90 (1s)"),
    ("R_100", "Volatility 100"),
]


async def find_safest_asset(public_ws_url: str = "wss://api.derivws.com/trading/v1/options/ws/public", target_ticks: int = 2, growth_rate: float = 0.01) -> Dict:
    """
    Varre os ativos candidatos e retorna o dicionário com o ativo campeão de sobrevivência.
    """
    logger.info("🔍 Escaneando todos os índices sintéticos para encontrar o ativo mais seguro ao vivo...")
    rankings = []

    try:
        async with websockets.connect(public_ws_url) as ws:
            for sym, name in CANDIDATE_SYMBOLS:
                req = {
                    "proposal": 1,
                    "amount": 1.0,
                    "basis": "stake",
                    "contract_type": "ACCU",
                    "currency": "USD",
                    "underlying_symbol": sym,
                    "growth_rate": growth_rate,
                    "req_id": 99
                }
                await ws.send(json.dumps(req))
                res = json.loads(await ws.recv())

                if "proposal" in res:
                    details = res["proposal"].get("contract_details", {})
                    history = details.get("ticks_stayed_in", [])
                    if history:
                        n = len(history)
                        survived_target = sum(1 for t in history if t >= target_ticks) / n * 100
                        avg_ticks = sum(history) / n
                        max_ticks = max(history)
                        barrier_pct = details.get("tick_size_barrier_percentage", "-")
                        
                        rankings.append({
                            "symbol": sym,
                            "name": name,
                            "survived_target_pct": survived_target,
                            "avg_ticks": avg_ticks,
                            "max_ticks": max_ticks,
                            "barrier_pct": barrier_pct
                        })
    except Exception as e:
        logger.warning(f"Erro ao escanear ativos: {e}. Usando R_10 como fallback padrão.")
        return {"symbol": "R_10", "name": "Volatility 10", "survived_target_pct": 99.0, "avg_ticks": 75.0}

    if not rankings:
        return {"symbol": "R_10", "name": "Volatility 10", "survived_target_pct": 99.0, "avg_ticks": 75.0}

    # Ordena: 1º maior taxa de sobrevivência no alvo de ticks, 2º maior média de ticks
    rankings.sort(key=lambda x: (x["survived_target_pct"], x["avg_ticks"]), reverse=True)
    winner = rankings[0]

    logger.info(f"🏆 ATIVO CAMPEÃO ELEITO: {winner['name']} ({winner['symbol']})")
    logger.info(f"   Taxa de Sobrevivência ({target_ticks} ticks): {winner['survived_target_pct']:.1f}% | Média de Vida: {winner['avg_ticks']:.1f} ticks")

    return winner


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    winner = asyncio.run(find_safest_asset(target_ticks=2))
    print("Vencedor:", winner)
