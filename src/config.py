import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BotConfig:
    # Credenciais Deriv
    token: str = os.getenv("DERIV_API_TOKEN", "")
    app_id: str = os.getenv("DERIV_APP_ID", "")
    account_id: str = os.getenv("DERIV_ACCOUNT_ID", "")  # Ex: VRTC... para conta Demo

    # Configurações do Ativo e Contrato
    symbol: str = os.getenv("SYMBOL", "R_10")
    auto_select_best_asset: bool = os.getenv("AUTO_SELECT_BEST_ASSET", "true").lower() in ("true", "1", "yes")
    contract_type: str = "ACCU"
    growth_rate: float = float(os.getenv("GROWTH_RATE", "0.01"))  # 1% ao tick
    stake_amount: float = float(os.getenv("STAKE_AMOUNT", "1.00"))  # $1.00 por ordem

    # Lógica de Saída Rápida (Cash Out)
    exit_ticks: int = int(os.getenv("EXIT_TICKS", "2"))  # Sai com lucro no 2º tick!
    take_profit_usd: float = float(os.getenv("TAKE_PROFIT_USD", "0.05"))  # Proteção nativa

    # Gestão de Risco Diária (Travas Rígidas)
    daily_stop_loss_usd: float = float(os.getenv("DAILY_STOP_LOSS_USD", "2.00"))  # Limite máximo de perda no dia
    daily_take_profit_usd: float = float(os.getenv("DAILY_TAKE_PROFIT_USD", "2.00"))  # Meta máxima de ganho no dia
    max_consecutive_losses: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "2"))  # Pausa após 2 derrotas

    # Endpoints Oficiais v2
    rest_base_url: str = "https://api.derivws.com"
    public_ws_url: str = "wss://api.derivws.com/trading/v1/options/ws/public"
