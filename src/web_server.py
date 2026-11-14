"""
Servidor Web FastAPI Event-Driven e Reativo (Zero Polling).
Recursos:
1. Subscrição nativa de Saldo na Deriv (balance: 1, subscribe: 1) sem polling.
2. WebSocket Pub/Sub: Notificações instantâneas baseadas em eventos para o navegador.
3. Layout visual ultra-estável (sem layout shift).
"""

import asyncio
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import urllib.request

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import websockets

from config import BotConfig
from risk_manager import RiskManager
from asset_selector import find_safest_asset

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WebServer")

app = FastAPI(title="Deriv Quant Dashboard")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


class DashboardState:
    def __init__(self, config: BotConfig):
        self.config = config
        self.risk = RiskManager(config)
        self.is_running = False
        self.status_message = "Parado"
        self.account_id = config.account_id or "DOT..."
        self.account_balance = 0.0

        self.active_symbol = config.symbol
        self.active_asset_name = "Volatility 10"
        self.active_asset_rate = 99.0

        # Live Trade
        self.in_trade = False
        self.current_contract_id: Optional[int] = None
        self.current_ticks = 0
        self.current_profit = 0.0

        self.recent_trades: List[Dict[str, Any]] = []
        self.latest_log = "Sistema pronto. Subscrição de saldo ativa."
        self.bot_task: Optional[asyncio.Task] = None

        # Gerenciamento de conexões WebSocket do frontend (Event-Driven)
        self.connected_websockets: Set[WebSocket] = set()

    def to_dict(self) -> Dict[str, Any]:
        win_rate = (self.risk.wins / self.risk.total_trades * 100) if self.risk.total_trades > 0 else 0.0
        return {
            "is_running": self.is_running,
            "status_message": self.status_message,
            "account_id": self.account_id,
            "account_balance": self.account_balance,
            "daily_pnl": self.risk.daily_pnl,
            "tp_target": self.config.daily_take_profit_usd,
            "sl_target": self.config.daily_stop_loss_usd,
            "win_rate": win_rate,
            "wins": self.risk.wins,
            "losses": self.risk.losses,
            "total_trades": self.risk.total_trades,
            "active_symbol": self.active_symbol,
            "active_asset_name": self.active_asset_name,
            "active_asset_rate": self.active_asset_rate,
            "in_trade": self.in_trade,
            "current_contract_id": self.current_contract_id,
            "current_ticks": self.current_ticks,
            "exit_ticks": self.config.exit_ticks,
            "current_profit": self.current_profit,
            "recent_trades": self.recent_trades[:15],
            "latest_log": self.latest_log
        }

    async def notify_clients(self):
        """Envia atualização instantânea para todos os clientes conectados sem polling."""
        if not self.connected_websockets:
            return
        payload = self.to_dict()
        disconnected = set()
        for ws in self.connected_websockets:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.add(ws)
        self.connected_websockets -= disconnected


cfg = BotConfig()
state = DashboardState(cfg)


def fetch_initial_balance():
    """Busca o saldo inicial da conta via REST para exibir na inicialização."""
    try:
        headers = {
            "Authorization": f"Bearer {cfg.token}",
            "Deriv-App-ID": str(cfg.app_id),
            "User-Agent": "Mozilla/5.0"
        }
        url = f"{cfg.rest_base_url}/trading/v1/options/accounts"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            for acc in data.get("data", []):
                if acc.get("account_id") == cfg.account_id:
                    state.account_balance = float(acc.get("balance", 0.0))
                    state.account_id = acc.get("account_id")
                    logger.info(f"Saldo inicial carregado: ${state.account_balance:.2f} USD")
                    break
    except Exception as e:
        logger.warning(f"Erro ao obter saldo inicial: {e}")


fetch_initial_balance()


