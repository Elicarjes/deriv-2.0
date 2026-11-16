"""
Módulo de Autenticação e Segurança Multi-Usuário (Auth).
Implementa hashing seguro com PBKDF2-HMAC-SHA256, gerenciamento de tokens de sessão,
criação de usuários e controle de acesso para o modo Multi-Tenant (SaaS).
"""

from datetime import datetime, timedelta
import hashlib
import logging
from pathlib import Path
import secrets
import sqlite3
from typing import Optional, Dict, Any

logger = logging.getLogger("Auth")

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    """Gera hash PBKDF2 com salt aleatório de 16 bytes."""
    salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000
    ).hex()
    return f"{salt}${pw_hash}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verifica uma senha em texto contra o hash armazenado."""
    try:
        salt, pw_hash = stored_hash.split("$", 1)
        test_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            100_000
        ).hex()
        return secrets.compare_digest(pw_hash, test_hash)
    except Exception:
        return False


def init_auth_tables():
    """Inicializa as tabelas de usuários, sessões e garante que o usuário admin exista."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Tabela de Usuários
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0
            )
        """)

        # 2. Tabela de Tokens de Sessão (Login)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
        """)

        # 3. Tabela de Sessões de Trade por Usuário (Substitui sessões compartilhadas)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_trade_sessions (
                session_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_number INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                duration TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                trades_json TEXT NOT NULL,
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # 4. Verifica se a tabela settings possui a coluna user_id
        cursor.execute("PRAGMA table_info(settings)")
        settings_cols = {row["name"] for row in cursor.fetchall()}
        if "user_id" not in settings_cols:
            cursor.execute("ALTER TABLE settings ADD COLUMN user_id INTEGER DEFAULT 1")
            cursor.execute("UPDATE settings SET user_id = 1 WHERE id = 1")
            logger.info("Migração de settings: Coluna user_id adicionada.")

        # 5. Garante que exista ao menos 1 usuário (admin inicial)
        cursor.execute("SELECT id FROM users WHERE id = 1")
        admin_row = cursor.fetchone()
        if not admin_row:
            admin_pw_hash = hash_password("admin123")
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO users (id, username, email, password_hash, name, created_at, is_active, is_admin)
                VALUES (1, 'admin', 'admin@derivquant.com', ?, 'Administrador', ?, 1, 1)
            """, (admin_pw_hash, now_str))
            logger.info("👑 Usuário inicial 'admin' criado com sucesso (senha padrão: admin123).")

        conn.commit()


# Executa criação de tabelas na inicialização
init_auth_tables()


def register_user(username: str, password: str, name: str = "", email: str = "") -> Dict[str, Any]:
    """Cadastra um novo usuário no sistema e cria suas configurações padrão isoladas."""
    clean_username = username.strip().lower()
    clean_email = email.strip().lower() if email else None
    
    if len(clean_username) < 3:
        raise ValueError("O nome de usuário deve ter no mínimo 3 caracteres.")
    if len(password) < 6:
        raise ValueError("A senha deve ter no mínimo 6 caracteres.")

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pw_hash = hash_password(password)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, name, created_at, is_active, is_admin)
                VALUES (?, ?, ?, ?, ?, 1, 0)
            """, (clean_username, clean_email, pw_hash, name.strip() or clean_username, now_str))
            new_user_id = cursor.lastrowid

            # Cria linha de configuração padrão no banco para o novo usuário
            cursor.execute("""
                INSERT INTO settings (
                    user_id, growth_rate, stake_amount, exit_ticks,
                    session_stop_loss_usd, session_take_profit_usd,
                    daily_stop_loss_usd, daily_take_profit_usd, max_consecutive_losses,
                    wait_cycle_reset, max_entry_tick, operation_mode,
                    shield_trigger_losses, primary_loss_action, primary_recovery_max_steps,
                    primary_martingale_multiplier, fractional_installments, include_base_profit,
                    max_loss_recovery_cap, primary_token, primary_app_id, primary_account_id,
                    secondary_token, secondary_app_id, secondary_account_id, symbol,
                    auto_select_best_asset, updated_at
                ) VALUES (
                    ?, 0.05, 1.00, 5,
                    5.00, 5.00,
                    20.00, 20.00, 20,
                    0, 1, 'secondary_only',
                    2, 'return_to_shield', 1,
                    2.0, 2, 0,
                    20.00, '', '', '',
                    '', '', '', 'R_10',
                    1, ?
                )
            """, (new_user_id, now_str))

            conn.commit()
            logger.info(f"✨ Novo usuário cadastrado: {clean_username} (ID: {new_user_id})")
            return {
                "id": new_user_id,
                "username": clean_username,
                "name": name.strip() or clean_username,
                "email": clean_email
            }
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint failed: users.username" in str(e):
                raise ValueError("Este nome de usuário já está em uso.")
            if "UNIQUE constraint failed: users.email" in str(e):
                raise ValueError("Este e-mail já está em uso.")
            raise ValueError(f"Erro ao cadastrar usuário: {e}")


def authenticate_user(username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
    """Autentica o usuário pelo username ou email e senha."""
    clean = username_or_email.strip().lower()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, email, password_hash, name, is_active, is_admin
            FROM users
            WHERE (username = ? OR email = ?) AND is_active = 1
        """, (clean, clean))
        user = cursor.fetchone()
        if not user:
            return None

        if verify_password(password, user["password_hash"]):
            return {
                "id": user["id"],
                "username": user["username"],
                "name": user["name"] or user["username"],
                "email": user["email"],
                "is_admin": bool(user["is_admin"])
            }
        return None


def create_session_token(user_id: int, days_valid: int = 30) -> str:
    """Gera um token de sessão criptograficamente seguro e persiste no banco."""
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    exp_str = (now + timedelta(days=days_valid)).strftime("%Y-%m-%d %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_tokens (token, user_id, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (token, user_id, now_str, exp_str))
        conn.commit()

    return token


def get_user_by_token(token: str) -> Optional[Dict[str, Any]]:
    """Verifica se o token é válido e não expirou, retornando os dados do usuário."""
    if not token:
        return None
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.name, u.email, u.is_admin
            FROM user_tokens t
            JOIN users u ON u.id = t.user_id
            WHERE t.token = ? AND t.expires_at > ? AND u.is_active = 1
        """, (token, now_str))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)


def revoke_token(token: str):
    """Invalida o token de sessão (Logout)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_tokens WHERE token = ?", (token,))
        conn.commit()
