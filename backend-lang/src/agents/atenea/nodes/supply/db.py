"""
Conexión read-only a Supabase PostgreSQL para el módulo Supply Chain.
Usa psycopg2 con readonly=True — nunca escribe en la BD.
"""
import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

_DB_URL = os.getenv("SUPPLY_DB_URL")


@contextmanager
def cursor():
    """Context manager que entrega un cursor read-only y cierra la conexión al salir."""
    if not _DB_URL:
        raise RuntimeError("SUPPLY_DB_URL no está configurado en .env")
    conn = psycopg2.connect(_DB_URL)
    conn.set_session(readonly=True, autocommit=False)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
    finally:
        conn.close()
