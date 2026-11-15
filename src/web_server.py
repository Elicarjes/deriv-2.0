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
from session_manager import SessionManager
from account_client import AccountClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("WebServer")

app = FastAPI(title="Deriv Quant Dashboard")

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"


class DashboardState:
    def __init__(self, config: BotConfig):
        self.config = config
        self.risk = RiskManager(config)
        self.session_manager = SessionManager(BASE_DIR / "data" / "sessions.json")
        self.session_number = self.session_manager.get_next_session_number()
        self.session_id = f"sess_{int(datetime.now().timestamp())}"
        self.session_start_time = datetime.now()
        self.session_trades: List[Dict[str, Any]] = []

        # Contas Desacopladas (Multi-Contas PAT)
        self.primary_account = AccountClient(
            account_role="primary",
            name="Conta Primária (Real)",
            token=config.token,
            app_id=config.app_id,
            account_id=config.account_id,
            rest_base_url=config.rest_base_url
        )
        self.secondary_account = AccountClient(
            account_role="secondary",
            name="Conta Secundária (Escudo Demo)",
            token=config.secondary_token,
            app_id=config.secondary_app_id,
            account_id=config.secondary_account_id,
            rest_base_url=config.rest_base_url
        )

        # Modos de Operação: "shield_combined", "primary_only", "secondary_only"
        self.operation_mode = config.operation_mode
        self.shield_trigger_losses = config.shield_trigger_losses
        self.shield_losses_count = 0
        self.sniper_armed = False
        self.active_trade_account = "primary" if self.operation_mode == "primary_only" else "secondary"
        self.shield_wins = 0
        self.shield_losses = 0
        self.shield_pnl = 0.0

        active_acc = self.primary_account if self.active_trade_account == "primary" else self.secondary_account
        self.is_running = False
        self.status_message = "Parado"
        self.account_id = active_acc.account_id or "DOT..."
        self.account_balance = active_acc.balance
        self.account_type = active_acc.account_type
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
        self.current_cycle_tick = 0

        self.recent_trades: List[Dict[str, Any]] = []
        self.latest_log = "Sistema pronto. Subscrição de saldo ativa."
        self.bot_task: Optional[asyncio.Task] = None

        # Gerenciamento de conexões WebSocket do frontend (Event-Driven)
        self.connected_websockets: Set[WebSocket] = set()

    def get_active_account(self) -> AccountClient:
        """Retorna o cliente de conta atualmente em uso para trade."""
        if self.active_trade_account == "primary":
            return self.primary_account
        return self.secondary_account

    def archive_current_session(self) -> Optional[Dict[str, Any]]:
        """Arquiva a sessão corrente caso tenha executado ao menos 1 trade."""
        if not self.session_trades and self.risk.total_trades == 0:
            return None

        now = datetime.now()
        duration_sec = int((now - self.session_start_time).total_seconds())
        m, s = divmod(duration_sec, 60)
        h, m = divmod(m, 60)
        dur_str = f"{h}h {m}m {s}s" if h > 0 else f"{m}m {s}s"

        win_rate = (self.risk.wins / self.risk.total_trades * 100) if self.risk.total_trades > 0 else 0.0

        session_record = {
            "id": self.session_id,
            "number": self.session_number,
            "name": f"Sessão #{self.session_number}",
            "start_time": self.session_start_time.strftime("%d/%m/%Y %H:%M:%S"),
            "end_time": now.strftime("%d/%m/%Y %H:%M:%S"),
            "duration": dur_str,
            "config": {
                "growth_rate": self.config.growth_rate,
                "stake_amount": self.config.stake_amount,
                "exit_ticks": self.config.exit_ticks,
                "daily_stop_loss_usd": self.config.daily_stop_loss_usd,
                "daily_take_profit_usd": self.config.daily_take_profit_usd,
                "max_consecutive_losses": self.config.max_consecutive_losses,
                "wait_cycle_reset": self.config.wait_cycle_reset,
                "max_entry_tick": self.config.max_entry_tick
            },
            "summary": {
                "pnl": round(self.risk.daily_pnl, 2),
                "wins": self.risk.wins,
                "losses": self.risk.losses,
                "total_trades": self.risk.total_trades,
                "win_rate": round(win_rate, 1),
                "max_win_streak": self.risk.max_win_streak,
                "max_loss_streak": self.risk.max_loss_streak,
                "streaks": self.risk.get_streaks_summary()
            },
            "trades": list(self.session_trades)
        }
        self.session_manager.archive_session(session_record)
        return session_record

    def start_new_session(self, reason: str = "Novo ciclo de testes iniciado"):
        """Arquiva a sessão corrente (se tiver trades) e reinicia o estado para uma nova sessão limpa."""
        self.archive_current_session()
        self.risk = RiskManager(self.config)
        self.recent_trades.clear()
        self.session_trades.clear()
        self.shield_wins = 0
        self.shield_losses = 0
        self.shield_pnl = 0.0
        self.shield_losses_count = 0
        self.sniper_armed = False
        self.session_start_time = datetime.now()
        self.session_number = self.session_manager.get_next_session_number()
        self.session_id = f"sess_{int(datetime.now().timestamp())}"
        self.latest_log = f"✨ Nova Sessão #{self.session_number} iniciada! ({reason})"
        logger.info(f"✨ Nova Sessão #{self.session_number} iniciada ({reason}).")

    def to_dict(self) -> Dict[str, Any]:
        win_rate = (self.risk.wins / self.risk.total_trades * 100) if self.risk.total_trades > 0 else 0.0
        active_acc = self.get_active_account()

        return {
            "is_running": self.is_running,
            "status_message": self.status_message,
            "account_id": active_acc.account_id or self.account_id,
            "account_balance": active_acc.balance if active_acc.balance > 0 else self.account_balance,
            "account_type": active_acc.account_type,
            "rate_limit_status": self.rate_limit_status,
            "is_rate_limited": self.is_rate_limited,
            "account_limits": self.account_limits,
            "growth_rate": self.config.growth_rate,
            "stake_amount": self.config.stake_amount,
            "daily_stop_loss_usd": self.config.daily_stop_loss_usd,
            "daily_take_profit_usd": self.config.daily_take_profit_usd,
            "max_consecutive_losses": self.config.max_consecutive_losses,
            "wait_cycle_reset": self.config.wait_cycle_reset,
            "max_entry_tick": self.config.max_entry_tick,
            "current_cycle_tick": self.current_cycle_tick,
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
            "streaks": self.risk.get_streaks_summary(),
            "session_id": self.session_id,
            "session_number": self.session_number,
            "session_start_time": self.session_start_time.strftime("%H:%M:%S"),
            "archived_sessions_count": len(self.session_manager.get_all_sessions()),

            # Status Multi-Contas & Modo Escudo
            "operation_mode": self.operation_mode,
            "shield_trigger_losses": self.shield_trigger_losses,
            "shield_losses_count": self.shield_losses_count,
            "sniper_armed": self.sniper_armed,
            "shield_pnl": round(self.shield_pnl, 2),
            "shield_wins": self.shield_wins,
            "shield_losses": self.shield_losses,
            "primary_account_balance": self.primary_account.balance,
            "primary_account_id": self.primary_account.account_id,
            "secondary_account_balance": self.secondary_account.balance,
            "secondary_account_id": self.secondary_account.account_id,
            "active_trade_account": self.active_trade_account,
            "primary_account": self.primary_account.to_dict(),
            "secondary_account": self.secondary_account.to_dict()
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


def fetch_initial_balances():
    """Busca o saldo inicial de ambas as contas (Primária e Secundária) via REST."""
    bal_prim = state.primary_account.fetch_balance()
    bal_sec = state.secondary_account.fetch_balance()
    active_acc = state.get_active_account()
    state.account_balance = active_acc.balance
    state.account_id = active_acc.account_id
    state.account_type = active_acc.account_type
    logger.info(f"✅ Contas prontas: Primária ${bal_prim:.2f} ({state.primary_account.account_type}) | Secundária ${bal_sec:.2f} ({state.secondary_account.account_type})")


fetch_initial_balances()


class BotRunner:
    def __init__(self, dashboard_state: DashboardState):
        self.st = dashboard_state

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

    async def recv_next(self, ws, expected_msg_type: Optional[str] = None, req_id: Optional[int] = None, timeout: float = 12.0, account: Optional[AccountClient] = None) -> Optional[Dict[str, Any]]:
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
                if account:
                    account.balance = bal
                self.st.account_balance = bal
                logger.info(f"💵 Saldo em tempo real [{account.name if account else 'Conta'}]: ${bal:.2f} USD")
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

    async def cleanup_orphaned_positions_once(self, ws, account: Optional[AccountClient] = None):
        """
        Executado APENAS UMA VEZ na conexão para limpar contratos remanescentes.
        Zero Polling: Não roda durante o ciclo normal de trade.
        """
        try:
            await ws.send(json.dumps({"portfolio": 1, "req_id": 999}))
            r = await self.recv_next(ws, expected_msg_type="portfolio", req_id=999, timeout=5.0, account=account)
            if r and "portfolio" in r:
                contracts = r["portfolio"].get("contracts", [])
                if contracts:
                    logger.info(f"Identificado(s) {len(contracts)} contrato(s) órfão(s) na conexão [{account.name if account else ''}]. Liquidando...")
                    for c in contracts:
                        cid = c.get("contract_id")
                        await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 998}))
                        await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Aviso na checagem inicial de portfolio: {e}")

    def _handle_shield_post_trade(self, account: AccountClient, profit: float) -> bool:
        """Processa a transição de estado da Conta Escudo e retorna True se houver troca de conta."""
        if self.st.operation_mode != "shield_combined":
            return False

        if account.account_role == "secondary":
            if profit <= 0:
                self.st.shield_losses_count += 1
                if self.st.shield_losses_count >= self.st.shield_trigger_losses:
                    self.st.sniper_armed = True
                    self.st.latest_log = f"🎯 GATILHO ATIVADO: {self.st.shield_losses_count} derrotas consecutivas no Escudo! O PRÓXIMO TRADE SERÁ NA CONTA REAL!"
                    logger.warning(self.st.latest_log)
                    return True
                else:
                    self.st.latest_log = f"🛡️ Escudo Demo: {self.st.shield_losses_count}/{self.st.shield_trigger_losses} derrotas para armar Sniper Real."
            else:
                self.st.shield_losses_count = 0
                self.st.sniper_armed = False
                self.st.latest_log = f"🛡️ Vitória no Escudo Demo (+${profit:.2f})! Contador de perdas resetado (0/{self.st.shield_trigger_losses})."
        else:
            # Trade encerrado na Conta Primária (Real)
            self.st.sniper_armed = False
            self.st.shield_losses_count = 0
            if profit > 0:
                self.st.latest_log = f"💰 SNIPER REAL CONCLUÍDO COM VITÓRIA (+${profit:.2f})! Retornando ao Escudo Demo."
                logger.info(self.st.latest_log)
            else:
                self.st.latest_log = f"⚠️ Trade Real finalizado (${profit:.2f}). Retornando ao Escudo Demo para nova sondagem."
                logger.warning(self.st.latest_log)
            return True

        return False

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
        self.st.latest_log = f"Ativo campeão selecionado: {winner['name']} ({winner['survived_target_pct']:.1f}% em {self.st.config.exit_ticks}T)"
        await self.st.notify_clients()

        trade_count_scan = 0

        while self.st.is_running and self.st.risk.can_trade():
            # 1. Determina a conta alvo para este ciclo
            if self.st.operation_mode == "primary_only":
                target_account = self.st.primary_account
            elif self.st.operation_mode == "secondary_only":
                target_account = self.st.secondary_account
            else:  # "shield_combined"
                if self.st.sniper_armed:
                    target_account = self.st.primary_account
                    msg = "🎯 [MODO ESCUDO] Sniper armado! Disparando na CONTA REAL..."
                else:
                    target_account = self.st.secondary_account
                    msg = f"🛡️ [MODO ESCUDO] Sondando mercado no Escudo Demo ({self.st.shield_losses_count}/{self.st.shield_trigger_losses} losses)..."
                self.st.latest_log = msg

            self.st.active_trade_account = target_account.account_role
            self.st.account_id = target_account.account_id
            self.st.account_type = target_account.account_type
            await self.st.notify_clients()

            try:
                otp_url = target_account.get_otp_url()

                async with websockets.connect(otp_url, ping_interval=None) as ws:
                    hb_task = asyncio.create_task(self.heartbeat(ws))

                    # 1. Subscrição nativa de Saldo Deriv em tempo real
                    await ws.send(json.dumps({"balance": 1, "subscribe": 1, "req_id": 1}))

                    # 2. Limpeza única de contratos órfãos apenas na inicialização
                    await self.cleanup_orphaned_positions_once(ws, account=target_account)

                    # 3. Executa ordens enquanto estiver nesta conta
                    while self.st.is_running and self.st.risk.can_trade():
                        # A. Solicita Proposta Streaming
                        prop_req = {
                            "proposal": 1, "subscribe": 1,
                            "amount": self.st.config.stake_amount,
                            "basis": "stake", "contract_type": "ACCU",
                            "currency": "USD", "underlying_symbol": self.st.active_symbol,
                            "growth_rate": self.st.config.growth_rate,
                            "req_id": 10
                        }
                        await ws.send(json.dumps(prop_req))

                        prop_resp = await self.recv_next(ws, expected_msg_type="proposal", req_id=10, account=target_account)
                        if not prop_resp or "error" in prop_resp:
                            err_msg = prop_resp.get("error", {}).get("message", "Sem resposta") if prop_resp else "Timeout"
                            self.st.latest_log = f"Aviso de proposta: {err_msg}"
                            await self.st.notify_clients()
                            await asyncio.sleep(3)
                            continue

                        prop_id = prop_resp.get("proposal", {}).get("id")
                        sub_id = prop_resp.get("subscription", {}).get("id")

                        # Sincronização Inteligente de Ciclo (Esperar bater na parede)
                        if self.st.config.wait_cycle_reset:
                            prev_cycle_tick = None
                            cycle_ready = False

                            while not cycle_ready and self.st.is_running and self.st.risk.can_trade():
                                p_data = prop_resp.get("proposal", {})
                                p_details = p_data.get("contract_details", {})
                                tsi = p_details.get("ticks_stayed_in")

                                if tsi and len(tsi) == 1:
                                    cur_tick = tsi[0]
                                    self.st.current_cycle_tick = cur_tick

                                    # Condição 1: Já está no início do ciclo (tick 0 ou <= max_entry_tick)
                                    if cur_tick <= self.st.config.max_entry_tick:
                                        cycle_ready = True
                                        self.st.latest_log = f"⚡ Ciclo virgem detectado ({cur_tick}º tick)! Disparando entrada [{target_account.name}]..."
                                        logger.info(self.st.latest_log)
                                        await self.st.notify_clients()
                                        break

                                    # Condição 2: Reset detectado (cur_tick resetou após bater na parede)
                                    if prev_cycle_tick is not None and cur_tick < prev_cycle_tick:
                                        cycle_ready = True
                                        self.st.latest_log = f"💥 Parede atingida após {prev_cycle_tick} ticks! Novo ciclo ({cur_tick}T). Disparando compra [{target_account.name}]..."
                                        logger.info(self.st.latest_log)
                                        await self.st.notify_clients()
                                        break

                                    prev_cycle_tick = cur_tick
                                    self.st.latest_log = f"⏳ Aguardando ciclo resetar... ({cur_tick}º tick sem parede) [{target_account.name}]"
                                    await self.st.notify_clients()

                                # Aguarda o próximo tick do stream de proposta
                                prop_resp = await self.recv_next(ws, expected_msg_type="proposal", account=target_account)
                                if not prop_resp or "error" in prop_resp:
                                    break
                                prop_id = prop_resp.get("proposal", {}).get("id", prop_id)
                                sub_id = prop_resp.get("subscription", {}).get("id", sub_id)

                            if not cycle_ready:
                                if sub_id:
                                    await ws.send(json.dumps({"forget": sub_id}))
                                continue

                        if sub_id:
                            await ws.send(json.dumps({"forget": sub_id}))

                        # B. Executa Compra do Contrato
                        await ws.send(json.dumps({"buy": prop_id, "price": self.st.config.stake_amount, "req_id": 20}))
                        buy_resp = await self.recv_next(ws, expected_msg_type="buy", req_id=20, account=target_account)
                        
                        if not buy_resp or "error" in buy_resp:
                            err_msg = buy_resp.get("error", {}).get("message", "Falha na compra") if buy_resp else "Timeout"
                            self.st.latest_log = f"Falha na compra [{target_account.name}]: {err_msg}"
                            await self.st.notify_clients()
                            await asyncio.sleep(3)
                            continue

                        cid = buy_resp.get("buy", {}).get("contract_id")
                        self.st.current_contract_id = cid
                        self.st.in_trade = True
                        self.st.current_ticks = 0
                        self.st.current_profit = 0.0
                        self.st.latest_log = f"Ordem aberta ({target_account.account_type}): #{cid} ({self.st.active_asset_name})"
                        await self.st.notify_clients()

                        # C. Monitoramento em Tempo Real via Stream Push (proposal_open_contract)
                        await ws.send(json.dumps({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1, "req_id": 30}))
                        poc_sub = None
                        trade_done = False
                        account_switched = False

                        while not trade_done and self.st.is_running:
                            m = await self.recv_next(ws, account=target_account)
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
                                is_shield_trade = (self.st.operation_mode == "shield_combined" and target_account.account_role == "secondary")
                                if is_shield_trade:
                                    self.st.shield_pnl += p_final
                                    if p_final > 0:
                                        self.st.shield_wins += 1
                                    else:
                                        self.st.shield_losses += 1
                                else:
                                    # Contabiliza na Conta Primária (Alvo Sniper / Real)
                                    self.st.risk.register_trade(p_final)

                                self._record_trade(
                                    p_final,
                                    ticks=self.st.current_ticks,
                                    contract_id=cid,
                                    account_role=target_account.account_role,
                                    account_type=target_account.account_type
                                )
                                trade_done = True
                                account_switched = self._handle_shield_post_trade(target_account, p_final)
                                break

                            # D. Cash Out Automatizado ao atingir os ticks estipulados
                            if self.st.current_ticks >= self.st.config.exit_ticks and is_valid_to_sell:
                                self.st.latest_log = f"Alvo de {self.st.config.exit_ticks} ticks atingido! Disparando Cash Out [{target_account.name}]..."
                                await self.st.notify_clients()
                                await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 40}))
                                
                                sell_resp = await self.recv_next(ws, expected_msg_type="sell", req_id=40, account=target_account)
                                if sell_resp and "sell" in sell_resp:
                                    sold_for = float(sell_resp["sell"]["sold_for"])
                                    net = sold_for - self.st.config.stake_amount
                                    is_shield_trade = (self.st.operation_mode == "shield_combined" and target_account.account_role == "secondary")
                                    if is_shield_trade:
                                        self.st.shield_pnl += net
                                        if net > 0:
                                            self.st.shield_wins += 1
                                        else:
                                            self.st.shield_losses += 1
                                    else:
                                        self.st.risk.register_trade(net)

                                    self._record_trade(
                                        net,
                                        ticks=self.st.current_ticks,
                                        contract_id=cid,
                                        account_role=target_account.account_role,
                                        account_type=target_account.account_type
                                    )
                                    self.st.latest_log = f"CASH OUT CONFIRMADO: +${net:.2f} no {self.st.current_ticks}º tick ({target_account.name})"
                                    trade_done = True
                                    account_switched = self._handle_shield_post_trade(target_account, net)
                                    break

                        if poc_sub:
                            await ws.send(json.dumps({"forget": poc_sub}))

                        self.st.in_trade = False
                        self.st.current_contract_id = None
                        trade_count_scan += 1
                        await self.st.notify_clients()

                        # Se a lógica da Conta Escudo determinou troca de conta, troca de conexão WebSocket!
                        if account_switched:
                            logger.info("🔄 Transição de conta ativada! Trocando de conexão...")
                            break

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
                self.st.latest_log = f"Aviso de conexão [{target_account.name}]: {e}. Reconectando..."
                await self.st.notify_clients()
                await asyncio.sleep(5)

        self.st.is_running = False
        if not self.st.risk.can_trade():
            self.st.status_message = "Meta/Stop Batido"
            self.st.latest_log = f"FIM DE SESSÃO: {self.st.risk.stop_reason}"
            self.st.archive_current_session()
        else:
            self.st.status_message = "Parado"
        await self.st.notify_clients()

    def _record_trade(self, profit: float, ticks: int = 0, contract_id: Optional[int] = None, account_role: str = "secondary", account_type: str = "Demo"):
        now = datetime.now().strftime("%H:%M:%S")
        trade_item = {
            "time": now,
            "symbol": self.st.active_asset_name,
            "stake": self.st.config.stake_amount,
            "profit": round(profit, 2),
            "result": "VITÓRIA" if profit > 0 else "DERROTA",
            "ticks": ticks or self.st.current_ticks,
            "contract_id": contract_id or self.st.current_contract_id,
            "account_role": account_role,
            "account_type": account_type
        }
        self.st.recent_trades.insert(0, trade_item)
        self.st.session_trades.insert(0, trade_item)


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
    wait_cycle_reset: bool = True
    max_entry_tick: int = 1
    start_new_session: bool = False

    # Parâmetros da Conta Escudo e Multi-Contas
    operation_mode: Optional[str] = "secondary_only"
    shield_trigger_losses: Optional[int] = 2
    primary_token: Optional[str] = None
    primary_app_id: Optional[str] = None
    primary_account_id: Optional[str] = None
    secondary_token: Optional[str] = None
    secondary_app_id: Optional[str] = None
    secondary_account_id: Optional[str] = None


