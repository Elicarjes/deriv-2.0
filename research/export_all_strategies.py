import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from itertools import groupby
from collections import Counter
from datetime import datetime, timezone

from research.db_manager import get_rolling_window_candles, get_historical_records

# 1. Carregar candles da janela móvel (4 dias fechados + dia em andamento)
all_candles, window_info = get_rolling_window_candles(symbol="R_100", days_closed=4)
print(f"Total de velas M1 na janela de backtest: {len(all_candles)} (de {window_info['start_time']} até {window_info['end_time']})")
print(f"Dias presentes: {', '.join(window_info['days_list'])}")

# Obter recordes históricos permanentes do banco SQLite
historical_records = get_historical_records(symbol="R_100")
print(f"Recordes históricos carregados do DB: {historical_records['total_streaks']} streaks >= 6 velas.")

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

# 1. Seguidor de Cor (Trend) & Reversão Simples
def build_single_candle_strategy(mode="TREND"):
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
        exit_price = curr_c['close']
        
        if contract_type == "RISE":
            win = 1 if exit_price > entry_price else 0
        else:
            win = 1 if exit_price < entry_price else 0
            
        wins.append(win)
        day_str = curr_c['dt_utc'].split()[0]
        trades_list.append({
            'time': curr_c['dt_utc'].replace(" GMT", ""),
            'day': day_str,
            'prev_dir': prev_dir,
            'contract': contract_type,
            'entry': round(float(entry_price), 2),
            'exit': round(float(exit_price), 2),
            'delta': round(float(exit_price - entry_price), 2),
            'result': "WIN" if win == 1 else "LOSS",
            'win': win
        })
    return format_strategy_result(wins, trades_list)

print("Processando Seguidor de Cor M1...")
strategies["TREND_50S"] = build_single_candle_strategy(mode="TREND")
print("Processando Reversão de Cor M1...")
strategies["REVERSAL_50S"] = build_single_candle_strategy(mode="REVERSAL")

# 2. Estratégia do Milhão (M5 - Blocos de 5 minutos e Móvel)
def build_milhao_strategy(mode="MINORIA", block_size=5, is_rolling=False):
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
                continue
        else:
            if greens > reds:
                contract_type = "RISE"
                target_desc = f"{greens}V / {reds}R (Maioria: 🟢)"
            elif reds > greens:
                contract_type = "FALL"
                target_desc = f"{greens}V / {reds}R (Maioria: 🔴)"
            else:
                continue
                
        entry_price = next_c['open']
        exit_price = next_c['close']
        
        if contract_type == "RISE":
            win = 1 if exit_price > entry_price else 0
        else:
            win = 1 if exit_price < entry_price else 0
            
        wins.append(win)
        day_str = next_c['dt_utc'].split()[0]
        trades_list.append({
            'time': next_c['dt_utc'].replace(" GMT", ""),
            'day': day_str,
            'prev_dir': target_desc,
            'contract': contract_type,
            'entry': round(float(entry_price), 2),
            'exit': round(float(exit_price), 2),
            'delta': round(float(exit_price - entry_price), 2),
            'result': "WIN" if win == 1 else "LOSS",
            'win': win
        })
    return format_strategy_result(wins, trades_list)

print("Processando Milhão Minoria M5...")
strategies["MILHAO_MINORIA_M5"] = build_milhao_strategy(mode="MINORIA", block_size=5, is_rolling=False)
print("Processando Milhão Maioria M5...")
strategies["MILHAO_MAIORIA_M5"] = build_milhao_strategy(mode="MAIORIA", block_size=5, is_rolling=False)
print("Processando Milhão Minoria Móvel...")
strategies["MILHAO_MINORIA_MOVEL"] = build_milhao_strategy(mode="MINORIA", block_size=5, is_rolling=True)
print("Processando Milhão Maioria Móvel...")
strategies["MILHAO_MAIORIA_MOVEL"] = build_milhao_strategy(mode="MAIORIA", block_size=5, is_rolling=True)

# 3. Estratégia de Reversão por Streaks de Cor (Exaustão 6 a 15)
def build_reversal_streak_strategy(N=6, trigger_color="BOTH"):
    trades_list = []
    wins = []
    consec_red = 0
    consec_green = 0
    
    for i in range(len(all_candles)):
        c = all_candles[i]
        signal = None
        desc = ""
        
        if consec_red >= N and trigger_color in ("BOTH", "RED"):
            signal = "RISE"
            desc = f"{consec_red}x 🔴 Vermelhos (Reversão RISE)"
        elif consec_green >= N and trigger_color in ("BOTH", "GREEN"):
            signal = "FALL"
            desc = f"{consec_green}x 🟢 Verdes (Reversão FALL)"
            
        if signal:
            entry_price = c['open']
            exit_price = c['close']
            win = 1 if (signal == "RISE" and exit_price > entry_price) or (signal == "FALL" and exit_price < entry_price) else 0
            wins.append(win)
            day_str = c['dt_utc'].split()[0]
            trades_list.append({
                'time': c['dt_utc'].replace(" GMT", ""),
                'day': day_str,
                'prev_dir': desc,
                'contract': signal,
                'entry': round(float(entry_price), 2),
                'exit': round(float(exit_price), 2),
                'delta': round(float(exit_price - entry_price), 2),
                'result': "WIN" if win == 1 else "LOSS",
                'win': win
            })
            
        # Atualizar contadores
        if c['color'] == 'VERMELHO':
            consec_red += 1
            consec_green = 0
        elif c['color'] == 'VERDE':
            consec_green += 1
            consec_red = 0
        else:
            consec_red = 0
            consec_green = 0
            
    return format_strategy_result(wins, trades_list)

