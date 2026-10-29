"""
Tools compartidas entre múltiples nodos de agentes.

buscar_responsable se incluye en cualquier nodo que necesite asignar
un empleado como responsable (supply, tasks, etc.). Consume la API de
usuarios de Atlas usando el token de la sesión activa.
"""
import os
import httpx
from langchain_core.tools import tool

ATLAS_URL = os.getenv("ATLAS_AUTH_URL", "")


@tool("buscar_responsable")
def buscar_responsable(nombre_o_area: str) -> str:
    """Busca empleados disponibles para asignar como responsables o notificar.

    Usa esta herramienta cuando necesites saber el ID o nombre exacto de una
    persona antes de asignarla a una tarea, solicitud u otro proceso.

    Args:
        nombre_o_area: Nombre parcial del empleado o nombre del área a filtrar.
    """
    try:
        r = httpx.get(
            f"{ATLAS_URL}/users/search",
            params={"q": nombre_o_area},
            timeout=15,
        )
        if r.is_success:
            data = r.json()
            users = data.get("data", data) if isinstance(data, dict) else data
            if not users:
                return f"No se encontraron empleados que coincidan con '{nombre_o_area}'."
            lines = [
                f"• {u.get('name')} (ID: {u.get('id')}) | "
                f"{u.get('position', 'N/A')} | {u.get('area', 'N/A')} | "
                f"Tel: {u.get('phone', 'N/A')}"
                for u in (users if isinstance(users, list) else [users])[:10]
            ]
            return "Empleados encontrados:\n" + "\n".join(lines)
        return f"❌ Error al buscar responsables: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas: {str(e)}"
