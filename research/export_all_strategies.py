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

strategies = {}

# 1. Estratégia Nova: Seguidor de Cor (Trend Follower) 50s
def build_candle_strategy(mode="TREND", duration=50):
    trades_list = []
    wins = []
    
    # Começa em 00:01:00 GMT (aguarda o primeiro candle 00:00:00 fechar)
    for candle_open in range(day_start_gmt + 60, day_end_gmt, 60):
        prev_open_target = candle_open - 60
        idx_prev_open = np.searchsorted(epochs, prev_open_target)
        idx_prev_close = np.searchsorted(epochs, candle_open)
        
        if idx_prev_open >= len(epochs) or idx_prev_close >= len(epochs):
            continue
            
        p_prev_open = prices[idx_prev_open]
        p_prev_close = prices[idx_prev_close]
        
        if p_prev_close > p_prev_open:
            prev_dir = "VERDE"
            contract_type = "RISE" if mode == "TREND" else "FALL"
        elif p_prev_close < p_prev_open:
            prev_dir = "VERMELHO"
            contract_type = "FALL" if mode == "TREND" else "RISE"
        else:
            continue
            
        entry_price = prices[idx_prev_close]
        idx_exit = np.searchsorted(epochs, candle_open + duration)
        if idx_exit >= len(epochs):
            continue
            
        exit_price = prices[idx_exit]
        
        if contract_type == "RISE":
            win = 1 if exit_price > entry_price else 0
        else:
            win = 1 if exit_price < entry_price else 0
            
        wins.append(win)
        candle_dt = datetime.fromtimestamp(candle_open, timezone.utc)
        trades_list.append({
            'time': candle_dt.strftime('%H:%M:%S'),
            'prev_dir': prev_dir,
            'contract': contract_type,
            'entry': round(float(entry_price), 2),
            'exit': round(float(exit_price), 2),
            'delta': round(float(exit_price - entry_price), 2),
            'result': "WIN" if win == 1 else "LOSS",
            'win': win
        })
        
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
        'direct_rate': round(w_sum / tot * 100, 2),
        'loss_streaks': loss_streak_data,
        'win_streaks': win_streak_data,
        'trades': trades_list
    }

print("Processando Seguidor de Cor (Trend 50s GMT)...")
strategies["TREND_50S"] = build_candle_strategy(mode="TREND", duration=50)

print("Processando Reversão de Cor (Contra 50s GMT)...")
strategies["REVERSAL_50S"] = build_candle_strategy(mode="REVERSAL", duration=50)

# 2. Estratégia Anterior (Rise Fixo 15s GMT)
trades_15_list = []
wins_15s = []
for candle_open in range(day_start_gmt, day_end_gmt, 60):
    idx_entry = np.searchsorted(epochs, candle_open)
    idx_exit = np.searchsorted(epochs, candle_open + 15)
    if idx_entry >= len(epochs) or idx_exit >= len(epochs):
        continue
    entry_p = prices[idx_entry]
    exit_p = prices[idx_exit]
    win = 1 if exit_p > entry_p else 0
    wins_15s.append(win)
    candle_dt = datetime.fromtimestamp(candle_open, timezone.utc)
    trades_15_list.append({
        'time': candle_dt.strftime('%H:%M:%S'),
        'prev_dir': '-',
        'contract': 'RISE',
        'entry': round(float(entry_p), 2),
        'exit': round(float(exit_p), 2),
        'delta': round(float(exit_p - entry_p), 2),
        'result': "WIN" if win == 1 else "LOSS",
        'win': win
    })

streaks_15 = [(k, len(list(g))) for k, g in groupby(wins_15s)]
loss_15 = Counter([length for k, length in streaks_15 if k == 0])
win_15 = Counter([length for k, length in streaks_15 if k == 1])

strategies["RISE_15S"] = {
    'total_trades': len(trades_15_list),
    'direct_wins': sum(wins_15s),
    'direct_losses': len(wins_15s) - sum(wins_15s),
    'direct_rate': round(sum(wins_15s) / len(wins_15s) * 100, 2),
    'loss_streaks': [{'streak': f'{l}L', 'length': l, 'count': loss_15[l], 'label': f'{l}L (x{loss_15[l]})'} for l in sorted(loss_15.keys())],
    'win_streaks': [{'streak': f'{w}W', 'length': w, 'count': win_15[w], 'label': f'{w}W (x{win_15[w]})'} for w in sorted(win_15.keys())],
    'trades': trades_15_list
}

full_data = {
    'symbol': 'R_100',
    'date': '2026-11-21 GMT (Relógio Oficial Deriv)',
    'timezone': 'GMT (UTC+0)',
    'strategies': strategies
}

with open('data/backtest_result.json', 'w', encoding='utf-8') as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)

print("Sucesso! Exportado data/backtest_result.json 100% alinhado ao GMT da Deriv!")
print(f"Primeiro Trade Seguidor: {strategies['TREND_50S']['trades'][0]}")
