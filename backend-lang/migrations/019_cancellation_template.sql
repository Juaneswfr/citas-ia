-- 019: plantilla «cita cancelada» (kind = 'cancellation').
-- Se envía cuando el negocio cancela una cita desde el panel; no tiene interruptor ni tiempos en
-- followup_settings. Aquí solo se amplían los CHECK de kind de la migración 016.
-- (El runner envía cada trozo entre ';' a la BD: no dejar comentarios sueltos al final del archivo.)
ALTER TABLE followup_templates DROP CONSTRAINT IF EXISTS followup_templates_kind_check;

ALTER TABLE followup_templates ADD CONSTRAINT followup_templates_kind_check
    CHECK (kind IN ('reminder','post_visit','payment_due','reactivation','cancellation'));

ALTER TABLE followup_sends DROP CONSTRAINT IF EXISTS followup_sends_kind_check;

ALTER TABLE followup_sends ADD CONSTRAINT followup_sends_kind_check
    CHECK (kind IN ('reminder','post_visit','payment_due','reactivation','cancellation'));
