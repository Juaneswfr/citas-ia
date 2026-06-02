import os
import httpx
from langchain_core.tools import tool

TASKS_URL = os.getenv("ATENEA_TASKS_URL", "")


@tool("crear_tarea")
def crear_tarea(
    titulo: str,
    asignado_a: str,
    descripcion: str = "",
    prioridad: str = "media",
    fecha_limite: str = None,
) -> str:
    """Crea una tarea en Atlas y la asigna a un empleado.
    Prioridad: baja | media | alta | urgente. Fecha en formato ISO 8601."""
    try:
        r = httpx.post(
            TASKS_URL,
            json={
                "title": titulo,
                "description": descripcion,
                "assigned_to": asignado_a,
                "priority": prioridad,
                "due_date": fecha_limite,
            },
            timeout=15,
        )
        if r.is_success:
            task = r.json()
            return f"✅ Tarea '{titulo}' creada con ID #{task.get('id', 'N/A')}. Asignada a: {asignado_a}."
        return f"❌ Error al crear tarea: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas Tasks: {str(e)}"


@tool("consultar_tareas")
def consultar_tareas(asignado_a: str = None, estado: str = None) -> str:
    """Consulta tareas en Atlas. Filtra por empleado asignado y/o estado
    (pendiente, en_progreso, completada)."""
    try:
        params = {}
        if asignado_a:
            params["assigned_to"] = asignado_a
        if estado:
            params["status"] = estado
        r = httpx.get(TASKS_URL, params=params, timeout=15)
        if r.is_success:
            tasks = r.json()
            if not tasks:
                return "No se encontraron tareas con los criterios indicados."
            lines = [
                f"• #{t.get('id')}: {t.get('title')} — {t.get('status', 'N/A')} "
                f"| Asignada a: {t.get('assigned_to', 'N/A')}"
                for t in tasks[:10]
            ]
            return "Tareas encontradas:\n" + "\n".join(lines)
        return f"❌ Error al consultar tareas: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas Tasks: {str(e)}"


@tool("actualizar_tarea")
def actualizar_tarea(tarea_id: str, estado: str = None, comentario: str = None) -> str:
    """Actualiza el estado o agrega un comentario a una tarea existente en Atlas.
    Estados válidos: pendiente | en_progreso | completada | cancelada."""
    try:
        payload = {}
        if estado:
            payload["status"] = estado
        if comentario:
            payload["comment"] = comentario
        r = httpx.patch(f"{TASKS_URL}/{tarea_id}", json=payload, timeout=15)
        if r.is_success:
            return f"✅ Tarea #{tarea_id} actualizada correctamente."
        return f"❌ Error al actualizar tarea: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas Tasks: {str(e)}"


tools = [crear_tarea, consultar_tareas, actualizar_tarea]
tools_by_name = {t.name: t for t in tools}
