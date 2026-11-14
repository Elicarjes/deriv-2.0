"""
Módulo de Gerenciamento de Risco Rigoroso (Hard Stops).
Impede o robô de continuar operando se atingir a meta diária ou o limite de perda.
"""

import logging
from config import BotConfig

logger = logging.getLogger("RiskManager")


class RiskManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.daily_pnl: float = 0.0
        self.total_trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.consecutive_losses: int = 0
        self.is_stopped: bool = False
        self.stop_reason: str = ""

    def can_trade(self) -> bool:
        if self.is_stopped:
            return False

        # Trava 1: Stop Loss Diário
        if self.daily_pnl <= -abs(self.config.daily_stop_loss_usd):
            self.is_stopped = True
            self.stop_reason = f"STOP LOSS DIÁRIO ATINGIDO: Saldo atual ${self.daily_pnl:+.2f} (Limite: -${self.config.daily_stop_loss_usd:.2f})"
            logger.warning(f"🛑 {self.stop_reason}")
            return False

        # Trava 2: Take Profit Diário (Meta Batida)
        if self.daily_pnl >= abs(self.config.daily_take_profit_usd):
            self.is_stopped = True
            self.stop_reason = f"META DIÁRIA BATIDA COM SUCESSO: Saldo atual ${self.daily_pnl:+.2f} (Meta: +${self.config.daily_take_profit_usd:.2f})"
            logger.info(f"🎯 {self.stop_reason}")
            return False

        # Trava 3: Perdas Consecutivas
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            self.is_stopped = True
            self.stop_reason = f"CIRCUIT BREAKER: {self.consecutive_losses} perdas consecutivas. Parando para proteção."
            logger.warning(f"⚠️ {self.stop_reason}")
            return False

        return True

    def register_trade(self, profit_usd: float):
        self.total_trades += 1
        self.daily_pnl += profit_usd

        if profit_usd > 0:
            self.wins += 1
            self.consecutive_losses = 0
            logger.info(f"✅ TRADE VITORIOSO: +${profit_usd:.2f} | PnL Acumulado: ${self.daily_pnl:+.2f}")
        else:
            self.losses += 1
            self.consecutive_losses += 1
            logger.warning(f"❌ TRADE COM LOSS: ${profit_usd:.2f} | PnL Acumulado: ${self.daily_pnl:+.2f}")

        win_rate = (self.wins / self.total_trades) * 100 if self.total_trades > 0 else 0
        logger.info(f"📊 Estatísticas: {self.wins}W / {self.losses}L ({win_rate:.1f}% assertividade) | Total: {self.total_trades} trades")
