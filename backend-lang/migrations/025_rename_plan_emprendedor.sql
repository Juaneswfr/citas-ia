-- El plan «Arranque» pasa a llamarse «Emprendedor» (código y nombre). Es idempotente: si la 022 ya trae el código nuevo, no hace nada.
-- Solo renombra el nombre si nadie lo había editado desde Zumit Manager.
UPDATE billing_plans
SET code = 'emprendedor', name = CASE WHEN name = 'Arranque' THEN 'Emprendedor' ELSE name END
WHERE code = 'arranque' AND NOT EXISTS (SELECT 1 FROM billing_plans WHERE code = 'emprendedor');

-- Los eventos guardan el código del plan en su detalle: se actualizan para que la línea de tiempo y el embudo sigan coincidiendo
UPDATE billing_events
SET payload = REPLACE(payload::text, '"arranque"', '"emprendedor"')::jsonb
WHERE payload::text LIKE '%"arranque"%'
