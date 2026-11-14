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

async def inspect():
    async with websockets.connect(ws_url) as ws:
        # Garante sem posições
        await ws.send(json.dumps({"portfolio": 1}))
        r = json.loads(await ws.recv())
        contracts = r.get("portfolio", {}).get("contracts", [])
        for c in contracts:
            await ws.send(json.dumps({"sell": c["contract_id"], "price": 0}))

        # Proposta
        await ws.send(json.dumps({
            "proposal": 1, "subscribe": 1, "amount": 1.0,
            "basis": "stake", "contract_type": "ACCU",
            "currency": "USD", "underlying_symbol": "R_10", "growth_rate": 0.01
        }))
        prop_id, sub_id = None, None
        while not prop_id:
            m = json.loads(await ws.recv())
            if m.get("msg_type") == "proposal" and "proposal" in m:
                prop_id = m["proposal"]["id"]
                sub_id = m["subscription"]["id"]
        await ws.send(json.dumps({"forget": sub_id}))

        # Compra
        await ws.send(json.dumps({"buy": prop_id, "price": 1.0}))
        cid = None
        while not cid:
            m = json.loads(await ws.recv())
            if m.get("msg_type") == "buy":
                cid = m["buy"]["contract_id"]
                print("Comprou:", cid)

        # Inscreve no proposal_open_contract
        await ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1}))

        # Ouve mensagens
        count = 0
        while count < 6:
            m = json.loads(await ws.recv())
            if m.get("msg_type") == "proposal_open_contract":
                c = m["proposal_open_contract"]
                tick_stream = c.get("tick_stream", [])
                print(f"POC #{count}: profit={c.get('profit')}, is_valid_to_sell={c.get('is_valid_to_sell')}, tick_count={c.get('tick_count')}, len(tick_stream)={len(tick_stream)}")
                count += 1
                await asyncio.sleep(0.5)

        # Vende
        await ws.send(json.dumps({"sell": cid, "price": 0}))
        res = json.loads(await ws.recv())
        print("Sell:", res)

if __name__ == "__main__":
    asyncio.run(inspect())
