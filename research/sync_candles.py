import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
import websockets
from datetime import datetime, timezone
from research.db_manager import init_db, save_candles, detect_and_save_streaks, get_historical_records, get_rolling_window_candles

DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"

async def sync_candles_from_deriv(symbol: str = "R_100", target_candles: int = 8000):
    print(f"[*] Iniciando sincronização de candles M1 para {symbol} da Deriv API...")
    init_db()
    
    all_candles = []
    curr_end = "latest"
    batch = 0
    
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
        while len(all_candles) < target_candles and batch < 6:
            batch += 1
            req = {
                "ticks_history": symbol,
                "count": 2000,
                "end": curr_end,
                "style": "candles",
                "granularity": 60,
                "req_id": batch
            }
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            
            if "error" in res:
                print(f"[!] Erro retornado pela Deriv: {res['error']['message']}")
                break
                
            candles = res.get("candles", [])
            if not candles:
                print("[!] Nenhum candle adicional retornado.")
                break
                
            all_candles = candles + all_candles
            oldest = candles[0]["epoch"]
            dt_old = datetime.fromtimestamp(oldest, timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
            print(f"  -> Lote {batch}: {len(candles)} candles recebidos | Mais antigo: {dt_old}")
            
            curr_end = oldest - 60
            
    print(f"[*] Total de {len(all_candles)} candles baixados. Salvando no banco de dados permanente SQLite...")
    inserted = save_candles(symbol, all_candles)
    print(f"[✓] {inserted} novos candles persistidos no banco de dados.")
    
    print("[*] Detectando e catalogando sequências históricas >= 6 velas consecutivas...")
    streaks_count = detect_and_save_streaks(symbol, min_streak=6)
    print(f"[✓] Streaks >= 6 velas processados e salvos no banco perpétuo.")
    
    records = get_historical_records(symbol)
    print("\n" + "="*60)
    print("🏆 RECORDES HISTÓRICOS DE STREAKS (BANCO DE DADOS PERMANENTE)")
    print("="*60)
    if records["max_overall"]:
        mo = records["max_overall"]
        print(f"🔥 MAIOR STREAK DA HISTÓRIA: {mo['streak_len']} VELAS CONSECUTIVAS [{mo['direction']}]")
        print(f"   Início:  {mo['start_time']}")
        print(f"   Término: {mo['end_time']}")
        print(f"   Preços:  Entrada: {mo['open_price']} -> Saída: {mo['close_price']}")
        
    if records["max_green"]:
        mg = records["max_green"]
        print(f"🟢 Maior Streak Verde:     {mg['streak_len']} velas ({mg['start_time']} até {mg['end_time']})")
    if records["max_red"]:
        mr = records["max_red"]
        print(f"🔴 Maior Streak Vermelho:  {mr['streak_len']} velas ({mr['start_time']} até {mr['end_time']})")
        
    print(f"📊 Total de Streaks >= 6 velas catalogados: {records['total_streaks']}")
    print(f"📈 Distribuição de Frequência: {records['distribution']}")
    print("="*60 + "\n")
    
    # Valida janela de 4 dias fechados + hoje em andamento
    w_candles, w_info = get_rolling_window_candles(symbol, days_closed=4)
    print(f"[*] Janela Ativa de Backtest (4 dias fechados + dia atual em andamento):")
    print(f"   De: {w_info['start_time']} até {w_info['end_time']}")
    print(f"   Total de velas na janela ativa: {w_info['total_candles']}")
    print(f"   Dias presentes: {', '.join(w_info['days_list'])}")
    print(f"   Dia em andamento: {w_info['current_day']}")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(sync_candles_from_deriv("R_100", target_candles=8000))