print("Processando Reversões por Streaks de Cores (6 a 15 velas)...")
for n in range(6, 16):
    strategies[f"REV_STREAK_{n}_BOTH"] = build_reversal_streak_strategy(N=n, trigger_color="BOTH")
    strategies[f"REV_STREAK_{n}_RED"] = build_reversal_streak_strategy(N=n, trigger_color="RED")
    strategies[f"REV_STREAK_{n}_GREEN"] = build_reversal_streak_strategy(N=n, trigger_color="GREEN")

# 4. Três Mosqueteiros
def build_tres_mosqueteiros_strategy(mode="TREND", is_strict=False):
    trades_list = []
    wins = []
    i = 2
    while i < len(all_candles):
        c1 = all_candles[i - 2]
        c2 = all_candles[i - 1]
        c3 = all_candles[i]
        
        if c1['color'] in ('VERDE', 'VERMELHO') and c1['color'] == c2['color']:
            base_color = c1['color']
            if mode == "TREND":
                contract = "RISE" if base_color == "VERDE" else "FALL"
                desc = f"2x {base_color}s (3º Mosqueteiro -> {contract})"
            else:
                contract = "FALL" if base_color == "VERDE" else "RISE"
                desc = f"2x {base_color}s (Contra Mosqueteiro -> {contract})"
                
            entry_p = c3['open']
            exit_p = c3['close']
            win = 1 if (contract == "RISE" and exit_p > entry_p) or (contract == "FALL" and exit_p < entry_p) else 0
            wins.append(win)
            day_str = c3['dt_utc'].split()[0]
            trades_list.append({
                'time': c3['dt_utc'].replace(" GMT", ""),
                'day': day_str,
                'prev_dir': desc,
                'contract': contract,
                'entry': round(float(entry_p), 2),
                'exit': round(float(exit_p), 2),
                'delta': round(float(exit_p - entry_p), 2),
                'result': "WIN" if win == 1 else "LOSS",
                'win': win
            })
            i += 3 if is_strict else 1
        else:
            i += 1
            
    return format_strategy_result(wins, trades_list)

print("Processando Três Mosqueteiros...")
strategies["TRES_MOSQUETEIROS"] = build_tres_mosqueteiros_strategy(mode="TREND", is_strict=False)
strategies["CONTRA_MOSQUETEIROS"] = build_tres_mosqueteiros_strategy(mode="REVERSAL", is_strict=False)
strategies["TRES_MOSQUETEIROS_ESTRITO"] = build_tres_mosqueteiros_strategy(mode="TREND", is_strict=True)

# 5. Alternância Contínua
def build_alternancia_strategy(start_with="RISE"):
    trades_list = []
    wins = []
    current_contract = start_with
    
    for i, c in enumerate(all_candles):
        entry_p = c['open']
        exit_p = c['close']
        win = 1 if (current_contract == "RISE" and exit_p > entry_p) or (current_contract == "FALL" and exit_p < entry_p) else 0
        wins.append(win)
        
        next_contract = "FALL" if current_contract == "RISE" else "RISE"
        desc = f"Alternância #{i+1} (Ciclo: {'▲' if current_contract == 'RISE' else '▼'})"
        day_str = c['dt_utc'].split()[0]
        
        trades_list.append({
            'time': c['dt_utc'].replace(" GMT", ""),
            'day': day_str,
            'prev_dir': desc,
            'contract': current_contract,
            'entry': round(float(entry_p), 2),
            'exit': round(float(exit_p), 2),
            'delta': round(float(exit_p - entry_p), 2),
            'result': "WIN" if win == 1 else "LOSS",
            'win': win
        })
        current_contract = next_contract
        
    return format_strategy_result(wins, trades_list)

print("Processando Alternâncias...")
strategies["ALTERNADA_RISE_FALL"] = build_alternancia_strategy(start_with="RISE")
strategies["ALTERNADA_FALL_RISE"] = build_alternancia_strategy(start_with="FALL")

full_data = {
    'symbol': 'R_100',
    'date': f"{window_info['days_list'][0]} até {window_info['days_list'][-1]} ({len(all_candles):,} velas / 5 dias)",
    'timezone': 'GMT (UTC+0)',
    'window_info': window_info,
    'historical_records': historical_records,
    'strategies': strategies
}

output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "backtest_result.json")
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)

print(f"\n[OK] Sucesso! {output_path} gerado com sucesso!")
print(f"Total de estratégias compiladas: {len(strategies)}")
print(f"Recorde Histórico Perpétuo: {historical_records['max_overall']['streak_len']} velas consecutivas [{historical_records['max_overall']['direction']}] em {historical_records['max_overall']['start_time']}")
