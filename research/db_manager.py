import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
from itertools import groupby

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "deriv_history.db")

def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Tabela de candles (persistência perpétua)
    c.execute("""
    CREATE TABLE IF NOT EXISTS candles (
        symbol TEXT NOT NULL,
        epoch INTEGER NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        color TEXT NOT NULL,
        dt_utc TEXT NOT NULL,
        PRIMARY KEY (symbol, epoch)
    );
    """)
    
    # Tabela de streaks de candles >= 6 velas consecutivas (persistência perpétua)
    c.execute("""
    CREATE TABLE IF NOT EXISTS candle_streaks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        streak_len INTEGER NOT NULL,
        start_epoch INTEGER NOT NULL,
        end_epoch INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        open_price REAL,
        close_price REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(symbol, direction, start_epoch, end_epoch)
    );
    """)
    
    conn.commit()
    conn.close()

def save_candles(symbol: str, candles: List[Dict[str, Any]]) -> int:
    """Salva candles no banco de dados com INSERT OR IGNORE."""
    init_db()
    conn = get_connection()
    c = conn.cursor()
    
    rows = []
    for cd in candles:
        ep = cd["epoch"]
        o = float(cd["open"])
        h = float(cd["high"])
        l = float(cd["low"])
        cl = float(cd["close"])
        color = "VERDE" if cl > o else ("VERMELHO" if cl < o else "DOJI")
        dt_str = datetime.fromtimestamp(ep, timezone.utc).strftime("%Y-%m-%d %H:%M:%S GMT")
        rows.append((symbol, ep, o, h, l, cl, color, dt_str))
        
    c.executemany("""
    INSERT OR IGNORE INTO candles (symbol, epoch, open, high, low, close, color, dt_utc)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    
    inserted = c.rowcount
    conn.commit()
    conn.close()
    return inserted

def detect_and_save_streaks(symbol: str = "R_100", min_streak: int = 6) -> int:
    """
    Analisa todos os candles históricos no banco e registra permanentemente
    todas as sequências de mesma cor com tamanho >= min_streak.
    """
    init_db()
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("""
    SELECT epoch, open, close, color, dt_utc 
    FROM candles 
    WHERE symbol = ? 
    ORDER BY epoch ASC
    """, (symbol,))
    
    all_rows = c.fetchall()
    if not all_rows:
        conn.close()
        return 0
        
    streaks_to_insert = []
    for k, g in groupby(all_rows, key=lambda x: x["color"]):
        group = list(g)
        if k in ("VERDE", "VERMELHO") and len(group) >= min_streak:
            first = group[0]
            last = group[-1]
            streaks_to_insert.append((
                symbol,
                k,
                len(group),
                first["epoch"],
                last["epoch"],
                first["dt_utc"],
                last["dt_utc"],
                first["open"],
                last["close"]
            ))
            
    c.executemany("""
    INSERT OR IGNORE INTO candle_streaks 
    (symbol, direction, streak_len, start_epoch, end_epoch, start_time, end_time, open_price, close_price)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, streaks_to_insert)
    
    inserted = c.rowcount
    conn.commit()
    conn.close()
    return len(streaks_to_insert)

def get_historical_records(symbol: str = "R_100") -> Dict[str, Any]:
    """Retorna os recordes de streaks históricos absolutos e a distribuição."""
    init_db()
    conn = get_connection()
    c = conn.cursor()
    
    # Maior streak geral da história
    c.execute("""
    SELECT * FROM candle_streaks 
    WHERE symbol = ? 
    ORDER BY streak_len DESC, start_epoch ASC 
    LIMIT 1
    """, (symbol,))
    row_overall = c.fetchone()
    max_overall = dict(row_overall) if row_overall else None
    
    # Maior streak VERDE
    c.execute("""
    SELECT * FROM candle_streaks 
    WHERE symbol = ? AND direction = 'VERDE'
    ORDER BY streak_len DESC, start_epoch ASC 
    LIMIT 1
    """, (symbol,))
    row_green = c.fetchone()
    max_green = dict(row_green) if row_green else None
    
    # Maior streak VERMELHO
    c.execute("""
    SELECT * FROM candle_streaks 
    WHERE symbol = ? AND direction = 'VERMELHO'
    ORDER BY streak_len DESC, start_epoch ASC 
    LIMIT 1
    """, (symbol,))
    row_red = c.fetchone()
    max_red = dict(row_red) if row_red else None
    
    # Distribuição por tamanho
    c.execute("""
    SELECT streak_len, COUNT(*) as cnt 
    FROM candle_streaks 
    WHERE symbol = ? 
    GROUP BY streak_len 
    ORDER BY streak_len ASC
    """, (symbol,))
    dist_rows = c.fetchall()
    distribution = {str(r["streak_len"]): r["cnt"] for r in dist_rows}
    
    # Contagem total
    c.execute("SELECT COUNT(*) FROM candle_streaks WHERE symbol = ?", (symbol,))
    total_streaks = c.fetchone()[0]
    
    # Lista de todos os streaks >= 6 (ordenados do maior para o menor e depois mais recentes)
    c.execute("""
    SELECT id, direction, streak_len, start_epoch, end_epoch, start_time, end_time, open_price, close_price
    FROM candle_streaks 
    WHERE symbol = ? 
    ORDER BY streak_len DESC, start_epoch DESC
    """, (symbol,))
    all_streaks = [dict(r) for r in c.fetchall()]
    
    conn.close()
    
    return {
        "max_overall": max_overall,
        "max_green": max_green,
        "max_red": max_red,
        "total_streaks": total_streaks,
        "distribution": distribution,
        "all_streaks": all_streaks
    }

def get_rolling_window_candles(symbol: str = "R_100", days_closed: int = 4) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retorna os candles da janela deslizante:
    - Os últimos `days_closed` dias UTC fechados (00:00:00 a 23:59:59).
    - O dia UTC atual em andamento (de 00:00:00 até agora).
    - Descarte automático de qualquer dia anterior além dos 4 dias fechados.
    """
    init_db()
    conn = get_connection()
    c = conn.cursor()
    
    # Horário UTC atual
    now_utc = datetime.now(timezone.utc)
    today_start = datetime(now_utc.year, now_utc.month, now_utc.day, 0, 0, 0, tzinfo=timezone.utc)
    
    # Janela: 4 dias fechados anteriores + hoje em andamento
    window_start = today_start - timedelta(days=days_closed)
    start_epoch = int(window_start.timestamp())
    
    c.execute("""
    SELECT epoch, open, high, low, close, color, dt_utc 
    FROM candles 
    WHERE symbol = ? AND epoch >= ? 
    ORDER BY epoch ASC
    """, (symbol, start_epoch))
    
    rows = c.fetchall()
    candles = [dict(r) for r in rows]
    conn.close()
    
    # Identificar os dias presentes na janela
    days_set = set()
    for cd in candles:
        day_str = cd["dt_utc"].split()[0]
        days_set.add(day_str)
        
    days_sorted = sorted(list(days_set))
    today_str = today_start.strftime("%Y-%m-%d")
    
    window_info = {
        "start_epoch": start_epoch,
        "start_time": window_start.strftime("%Y-%m-%d 00:00:00 GMT"),
        "end_time": candles[-1]["dt_utc"] if candles else now_utc.strftime("%Y-%m-%d %H:%M:%S GMT"),
        "days_closed_target": days_closed,
        "current_day": today_str,
        "days_list": days_sorted,
        "total_candles": len(candles),
        "is_full_window": len(candles) >= (days_closed + 1) * 1440
    }
    
    return candles, window_info