@app.get("/api/config")
async def get_config():
    prim_accs = await asyncio.to_thread(state.primary_account.fetch_available_accounts)
    sec_accs = await asyncio.to_thread(state.secondary_account.fetch_available_accounts)
    return {
        "growth_rate": state.config.growth_rate,
        "stake_amount": state.config.stake_amount,
        "exit_ticks": state.config.exit_ticks,
        "daily_stop_loss_usd": state.config.daily_stop_loss_usd,
        "daily_take_profit_usd": state.config.daily_take_profit_usd,
        "max_consecutive_losses": state.config.max_consecutive_losses,
        "wait_cycle_reset": state.config.wait_cycle_reset,
        "max_entry_tick": state.config.max_entry_tick,
        "operation_mode": state.operation_mode,
        "shield_trigger_losses": state.shield_trigger_losses,
        "primary_token": state.primary_account.token,
        "primary_app_id": state.primary_account.app_id,
        "primary_account_id": state.primary_account.account_id,
        "primary_available_accounts": prim_accs,
        "secondary_token": state.secondary_account.token,
        "secondary_app_id": state.secondary_account.app_id,
        "secondary_account_id": state.secondary_account.account_id,
        "secondary_available_accounts": sec_accs
    }


class AccountsListRequest(BaseModel):
    token: str
    app_id: str


