"""
Módulo de Gerenciamento de Risco Rigoroso (Hard Stops) e Histórico de Streaks.
Registra a frequência de ocorrência de cada tamanho de sequência de vitórias e derrotas.
Exemplo:
- Sequência de 1 Derrota: ocorreu 8 vezes -> 1L (8x)
- Sequência de 3 Derrotas seguidas: ocorreu 5 vezes -> 3L (5x)
- Sequência de 8 Vitórias seguidas: ocorreu 3 vezes -> 8W (3x)
"""

import logging
from typing import Dict, List, Any
from config import BotConfig

logger = logging.getLogger("RiskManager")


class RiskManager:
    def __init__(self, config: BotConfig):
        self.config = config
        self.daily_pnl: float = 0.0
        self.total_trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        
        # Streaks atuais
        self.current_win_streak: int = 0
        self.current_loss_streak: int = 0
        
        # Recordes máximos da sessão
        self.max_win_streak: int = 0
        self.max_loss_streak: int = 0

        # Histograma de Frequência de Streaks: {tamanho_da_sequencia: quantidade_de_vezes}
        # Ex: {1: 8, 2: 3, 3: 5} -> 3 derrotas seguidas ocorreu 5 vezes
        self.win_streak_counts: Dict[int, int] = {}
        self.loss_streak_counts: Dict[int, int] = {}

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

        # Trava 3: Perdas Consecutivas Imediatas (Circuit Breaker)
        if self.current_loss_streak >= self.config.max_consecutive_losses:
            self.is_stopped = True
            self.stop_reason = f"CIRCUIT BREAKER: {self.current_loss_streak} perdas consecutivas. Parando para proteção."
            logger.warning(f"⚠️ {self.stop_reason}")
            return False

        return True

    def register_trade(self, profit_usd: float):
        self.total_trades += 1
        self.daily_pnl += profit_usd

        if profit_usd > 0:
            self.wins += 1

            # Se vínhamos de uma sequência de derrotas, essa sequência terminou e foi registrada
            if self.current_loss_streak > 0:
                self.loss_streak_counts[self.current_loss_streak] = (
                    self.loss_streak_counts.get(self.current_loss_streak, 0) + 1
                )
                self.current_loss_streak = 0

            # Incrementa sequência atual de vitórias
            self.current_win_streak += 1
            if self.current_win_streak > self.max_win_streak:
                self.max_win_streak = self.current_win_streak

            logger.info(f"✅ VITÓRIA: +${profit_usd:.2f} | PnL: ${self.daily_pnl:+.2f} | Streak Atual: {self.current_win_streak}W")
        else:
            self.losses += 1

            # Se vínhamos de uma sequência de vitórias, essa sequência terminou e foi registrada
            if self.current_win_streak > 0:
                self.win_streak_counts[self.current_win_streak] = (
                    self.win_streak_counts.get(self.current_win_streak, 0) + 1
                )
                self.current_win_streak = 0

            # Incrementa sequência atual de derrotas
            self.current_loss_streak += 1
            if self.current_loss_streak > self.max_loss_streak:
                self.max_loss_streak = self.current_loss_streak

            logger.warning(f"❌ DERROTA: ${profit_usd:.2f} | PnL: ${self.daily_pnl:+.2f} | Streak Atual: {self.current_loss_streak}L")

    def get_streaks_summary(self) -> Dict[str, Any]:
        """
        Retorna as frequências ordenadas para o Dashboard.
        Inclui também a sequência atual em andamento na contagem para visualização em tempo real.
        """
        # Clona os dicionários de histórico
        win_counts = dict(self.win_streak_counts)
        loss_counts = dict(self.loss_streak_counts)

        # Se houver uma sequência em andamento, contabiliza temporariamente para o usuário ver ao vivo
        if self.current_win_streak > 0:
            win_counts[self.current_win_streak] = win_counts.get(self.current_win_streak, 0) + 1
        if self.current_loss_streak > 0:
            loss_counts[self.current_loss_streak] = loss_counts.get(self.current_loss_streak, 0) + 1

        # Formata listas ordenadas pelo tamanho da sequência (ex: 1, 2, 3...)
        # Cada item: {"length": 3, "count": 5, "label": "3L (5x)"}
        sorted_losses = [
            {"streak": k, "count": v, "label": f"{k}L ({v}x)"}
            for k, v in sorted(loss_counts.items())
        ]
        sorted_wins = [
            {"streak": k, "count": v, "label": f"{k}W ({v}x)"}
            for k, v in sorted(win_counts.items(), reverse=True)
        ]

        current_type = "W" if self.current_win_streak > 0 else ("L" if self.current_loss_streak > 0 else "-")
        current_val = self.current_win_streak if self.current_win_streak > 0 else self.current_loss_streak

        return {
            "current_streak_type": current_type,
            "current_streak_val": current_val,
            "max_win_streak": self.max_win_streak,
            "max_loss_streak": self.max_loss_streak,
            "loss_streaks_list": sorted_losses,
            "win_streaks_list": sorted_wins
        }
