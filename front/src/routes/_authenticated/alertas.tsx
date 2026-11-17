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
import { useDashboardInsights } from "@/hooks/use-dashboard-insights";
import { useActionTarget } from "@/hooks/use-action-target";
import { actionItems, type ActionItem } from "@/lib/dashboard-insights";
import type { AgentAlertOut } from "@/lib/types/api";

export const Route = createFileRoute("/_authenticated/alertas")({
  head: () => ({ meta: [{ title: "Alertas · Zumit" }] }),
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

/** Pendiente de «Para hacer hoy»: no se resuelve a mano, desaparece al atender la causa. */
function TodoRow({ item, onOpen }: { item: ActionItem; onOpen: (item: ActionItem) => void }) {
  const cfg = SEVERITY_CFG[item.urgent ? 'warning' : 'info'];
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '14px 20px', borderBottom: '1px solid var(--line)' }}>
      <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', flexShrink: 0, display: 'grid', placeItems: 'center', background: cfg.bg, color: cfg.color }}>
        <Icon name={cfg.icon} size={16} />
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ marginBottom: 3 }}>
          <Tag hue={item.urgent ? 'clay' : 'steel'} style={{ fontSize: 11 }}>Para hacer hoy</Tag>
        </div>
        <div style={{ font: '500 13.5px/1.5 var(--font-sans)', color: 'var(--ink-1)' }}>{item.label}</div>
        <div style={{ font: '400 12.5px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>{item.hint}</div>
      </div>
      <Button variant={item.urgent ? 'primary' : 'secondary'} size="sm" iconRight="arrowR" onClick={() => onOpen(item)}>
        {item.cta}
      </Button>
    </div>
  );
}

function AlertasPage() {
  const { workspaceId } = useAuth();
  const insights = useDashboardInsights();
  const openTodo = useActionTarget(insights.data);
  const todos = insights.data ? actionItems(insights.data.actions) : [];
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

  const shownTodos = showResolved ? [] : todos;
  const bySeverity = (s: AgentAlertOut['severity']) =>
    alerts.filter(a => a.severity === s).length;
  const todoBySeverity = (s: AgentAlertOut['severity']) =>
    shownTodos.filter(t => (t.urgent ? 'warning' : 'info') === s).length;
  const countOf = (s: AgentAlertOut['severity']) => bySeverity(s) + todoBySeverity(s);
  const bySeverityList = (s: AgentAlertOut['severity']) => alerts.filter(a => a.severity === s);
  const critical = bySeverityList('critical');
  const errors   = bySeverityList('error');
  const warnings = bySeverityList('warning');
  const infos    = bySeverityList('info');

  const ordered = [...critical, ...errors, ...warnings, ...infos];

  return (
    <div className="page page-enter" style={{ maxWidth: 820 }}>

      {/* Encabezado */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 22 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Agente IA</div>
          <h2 style={{ margin: 0, font: '400 28px/1.08 var(--font-serif)', letterSpacing: '-0.01em', color: 'var(--ink-1)' }}>
            Alertas <span className="serif-i">y pendientes</span>
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
            const count = countOf(sev);
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
        ) : ordered.length === 0 && shownTodos.length === 0 ? (
          <div style={{ padding: '48px 20px', textAlign: 'center' }}>
            <Icon name="check" size={28} style={{ color: 'var(--success)', marginBottom: 10 }} />
            <div style={{ font: '500 14px/1.4 var(--font-sans)', color: 'var(--ink-2)' }}>
              {showResolved ? 'Sin alertas resueltas.' : 'Sin alertas pendientes.'}
            </div>
          </div>
        ) : (
          <>
            {shownTodos.map(t => <TodoRow key={t.key} item={t} onOpen={openTodo} />)}
            {ordered.map(a => (
              <AlertRow key={a.id} alert={a} onResolve={resolve} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}
