"""
Módulo de Banco de Dados SQLite para Persistência de Configurações (SettingsDB).
Armazena e recupera os parâmetros operacionais, credenciais PAT, limites de risco
e regras de Martingale / Modo Escudo de forma definitiva e independente de arquivos de texto.
"""

from datetime import datetime
import logging
from pathlib import Path
import sqlite3
from typing import Dict, Any, Optional

logger = logging.getLogger("SettingsDB")


class SettingsDB:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Cria a tabela de configurações e aplica migrações de novas colunas caso necessário."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    growth_rate REAL NOT NULL DEFAULT 0.05,
                    stake_amount REAL NOT NULL DEFAULT 1.00,
                    exit_ticks INTEGER NOT NULL DEFAULT 6,
                    session_stop_loss_usd REAL NOT NULL DEFAULT 5.00,
                    session_take_profit_usd REAL NOT NULL DEFAULT 5.00,
                    daily_stop_loss_usd REAL NOT NULL DEFAULT 20.00,
                    daily_take_profit_usd REAL NOT NULL DEFAULT 20.00,
                    max_consecutive_losses INTEGER NOT NULL DEFAULT 20,
                    wait_cycle_reset INTEGER NOT NULL DEFAULT 1,
                    max_entry_tick INTEGER NOT NULL DEFAULT 1,
                    operation_mode TEXT NOT NULL DEFAULT 'shield_combined',
                    shield_trigger_losses INTEGER NOT NULL DEFAULT 2,
                    primary_loss_action TEXT NOT NULL DEFAULT 'return_to_shield',
                    primary_recovery_max_steps INTEGER NOT NULL DEFAULT 1,
                    primary_martingale_multiplier REAL NOT NULL DEFAULT 2.0,
                    fractional_installments INTEGER NOT NULL DEFAULT 2,
                    include_base_profit INTEGER NOT NULL DEFAULT 1,
                    max_loss_recovery_cap REAL NOT NULL DEFAULT 20.00,
                    primary_token TEXT DEFAULT '',
                    primary_app_id TEXT DEFAULT '',
                    primary_account_id TEXT DEFAULT '',
                    secondary_token TEXT DEFAULT '',
                    secondary_app_id TEXT DEFAULT '',
                    secondary_account_id TEXT DEFAULT '',
                    symbol TEXT NOT NULL DEFAULT 'R_10',
                    auto_select_best_asset INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL DEFAULT ''
                )
            """)

            # Tabela de histórico de auditoria de alterações
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    changed_at TEXT NOT NULL,
                    reason TEXT DEFAULT '',
                    config_json TEXT NOT NULL
                )
            """)
            conn.commit()

        # Verifica e aplica colunas que possam faltar em bancos já existentes
        self._ensure_columns()

    def _ensure_columns(self):
        """Garante que todas as colunas existem na tabela, adicionando-as dinamicamente se necessário."""
        expected_columns = {
            "growth_rate": "REAL NOT NULL DEFAULT 0.05",
            "stake_amount": "REAL NOT NULL DEFAULT 1.00",
            "exit_ticks": "INTEGER NOT NULL DEFAULT 6",
            "session_stop_loss_usd": "REAL NOT NULL DEFAULT 5.00",
            "session_take_profit_usd": "REAL NOT NULL DEFAULT 5.00",
            "daily_stop_loss_usd": "REAL NOT NULL DEFAULT 20.00",
            "daily_take_profit_usd": "REAL NOT NULL DEFAULT 20.00",
            "max_consecutive_losses": "INTEGER NOT NULL DEFAULT 20",
            "wait_cycle_reset": "INTEGER NOT NULL DEFAULT 1",
            "max_entry_tick": "INTEGER NOT NULL DEFAULT 1",
            "operation_mode": "TEXT NOT NULL DEFAULT 'shield_combined'",
            "shield_trigger_losses": "INTEGER NOT NULL DEFAULT 2",
            "primary_loss_action": "TEXT NOT NULL DEFAULT 'return_to_shield'",
            "primary_recovery_max_steps": "INTEGER NOT NULL DEFAULT 1",
            "primary_martingale_multiplier": "REAL NOT NULL DEFAULT 2.0",
            "fractional_installments": "INTEGER NOT NULL DEFAULT 2",
            "include_base_profit": "INTEGER NOT NULL DEFAULT 1",
            "max_loss_recovery_cap": "REAL NOT NULL DEFAULT 20.00",
            "primary_token": "TEXT DEFAULT ''",
            "primary_app_id": "TEXT DEFAULT ''",
            "primary_account_id": "TEXT DEFAULT ''",
            "secondary_token": "TEXT DEFAULT ''",
            "secondary_app_id": "TEXT DEFAULT ''",
            "secondary_account_id": "TEXT DEFAULT ''",
            "symbol": "TEXT NOT NULL DEFAULT 'R_10'",
            "auto_select_best_asset": "INTEGER NOT NULL DEFAULT 1",
            "updated_at": "TEXT NOT NULL DEFAULT ''"
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(settings)")
            existing = {row["name"] for row in cursor.fetchall()}

            for col, col_def in expected_columns.items():
                if col not in existing:
                    logger.info(f"Adicionando coluna faltante '{col}' ao banco de dados SQLite...")
                    cursor.execute(f"ALTER TABLE settings ADD COLUMN {col} {col_def}")
            conn.commit()

    def seed_if_empty(self, initial_values: Dict[str, Any]):
        """Insere o primeiro registro se o banco de dados estiver vazio."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS total FROM settings WHERE id = 1")
            row = cursor.fetchone()
            if row and row["total"] == 0:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                fields = [
                    "id", "growth_rate", "stake_amount", "exit_ticks",
                    "session_stop_loss_usd", "session_take_profit_usd",
                    "daily_stop_loss_usd", "daily_take_profit_usd", "max_consecutive_losses",
                    "wait_cycle_reset", "max_entry_tick", "operation_mode",
                    "shield_trigger_losses", "primary_loss_action", "primary_recovery_max_steps",
                    "primary_martingale_multiplier", "fractional_installments", "include_base_profit",
                    "max_loss_recovery_cap", "primary_token", "primary_app_id",
                    "primary_account_id", "secondary_token", "secondary_app_id",
                    "secondary_account_id", "symbol", "auto_select_best_asset", "updated_at"
                ]
                placeholders = ", ".join(["?"] * len(fields))
                values = [
                    1,
                    float(initial_values.get("growth_rate", 0.05)),
                    float(initial_values.get("stake_amount", 1.00)),
                    int(initial_values.get("exit_ticks", 6)),
                    float(initial_values.get("session_stop_loss_usd", 5.00)),
                    float(initial_values.get("session_take_profit_usd", 5.00)),
                    float(initial_values.get("daily_stop_loss_usd", 20.00)),
                    float(initial_values.get("daily_take_profit_usd", 20.00)),
                    int(initial_values.get("max_consecutive_losses", 20)),
                    1 if initial_values.get("wait_cycle_reset", True) else 0,
                    int(initial_values.get("max_entry_tick", 1)),
                    str(initial_values.get("operation_mode", "shield_combined")),
                    int(initial_values.get("shield_trigger_losses", 2)),
                    str(initial_values.get("primary_loss_action", "return_to_shield")),
                    int(initial_values.get("primary_recovery_max_steps", 1)),
                    float(initial_values.get("primary_martingale_multiplier", 2.0)),
                    int(initial_values.get("fractional_installments", 2)),
                    1 if initial_values.get("include_base_profit", True) else 0,
                    float(initial_values.get("max_loss_recovery_cap", 20.00)),
                    str(initial_values.get("primary_token", "")),
                    str(initial_values.get("primary_app_id", "")),
                    str(initial_values.get("primary_account_id", "")),
                    str(initial_values.get("secondary_token", "")),
                    str(initial_values.get("secondary_app_id", "")),
                    str(initial_values.get("secondary_account_id", "")),
                    str(initial_values.get("symbol", "R_10")),
                    1 if initial_values.get("auto_select_best_asset", True) else 0,
                    now_str
                ]
                cursor.execute(f"INSERT INTO settings ({', '.join(fields)}) VALUES ({placeholders})", values)
                conn.commit()
                logger.info("📦 Banco de dados SQLite semeado com configurações iniciais com sucesso.")

    def get_settings(self) -> Dict[str, Any]:
        """Recupera as configurações ativas do banco SQLite."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM settings WHERE id = 1")
            row = cursor.fetchone()
            if not row:
                return {}
            data = dict(row)
            data["wait_cycle_reset"] = bool(data.get("wait_cycle_reset", 1))
            data["auto_select_best_asset"] = bool(data.get("auto_select_best_asset", 1))
            data["include_base_profit"] = bool(data.get("include_base_profit", 1))
            return data

    def save_settings(self, updates: Dict[str, Any], reason: str = "Ajuste manual no painel") -> Dict[str, Any]:
        """Salva as alterações no banco SQLite com auditoria de versão."""
        current = self.get_settings()
        if not current:
            self.seed_if_empty(updates)
            current = self.get_settings()

        # Mescla os valores atualizados
        merged = {**current, **updates}
        merged["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        allowed_keys = [
            "growth_rate", "stake_amount", "exit_ticks",
            "session_stop_loss_usd", "session_take_profit_usd",
            "daily_stop_loss_usd", "daily_take_profit_usd", "max_consecutive_losses",
            "wait_cycle_reset", "max_entry_tick", "operation_mode",
            "shield_trigger_losses", "primary_loss_action", "primary_recovery_max_steps",
            "primary_martingale_multiplier", "fractional_installments", "include_base_profit",
            "max_loss_recovery_cap", "primary_token", "primary_app_id",
            "primary_account_id", "secondary_token", "secondary_app_id",
            "secondary_account_id", "symbol", "auto_select_best_asset", "updated_at"
        ]

        set_clauses = []
        values = []
        for key in allowed_keys:
            if key in merged:
                set_clauses.append(f"{key} = ?")
                val = merged[key]
                if isinstance(val, bool):
                    val = 1 if val else 0
                values.append(val)

        if not set_clauses:
            return current

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE settings SET {', '.join(set_clauses)} WHERE id = 1", values)

            # Grava histórico de versão
            import json
            cursor.execute(
                "INSERT INTO settings_history (changed_at, reason, config_json) VALUES (?, ?, ?)",
                (merged["updated_at"], reason, json.dumps(merged))
            )
            conn.commit()

        logger.info(f"💾 Configurações salvas no SQLite com sucesso ({reason}).")
        return self.get_settings()
