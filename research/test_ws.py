import asyncio
import json
import websockets

async def test():
    # Nova API Deriv (Developers AI Hub / llms.txt)
    url = "wss://api.derivws.com/trading/v1/options/ws/public"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://deriv.com"
    }
    print(f"Testing Nova API Deriv: {url}...")
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            # 1. Ping
            await ws.send(json.dumps({"ping": 1}))
            res = await ws.recv()
            print(f"[✓] Ping response: {res}")

            # 2. Server Time (GMT)
            await ws.send(json.dumps({"time": 1}))
            res_time = await ws.recv()
            print(f"[✓] Deriv GMT Time: {res_time}")

            # 3. Ticks History (Nova API: underlying_symbol / ticks_history)
            await ws.send(json.dumps({
                "ticks_history": "R_100",
                "count": 3,
                "end": "latest",
                "style": "ticks"
            }))
            res_ticks = await ws.recv()
            print(f"[✓] Ticks History: {res_ticks[:120]}...")
            return True
    except Exception as e:
        print(f"[X] Falha na conexão com {url}: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test())
