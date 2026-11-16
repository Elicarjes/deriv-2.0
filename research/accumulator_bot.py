"""
Robô de Produção: Deriv Accumulator Bot (ACCU) com Heartbeat e Auto-Reconnect.
Executa em loop contínuo até atingir a Meta Diária (Take Profit) ou Limite de Perda (Stop Loss).

Recursos de Robustez:
1. Heartbeat em background: Envia {"ping": 1} a cada 20s para manter a conexão viva.
2. Resiliência a quedas: Se a internet oscilar ou o socket fechar, renova o OTP e reconecta sem perder o saldo.
3. Cash Out automatizado em N ticks (ex: 2 ticks).
4. Gerenciamento de Risco Rigoroso (Hard Stop Loss / Take Profit diários).
"""

import asyncio
import json
import logging
import signal
import sys
from typing import Optional
import urllib.request
import websockets

from config import BotConfig
from risk_manager import RiskManager
from asset_selector import find_safest_asset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("AccumulatorBot")


class AccumulatorBot:
    def __init__(self, config: BotConfig):
        self.config = config
        self.risk = RiskManager(config)
        self.is_running = True
        self.active_symbol = config.symbol
        self.active_asset_name = config.symbol
        self.current_contract_id: Optional[int] = None
        self.active_ws: Optional[websockets.WebSocketClientProtocol] = None

    async def update_best_asset(self):
        """Seleciona dinamicamente o ativo com maior chance de sobrevivência."""
        if not self.config.auto_select_best_asset:
            return
        winner = await find_safest_asset(
            public_ws_url=self.config.public_ws_url,
            target_ticks=self.config.exit_ticks,
            growth_rate=self.config.growth_rate
        )
        self.active_symbol = winner["symbol"]
        self.active_asset_name = winner["name"]
        logger.info(f"🎯 Ativo Selecionado para Trading: {self.active_asset_name} ({self.active_symbol})")

    def get_otp_url(self) -> str:
        """Gera um OTP WebSocket via REST usando o PAT e App ID."""
        headers = {
            "Authorization": f"Bearer {self.config.token}",
            "Deriv-App-ID": str(self.config.app_id),
            "User-Agent": "Mozilla/5.0"
        }

        account_id = self.config.account_id
        if not account_id:
            acc_url = f"{self.config.rest_base_url}/trading/v1/options/accounts"
            req = urllib.request.Request(acc_url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for acc in data.get("data", []):
                    if acc.get("account_type") == "demo" or "DOT" in acc.get("account_id", ""):
                        account_id = acc.get("account_id")
                        break

        otp_url = f"{self.config.rest_base_url}/trading/v1/options/accounts/{account_id}/otp"
        req = urllib.request.Request(otp_url, headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ws_url = data.get("data", {}).get("url")
            if not ws_url:
                raise ConnectionError("A Deriv não retornou a URL de conexão OTP.")
            return ws_url

    async def heartbeat(self, ws):
        """Mantém a conexão com a Deriv ativa enviando ping a cada 20 segundos."""
        try:
            while self.is_running:
                await asyncio.sleep(20)
                try:
                    await ws.send(json.dumps({"ping": 1}))
                    logger.debug("💓 Heartbeat ping enviado à Deriv.")
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def handle_rate_limit_backoff(self, error_message: str):
        """Aplica resfriamento de 60s quando a Deriv sinaliza rate limit."""
        logger.warning(f"🛑 RATE LIMIT DETECTADO ({error_message}). Pausando 60 segundos para resfriamento...")
        await asyncio.sleep(60)
        logger.info("✅ Resfriamento concluído. Retomando operações...")

    async def recv_next(self, ws, expected_msg_type: Optional[str] = None, req_id: Optional[int] = None, timeout: float = 12.0) -> Optional[dict]:
        """Consome mensagens do WebSocket de forma orientada a eventos sem dessincronização."""
        start_time = asyncio.get_event_loop().time()
        while self.is_running:
            remaining = timeout - (asyncio.get_event_loop().time() - start_time)
            if remaining <= 0:
                logger.warning(f"Timeout aguardando {expected_msg_type or req_id}")
                return None

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                m = json.loads(raw)
            except asyncio.TimeoutError:
                return None

            if m.get("msg_type") == "ping":
                continue

            if "error" in m:
                err = m["error"]
                err_code = str(err.get("code", ""))
                err_msg = str(err.get("message", ""))
                if err_code in ("RateLimit", "TooManyRequests") or "rate limit" in err_msg.lower() or "too many" in err_msg.lower():
                    await self.handle_rate_limit_backoff(err_msg)
                elif "maximum daily turnover" in err_msg.lower() or "turnover limit" in err_msg.lower():
                    self.risk.is_stopped = True
                    self.risk.stop_reason = f"Limite diário de turnover atingido: {err_msg}"
                    logger.error(f"🛑 {self.risk.stop_reason}")
                return m

            if req_id is not None and m.get("req_id") == req_id:
                return m
            if expected_msg_type and m.get("msg_type") == expected_msg_type:
                return m
            if expected_msg_type is None and req_id is None:
                return m

        return None

    async def cleanup_orphaned_positions_once(self, ws):
        """Executado APENAS UMA VEZ na conexão para limpar contratos remanescentes (Zero Polling)."""
        try:
            await ws.send(json.dumps({"portfolio": 1, "req_id": 999}))
            res = await self.recv_next(ws, expected_msg_type="portfolio", req_id=999, timeout=5.0)
            if res and res.get("msg_type") == "portfolio":
                contracts = res.get("portfolio", {}).get("contracts", [])
                if contracts:
                    logger.info(f"Identificado(s) {len(contracts)} contrato(s) órfão(s). Liquidando...")
                    for c in contracts:
                        cid = c.get("contract_id")
                        await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 998}))
                        await asyncio.sleep(1)
        except Exception as e:
            logger.debug(f"Aviso na checagem inicial de portfolio: {e}")

    async def execute_trade(self, ws):
        """Executa um ciclo completo de trade com monitoramento de ticks e Cash Out (Zero Polling)."""
        if not self.risk.can_trade():
            return

        logger.info(f"⚡ Iniciando ciclo de trade ({self.active_asset_name} [{self.active_symbol}] ACCU {self.config.growth_rate*100:.0f}%/tick | Stake: ${self.config.stake_amount:.2f})...")

        # 1. Solicita proposta streaming
        proposal_req = {
            "proposal": 1,
            "subscribe": 1,
            "amount": self.config.stake_amount,
            "basis": "stake",
            "contract_type": "ACCU",
            "currency": "USD",
            "underlying_symbol": self.active_symbol,
            "growth_rate": self.config.growth_rate,
            "req_id": 10
        }
        await ws.send(json.dumps(proposal_req))

        prop_msg = await self.recv_next(ws, expected_msg_type="proposal", req_id=10)
        if not prop_msg or "error" in prop_msg:
            err = prop_msg.get("error", {}).get("message", "Sem resposta") if prop_msg else "Timeout"
            logger.error(f"Erro na proposta: {err}")
            await asyncio.sleep(5)
            return

        proposal_id = prop_msg["proposal"]["id"]
        sub_id = prop_msg.get("subscription", {}).get("id")

        # Sincronização Inteligente de Ciclo (Esperar bater na parede)
        if self.config.wait_cycle_reset:
            prev_cycle_tick = None
            cycle_ready = False

            while not cycle_ready and self.is_running and self.risk.can_trade():
                p_data = prop_msg.get("proposal", {})
                p_details = p_data.get("contract_details", {})
                tsi = p_details.get("ticks_stayed_in")

                if tsi and len(tsi) == 1:
                    cur_tick = tsi[0]

                    if cur_tick <= self.config.max_entry_tick:
                        cycle_ready = True
                        logger.info(f"⚡ Ciclo virgem detectado ({cur_tick}º tick)! Disparando entrada...")
                        break

                    if prev_cycle_tick is not None and cur_tick < prev_cycle_tick:
                        cycle_ready = True
                        logger.info(f"💥 Parede atingida após {prev_cycle_tick} ticks! Novo ciclo iniciado ({cur_tick}T). Disparando compra...")
                        break

                    prev_cycle_tick = cur_tick
                    logger.info(f"⏳ Aguardando ciclo resetar... (Ativo no {cur_tick}º tick sem bater na parede)")

                prop_msg = await self.recv_next(ws, expected_msg_type="proposal")
                if not prop_msg or "error" in prop_msg:
                    break
                proposal_id = prop_msg.get("proposal", {}).get("id", proposal_id)
                sub_id = prop_msg.get("subscription", {}).get("id", sub_id)

            if not cycle_ready:
                if sub_id:
                    await ws.send(json.dumps({"forget": sub_id}))
                return

        spot = prop_msg.get("proposal", {}).get("spot")
        logger.info(f"Proposta aprovada (ID: {proposal_id[:8]}... | Spot: {spot})")

        if sub_id:
            await ws.send(json.dumps({"forget": sub_id}))

        # 2. Compra do Contrato
        buy_req = {
            "buy": proposal_id,
            "price": self.config.stake_amount,
            "req_id": 20
        }
        await ws.send(json.dumps(buy_req))

        buy_msg = await self.recv_next(ws, expected_msg_type="buy", req_id=20)
        if not buy_msg or "error" in buy_msg:
            err = buy_msg.get("error", {}).get("message", "Falha na compra") if buy_msg else "Timeout"
            logger.error(f"Falha na compra: {err}")
            await asyncio.sleep(3)
            return

        contract_id = buy_msg["buy"]["contract_id"]
        self.current_contract_id = contract_id
        logger.info(f"🛒 Ordem Comprada! Contrato #{contract_id}")

        # 3. Acompanhamento em tempo real via Stream Push
        poc_req = {
            "proposal_open_contract": 1,
            "contract_id": contract_id,
            "subscribe": 1,
            "req_id": 30
        }
        await ws.send(json.dumps(poc_req))

        poc_sub_id = None
        trade_finished = False

        while not trade_finished and self.is_running:
            msg = await self.recv_next(ws)
            if not msg:
                continue

            if msg.get("msg_type") != "proposal_open_contract":
                continue

            contract = msg.get("proposal_open_contract", {})
            poc_sub_id = msg.get("subscription", {}).get("id")

            tick_stream = contract.get("tick_stream", [])
            tick_count = len(tick_stream)
            current_profit = float(contract.get("profit", 0.0))
            is_valid_to_sell = contract.get("is_valid_to_sell", 0)
            is_sold = contract.get("is_sold", 0)
            status = contract.get("status")

            logger.info(f"  👉 Tick #{tick_count} | Lucro: ${current_profit:+.2f} | Status: {status}")

            # Se o contrato encerrou (bateu barreira ou take profit)
            if is_sold:
                profit_final = float(contract.get("profit", 0.0))
                self.risk.register_trade(profit_final)
                self.current_contract_id = None
                trade_finished = True
                break

            # Se atingiu a meta de ticks e pode vender
            if tick_count >= self.config.exit_ticks and is_valid_to_sell:
                logger.info(f"🎯 Meta de {self.config.exit_ticks} Ticks atingida! Disparando CASH OUT...")
                sell_req = {"sell": contract_id, "price": 0, "req_id": 40}
                await ws.send(json.dumps(sell_req))

                sell_msg = await self.recv_next(ws, expected_msg_type="sell", req_id=40)
                if sell_msg and "sell" in sell_msg:
                    sold_for = float(sell_msg["sell"]["sold_for"])
                    net_profit = sold_for - self.config.stake_amount
                    logger.info(f"💰 CASH OUT CONFIRMADO: Recebido ${sold_for:.2f} (Lucro: ${net_profit:+.2f})")
                    self.risk.register_trade(net_profit)
                trade_finished = True
                self.current_contract_id = None
                break

        if poc_sub_id:
            await ws.send(json.dumps({"forget": poc_sub_id}))

    async def run(self):
        """Loop principal resiliente: reconecta automaticamente se a conexão cair."""
        print("\n" + "=" * 80)
        print(" INICIANDO DERIV ACCUMULATOR BOT (SELEÇÃO INTELIGENTE DE ATIVO)")
        print(f" Conta: {self.config.account_id}")
        print(f" Meta Diária (Take Profit) : +${self.config.daily_take_profit_usd:.2f}")
        print(f" Limite Diário (Stop Loss) : -${self.config.daily_stop_loss_usd:.2f}")
        print(f" Estratégia : Cash Out automático após {self.config.exit_ticks} Ticks (Stake: ${self.config.stake_amount:.2f})")
        print(" Modo Adaptativo: O robô escaneia e elege o ativo com maior sobrevivência.")
        print("=" * 80 + "\n")

        # Seleciona o melhor ativo antes de começar
        await self.update_best_asset()

        trades_since_last_scan = 0

        while self.risk.can_trade() and self.is_running:
            try:
                otp_url = self.get_otp_url()
                logger.info(f"Conectado ao canal de trading para {self.active_asset_name} ({self.active_symbol})...")

                async with websockets.connect(
                    otp_url,
                    ping_interval=None,
                ) as ws:
                    self.active_ws = ws
                    hb_task = asyncio.create_task(self.heartbeat(ws))

                    # Limpeza única de contratos órfãos apenas na conexão (Zero Polling)
                    await self.cleanup_orphaned_positions_once(ws)

                    while self.risk.can_trade() and self.is_running:
                        await self.execute_trade(ws)
                        trades_since_last_scan += 1

                        # A cada 5 trades, reavalia se outro ativo virou o mais seguro
                        if trades_since_last_scan >= 5 and self.config.auto_select_best_asset:
                            await self.update_best_asset()
                            trades_since_last_scan = 0

                        if self.risk.can_trade() and self.is_running:
                            logger.info("⏳ Aguardando 5 segundos para o próximo ciclo...")
                            await asyncio.sleep(5)

                    hb_task.cancel()

            except (websockets.ConnectionClosed, ConnectionError) as e:
                if not self.risk.can_trade() or not self.is_running:
                    break
                logger.warning(f"⚠️ Conexão oscilou ({e}). Reconectando com novo OTP em 5 segundos...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Erro inesperado no loop: {e}")
                await asyncio.sleep(5)

        print("\n" + "=" * 80)
        print(f" 🛑 SESSÃO FINALIZADA: {self.risk.stop_reason}")
        print(f" Total de Operações: {self.risk.total_trades}")
        print(f" Vitórias: {self.risk.wins} | Derrotas: {self.risk.losses}")
        print(f" Saldo Líquido Final: ${self.risk.daily_pnl:+.2f}")
        print("=" * 80 + "\n")


def handle_shutdown(bot):
    print("\n[AVISO] Sinal de encerramento recebido (Ctrl+C). Finalizando graciosamente...")
    bot.is_running = False


if __name__ == "__main__":
    cfg = BotConfig()
    bot = AccumulatorBot(cfg)

    # Captura Ctrl+C para parada graciosa
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        print("\nRobô interrompido pelo usuário. Até a próxima sessão!")
