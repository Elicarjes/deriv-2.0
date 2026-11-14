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

    async def ensure_no_open_positions(self, ws):
        """Garante que qualquer contrato anterior esteja totalmente liquidado antes de nova compra."""
        while self.is_running:
            await ws.send(json.dumps({"portfolio": 1, "req_id": 5}))
            res = json.loads(await ws.recv())
            # Se for resposta de ping/outra, procura a resposta do portfolio
            if res.get("msg_type") == "portfolio":
                contracts = res.get("portfolio", {}).get("contracts", [])
                if not contracts:
                    return True
                logger.info(f"Aguardando liquidação de {len(contracts)} contrato(s) em aberto na Deriv...")
                for c in contracts:
                    cid = c.get("contract_id")
                    # Tenta forçar o sell se estiver aberto há tempo
                    await ws.send(json.dumps({"sell": cid, "price": 0, "req_id": 6}))
                await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)

    async def execute_trade(self, ws):
        """Executa um ciclo completo de trade com monitoramento de ticks e Cash Out."""
        if not self.risk.can_trade():
            return

        # Garante que a conta não tem posição aberta concorrente
        await self.ensure_no_open_positions(ws)

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

        proposal_id = None
        sub_id = None

        while not proposal_id and self.is_running:
            msg = json.loads(await ws.recv())
            if msg.get("msg_type") == "proposal" and "proposal" in msg:
                proposal_id = msg["proposal"]["id"]
                sub_id = msg.get("subscription", {}).get("id")
                spot = msg["proposal"].get("spot")
                logger.info(f"Proposta aprovada (ID: {proposal_id[:8]}... | Spot: {spot})")
                break
            elif "error" in msg:
                logger.error(f"Erro na proposta: {msg['error']['message']}")
                # Se há posições abertas órfãs, espera 5 segundos
                await asyncio.sleep(5)
                return

        if sub_id:
            await ws.send(json.dumps({"forget": sub_id}))

        # 2. Compra do Contrato
        buy_req = {
            "buy": proposal_id,
            "price": self.config.stake_amount,
            "req_id": 20
        }
        await ws.send(json.dumps(buy_req))

        contract_id = None
        while not contract_id and self.is_running:
            msg = json.loads(await ws.recv())
            if msg.get("msg_type") == "buy" and "buy" in msg:
                contract_id = msg["buy"]["contract_id"]
                self.current_contract_id = contract_id
                logger.info(f"🛒 Ordem Comprada! Contrato #{contract_id}")
                break
            elif "error" in msg:
                logger.error(f"Falha na compra: {msg['error']['message']}")
                return

        # 3. Acompanhamento em tempo real
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
            msg = json.loads(await ws.recv())
            
            # Trata respostas de ping se chegarem
            if msg.get("msg_type") == "ping":
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

                # Aguarda confirmação do Cash Out
                while True:
                    sell_msg = json.loads(await ws.recv())
                    if sell_msg.get("msg_type") == "sell":
                        sold_for = float(sell_msg["sell"]["sold_for"])
                        net_profit = sold_for - self.config.stake_amount
                        logger.info(f"💰 CASH OUT CONFIRMADO: Recebido ${sold_for:.2f} (Lucro: ${net_profit:+.2f})")
                        self.risk.register_trade(net_profit)
                        self.current_contract_id = None
                        trade_finished = True
                        break
                    elif "error" in sell_msg:
                        logger.warning(f"Aviso de venda: {sell_msg['error']['message']}")
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
