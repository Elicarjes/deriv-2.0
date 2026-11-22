"""
Backtest Quantitativo de Opções Deriv: Rise (Call) 15s no Início de Candle de 1m
Suporta Martingale sequencial (G0, G1, G2, G3), análise de Streaks consecutivas (Loss e Win),
análise financeira e breakdown horário com exportação automática de Dashboard HTML.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
import argparse
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Any
from itertools import groupby
from collections import Counter

import pandas as pd
import numpy as np
from tabulate import tabulate
import websockets

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"


async def fetch_ticks_from_deriv(symbol: str, target_date_str: str = None, hours: int = 24) -> pd.DataFrame:
    """
    Baixa ticks da Deriv API pública.
    Se target_date_str for fornecido (ex: '2026-11-21'), baixa os ticks desse dia UTC completo.
    Caso contrário, baixa as últimas `hours` horas.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"ticks_{symbol}_{target_date_str or f'{hours}h'}.csv")

    if os.path.exists(cache_file):
        print(f"[*] Carregando ticks do cache local: {cache_file}")
        df = pd.read_csv(cache_file)
        df["datetime"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
        return df

    if target_date_str:
        dt_start = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        dt_end = dt_start + timedelta(days=1)
        end_epoch = int(dt_end.timestamp())
        start_epoch = int(dt_start.timestamp())
        print(f"[*] Solicitando ticks para o dia {target_date_str} (Epoch {start_epoch} até {end_epoch})...")
    else:
        dt_end = datetime.now(timezone.utc)
        dt_start = dt_end - timedelta(hours=hours)
        end_epoch = int(dt_end.timestamp())
        start_epoch = int(dt_start.timestamp())
        print(f"[*] Solicitando ticks para as últimas {hours}h...")

    all_times = []
    all_prices = []
    curr_end = end_epoch

    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        batch = 0
        while True:
            batch += 1
            req = {
                "ticks_history": symbol,
                "count": 2000,
                "end": curr_end,
                "style": "ticks",
                "req_id": batch
            }
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())

            if "error" in res:
                print(f"[!] Erro retornado pela Deriv: {res['error']['message']}")
                break

            h = res.get("history", {})
            times = h.get("times", [])
            prices = h.get("prices", [])

            if not times:
                print("[!] Sem mais ticks disponíveis.")
                break

            all_times = times + all_times
            all_prices = prices + all_prices

            oldest = times[0]
            print(f"  -> Lote {batch}: {len(times)} ticks recebidos | Mais antigo: {datetime.fromtimestamp(oldest, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")

            if oldest <= start_epoch:
                break

            curr_end = oldest - 1

    df = pd.DataFrame({"epoch": all_times, "price": all_prices})
    df = df.drop_duplicates(subset=["epoch"]).sort_values(by="epoch")
    df = df[(df["epoch"] >= start_epoch) & (df["epoch"] <= end_epoch)].copy()
    df["datetime"] = pd.to_datetime(df["epoch"], unit="s", utc=True)

    print(f"[*] Total de {len(df):,} ticks válidos no período. Salvando cache...")
    df.to_csv(cache_file, index=False)
    return df


