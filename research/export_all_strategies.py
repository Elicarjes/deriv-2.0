import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
import numpy as np
from itertools import groupby
from collections import Counter
from datetime import datetime, timezone

df_ticks = pd.read_csv('data/ticks_R_100_2026-11-21.csv')
epochs = df_ticks['epoch'].to_numpy()
prices = df_ticks['price'].to_numpy()

# 2026-11-21 00:00:00 GMT = 1795219200
# 2026-11-21 23:59:00 GMT = 1795305540
day_start_gmt = 1795219200
day_end_gmt = 1795305600

# 1. Pré-computar todos os 1.440 candles de M1 do dia (Open, Close, Cor)
all_candles = []
for c_open in range(day_start_gmt, day_end_gmt, 60):
    idx_open = np.searchsorted(epochs, c_open)
    idx_close = np.searchsorted(epochs, c_open + 60)
    if idx_open < len(epochs) and idx_close < len(epochs):
        o = prices[idx_open]
        c = prices[idx_close]
        color = "VERDE" if c > o else ("VERMELHO" if c < o else "DOJI")
        all_candles.append({
            'time': c_open,
            'dt': datetime.fromtimestamp(c_open, timezone.utc).strftime('%H:%M:%S'),
            'color': color,
            'open': o,
            'close': c
        })

print(f"Total de velas M1 computadas: {len(all_candles)}")

def format_strategy_result(wins, trades_list):
    streaks = [(k, len(list(g))) for k, g in groupby(wins)]
    loss_streaks = [length for k, length in streaks if k == 0]
    win_streaks = [length for k, length in streaks if k == 1]
    loss_counts = Counter(loss_streaks)
    win_counts = Counter(win_streaks)
    
    loss_streak_data = [{'streak': f'{l}L', 'length': l, 'count': loss_counts[l], 'label': f'{l}L (x{loss_counts[l]})'} for l in sorted(loss_counts.keys())]
    win_streak_data = [{'streak': f'{w}W', 'length': w, 'count': win_counts[w], 'label': f'{w}W (x{win_counts[w]})'} for w in sorted(win_counts.keys())]
    
    w_sum = sum(wins)
    tot = len(wins)
    return {
        'total_trades': tot,
        'direct_wins': w_sum,
        'direct_losses': tot - w_sum,
        'direct_rate': round(w_sum / tot * 100, 2) if tot > 0 else 0,
        'loss_streaks': loss_streak_data,
        'win_streaks': win_streak_data,
        'trades': trades_list
    }

strategies = {}

# 1. Estratégia Seguidor de Cor (Trend 50s) & Reversão (50s)
def build_single_candle_strategy(mode="TREND", duration=50):
    trades_list = []
    wins = []
    
    for i in range(1, len(all_candles)):
        prev_c = all_candles[i - 1]
        curr_c = all_candles[i]
        
        if prev_c['color'] == "VERDE":
            prev_dir = "🟢 Verde"
            contract_type = "RISE" if mode == "TREND" else "FALL"
        elif prev_c['color'] == "VERMELHO":
            prev_dir = "🔴 Vermelho"
            contract_type = "FALL" if mode == "TREND" else "RISE"
        else:
            continue
            
        entry_price = curr_c['open']
        idx_exit = np.searchsorted(epochs, curr_c['time'] + duration)
        if idx_exit >= len(epochs):
            continue
            
        exit_price = prices[idx_exit]
        
        if contract_type == "RISE":
            win = 1 if exit_price > entry_price else 0
        else:
            win = 1 if exit_price < entry_price else 0
            
        wins.append(win)
        trades_list.append({
            'time': curr_c['dt'],
            'prev_dir': prev_dir,
            'contract': contract_type,
            'entry': round(float(entry_price), 2),
            'exit': round(float(exit_price), 2),
            'delta': round(float(exit_price - entry_price), 2),
            'result': "WIN" if win == 1 else "LOSS",
            'win': win
        })
    return format_strategy_result(wins, trades_list)

print("Processando Seguidor de Cor M1 (50s)...")
strategies["TREND_50S"] = build_single_candle_strategy(mode="TREND", duration=50)

print("Processando Reversão de Cor M1 (50s)...")
strategies["REVERSAL_50S"] = build_single_candle_strategy(mode="REVERSAL", duration=50)