class BotRunner:
    def __init__(self, dashboard_state: DashboardState):
        self.st = dashboard_state

    def get_otp_url(self) -> str:
        headers = {
            "Authorization": f"Bearer {self.st.config.token}",
            "Deriv-App-ID": str(self.st.config.app_id),
            "User-Agent": "Mozilla/5.0"
        }
        otp_url = f"{self.st.config.rest_base_url}/trading/v1/options/accounts/{self.st.config.account_id}/otp"
        req = urllib.request.Request(otp_url, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["data"]["url"]

    async def heartbeat(self, ws):
        try:
            while self.st.is_running:
                await asyncio.sleep(20)
                try:
                    await ws.send(json.dumps({"ping": 1}))
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def listen_messages(self, ws):
        """Ouve todas as mensagens em background (saldo nativo, ticks, confirmações)."""
        try:
            async for raw in ws:
                msg = json.loads(raw)
                msg_type = msg.get("msg_type")

                # Subscrição nativa de Saldo da Deriv (Zero Polling)
                if msg_type == "balance" and "balance" in msg:
                    bal = float(msg["balance"].get("balance", self.st.account_balance))
                    if bal != self.st.account_balance:
                        self.st.account_balance = bal
                        logger.info(f"💵 Saldo atualizado em tempo real via Stream Deriv: ${bal:.2f} USD")
                        await self.st.notify_clients()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Stream listener finalizado: {e}")

    async def run_loop(self):
        self.st.is_running = True
        self.st.status_message = "Ativo"
        self.st.latest_log = "Escaneando o ativo mais seguro do momento..."
        await self.st.notify_clients()

        winner = await find_safest_asset(
            public_ws_url=self.st.config.public_ws_url,
            target_ticks=self.st.config.exit_ticks,
            growth_rate=self.st.config.growth_rate
        )
        self.st.active_symbol = winner["symbol"]
        self.st.active_asset_name = winner["name"]
        self.st.active_asset_rate = winner["survived_target_pct"]
        self.st.latest_log = f"Ativo campeão selecionado: {winner['name']} ({winner['survived_target_pct']:.1f}% em 2T)"
        await self.st.notify_clients()

        trade_count_scan = 0

        while self.st.is_running and self.st.risk.can_trade():
            try:
                otp_url = self.get_otp_url()

                async with websockets.connect(otp_url, ping_interval=None) as ws:
                    hb_task = asyncio.create_task(self.heartbeat(ws))

                    # 1. Subscreve ao Saldo Nativo da Deriv em tempo real (Stream Push oficial)
                    await ws.send(json.dumps({"balance": 1, "subscribe": 1, "req_id": 1}))

                    while self.st.is_running and self.st.risk.can_trade():
                        # Garante que não há posições abertas órfãs
                        await ws.send(json.dumps({"portfolio": 1, "req_id": 2}))
                        r = json.loads(await ws.recv())
                        if r.get("msg_type") == "portfolio" and r.get("portfolio", {}).get("contracts"):
                            await asyncio.sleep(2)
                            continue

                        # Proposta
                        prop_req = {
                            "proposal": 1, "subscribe": 1,
                            "amount": self.st.config.stake_amount,
                            "basis": "stake", "contract_type": "ACCU",
                            "currency": "USD", "underlying_symbol": self.st.active_symbol,
                            "growth_rate": self.st.config.growth_rate,
                            "req_id": 10
                        }
                        await ws.send(json.dumps(prop_req))

                        prop_id, sub_id = None, None
                        while not prop_id and self.st.is_running:
                            m = json.loads(await ws.recv())
                            # Trata se vier atualização de saldo no meio
                            if m.get("msg_type") == "balance":
                                self.st.account_balance = float(m["balance"].get("balance", self.st.account_balance))
                                await self.st.notify_clients()
                            elif m.get("msg_type") == "proposal" and "proposal" in m:
                                prop_id = m["proposal"]["id"]
                                sub_id = m.get("subscription", {}).get("id")
                                break
                            elif "error" in m:
                                await asyncio.sleep(3)
                                break

                        if not prop_id:
                            continue

                        if sub_id:
                            await ws.send(json.dumps({"forget": sub_id}))

                        # Compra
                        await ws.send(json.dumps({"buy": prop_id, "price": self.st.config.stake_amount, "req_id": 20}))
                        
                        cid = None
                        while not cid and self.st.is_running:
                            m = json.loads(await ws.recv())
                            if m.get("msg_type") == "balance":
                                self.st.account_balance = float(m["balance"].get("balance", self.st.account_balance))
                                await self.st.notify_clients()
                            elif m.get("msg_type") == "buy" and "buy" in m:
                                cid = m["buy"]["contract_id"]
                                self.st.current_contract_id = cid
                                self.st.in_trade = True
                                self.st.current_ticks = 0
                                self.st.current_profit = 0.0
                                self.st.latest_log = f"Ordem aberta: Contrato #{cid} ({self.st.active_asset_name})"
                                await self.st.notify_clients()
                                break
                            elif "error" in m:
                                break

                        if not cid:
                            continue

                        # Monitora proposal_open_contract
                        await ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1, "req_id": 30}))
                        poc_sub = None
                        trade_done = False

                        while not trade_done and self.st.is_running:
                            m = json.loads(await ws.recv())
                            if m.get("msg_type") == "balance":
                                self.st.account_balance = float(m["balance"].get("balance", self.st.account_balance))
                                await self.st.notify_clients()
                                continue

                            if m.get("msg_type") != "proposal_open_contract":
                                continue
                            
                            c = m.get("proposal_open_contract", {})
                            poc_sub = m.get("subscription", {}).get("id")

                            # A Deriv retorna o total de ticks passados dentro de 'tick_stream'
                            tick_stream = c.get("tick_stream", [])
                            self.st.current_ticks = len(tick_stream)
                            self.st.current_profit = float(c.get("profit", 0.0))
                            is_valid_to_sell = c.get("is_valid_to_sell", 0)
                            is_sold = c.get("is_sold", 0)

                            await self.st.notify_clients()

                            if is_sold:
                                p_final = float(c.get("profit", 0.0))
                                self.st.risk.register_trade(p_final)
                                self._record_trade(p_final)
                                trade_done = True
                                break

                            # Cash Out estrito no 5º tick (ou exit_ticks configurado)
                            if self.st.current_ticks >= self.st.config.exit_ticks and is_valid_to_sell:
                                self.st.latest_log = f"Alvo de {self.st.config.exit_ticks} ticks atingido! Disparando Cash Out..."
                                await self.st.notify_clients()
                                await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 40}))
                                
                                while True:
                                    sm = json.loads(await ws.recv())
                                    if sm.get("msg_type") == "balance":
                                        self.st.account_balance = float(sm["balance"].get("balance", self.st.account_balance))
                                        await self.st.notify_clients()
                                    elif sm.get("msg_type") == "sell":
                                        sold_for = float(sm["sell"]["sold_for"])
                                        net = sold_for - self.st.config.stake_amount
                                        self.st.risk.register_trade(net)
                                        self._record_trade(net)
                                        self.st.latest_log = f"CASH OUT: +${net:.2f} no {self.st.current_ticks}º tick"
                                        trade_done = True
                                        break
                                    elif "error" in sm:
                                        break

                        if poc_sub:
                            await ws.send(json.dumps({"forget": poc_sub}))

                        self.st.in_trade = False
                        trade_count_scan += 1
                        await self.st.notify_clients()

                        # Reavaliação a cada 5 trades
                        if trade_count_scan >= 5:
                            w = await find_safest_asset(self.st.config.public_ws_url, self.st.config.exit_ticks, self.st.config.growth_rate)
                            self.st.active_symbol = w["symbol"]
                            self.st.active_asset_name = w["name"]
                            self.st.active_asset_rate = w["survived_target_pct"]
                            trade_count_scan = 0
                            await self.st.notify_clients()

                        if self.st.risk.can_trade() and self.st.is_running:
                            await asyncio.sleep(5)

                    hb_task.cancel()

            except Exception as e:
                self.st.latest_log = f"Aviso de conexão: {e}. Reconectando..."
                await self.st.notify_clients()
                await asyncio.sleep(5)

        self.st.is_running = False
        if not self.st.risk.can_trade():
            self.st.status_message = "Meta/Stop Batido"
            self.st.latest_log = f"FIM DE SESSÃO: {self.st.risk.stop_reason}"
        else:
            self.st.status_message = "Parado"
        await self.st.notify_clients()

    def _record_trade(self, profit: float):
        now = datetime.now().strftime("%H:%M:%S")
        self.st.recent_trades.insert(0, {
            "time": now,
            "symbol": self.st.active_asset_name,
            "stake": self.st.config.stake_amount,
            "profit": profit
        })


