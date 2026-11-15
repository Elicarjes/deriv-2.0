"""
Módulo de Gerenciamento e Persistência do Histórico de Sessões de Trading.
Permite salvar, consultar e analisar testes com diferentes configurações,
métricas de streaks, contratos e resultados financeiros.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger("SessionManager")


class SessionManager:
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self):
        """Garante que o diretório e o arquivo de persistência existam."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.storage_path.exists():
                self.storage_path.write_text("[]", encoding="utf-8")
        except Exception as e:
            logger.error(f"Erro ao inicializar arquivo de sessões: {e}")

    def load_sessions(self) -> List[Dict[str, Any]]:
        """Carrega todas as sessões salvas do disco."""
        try:
            if not self.storage_path.exists():
                return []
            content = self.storage_path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            return json.loads(content)
        except Exception as e:
            logger.error(f"Erro ao ler sessões salvas: {e}")
            return []

    def save_sessions(self, sessions: List[Dict[str, Any]]):
        """Grava a lista de sessões no disco em formato JSON identado."""
        try:
            self.storage_path.write_text(json.dumps(sessions, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"Erro ao gravar sessões no disco: {e}")

    def get_next_session_number(self) -> int:
        """Determina o próximo número sequencial de sessão."""
        sessions = self.load_sessions()
        if not sessions:
            return 1
        max_num = max([s.get("number", 0) for s in sessions] + [0])
        return max_num + 1

    def archive_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Arquiva uma sessão finalizada adicionando-a ao histórico."""
        sessions = self.load_sessions()
        sessions.insert(0, session_data)  # Mais recente no topo
        self.save_sessions(sessions)
        logger.info(f"💾 Sessão #{session_data.get('number')} arquivada com sucesso ({len(session_data.get('trades', []))} trades).")
        return session_data

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Retorna todas as sessões ordenadas da mais recente para a mais antiga."""
        return self.load_sessions()

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Busca uma sessão específica pelo identificador único."""
        sessions = self.load_sessions()
        for s in sessions:
            if s.get("id") == session_id:
                return s
        return None

    def delete_session(self, session_id: str) -> bool:
        """Remove uma sessão específica do histórico."""
        sessions = self.load_sessions()
        initial_len = len(sessions)
        sessions = [s for s in sessions if s.get("id") != session_id]
        if len(sessions) < initial_len:
            self.save_sessions(sessions)
            return True
        return False

    def clear_all(self):
        """Limpa todo o histórico de sessões arquivadas."""
        self.save_sessions([])
        logger.info("🗑️ Todo o histórico de sessões foi limpo.")
