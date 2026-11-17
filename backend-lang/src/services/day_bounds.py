"""Cortes por día en la zona horaria del negocio, para filtros `from_date` / `to_date`.

El servidor corre en UTC: un corte por día tiene que usar `workspaces.timezone`, o las citas de la
tarde-noche (después de las 19:00 en Colombia) caen en el día siguiente. Las consultas que lo usan
deben tener los parámetros `:workspace_id`, `:from_date` y/o `:to_date`.
"""
WS_TZ = "(SELECT timezone FROM workspaces WHERE id = :workspace_id)"
# Primer instante del día `from_date` y primer instante del día siguiente a `to_date`, en la zona del negocio.
FROM_DAY = f"(CAST(CAST(:from_date AS date) AS timestamp) AT TIME ZONE {WS_TZ})"
AFTER_TO_DAY = f"((CAST(CAST(:to_date AS date) AS timestamp) + INTERVAL '1 day') AT TIME ZONE {WS_TZ})"