@app.post("/api/accounts/list")
async def list_accounts(req: AccountsListRequest):
    token = req.token.strip()
    app_id = req.app_id.strip()
    if not token or not app_id:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Token e App ID são obrigatórios."})
    
    client = AccountClient(account_role="temp", name="Temp", token=token, app_id=app_id)
    accounts = await asyncio.to_thread(client.fetch_available_accounts)
    return {"status": "success", "accounts": accounts}


@app.post("/api/config")
async def update_config(cfg_in: ConfigUpdateRequest):
    if cfg_in.stake_amount < 1.0:
        return JSONResponse(status_code=400, content={"status": "error", "message": "A Stake mínima exigida pela Deriv para Accumulators é $1.00 USD."})
    if cfg_in.exit_ticks < 2:
        return JSONResponse(status_code=400, content={"status": "error", "message": "A saída deve ser no mínimo de 2 ticks (o 1º tick é o Entry Spot, que não gera lucro)."})

    state.config.growth_rate = round(float(cfg_in.growth_rate), 4)
    state.config.stake_amount = round(float(cfg_in.stake_amount), 2)
    state.config.exit_ticks = int(cfg_in.exit_ticks)
    state.config.daily_stop_loss_usd = round(abs(float(cfg_in.daily_stop_loss_usd)), 2)
    state.config.daily_take_profit_usd = round(abs(float(cfg_in.daily_take_profit_usd)), 2)
    state.config.max_consecutive_losses = int(cfg_in.max_consecutive_losses)
    state.config.wait_cycle_reset = bool(cfg_in.wait_cycle_reset)
    state.config.max_entry_tick = int(cfg_in.max_entry_tick)

    # Atualizações de Modo de Operação e Contas
    if cfg_in.operation_mode:
        state.operation_mode = cfg_in.operation_mode
        state.config.operation_mode = cfg_in.operation_mode
    if cfg_in.shield_trigger_losses is not None:
        state.shield_trigger_losses = max(1, int(cfg_in.shield_trigger_losses))
        state.config.shield_trigger_losses = state.shield_trigger_losses

    if cfg_in.primary_token:
        state.primary_account.token = cfg_in.primary_token.strip()
        state.config.token = state.primary_account.token
    if cfg_in.primary_app_id:
        state.primary_account.app_id = cfg_in.primary_app_id.strip()
        state.config.app_id = state.primary_account.app_id
    if cfg_in.primary_account_id:
        state.primary_account.account_id = cfg_in.primary_account_id.strip()
        state.config.account_id = state.primary_account.account_id

    if cfg_in.secondary_token:
        state.secondary_account.token = cfg_in.secondary_token.strip()
        state.config.secondary_token = state.secondary_account.token
    if cfg_in.secondary_app_id:
        state.secondary_account.app_id = cfg_in.secondary_app_id.strip()
        state.config.secondary_app_id = state.secondary_account.app_id
    if cfg_in.secondary_account_id:
        state.secondary_account.account_id = cfg_in.secondary_account_id.strip()
        state.config.secondary_account_id = state.secondary_account.account_id

    # Atualiza saldos se credenciais mudaram
    state.primary_account.fetch_balance()
    state.secondary_account.fetch_balance()

    # Se o usuário solicitou iniciar como uma nova sessão de teste
    if cfg_in.start_new_session and not state.in_trade:
        state.start_new_session("Parâmetros atualizados no painel")
    elif state.risk.is_stopped:
        # Reavalia o RiskManager se estava bloqueado por meta anterior
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
        "MAX_CONSECUTIVE_LOSSES": str(state.config.max_consecutive_losses),
        "WAIT_CYCLE_RESET": str(state.config.wait_cycle_reset).lower(),
        "MAX_ENTRY_TICK": str(state.config.max_entry_tick),
        "OPERATION_MODE": state.operation_mode,
        "SHIELD_TRIGGER_LOSSES": str(state.shield_trigger_losses),
        "DERIV_PRIMARY_API_TOKEN": state.primary_account.token,
        "DERIV_PRIMARY_APP_ID": state.primary_account.app_id,
        "DERIV_PRIMARY_ACCOUNT_ID": state.primary_account.account_id,
        "DERIV_SECONDARY_API_TOKEN": state.secondary_account.token,
        "DERIV_SECONDARY_APP_ID": state.secondary_account.app_id,
        "DERIV_SECONDARY_ACCOUNT_ID": state.secondary_account.account_id
    })

    log_msg = f"⚙️ Configurações salvas: Modo {state.operation_mode} | Gatilho {state.shield_trigger_losses}L | Stake ${state.config.stake_amount:.2f} | Growth {state.config.growth_rate*100:.0f}% | Saída {state.config.exit_ticks}T"
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
            "max_consecutive_losses": state.config.max_consecutive_losses,
            "wait_cycle_reset": state.config.wait_cycle_reset,
            "max_entry_tick": state.config.max_entry_tick,
            "operation_mode": state.operation_mode,
            "shield_trigger_losses": state.shield_trigger_losses
        }
    }


