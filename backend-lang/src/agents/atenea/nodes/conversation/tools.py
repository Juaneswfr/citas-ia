"""
Tools del módulo conversacional.

- buscar_empleado      → directorio por nombre o área
- cumpleanos_proximos  → próximos N días
- quien_hace           → responsable de una función/área
- mis_permisos         → módulos habilitados del usuario (lee del estado, sin API call)
- info_catalogo_plu    → ficha e imagen de un producto por PLU (catálogo público)
"""
import os
from typing import Annotated

import httpx
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

CLARITY_URL  = os.getenv("CLARITY_URL", "")
_SUPPLY_URL = os.getenv("ATENEA_SUPPLY_URL", "")

_MODULE_LABELS = {
    "supply-chain": "📦 *Supply Chain* — inventario, contenedores y órdenes de compra",
    "tasks":        "✅ *Tareas* — crear, asignar y hacer seguimiento de tareas",
    "dashboards":   "📊 *Dashboards* — reportes y métricas del negocio",
    "clarity":      "🔍 *Clarity* — análisis y claridad de datos",
    "users":        "👥 *Usuarios* — directorio y gestión de personas",
    "cobrobot":     "💰 *CobroBot* — gestión de cobros y cartera",
}


def _bearer(state: dict) -> dict:
    """Extrae el token de state['session']['access_token'] y arma el header."""
    token = (state.get("session") or {}).get("access_token", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


@tool("buscar_empleado")
def buscar_empleado(
    nombre_o_area: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Busca información de un empleado por nombre o área: cargo, teléfono, email."""
    try:
        r = httpx.get(
            f"{CLARITY_URL}/users/search",
            params={"q": nombre_o_area},
            headers=_bearer(state),
            timeout=15,
        )
        if r.is_success:
            data = r.json()
            users = data.get("data", data) if isinstance(data, dict) else data
            if not users:
                return f"No encontré a nadie que coincida con '{nombre_o_area}'."
            lines = []
            for u in (users if isinstance(users, list) else [users])[:5]:
                lines.append(
                    f"• {u.get('name')} | {u.get('position', 'N/A')}\n"
                    f"  Área: {u.get('area', 'N/A')} | "
                    f"Tel: {u.get('phone', 'N/A')} | "
                    f"Email: {u.get('email', 'N/A')}"
                )
            return "Empleados encontrados:\n" + "\n".join(lines)
        return f"❌ Error al buscar: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas: {str(e)}"


@tool("cumpleanos_proximos")
def cumpleanos_proximos(
    dias: int = 7,
    state: Annotated[dict, InjectedState] = None,
) -> str:
    """Muestra los empleados que cumplen años en los próximos N días (default 7)."""
    from datetime import date, timedelta

    hoy   = date.today()
    hasta = hoy + timedelta(days=dias)
    try:
        r = httpx.get(
            f"{CLARITY_URL}/users/birthdays",
            params={"from": hoy.isoformat(), "to": hasta.isoformat()},
            headers=_bearer(state or {}),
            timeout=15,
        )
        if r.is_success:
            users = r.json()
            if not users:
                return f"No hay cumpleaños en los próximos {dias} días. 🎂"
            lines = []
            for u in users:
                lines.append(
                    f"• {u.get('name')} — {u.get('birthday_date', 'N/A')} | "
                    f"Área: {u.get('area', 'N/A')}"
                )
            return f"🎂 Cumpleaños próximos ({dias} días):\n" + "\n".join(lines)
        return f"❌ Error: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión: {str(e)}"


@tool("quien_hace")
def quien_hace(
    descripcion: str,
    state: Annotated[dict, InjectedState],
) -> str:
    """Encuentra quién es responsable de una función o área en la empresa.

    Ejemplos: 'quién maneja contabilidad', 'responsable de TI', 'quién aprueba vacaciones'.
    """
    try:
        r = httpx.get(
            f"{CLARITY_URL}/users/search",
            params={"q": descripcion},
            headers=_bearer(state),
            timeout=15,
        )
        if r.is_success:
            data = r.json()
            users = data.get("data", data) if isinstance(data, dict) else data
            if not users:
                return f"No encontré a nadie encargado de '{descripcion}'."
            lines = []
            for u in (users if isinstance(users, list) else [users])[:5]:
                lines.append(
                    f"• {u.get('name')} | {u.get('position', 'N/A')} | "
                    f"Área: {u.get('area', 'N/A')} | "
                    f"Tel: {u.get('phone', 'N/A')}"
                )
            return "Responsables encontrados:\n" + "\n".join(lines)
        return f"❌ Error: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión: {str(e)}"


@tool("mis_permisos")
def mis_permisos(state: Annotated[dict, InjectedState]) -> str:
    """Muestra los módulos y capacidades habilitadas para el usuario actual."""
    atlas_tools = state.get("atlas_tools") or []

    if not atlas_tools:
        return "No tienes módulos habilitados en este momento. Contacta al administrador."

    lines = ["Tus módulos habilitados:"]
    for t in atlas_tools:
        key   = t.get("key", "")
        name  = t.get("name", key)
        roles = t.get("roles", [])

        label    = _MODULE_LABELS.get(key, f"• {name}")
        role_tag = f" _(rol: {', '.join(roles)})_" if roles else ""
        lines.append(f"{label}{role_tag}")

    lines.append(
        "\nPuedes preguntarme sobre cualquiera de estos módulos "
        "y te ayudo con lo que necesites."
    )
    return "\n".join(lines)


@tool("info_catalogo_plu")
def info_catalogo_plu(plu: str) -> str:
    """Obtiene la ficha completa de un producto del catálogo por PLU: nombre, categoría
    e imagen. Úsala cuando el usuario pida ver un producto o su foto."""
    if not _SUPPLY_URL:
        return "❌ ATENEA_SUPPLY_URL no está configurado."
    try:
        r = httpx.get(
            f"{_SUPPLY_URL.rstrip('/')}/api/catalog/products",
            params={"plu": plu},
            timeout=15,
        )
        if r.status_code == 404:
            return f"No se encontró ningún producto con PLU '{plu}' en el catálogo."
        if not r.is_success:
            return f"❌ Error al consultar el catálogo: {r.text}"

        p      = r.json()
        images = p.get("images") or []
        lines  = []

        if images:
            lines.append(f"[IMAGE: {images[0]}]")

        lines.append(f"*{p.get('name', 'Sin nombre')}*")
        lines.append(f"PLU: {p.get('plu', plu)}")

        if p.get("category_name"):
            lines.append(f"Categoría: {p['category_name']}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error de conexión con el catálogo: {e}"


tools = [buscar_empleado, cumpleanos_proximos, quien_hace, mis_permisos, info_catalogo_plu]
