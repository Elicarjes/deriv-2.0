import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
from itertools import groupby
from collections import Counter
from datetime import datetime

df_ticks = pd.read_csv('data/ticks_R_100_2026-11-21.csv')
from research.backtest_rise_15s import simulate_rise_orders

durations = [15, 30, 45, 60]
durations_data = {}

for dur in durations:
    df_trades = simulate_rise_orders(df_ticks, duration_seconds=dur)
    wins = df_trades['win'].tolist()
    
    streaks = [(k, len(list(g))) for k, g in groupby(wins)]
    loss_streaks = [length for k, length in streaks if k == 0]
    win_streaks = [length for k, length in streaks if k == 1]
    loss_counts = Counter(loss_streaks)
    win_counts = Counter(win_streaks)
    
    loss_streak_data = [{'streak': f'{l}L', 'length': l, 'count': loss_counts[l], 'label': f'{l}L (x{loss_counts[l]})'} for l in sorted(loss_counts.keys())]
    win_streak_data = [{'streak': f'{w}W', 'length': w, 'count': win_counts[w], 'label': f'{w}W (x{win_counts[w]})'} for w in sorted(win_counts.keys())]
    
    trades_list = []
    for idx, r in df_trades.iterrows():
        trades_list.append({
            'time': r['candle_time'].strftime('%H:%M:%S'),
            'entry': round(float(r['entry_price']), 2),
            'exit': round(float(r['exit_price']), 2),
            'delta': round(float(r['delta']), 2),
            'result': r['result'],
            'win': int(r['win'])
        })
        
    w_sum = int(df_trades['win'].sum())
    total_t = len(df_trades)
    durations_data[str(dur)] = {
        'duration': dur,
        'total_trades': total_t,
        'direct_wins': w_sum,
        'direct_losses': total_t - w_sum,
        'direct_rate': round(w_sum / total_t * 100, 2),
        'loss_streaks': loss_streak_data,
        'win_streaks': win_streak_data,
        'trades': trades_list
    }
    print(f"Duração {dur}s: Total={total_t}, Wins={w_sum}, WinRate={w_sum/total_t*100:.2f}%")

data = {
    'symbol': 'R_100',
    'date': '2026-11-21',
    'durations': durations_data
}

with open('data/backtest_result.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('Salvo com sucesso em data/backtest_result.json com todas as 4 durações!')
