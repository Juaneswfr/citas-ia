import os
import httpx
from langchain_core.tools import tool

ATLAS_URL = os.getenv("ATLAS_AUTH_URL", "")


@tool("consultar_usuario")
def consultar_usuario(nombre_o_phone: str) -> str:
    """Busca un empleado en el directorio de Atlas por nombre o número de teléfono."""
    try:
        r = httpx.get(
            f"{ATLAS_URL}/users/search",
            params={"q": nombre_o_phone},
            timeout=15,
        )
        if r.is_success:
            data = r.json()
            users = data.get("data", data) if isinstance(data, dict) else data
            if not users:
                return f"No se encontró ningún empleado con '{nombre_o_phone}'."
            u = users[0] if isinstance(users, list) else users
            return (
                f"Empleado encontrado:\n"
                f"• Nombre: {u.get('name')}\n"
                f"• Teléfono: {u.get('phone')}\n"
                f"• Email: {u.get('email')}\n"
                f"• Área: {u.get('area', 'N/A')}\n"
                f"• position: {u.get('position', 'N/A')}"
            )
        return f"❌ Error al consultar usuario: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas: {str(e)}"


@tool("listar_usuarios")
def listar_usuarios(area: str = None, position: str = None) -> str:
    """Lista empleados del directorio filtrando por área y/o position."""
    try:
        params = {}
        if area:
            params["area"] = area
        if position:
            params["position"] = position
        r = httpx.get(f"{ATLAS_URL}/users", params=params, timeout=15)
        if r.is_success:
            data = r.json()
            users = data.get("data", data) if isinstance(data, dict) else data
            if not users:
                return "No se encontraron empleados con los filtros indicados."
            lines = [
                f"• {u.get('name')} | {u.get('position', 'N/A')} | {u.get('area', 'N/A')}"
                for u in users[:10]
            ]
            return "Empleados encontrados:\n" + "\n".join(lines)
        return f"❌ Error al listar usuarios: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas: {str(e)}"


tools = [consultar_usuario, listar_usuarios]
tools_by_name = {t.name: t for t in tools}