# 2. Estratégia do Milhão (M5 - Blocos de 5 minutos)
def build_milhao_strategy(mode="MINORIA", block_size=5, duration=50, is_rolling=False):
    trades_list = []
    wins = []
    
    step = 1 if is_rolling else block_size
    start_range = block_size if is_rolling else 0
    end_range = len(all_candles) - (1 if is_rolling else block_size)
    
    for i in range(start_range, end_range + 1, step):
        if is_rolling:
            block = all_candles[i - block_size : i]
            next_c = all_candles[i]
        else:
            block = all_candles[i : i + block_size]
            if i + block_size >= len(all_candles):
                break
            next_c = all_candles[i + block_size]
            
        greens = sum(1 for c in block if c['color'] == "VERDE")
        reds = sum(1 for c in block if c['color'] == "VERMELHO")
        
        if mode == "MINORIA":
            if greens < reds:
                contract_type = "RISE"
                target_desc = f"{greens}V / {reds}R (Minoria: 🟢)"
            elif reds < greens:
                contract_type = "FALL"
                target_desc = f"{greens}V / {reds}R (Minoria: 🔴)"
            else:
                continue # Empate
        else: # MAIORIA
            if greens > reds:
                contract_type = "RISE"
                target_desc = f"{greens}V / {reds}R (Maioria: 🟢)"
            elif reds > greens:
                contract_type = "FALL"
                target_desc = f"{greens}V / {reds}R (Maioria: 🔴)"
            else:
                continue # Empate
                
        entry_price = next_c['open']
        idx_exit = np.searchsorted(epochs, next_c['time'] + duration)
        if idx_exit >= len(epochs):
            continue
            
        exit_price = prices[idx_exit]
        
        if contract_type == "RISE":
            win = 1 if exit_price > entry_price else 0
        else:
            win = 1 if exit_price < entry_price else 0
            
        wins.append(win)
        trades_list.append({
            'time': next_c['dt'],
            'prev_dir': target_desc,
            'contract': contract_type,
            'entry': round(float(entry_price), 2),
            'exit': round(float(exit_price), 2),
            'delta': round(float(exit_price - entry_price), 2),
            'result': "WIN" if win == 1 else "LOSS",
            'win': win
        })
    return format_strategy_result(wins, trades_list)

print("Processando Milhão Minoria M5 (Blocos 5 min)...")
strategies["MILHAO_MINORIA_M5"] = build_milhao_strategy(mode="MINORIA", block_size=5, duration=50, is_rolling=False)

print("Processando Milhão Maioria M5 (Blocos 5 min)...")
strategies["MILHAO_MAIORIA_M5"] = build_milhao_strategy(mode="MAIORIA", block_size=5, duration=50, is_rolling=False)

print("Processando Milhão Minoria Móvel (5 velas contínuas)...")
strategies["MILHAO_MINORIA_MOVEL"] = build_milhao_strategy(mode="MINORIA", block_size=5, duration=50, is_rolling=True)

print("Processando Milhão Maioria Móvel (5 velas contínuas)...")
strategies["MILHAO_MAIORIA_MOVEL"] = build_milhao_strategy(mode="MAIORIA", block_size=5, duration=50, is_rolling=True)

# 3. Estratégia Anterior (Rise Fixo 15s GMT)
trades_15_list = []
wins_15s = []
for c in all_candles:
    idx_entry = np.searchsorted(epochs, c['time'])
    idx_exit = np.searchsorted(epochs, c['time'] + 15)
    if idx_entry >= len(epochs) or idx_exit >= len(epochs):
        continue
    entry_p = prices[idx_entry]
    exit_p = prices[idx_exit]
    win = 1 if exit_p > entry_p else 0
    wins_15s.append(win)
    trades_15_list.append({
        'time': c['dt'],
        'prev_dir': '-',
        'contract': 'RISE',
        'entry': round(float(entry_p), 2),
        'exit': round(float(exit_p), 2),
        'delta': round(float(exit_p - entry_p), 2),
        'result': "WIN" if win == 1 else "LOSS",
        'win': win
    })

strategies["RISE_15S"] = format_strategy_result(wins_15s, trades_15_list)

full_data = {
    'symbol': 'R_100',
    'date': '2026-11-21 GMT (Relógio Oficial Deriv)',
    'timezone': 'GMT (UTC+0)',
    'strategies': strategies
}

with open('data/backtest_result.json', 'w', encoding='utf-8') as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)

print("\n[OK] Sucesso! data/backtest_result.json atualizado com todas as estratégias do Milhão!")
for k, s in strategies.items():
    print(f"-> {k}: {s['total_trades']} trades | Wins: {s['direct_wins']} | Losses: {s['direct_losses']} | Assertividade: {s['direct_rate']}%")
