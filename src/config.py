import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    # Credenciais Deriv - Conta Primária (Real por padrão)
    token: str = os.getenv("DERIV_PRIMARY_API_TOKEN", os.getenv("DERIV_API_TOKEN", ""))
    app_id: str = os.getenv("DERIV_PRIMARY_APP_ID", os.getenv("DERIV_APP_ID", "34XANuYNS8JMRsKZsNfFz"))
    account_id: str = os.getenv("DERIV_PRIMARY_ACCOUNT_ID", os.getenv("DERIV_ACCOUNT_ID", ""))

    # Credenciais Deriv - Conta Secundária (Escudo / Demo por padrão)
    secondary_token: str = os.getenv("DERIV_SECONDARY_API_TOKEN", os.getenv("DERIV_API_TOKEN", ""))
    secondary_app_id: str = os.getenv("DERIV_SECONDARY_APP_ID", os.getenv("DERIV_APP_ID", "34XANuYNS8JMRsKZsNfFz"))
    secondary_account_id: str = os.getenv("DERIV_SECONDARY_ACCOUNT_ID", os.getenv("DERIV_ACCOUNT_ID", ""))

    # Modos de Operação:
    # - "shield_combined": Opera na Conta Secundária (Demo) e após X derrotas dispara sniper na Conta Primária (Real)
    # - "primary_only": Opera exclusivamente na Conta Primária (Real)
    # - "secondary_only": Opera exclusivamente na Conta Secundária (Demo)
    operation_mode: str = os.getenv("OPERATION_MODE", "secondary_only")
    shield_trigger_losses: int = int(os.getenv("SHIELD_TRIGGER_LOSSES", "2"))  # X derrotas na demo para armar a Real

    # Ação pós-loss (Modos Escudo e Isolado):
    # - "return_to_shield"      : Tiro Único Conservador (Volta imediatamente ao Escudo Demo ou mantém stake)
    # - "recovery_martingale"   : Multiplicador Clássico (ex: 2.0x por X tentativas)
    # - "fractional_martingale" : Martingale Parcelado (Dilui o prejuízo acumulado em X parcelas baseadas no payout)
    primary_loss_action: str = os.getenv("PRIMARY_LOSS_ACTION", "return_to_shield")
    primary_recovery_max_steps: int = int(os.getenv("PRIMARY_RECOVERY_MAX_STEPS", "1"))
    primary_martingale_multiplier: float = float(os.getenv("PRIMARY_MARTINGALE_MULTIPLIER", "2.0"))

    # Parâmetros do Martingale Parcelado
    fractional_installments: int = int(os.getenv("FRACTIONAL_INSTALLMENTS", "2"))
    include_base_profit: bool = os.getenv("INCLUDE_BASE_PROFIT", "true").lower() in ("true", "1", "yes")
    max_loss_recovery_cap: float = float(os.getenv("MAX_LOSS_RECOVERY_CAP", "20.00"))

    # Configurações do Ativo e Contrato
    symbol: str = os.getenv("SYMBOL", "R_10")
    auto_select_best_asset: bool = os.getenv("AUTO_SELECT_BEST_ASSET", "true").lower() in ("true", "1", "yes")
    contract_type: str = "ACCU"
    growth_rate: float = float(os.getenv("GROWTH_RATE", "0.01"))  # 1% ao tick
    stake_amount: float = float(os.getenv("STAKE_AMOUNT", "1.00"))  # $1.00 por ordem

    # Lógica de Saída Rápida (Cash Out)
    exit_ticks: int = int(os.getenv("EXIT_TICKS", "2"))  # Sai com lucro no 2º tick!
    take_profit_usd: float = float(os.getenv("TAKE_PROFIT_USD", "0.05"))  # Proteção nativa

    # Gestão de Risco por Sessão
    session_stop_loss_usd: float = float(os.getenv("SESSION_STOP_LOSS_USD", "5.00"))  # Limite máximo de perda na sessão
    session_take_profit_usd: float = float(os.getenv("SESSION_TAKE_PROFIT_USD", "5.00"))  # Meta máxima de ganho na sessão

    # Gestão de Risco Diária (Travas Rígidas Globais)
    daily_stop_loss_usd: float = float(os.getenv("DAILY_STOP_LOSS_USD", "20.00"))  # Limite máximo de perda no dia
    daily_take_profit_usd: float = float(os.getenv("DAILY_TAKE_PROFIT_USD", "20.00"))  # Meta máxima de ganho no dia
    max_consecutive_losses: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "20"))  # Pausa após N derrotas

    # Sincronização Inteligente de Ciclo (Esperar bater na parede)
    wait_cycle_reset: bool = os.getenv("WAIT_CYCLE_RESET", "true").lower() in ("true", "1", "yes")
    max_entry_tick: int = int(os.getenv("MAX_ENTRY_TICK", "1"))

    # Endpoints Oficiais v2
    rest_base_url: str = "https://api.derivws.com"
    public_ws_url: str = "wss://api.derivws.com/trading/v1/options/ws/public"
