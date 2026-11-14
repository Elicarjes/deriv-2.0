import asyncio
import json
import urllib.request
import websockets
from config import BotConfig

cfg = BotConfig()
headers = {
    "Authorization": f"Bearer {cfg.token}",
    "Deriv-App-ID": str(cfg.app_id),
    "User-Agent": "Mozilla/5.0"
}

otp_req = urllib.request.Request(f"{cfg.rest_base_url}/trading/v1/options/accounts/{cfg.account_id}/otp", headers=headers, method="POST")
with urllib.request.urlopen(otp_req) as resp:
    ws_url = json.loads(resp.read().decode("utf-8"))["data"]["url"]

async def check():
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"portfolio": 1}))
        r = json.loads(await ws.recv())
        contracts = r.get("portfolio", {}).get("contracts", [])
        print("Contratos abertos:", len(contracts))
        for c in contracts:
            cid = c.get("contract_id")
            ctype = c.get("contract_type")
            print(f"Fechando contrato {cid} ({ctype})...")
            await ws.send(json.dumps({"sell": cid, "price": 0}))
            res = json.loads(await ws.recv())
            print("Sell:", res)

if __name__ == "__main__":
    asyncio.run(check())