def simulate_rise_orders(df_ticks: pd.DataFrame, duration_seconds: int = 15) -> pd.DataFrame:
    """
    Identifica o início de cada candle de 1 minuto (segundo :00).
    Captura o tick de entrada (em :00 ou primeiro >= :00) e o tick de saída em :15s.
    Avalia se foi WIN (exit_price > entry_price) ou LOSS.
    """
    df_sorted = df_ticks.sort_values("epoch").reset_index(drop=True)
    epochs = df_sorted["epoch"].to_numpy()
    prices = df_sorted["price"].to_numpy()

    min_epoch = int(epochs[0])
    max_epoch = int(epochs[-1])

    first_minute = ((min_epoch + 59) // 60) * 60
    last_minute = (max_epoch // 60) * 60

    results = []

    for candle_open_epoch in range(first_minute, last_minute, 60):
        idx_open = np.searchsorted(epochs, candle_open_epoch)
        if idx_open >= len(epochs):
            continue

        actual_open_epoch = epochs[idx_open]
        if actual_open_epoch > candle_open_epoch + 3:
            continue

        entry_price = prices[idx_open]

        expiry_target_epoch = candle_open_epoch + duration_seconds
        idx_exit = np.searchsorted(epochs, expiry_target_epoch)
        if idx_exit >= len(epochs):
            continue

        actual_exit_epoch = epochs[idx_exit]
        if actual_exit_epoch > expiry_target_epoch + 3:
            continue

        exit_price = prices[idx_exit]

        is_win = exit_price > entry_price
        is_tie = exit_price == entry_price

        candle_dt = datetime.fromtimestamp(candle_open_epoch, timezone.utc)

        results.append({
            "candle_epoch": candle_open_epoch,
            "candle_time": candle_dt,
            "hour": candle_dt.hour,
            "open_epoch": actual_open_epoch,
            "exit_epoch": actual_exit_epoch,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "delta": round(exit_price - entry_price, 4),
            "result": "WIN" if is_win else ("TIE" if is_tie else "LOSS"),
            "win": 1 if is_win else 0
        })

    return pd.DataFrame(results)


def calculate_streaks(df_trades: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Calcula sequências consecutivas (streaks) de Loss e de Win.
    """
    wins = df_trades["win"].tolist()
    streaks = [(k, len(list(g))) for k, g in groupby(wins)]
    loss_streaks = [length for k, length in streaks if k == 0]
    win_streaks = [length for k, length in streaks if k == 1]

    loss_counts = Counter(loss_streaks)
    win_counts = Counter(win_streaks)

    loss_streak_data = [
        {"streak": f"{l}L", "length": l, "count": loss_counts[l], "label": f"{l}L (x{loss_counts[l]})"}
        for l in sorted(loss_counts.keys())
    ]
    win_streak_data = [
        {"streak": f"{w}W", "length": w, "count": win_counts[w], "label": f"{w}W (x{win_counts[w]})"}
        for w in sorted(win_counts.keys())
    ]
    return loss_streak_data, win_streak_data


def simulate_martingale(
    df_trades: pd.DataFrame,
    base_stake: float = 1.0,
    payout_pct: float = 88.0,
    multiplier: float = 2.15,
    max_gales: int = 0,
    mode: str = "LOSS_STREAK",
    streak_count: int = 2
) -> Dict[str, Any]:
    trades = df_trades.to_dict(orient="records")
    payout_factor = payout_pct / 100.0

    cycle_outcomes = {f"G{i}": 0 for i in range(max_gales + 1)}
    cycle_outcomes["TOTAL_LOSS"] = 0

    total_cycles = 0
    state = "MASTER" if mode == "DIRECT" else "SLAVE"
    consec_losses_slave = 0
    consec_wins_slave = 0
    current_gale = 0
    accumulated_loss = 0.0

    pnl_history = [0.0]
    stakes_history = []
    daily_pnl = 0.0
    wins_count = 0
    losses_count = 0
    master_orders = 0
    slave_orders = 0

    max_drawdown = 0.0
    peak_pnl = 0.0
    consecutive_losses = 0
    max_consecutive_losses = 0

    for t in trades:
        is_master = (mode == "DIRECT") or (state == "MASTER")

        if is_master:
            master_orders += 1
            stake = base_stake * (multiplier ** current_gale)
            stakes_history.append(stake)

            if t["win"] == 1:
                profit = (stake * payout_factor) - accumulated_loss
                daily_pnl += profit
                wins_count += 1
                consecutive_losses = 0

                cycle_outcomes[f"G{current_gale}"] += 1
                total_cycles += 1

                state = "MASTER" if mode == "DIRECT" else "SLAVE"
                consec_losses_slave = 0
                consec_wins_slave = 0
                current_gale = 0
                accumulated_loss = 0.0
            else:
                accumulated_loss += stake
                daily_pnl -= stake
                losses_count += 1
                consecutive_losses += 1
                if consecutive_losses > max_consecutive_losses:
                    max_consecutive_losses = consecutive_losses

                if current_gale < max_gales:
                    current_gale += 1
                else:
                    cycle_outcomes["TOTAL_LOSS"] += 1
                    total_cycles += 1
                    state = "MASTER" if mode == "DIRECT" else "SLAVE"
                    consec_losses_slave = 0
                    consec_wins_slave = 0
                    current_gale = 0
                    accumulated_loss = 0.0

            pnl_history.append(daily_pnl)
            if daily_pnl > peak_pnl:
                peak_pnl = daily_pnl
            drawdown = peak_pnl - daily_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        else:
            slave_orders += 1
            if t["win"] == 1:
                consec_wins_slave += 1
                consec_losses_slave = 0
                if mode == "WIN_STREAK" and consec_wins_slave >= streak_count:
                    state = "MASTER"
                    current_gale = 0
                    accumulated_loss = 0.0
            else:
                consec_losses_slave += 1
                consec_wins_slave = 0
                if mode == "LOSS_STREAK" and consec_losses_slave >= streak_count:
                    state = "MASTER"
                    current_gale = 0
                    accumulated_loss = 0.0

    return {
        "total_trades": len(trades),
        "slave_orders": slave_orders,
        "master_orders": master_orders,
        "mode": mode,
        "streak_count": streak_count,
        "max_gales": max_gales,
        "total_cycles": total_cycles,
        "wins_count": wins_count,
        "losses_count": losses_count,
        "cycle_outcomes": cycle_outcomes,
        "daily_pnl": daily_pnl,
        "max_drawdown": max_drawdown,
        "max_consecutive_losses": max_consecutive_losses,
        "pnl_history": pnl_history,
        "stakes_history": stakes_history
    }


def print_detailed_report(
    symbol: str,
    date_label: str,
    df_trades: pd.DataFrame,
    mg_results: Dict[str, Any],
    loss_streaks: List[Dict[str, Any]],
    win_streaks: List[Dict[str, Any]],
    base_stake: float,
    payout_pct: float,
    multiplier: float
):
    total_trades = len(df_trades)
    direct_wins = df_trades["win"].sum()
    direct_losses = total_trades - direct_wins
    direct_win_rate = (direct_wins / total_trades * 100) if total_trades > 0 else 0

    print("\n" + "=" * 78)
    print(f" RELATÓRIO DE BACKTEST QUANTITATIVO DERIV: {symbol} - {date_label}")
    print("=" * 78)
    print(f"  Contrato: Rise (CALL) | Início: Abertura do Candle (1m) | Expiração: 15s")
    print(f"  Total de Candles / Entradas Analisadas: {total_trades:,}")
    print(f"  Parâmetros Financeiros: Stake Base: ${base_stake:.2f} | Payout: {payout_pct:.1f}% | Mult. Gale: {multiplier:.2f}x")
    print("-" * 78)

    # 1. Assertividade Direta
    print("\n[1] RESULTADOS SEM GALE (MÃO FIXA - 1ª ENTRADA):")
    summary_direct = [
        ["Total de Ordens", f"{total_trades:,}"],
        ["Vitórias (Win Direto)", f"{direct_wins:,}"],
        ["Derrotas (Loss Direto)", f"{direct_losses:,}"],
        ["Taxa de Acerto (Win Rate)", f"{direct_win_rate:.2f}%"],
    ]
    print(tabulate(summary_direct, headers=["Métrica", "Valor"], tablefmt="fancy_grid"))

    # 2. STREAKS (Sequências Consecutivas)
    print("\n[2] ANÁLISE DE STREAKS (SEQUÊNCIAS CONSECUTIVAS):")
    loss_str = " | ".join([s["label"] for s in loss_streaks])
    win_str = " | ".join([s["label"] for s in win_streaks])
    print(f"  🔻 LOSS STREAKS: {loss_str}")
    print(f"  🟢 WIN STREAKS : {win_str}")

    # 3. Desempenho com Martingale
    outcomes = mg_results["cycle_outcomes"]
    tot_cycles = mg_results["total_cycles"]

    g0 = outcomes.get("G0", 0)
    g1 = outcomes.get("G1", 0)
    g2 = outcomes.get("G2", 0)
    g3 = outcomes.get("G3", 0)
    loss_tot = outcomes.get("TOTAL_LOSS", 0)

    acc_g1 = g0 + g1
    acc_g2 = acc_g1 + g2
    acc_g3 = acc_g2 + g3

    pct_g0 = (g0 / tot_cycles * 100) if tot_cycles else 0
    pct_g1 = (g1 / tot_cycles * 100) if tot_cycles else 0
    pct_g2 = (g2 / tot_cycles * 100) if tot_cycles else 0
    pct_g3 = (g3 / tot_cycles * 100) if tot_cycles else 0
    pct_loss_tot = (loss_tot / tot_cycles * 100) if tot_cycles else 0

    pct_acc_g1 = (acc_g1 / tot_cycles * 100) if tot_cycles else 0
    pct_acc_g2 = (acc_g2 / tot_cycles * 100) if tot_cycles else 0
    pct_acc_g3 = (acc_g3 / tot_cycles * 100) if tot_cycles else 0

    print("\n[3] DISTRIBUIÇÃO E EFICIÊNCIA DO MARTINGALE (CICLOS):")
    mg_table = [
        ["G0 (Primeira Mão)", g0, f"{pct_g0:.2f}%", g0, f"{pct_g0:.2f}%"],
        ["G1 (1º Gale)", g1, f"{pct_g1:.2f}%", acc_g1, f"{pct_acc_g1:.2f}%"],
        ["G2 (2º Gale)", g2, f"{pct_g2:.2f}%", acc_g2, f"{pct_acc_g2:.2f}%"],
        ["G3 (3º Gale)", g3, f"{pct_g3:.2f}%", acc_g3, f"{pct_acc_g3:.2f}%"],
        ["LOSS TOTAL (Stop Ciclo)", loss_tot, f"{pct_loss_tot:.2f}%", "-", "-"],
    ]
    print(tabulate(
        mg_table,
        headers=["Nível", "Ciclos Ganhos", "% Individual", "Acumulado", "% Acumulada"],
        tablefmt="fancy_grid"
    ))

    # 4. Resumo Financeiro
    print("\n[4] PERFORMANCE FINANCEIRA (SIMULAÇÃO COM G3):")
    pnl = mg_results["daily_pnl"]
    dd = mg_results["max_drawdown"]
    consec_loss = mg_results["max_consecutive_losses"]

    stakes = [
        base_stake,
        base_stake * multiplier,
        base_stake * (multiplier ** 2),
        base_stake * (multiplier ** 3)
    ]
    risk_per_cycle = sum(stakes)

    fin_table = [
        ["Stake Base (G0)", f"${base_stake:.2f}"],
        ["Stake G1", f"${stakes[1]:.2f}"],
        ["Stake G2", f"${stakes[2]:.2f}"],
        ["Stake G3", f"${stakes[3]:.2f}"],
        ["Risco Máximo por Ciclo (G0+G1+G2+G3)", f"${risk_per_cycle:.2f}"],
        ["Resultado Líquido do Dia", f"{'+' if pnl >= 0 else ''}${pnl:.2f}"],
        ["Drawdown Máximo Flutuante", f"${dd:.2f}"],
        ["Maior Sequência de Derrotas", f"{consec_loss} ordens"],
    ]
    print(tabulate(fin_table, headers=["Indicador Financeiro", "Valor"], tablefmt="fancy_grid"))

    print("=" * 78 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Backtest Rise 15s na Deriv")
    parser.add_argument("--symbol", type=str, default="R_100", help="Símbolo Deriv (ex: R_100, 1HZ100V)")
    parser.add_argument("--date", type=str, default=None, help="Data específica YYYY-MM-DD (ex: 2026-11-21)")
    parser.add_argument("--hours", type=int, default=24, help="Quantidade de horas se não especificar data (default: 24)")
    parser.add_argument("--duration", type=int, default=15, help="Duração da opção em segundos (default: 15)")
    parser.add_argument("--stake", type=float, default=1.0, help="Stake base em USD (default: 1.00)")
    parser.add_argument("--payout", type=float, default=88.0, help="Payout percentual (default: 88.0 ou 0.88)")
    parser.add_argument("--multiplier", type=float, default=2.15, help="Multiplicador do Martingale (default: 2.15)")
    parser.add_argument("--max-gales", type=int, default=0, choices=[0, 1, 2, 3], help="Nível de Gale na Real: 0 (Mão Fixa - Padrão), 1 (G1), 2 (G2), 3 (G3)")
    parser.add_argument("--mode", type=str, default="LOSS_STREAK", choices=["LOSS_STREAK", "WIN_STREAK", "DIRECT"], help="Modo de Operação: 1-LOSS_STREAK, 2-WIN_STREAK, 3-DIRECT")
    parser.add_argument("--streak-count", type=int, default=2, help="Quantidade de Streaks de 1 a 15 para ativar a Real (default: 2)")

    args = parser.parse_args()
    target_date = args.date or "2026-11-21"

    df_ticks = await fetch_ticks_from_deriv(symbol=args.symbol, target_date_str=target_date, hours=args.hours)

    if df_ticks.empty or len(df_ticks) < 100:
        df_ticks = await fetch_ticks_from_deriv(symbol=args.symbol, target_date_str=None, hours=24)
        target_date = "Últimas 24 Horas"

    df_trades = simulate_rise_orders(df_ticks, duration_seconds=args.duration)
    if df_trades.empty:
        print("[!] Nenhuma ordem simulada.")
        return

    loss_streaks, win_streaks = calculate_streaks(df_trades)

    mg_results = simulate_martingale(
        df_trades=df_trades,
        base_stake=args.stake,
        payout_pct=args.payout,
        multiplier=args.multiplier,
        max_gales=args.max_gales,
        mode=args.mode,
        streak_count=args.streak_count
    )

    print_detailed_report(
        symbol=args.symbol,
        date_label=target_date,
        df_trades=df_trades,
        mg_results=mg_results,
        loss_streaks=loss_streaks,
        win_streaks=win_streaks,
        base_stake=args.stake,
        payout_pct=args.payout,
        multiplier=args.multiplier
    )

    # Atualiza JSON e Dashboard HTML
    try:
        from research.generate_html import generate
        generate()
    except Exception as e:
        print(f"[!] Erro ao atualizar dashboard HTML: {e}")


if __name__ == "__main__":
    asyncio.run(main())
