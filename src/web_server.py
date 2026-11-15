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
from pydantic import BaseModel
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
        self.account_type = "Demo" if ("DOT" in self.account_id or "demo" in self.account_id.lower()) else "Real"
        self.rate_limit_status = "OK • Teto 360 req/min"
        self.is_rate_limited = False
        self.account_limits = {
            "trading_budget_min": 360,
            "portfolio_budget_min": 30,
            "max_concurrent_contracts": 1,
            "architecture": "Event-Driven Push (Zero Polling)"
        }

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
            "account_type": self.account_type,
            "rate_limit_status": self.rate_limit_status,
            "is_rate_limited": self.is_rate_limited,
            "account_limits": self.account_limits,
            "growth_rate": self.config.growth_rate,
            "stake_amount": self.config.stake_amount,
            "daily_stop_loss_usd": self.config.daily_stop_loss_usd,
            "daily_take_profit_usd": self.config.daily_take_profit_usd,
            "max_consecutive_losses": self.config.max_consecutive_losses,
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
            "latest_log": self.latest_log,
            "streaks": self.risk.get_streaks_summary()
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

    async def handle_rate_limit_backoff(self, error_message: str):
        """Aplica resfriamento inteligente de 60s quando a Deriv sinaliza rate limit."""
        self.st.is_rate_limited = True
        self.st.rate_limit_status = "⚠️ Resfriando (60s)"
        self.st.latest_log = f"⚠️ Rate limit detectado ({error_message}). Ativando resfriamento automático de 60s..."
        logger.warning(f"🛑 RATE LIMIT: {error_message}. Pausando 60 segundos...")
        await self.st.notify_clients()
        await asyncio.sleep(60)
        self.st.is_rate_limited = False
        self.st.rate_limit_status = "OK • Teto 360 req/min"
        self.st.latest_log = "Resfriamento concluído. Retomando operações normalmente."
        logger.info("✅ Resfriamento de rate limit concluído. Retomando...")
        await self.st.notify_clients()

    async def recv_next(self, ws, expected_msg_type: Optional[str] = None, req_id: Optional[int] = None, timeout: float = 12.0) -> Optional[Dict[str, Any]]:
        """
        Consome mensagens do WebSocket de forma orientada a eventos.
        Trata atualizações de saldo e pings concorrentes sem dessincronizar.
        """
        start_time = asyncio.get_event_loop().time()
        while self.st.is_running:
            remaining = timeout - (asyncio.get_event_loop().time() - start_time)
            if remaining <= 0:
                logger.warning(f"Timeout aguardando resposta {expected_msg_type or req_id}")
                return None

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                m = json.loads(raw)
            except asyncio.TimeoutError:
                return None

            # 1. Trata subscrição de Saldo nativo em tempo real
            if m.get("msg_type") == "balance" and "balance" in m:
                bal = float(m["balance"].get("balance", self.st.account_balance))
                if bal != self.st.account_balance:
                    self.st.account_balance = bal
                    logger.info(f"💵 Saldo em tempo real: ${bal:.2f} USD")
                    await self.st.notify_clients()
                continue

            # 2. Ignora pings de heartbeat
            if m.get("msg_type") == "ping":
                continue

            # 3. Trata erros com detecção de Rate Limit
            if "error" in m:
                err = m["error"]
                err_code = str(err.get("code", ""))
                err_msg = str(err.get("message", ""))
                
                # Detecção de Rate Limit / Too Many Requests
                if err_code in ("RateLimit", "TooManyRequests") or "rate limit" in err_msg.lower() or "too many" in err_msg.lower():
                    await self.handle_rate_limit_backoff(err_msg)
                elif "maximum daily turnover" in err_msg.lower() or "turnover limit" in err_msg.lower():
                    self.st.risk.is_stopped = True
                    self.st.risk.stop_reason = f"Limite diário de turnover atingido: {err_msg}"
                    self.st.latest_log = f"🛑 {self.st.risk.stop_reason}"
                    await self.st.notify_clients()
                return m

            # 4. Verifica correspondência
            if req_id is not None and m.get("req_id") == req_id:
                return m
            if expected_msg_type and m.get("msg_type") == expected_msg_type:
                return m
            if expected_msg_type is None and req_id is None:
                return m

        return None

    async def cleanup_orphaned_positions_once(self, ws):
        """
        Executado APENAS UMA VEZ na conexão para limpar contratos remanescentes.
        Zero Polling: Não roda durante o ciclo normal de trade.
        """
        try:
            await ws.send(json.dumps({"portfolio": 1, "req_id": 999}))
            r = await self.recv_next(ws, expected_msg_type="portfolio", req_id=999, timeout=5.0)
            if r and "portfolio" in r:
                contracts = r["portfolio"].get("contracts", [])
                if contracts:
                    logger.info(f"Identificado(s) {len(contracts)} contrato(s) órfão(s) na conexão. Liquidando...")
                    for c in contracts:
                        cid = c.get("contract_id")
                        await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 998}))
                        await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Aviso na checagem inicial de portfolio: {e}")

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

                    # 1. Subscrição nativa de Saldo Deriv em tempo real (Push Stream oficial)
                    await ws.send(json.dumps({"balance": 1, "subscribe": 1, "req_id": 1}))

                    # 2. Limpeza única de contratos órfãos apenas na inicialização da conexão (Sem Polling!)
                    await self.cleanup_orphaned_positions_once(ws)

                    # 3. Loop de Trading 100% Event-Driven (Zero Polling de Portfolio)
                    while self.st.is_running and self.st.risk.can_trade():
                        # A. Solicita Proposta
                        prop_req = {
                            "proposal": 1, "subscribe": 1,
                            "amount": self.st.config.stake_amount,
                            "basis": "stake", "contract_type": "ACCU",
                            "currency": "USD", "underlying_symbol": self.st.active_symbol,
                            "growth_rate": self.st.config.growth_rate,
                            "req_id": 10
                        }
                        await ws.send(json.dumps(prop_req))

                        prop_resp = await self.recv_next(ws, expected_msg_type="proposal", req_id=10)
                        if not prop_resp or "error" in prop_resp:
                            err_msg = prop_resp.get("error", {}).get("message", "Sem resposta") if prop_resp else "Timeout"
                            self.st.latest_log = f"Aviso de proposta: {err_msg}"
                            await self.st.notify_clients()
                            await asyncio.sleep(3)
                            continue

                        prop_id = prop_resp.get("proposal", {}).get("id")
                        sub_id = prop_resp.get("subscription", {}).get("id")

                        if sub_id:
                            await ws.send(json.dumps({"forget": sub_id}))

                        # B. Executa Compra do Contrato
                        await ws.send(json.dumps({"buy": prop_id, "price": self.st.config.stake_amount, "req_id": 20}))
                        buy_resp = await self.recv_next(ws, expected_msg_type="buy", req_id=20)
                        
                        if not buy_resp or "error" in buy_resp:
                            err_msg = buy_resp.get("error", {}).get("message", "Falha na compra") if buy_resp else "Timeout"
                            self.st.latest_log = f"Falha na compra: {err_msg}"
                            await self.st.notify_clients()
                            await asyncio.sleep(3)
                            continue

                        cid = buy_resp.get("buy", {}).get("contract_id")
                        self.st.current_contract_id = cid
                        self.st.in_trade = True
                        self.st.current_ticks = 0
                        self.st.current_profit = 0.0
                        self.st.latest_log = f"Ordem aberta: Contrato #{cid} ({self.st.active_asset_name})"
                        await self.st.notify_clients()

                        # C. Monitoramento em Tempo Real via Stream Push (proposal_open_contract)
                        await ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1, "req_id": 30}))
                        poc_sub = None
                        trade_done = False

                        while not trade_done and self.st.is_running:
                            m = await self.recv_next(ws)
                            if not m:
                                continue

                            if m.get("msg_type") != "proposal_open_contract":
                                continue
                            
                            c = m.get("proposal_open_contract", {})
                            poc_sub = m.get("subscription", {}).get("id")

                            tick_stream = c.get("tick_stream", [])
                            self.st.current_ticks = len(tick_stream)
                            self.st.current_profit = float(c.get("profit", 0.0))
                            is_valid_to_sell = c.get("is_valid_to_sell", 0)
                            is_sold = c.get("is_sold", 0)

                            await self.st.notify_clients()

                            # Se o contrato encerrou nativamente (ex: bateu barreira)
                            if is_sold:
                                p_final = float(c.get("profit", 0.0))
                                self.st.risk.register_trade(p_final)
                                self._record_trade(p_final)
                                trade_done = True
                                break

                            # D. Cash Out Automatizado ao atingir os ticks estipulados
                            if self.st.current_ticks >= self.st.config.exit_ticks and is_valid_to_sell:
                                self.st.latest_log = f"Alvo de {self.st.config.exit_ticks} ticks atingido! Disparando Cash Out..."
                                await self.st.notify_clients()
                                await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 40}))
                                
                                sell_resp = await self.recv_next(ws, expected_msg_type="sell", req_id=40)
                                if sell_resp and "sell" in sell_resp:
                                    sold_for = float(sell_resp["sell"]["sold_for"])
                                    net = sold_for - self.st.config.stake_amount
                                    self.st.risk.register_trade(net)
                                    self._record_trade(net)
                                    self.st.latest_log = f"CASH OUT CONFIRMADO: +${net:.2f} no {self.st.current_ticks}º tick"
                                trade_done = True
                                break

                        if poc_sub:
                            await ws.send(json.dumps({"forget": poc_sub}))

                        self.st.in_trade = False
                        self.st.current_contract_id = None
                        trade_count_scan += 1
                        await self.st.notify_clients()

                        # Reavaliação inteligente a cada 5 trades
                        if trade_count_scan >= 5 and self.st.config.auto_select_best_asset:
                            w = await find_safest_asset(self.st.config.public_ws_url, self.st.config.exit_ticks, self.st.config.growth_rate)
                            self.st.active_symbol = w["symbol"]
                            self.st.active_asset_name = w["name"]
                            self.st.active_asset_rate = w["survived_target_pct"]
                            trade_count_scan = 0
                            await self.st.notify_clients()

                        # Pausa de segurança saudável entre ciclos para respeitar rate limits
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


