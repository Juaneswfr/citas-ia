// Seguimiento por WhatsApp (espejo de backend-lang/src/schemas/followups.py).

/** Seguimientos que envía el worker: cada uno tiene interruptor y tiempo en FollowupSettings. */
export type ScheduledFollowupKind = 'reminder' | 'post_visit' | 'payment_due' | 'reactivation';
/** 'cancellation' sale cuando el negocio cancela una cita desde el panel: no se programa ni se apaga. */
export type FollowupKind = ScheduledFollowupKind | 'cancellation';
export type TemplateStatus = 'not_created' | 'pending' | 'approved' | 'rejected' | 'disabled' | 'error';

export interface FollowupSettings {
  reminder_enabled: boolean;
  reminder_hours_before: number;
  post_visit_enabled: boolean;
  post_visit_hours_after: number;
  payment_due_enabled: boolean;
  payment_due_days: number;
  reactivation_enabled: boolean;
  reactivation_days: number;
}

export interface FollowupTemplateOut {
  kind: FollowupKind;
  name: string;
  category: string;
  body: string;
  buttons: string[];
  status: TemplateStatus;
  detail: string | null;
  synced_at: string | null;
}

export interface FollowupTemplatesOut {
  /** Hay un número de WhatsApp activo; sin él no se envía ningún seguimiento. */
  connected: boolean;
  can_activate: boolean;
  /** Por qué no se pueden activar las plantillas (sin canal, número de pruebas...). */
  reason: string | null;
  templates: FollowupTemplateOut[];
}