runner = BotRunner(state)


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = WEB_DIR / "index.html"
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


@app.get("/api/status")
async def get_status():
    return JSONResponse(content=state.to_dict())


@app.post("/api/start")
async def start_bot():
    if state.is_running:
        return {"status": "already_running", "message": "O robô já está em execução."}
    state.is_running = True
    state.status_message = "Ativo"
    state.bot_task = asyncio.create_task(runner.run_loop())
    await state.notify_clients()
    return {"status": "started", "message": "Robô iniciado com sucesso!"}


@app.post("/api/stop")
async def stop_bot():
    if not state.is_running:
        return {"status": "already_stopped", "message": "O robô já está pausado."}
    state.is_running = False
    state.status_message = "Parado"
    state.latest_log = "Parada solicitada pelo usuário."
    if state.bot_task and not state.bot_task.done():
        state.bot_task.cancel()
    await state.notify_clients()
    return {"status": "stopped", "message": "Robô pausado com sucesso!"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.connected_websockets.add(ws)
    # Envia estado inicial imediato
    await ws.send_json(state.to_dict())
    try:
        while True:
            # Mantém conexão viva aguardando mensagens (se houver) sem polling
            await ws.receive_text()
    except WebSocketDisconnect:
        state.connected_websockets.discard(ws)


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" INICIANDO DASHBOARD DERIV QUANT 2.0 (EVENT-DRIVEN)")
    print(" Acesse no seu navegador: http://localhost:8000")
    print("=" * 70 + "\n")
    uvicorn.run("web_server:app", host="0.0.0.0", port=8000, reload=False, app_dir="src")