def persist_env_config(updates: Dict[str, Any]):
    """Atualiza as chaves selecionadas no arquivo .env preservando comentários e outras variáveis."""
    try:
        env_path = BASE_DIR / ".env"
        if not env_path.exists():
            return
        lines = env_path.read_text(encoding="utf-8").splitlines()
        new_lines = []
        keys_updated = set()
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _ = stripped.split("=", 1)
                k = k.strip()
                if k in updates:
                    new_lines.append(f"{k}={updates[k]}")
                    keys_updated.add(k)
                    continue
            new_lines.append(line)
        for k, v in updates.items():
            if k not in keys_updated:
                new_lines.append(f"{k}={v}")
        env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        logger.info("💾 Arquivo .env atualizado com as novas configurações.")
    except Exception as e:
        logger.error(f"Erro ao persistir .env: {e}")


class ConfigUpdateRequest(BaseModel):
    growth_rate: float
    stake_amount: float
    exit_ticks: int
    daily_stop_loss_usd: float
    daily_take_profit_usd: float
    max_consecutive_losses: int


@app.get("/api/config")
async def get_config():
    return {
        "growth_rate": state.config.growth_rate,
        "stake_amount": state.config.stake_amount,
        "exit_ticks": state.config.exit_ticks,
        "daily_stop_loss_usd": state.config.daily_stop_loss_usd,
        "daily_take_profit_usd": state.config.daily_take_profit_usd,
        "max_consecutive_losses": state.config.max_consecutive_losses
    }


