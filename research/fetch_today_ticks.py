import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import asyncio
from datetime import datetime, timezone
import pandas as pd
import websockets

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DERIV_PUBLIC_WS = "wss://api.derivws.com/trading/v1/options/ws/public"

async def fetch_today_ticks(symbol: str = "R_100"):
    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
    start_epoch = int(today_start.timestamp())
    end_epoch = int(now_utc.timestamp())
    
    today_str = today_start.strftime("%Y-%m-%d")
    output_csv = os.path.join(DATA_DIR, f"ticks_{symbol}_{today_str}.csv")
    
    print(f"[*] Solicitando ticks para hoje {today_str} ({symbol})...")
    print(f"    De: {today_start.strftime('%Y-%m-%d %H:%M:%S GMT')} (Epoch {start_epoch})")
    print(f"    Até: {now_utc.strftime('%Y-%m-%d %H:%M:%S GMT')} (Epoch {end_epoch})")
    
    all_times = []
    all_prices = []
    curr_end = "latest"
    batch = 0
    
    async with websockets.connect(DERIV_PUBLIC_WS) as ws:
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
            dt_old = datetime.fromtimestamp(oldest, timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
            print(f"  -> Lote {batch}: {len(times)} ticks recebidos | Mais antigo: {dt_old}")
            
            if oldest <= start_epoch:
                print(f"[✓] Atingiu o início do dia UTC ({today_str} 00:00:00 GMT).")
                break
                
            curr_end = oldest - 1
            
    df = pd.DataFrame({"epoch": all_times, "price": all_prices})
    df = df.drop_duplicates(subset=["epoch"]).sort_values(by="epoch")
    df = df[(df["epoch"] >= start_epoch) & (df["epoch"] <= end_epoch)].copy()
    df["datetime"] = pd.to_datetime(df["epoch"], unit="s", utc=True)
    
    print(f"[*] Total de {len(df):,} ticks válidos coletados para hoje ({today_str}).")
    df.to_csv(output_csv, index=False)
    print(f"[✓] Ticks salvos com sucesso em: {output_csv}")
    
    if len(df) > 0:
        dt_min = df["datetime"].min().strftime("%Y-%m-%d %H:%M:%S GMT")
        dt_max = df["datetime"].max().strftime("%Y-%m-%d %H:%M:%S GMT")
        print(f"    Cobertura dos ticks: {dt_min} até {dt_max}")
        print(f"    Preço Inicial: {df['price'].iloc[0]:.2f} | Preço Atual: {df['price'].iloc[-1]:.2f}")
    
    return df

if __name__ == "__main__":
    asyncio.run(fetch_today_ticks("R_100"))
