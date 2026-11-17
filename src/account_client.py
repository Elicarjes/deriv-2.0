"""
Módulo de Cliente de Conta Deriv (AccountClient).
Permite conectar e gerenciar múltiplas contas (Primária e Secundária/Escudo)
de forma desacoplada, independente e orientada a eventos.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict, Any

logger = logging.getLogger("AccountClient")


class AccountClient:
    def __init__(
        self,
        account_role: str,  # "primary" ou "secondary"
        name: str = "",
        token: str = "",
        app_id: str = "",
        account_id: str = "",
        rest_base_url: str = "https://api.derivws.com"
    ):
        self.account_role = account_role
        self._name = name
        self.token = token.strip() if token else ""
        self.app_id = str(app_id).strip() if app_id else ""
        self.account_id = str(account_id).strip() if account_id else ""
        self.rest_base_url = rest_base_url
        self.balance: float = 0.0
        self.is_connected: bool = False
        self.last_error: str = ""

    @property
    def name(self) -> str:
        role_title = "Conta Primária" if self.account_role == "primary" else ("Conta Secundária (Escudo)" if self.account_role == "secondary" else "Conta")
        return f"{role_title} ({self.account_type})"

    @name.setter
    def name(self, val: str):
        self._name = val

    @property
    def account_type(self) -> str:
        aid = self.account_id.upper()
        if "DOT" in aid or "VRTC" in aid or "DEMO" in aid:
            return "Demo"
        elif "ROT" in aid or "REAL" in aid or "CR" in aid:
            return "Real"
        return "Demo" if not self.account_id else "Real"

    def is_configured(self) -> bool:
        return bool(self.token and self.account_id)

    def fetch_available_accounts(self) -> list:
        """Busca todas as contas (Real e Demo) associadas a este token via REST API."""
        if not self.token or not self.app_id:
            return []
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Deriv-App-ID": str(self.app_id),
                "User-Agent": "Mozilla/5.0"
            }
            url = f"{self.rest_base_url}/trading/v1/options/accounts"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"Erro ao listar contas disponíveis ({self.name}): {e}")
            return []

    def fetch_balance(self) -> float:
        """Busca o saldo inicial da conta via REST API oficial."""
        if not self.is_configured():
            return 0.0
        try:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Deriv-App-ID": str(self.app_id),
                "User-Agent": "Mozilla/5.0"
            }
            url = f"{self.rest_base_url}/trading/v1/options/accounts"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                accounts_list = data.get("data", [])
                for acc in accounts_list:
                    if acc.get("account_id") == self.account_id:
                        self.balance = float(acc.get("balance", 0.0))
                        logger.info(f"💵 Saldo carregado [{self.name}]: ${self.balance:.2f} USD ({self.account_type})")
                        return self.balance
                # Se não encontrou pelo account_id exato, auto-corrige para a primeira correspondente
                if accounts_list:
                    matched_acc = None
                    if self.account_role == "secondary":
                        matched_acc = next((a for a in accounts_list if a.get("account_type") == "demo"), accounts_list[0])
                    else:
                        matched_acc = accounts_list[0]
                    old_id = self.account_id
                    self.account_id = matched_acc.get("account_id", self.account_id)
                    self.balance = float(matched_acc.get("balance", 0.0))
                    logger.info(f"🔄 Auto-alinhamento de conta [{self.name}]: ID corrigido de '{old_id}' para '{self.account_id}' (Saldo: ${self.balance:.2f})")
                    return self.balance
        except Exception as e:
            self.last_error = str(e)
            logger.warning(f"Aviso ao buscar saldo da {self.name} ({self.account_id}): {e}")
        return self.balance

    def get_otp_url(self) -> str:
        """Solicita OTP para conexão WebSocket autenticada dedicada, com auto-recuperação."""
        if not self.token:
            raise ValueError(f"{self.name} não possui Token PAT configurado.")

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Deriv-App-ID": str(self.app_id),
            "User-Agent": "Mozilla/5.0"
        }

        # Tentativa inicial com a conta atual
        if self.account_id:
            try:
                otp_url = f"{self.rest_base_url}/trading/v1/options/accounts/{self.account_id}/otp"
                req = urllib.request.Request(otp_url, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["data"]["url"]
            except urllib.error.HTTPError as he:
                if he.code != 404:
                    raise
                logger.warning(f"⚠️ Conta '{self.account_id}' retornou 404 para o token [{self.name}]. Buscando contas válidas...")

        # Se não tem account_id ou deu 404: busca contas ativas na Deriv para este token
        available = self.fetch_available_accounts()
        if not available:
            raise ValueError(f"Nenhuma conta ativa encontrada na Deriv para o token de {self.name}.")

        best_acc = None
        if self.account_role == "secondary":
            best_acc = next((a for a in available if a.get("account_type") == "demo"), available[0])
        else:
            best_acc = available[0]

        self.account_id = best_acc["account_id"]
        logger.info(f"✅ Conta auto-corrigida para '{self.account_id}' [{self.name}]. Gerando OTP...")

        otp_url = f"{self.rest_base_url}/trading/v1/options/accounts/{self.account_id}/otp"
        req = urllib.request.Request(otp_url, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["data"]["url"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.account_role,
            "name": self.name,
            "account_id": self.account_id,
            "account_type": self.account_type,
            "balance": self.balance,
            "is_configured": self.is_configured(),
            "is_connected": self.is_connected
        }
