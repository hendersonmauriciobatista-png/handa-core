# =============================================================================
# core/persistence/postgres_state_repository.py
# H&A — PostgreSQL State Repository (Railway Ready)
# =============================================================================

import os
import json
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from core.persistence.state_repository import StateRepository


class PostgresStateRepository(StateRepository):
    """
    Implementação PostgreSQL para persistência do H&A.

    Compatível com Railway (DATABASE_URL).
    """

    def __init__(self):
        self.database_url = os.getenv("DATABASE_URL")

        if not self.database_url:
            raise RuntimeError(
                "[PERSISTENCE] DATABASE_URL não configurada — LIVE BLOQUEADO"
            )

        self.conn = psycopg2.connect(self.database_url, sslmode="require")
        self.conn.autocommit = True

    # =============================================================================
    # INIT
    # =============================================================================
    def initialize(self) -> None:
        """
        Cria tabela principal de estado do sistema.
        """
        with self.conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    updated_at TIMESTAMP DEFAULT NOW()
                );
                """)

    # =============================================================================
    # SAVE
    # =============================================================================
    def save_system_state(self, key: str, value: Dict[str, Any]) -> None:
        """
        Salva ou atualiza estado no banco.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO system_state (key, value, updated_at)
                VALUES (%s, %s::jsonb, NOW())
                ON CONFLICT (key)
                DO UPDATE SET
                    value = EXCLUDED.value,
                    updated_at = NOW();
                """,
                (key, json.dumps(value)),
            )

    # =============================================================================
    # LOAD
    # =============================================================================
    def load_system_state(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Carrega estado do banco.
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT value
                FROM system_state
                WHERE key = %s;
                """,
                (key,),
            )

            row = cur.fetchone()

            if not row:
                return None

            return row["value"]

    # =============================================================================
    # DELETE
    # =============================================================================
    def delete_system_state(self, key: str) -> None:
        """
        Remove estado do banco.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM system_state
                WHERE key = %s;
                """,
                (key,),
            )

    # =============================================================================
    # CLOSE
    # =============================================================================
    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