@app.post("/api/config")
async def update_config(cfg_in: ConfigUpdateRequest):
    if cfg_in.stake_amount <= 0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "O valor da Stake deve ser maior que zero."})
    if cfg_in.exit_ticks < 1:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Exit Ticks deve ser pelo menos 1."})

    state.config.growth_rate = round(float(cfg_in.growth_rate), 4)
    state.config.stake_amount = round(float(cfg_in.stake_amount), 2)
    state.config.exit_ticks = int(cfg_in.exit_ticks)
    state.config.daily_stop_loss_usd = round(abs(float(cfg_in.daily_stop_loss_usd)), 2)
    state.config.daily_take_profit_usd = round(abs(float(cfg_in.daily_take_profit_usd)), 2)
    state.config.max_consecutive_losses = int(cfg_in.max_consecutive_losses)

    # Reavalia o RiskManager se estava bloqueado por meta anterior
    if state.risk.is_stopped:
        if (state.risk.daily_pnl > -abs(state.config.daily_stop_loss_usd) and
            state.risk.daily_pnl < abs(state.config.daily_take_profit_usd) and
            state.risk.current_loss_streak < state.config.max_consecutive_losses):
            state.risk.is_stopped = False
            state.risk.stop_reason = ""
            state.status_message = "Parado" if not state.is_running else "Ativo"

    # Persiste no .env para reter entre reinicializações
    persist_env_config({
        "GROWTH_RATE": f"{state.config.growth_rate:.2f}",
        "STAKE_AMOUNT": f"{state.config.stake_amount:.2f}",
        "EXIT_TICKS": str(state.config.exit_ticks),
        "DAILY_STOP_LOSS_USD": f"{state.config.daily_stop_loss_usd:.2f}",
        "DAILY_TAKE_PROFIT_USD": f"{state.config.daily_take_profit_usd:.2f}",
        "MAX_CONSECUTIVE_LOSSES": str(state.config.max_consecutive_losses)
    })

    log_msg = f"⚙️ Configurações salvas: Stake ${state.config.stake_amount:.2f} | Growth {state.config.growth_rate*100:.0f}% | Saída {state.config.exit_ticks}T | TP ${state.config.daily_take_profit_usd:.2f} | SL ${state.config.daily_stop_loss_usd:.2f} | Max Loss {state.config.max_consecutive_losses}"
    state.latest_log = log_msg
    logger.info(log_msg)
    await state.notify_clients()

    return {
        "status": "success",
        "message": "Configurações salvas e aplicadas com sucesso!",
        "config": {
            "growth_rate": state.config.growth_rate,
            "stake_amount": state.config.stake_amount,
            "exit_ticks": state.config.exit_ticks,
            "daily_stop_loss_usd": state.config.daily_stop_loss_usd,
            "daily_take_profit_usd": state.config.daily_take_profit_usd,
            "max_consecutive_losses": state.config.max_consecutive_losses
        }
    }


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
