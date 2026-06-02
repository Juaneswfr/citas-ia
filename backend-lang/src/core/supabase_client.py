"""
Cliente Supabase singleton.

El service_role_key MUST usarse únicamente aquí, en el backend,
nunca expuesto al frontend ni al agente (Principio VII, Constitución).
"""
from functools import lru_cache

from supabase import Client, create_client

from core.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Retorna el cliente Supabase con service role para operaciones de backend."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


@lru_cache
def get_supabase_anon() -> Client:
    """
    Cliente Supabase con llave anónima.
    Usar cuando se quiere que RLS aplique según el JWT del usuario.
    """
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_anon_key)
