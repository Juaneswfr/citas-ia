import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow, parseISO } from "date-fns";
import { es } from "date-fns/locale";
import { Icon } from "@/components/hilo/icons";
import { Button, Tag } from "@/components/hilo/primitives";
import { listAgentAlerts, resolveAgentAlert } from "@/lib/api/alerts";
import { useAuth } from "@/lib/auth-context";
import type { AgentAlertOut } from "@/lib/types/api";

export const Route = createFileRoute("/_authenticated/alertas")({
  head: () => ({ meta: [{ title: "Alertas · Hilo" }] }),
  component: AlertasPage,
});

const SEVERITY_CFG = {
  info:     { label: 'Info',     bg: 'var(--surface-tint)',                                           color: 'var(--ink-2)',   icon: 'bell'  },
  warning:  { label: 'Aviso',    bg: 'color-mix(in srgb, var(--warning) 10%, var(--surface))',        color: 'var(--warning)', icon: 'bell'  },
  error:    { label: 'Error',    bg: 'color-mix(in srgb, var(--danger) 10%, var(--surface))',         color: 'var(--danger)',  icon: 'x'     },
  critical: { label: 'Crítico',  bg: 'color-mix(in srgb, var(--danger) 18%, var(--surface))',         color: 'var(--danger)',  icon: 'x'     },
} as const;

function AlertRow({ alert, onResolve }: { alert: AgentAlertOut; onResolve: (id: string) => void }) {
  const navigate = useNavigate();
  const cfg = SEVERITY_CFG[alert.severity] ?? SEVERITY_CFG.info;
  const ago = formatDistanceToNow(parseISO(alert.created_at), { locale: es, addSuffix: true });

  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--line)' }}>
      <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', flexShrink: 0, display: 'grid', placeItems: 'center', background: cfg.bg, color: cfg.color }}>
        <Icon name={cfg.icon} size={16} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
          <Tag hue={alert.severity === 'info' ? 'steel' : alert.severity === 'warning' ? 'clay' : 'wine'} style={{ fontSize: 11 }}>
            {cfg.label}
          </Tag>
          <span style={{ font: '400 11.5px/1 var(--font-sans)', color: 'var(--ink-3)' }}>{ago}</span>
        </div>
        <div style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--ink-1)', wordBreak: 'break-word' }}>{alert.reason}</div>
      </div>
      <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
        {alert.conversation_id && (
          <Button variant="ghost" size="sm" onClick={() => navigate({ to: '/messages' })}>Ver conv.</Button>
        )}
        <Button variant="ghost" size="sm" onClick={() => onResolve(alert.id)}>Resolver</Button>
      </div>
    </div>
  );
}

function AlertasPage() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  const [showResolved, setShowResolved] = useState(false);

  const { data: alerts = [], isLoading } = useQuery({
    queryKey: ['agent-alerts', workspaceId, showResolved],
    queryFn: () => listAgentAlerts(workspaceId!, showResolved),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });

  const { mutate: resolve } = useMutation({
    mutationFn: (alertId: string) => resolveAgentAlert(workspaceId!, alertId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['agent-alerts'] });
      qc.invalidateQueries({ queryKey: ['agent-alerts-count'] });
      toast.success('Alerta resuelta.');
    },
    onError: () => toast.error('No se pudo resolver la alerta.'),
  });

  const bySeverity = (s: AgentAlertOut['severity']) => alerts.filter(a => a.severity === s);
  const critical = bySeverity('critical');
  const errors   = bySeverity('error');
  const warnings = bySeverity('warning');
  const infos    = bySeverity('info');

  const ordered = [...critical, ...errors, ...warnings, ...infos];

  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '26px 30px 48px', animation: 'hilo-fade-up var(--dur-3) var(--ease-out)' }}>

      {/* Encabezado */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 22 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Agente IA</div>
          <h2 style={{ margin: 0, font: '400 28px/1.08 var(--font-serif)', letterSpacing: '-0.01em', color: 'var(--ink-1)' }}>
            Alertas <span className="serif-i">del agente</span>
          </h2>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShowResolved(v => !v)}
        >
          {showResolved ? 'Ver pendientes' : 'Ver resueltas'}
        </Button>
      </div>

      {/* Contadores por severidad */}
      {!showResolved && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, marginBottom: 20 }}>
          {(['critical', 'error', 'warning', 'info'] as const).map(sev => {
            const cfg = SEVERITY_CFG[sev];
            const count = bySeverity(sev).length;
            return (
              <div key={sev} className="card" style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ width: 28, height: 28, borderRadius: 'var(--r-sm)', display: 'grid', placeItems: 'center', background: cfg.bg, color: cfg.color, flexShrink: 0 }}>
                  <Icon name={cfg.icon} size={14} />
                </span>
                <div>
                  <div style={{ font: '600 18px/1 var(--font-sans)', color: count > 0 ? cfg.color : 'var(--ink-3)', letterSpacing: '-0.02em' }}>{count}</div>
                  <div style={{ font: '400 11px/1 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>{cfg.label}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Lista */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--ink-3)', font: '400 13px/1 var(--font-sans)' }}>
            Cargando alertas…
          </div>
        ) : ordered.length === 0 ? (
          <div style={{ padding: '48px 20px', textAlign: 'center' }}>
            <Icon name="check" size={28} style={{ color: 'var(--success)', marginBottom: 10 }} />
            <div style={{ font: '500 14px/1.4 var(--font-sans)', color: 'var(--ink-2)' }}>
              {showResolved ? 'Sin alertas resueltas.' : 'Sin alertas pendientes.'}
            </div>
          </div>
        ) : (
          ordered.map(a => (
            <AlertRow key={a.id} alert={a} onResolve={resolve} />
          ))
        )}
      </div>
    </div>
  );
}