# ==========================================
# ENDPOINTS DE HISTÓRICO DE SESSÕES
# ==========================================
@app.get("/api/sessions")
async def get_sessions():
    sessions = state.session_manager.get_all_sessions()
    return JSONResponse(content={
        "sessions": sessions,
        "current_session": {
            "id": state.session_id,
            "number": state.session_number,
            "start_time": state.session_start_time.strftime("%d/%m/%Y %H:%M:%S"),
            "total_trades": state.risk.total_trades,
            "pnl": state.risk.daily_pnl
        }
    })


@app.post("/api/session/new")
async def new_session():
    if state.in_trade:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Aguarde o contrato em andamento finalizar para iniciar uma nova sessão."
        })
    state.start_new_session(reason="Solicitado manualmente pelo usuário")
    await state.notify_clients()
    return {
        "status": "success",
        "message": f"Nova Sessão #{state.session_number} iniciada com sucesso!",
        "session_number": state.session_number
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    success = state.session_manager.delete_session(session_id)
    if success:
        await state.notify_clients()
        return {"status": "success", "message": "Sessão removida do histórico."}
    return JSONResponse(status_code=404, content={"status": "error", "message": "Sessão não encontrada."})


@app.delete("/api/sessions")
async def clear_all_sessions():
    state.session_manager.clear_all()
    await state.notify_clients()
    return {"status": "success", "message": "Todo o histórico de sessões foi limpo com sucesso."}


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
