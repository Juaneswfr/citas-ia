import os
import httpx
from langchain_core.tools import tool

DASHBOARDS_URL = os.getenv("ATENEA_DASHBOARDS_URL", "")


@tool("consultar_dashboard")
def consultar_dashboard(nombre: str, periodo: str = "mes_actual") -> str:
    """Consulta los indicadores y métricas de un dashboard específico.
    Períodos: hoy | semana_actual | mes_actual | trimestre | año."""
    try:
        r = httpx.get(
            f"{DASHBOARDS_URL}/{nombre}",
            params={"period": periodo},
            timeout=20,
        )
        if r.is_success:
            data = r.json()
            metrics = data.get("metrics", [])
            if not metrics:
                return f"No hay datos disponibles para el dashboard '{nombre}' en el período {periodo}."
            lines = [
                f"• {m.get('label')}: {m.get('value')} {m.get('unit', '')}"
                for m in metrics[:10]
            ]
            return f"Dashboard '{nombre}' — {periodo}:\n" + "\n".join(lines)
        return f"❌ Error al consultar dashboard: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas Dashboards: {str(e)}"


@tool("generar_reporte")
def generar_reporte(tipo: str, area: str = None, fecha_inicio: str = None, fecha_fin: str = None) -> str:
    """Genera un reporte en Atlas. Tipos comunes: ventas, produccion, asistencia, tareas.
    Fechas en formato ISO 8601 (YYYY-MM-DD)."""
    try:
        r = httpx.post(
            f"{DASHBOARDS_URL}/reports",
            json={
                "type": tipo,
                "area": area,
                "start_date": fecha_inicio,
                "end_date": fecha_fin,
            },
            timeout=30,
        )
        if r.is_success:
            rep = r.json()
            return (
                f"✅ Reporte '{tipo}' generado con ID #{rep.get('id', 'N/A')}.\n"
                f"Período: {rep.get('period', 'N/A')} | "
                f"Registros: {rep.get('records', 'N/A')}"
            )
        return f"❌ Error al generar reporte: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas Dashboards: {str(e)}"


@tool("exportar_reporte")
def exportar_reporte(reporte_id: str, formato: str = "pdf") -> str:
    """Exporta un reporte ya generado en formato pdf o excel.
    Devuelve el enlace de descarga."""
    try:
        r = httpx.post(
            f"{DASHBOARDS_URL}/reports/{reporte_id}/export",
            json={"format": formato},
            timeout=30,
        )
        if r.is_success:
            data = r.json()
            url = data.get("download_url", "N/A")
            return f"✅ Reporte #{reporte_id} listo en {formato.upper()}: {url}"
        return f"❌ Error al exportar reporte: {r.text}"
    except Exception as e:
        return f"❌ Error de conexión con Atlas Dashboards: {str(e)}"


tools = [consultar_dashboard, generar_reporte, exportar_reporte]
tools_by_name = {t.name: t for t in tools}
