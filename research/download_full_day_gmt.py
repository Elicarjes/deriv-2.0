import os
import sys
import asyncio
import json
import websockets
import pandas as pd
from datetime import datetime, timezone

DERIV_WS = "wss://api.derivws.com/trading/v1/options/ws/public"

async def download_day_gmt():
    # 2026-11-21 00:00:00 GMT = 1795219200
    # Include 1 minute before (23:59:00 GMT = 1795219140) to have previous candle for 00:00
    start_gmt = 1795219140
    # 2026-11-22 00:00:00 GMT = 1795305600
    end_gmt = 1795305600

    print(f"[*] Baixando ticks exatos da Deriv em GMT: {start_gmt} até {end_gmt}...")

    all_times = []
    all_prices = []
    curr_start = start_gmt

    async with websockets.connect(DERIV_WS) as ws:
        batch = 0
        while curr_start < end_gmt:
            batch += 1
            # Batch up to 2000 ticks = 4000s
            batch_end = min(curr_start + 4000, end_gmt)
            req = {
                "ticks_history": "R_100",
                "start": curr_start,
                "end": batch_end,
                "style": "ticks"
            }
            await ws.send(json.dumps(req))
            res = json.loads(await ws.recv())
            h = res.get("history", {})
            times = h.get("times", [])
            prices = h.get("prices", [])

            if not times:
                print(f"[!] Fim dos dados no lote {batch}")
                break

            all_times.extend(times)
            all_prices.extend(prices)

            first_dt = datetime.fromtimestamp(times[0], timezone.utc).strftime("%H:%M:%S")
            last_dt = datetime.fromtimestamp(times[-1], timezone.utc).strftime("%H:%M:%S")
            print(f"  -> Lote {batch}: {len(times)} ticks | {first_dt} até {last_dt} GMT")

            curr_start = times[-1] + 1

    df = pd.DataFrame({"epoch": all_times, "price": all_prices})
    df.drop_duplicates(subset=["epoch"], inplace=True)
    df.sort_values(by="epoch", inplace=True)
    df.reset_index(drop=True, inplace=True)

    cache_file = os.path.join("data", "ticks_R_100_2026-11-21.csv")
    df.to_csv(cache_file, index=False)
    print(f"[OK] Total de ticks salvos: {len(df)}. De {datetime.fromtimestamp(df['epoch'].min(), timezone.utc)} até {datetime.fromtimestamp(df['epoch'].max(), timezone.utc)} GMT!")

if __name__ == "__main__":
    asyncio.run(download_day_gmt())
