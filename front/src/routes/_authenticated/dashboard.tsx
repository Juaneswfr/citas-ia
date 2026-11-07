import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { format, parseISO, formatDistanceToNow } from "date-fns";
import { es } from "date-fns/locale";
import { Icon } from "@/components/hilo/icons";
import { Button, Tag, Dot } from "@/components/hilo/primitives";
import { fmtCOP } from "@/lib/hilo-data";
import type { HiloAppointment } from "@/lib/hilo-data";
import { useAppointments } from "@/hooks/use-appointments";
import { useConversations, useMessages } from "@/hooks/use-conversations";
import { listChannels, listCalendars } from "@/lib/api/channels";
import { listCustomers } from "@/lib/api/conversations";
import { getWorkspaceStats } from "@/lib/api/workspaces";
import { useAuth } from "@/lib/auth-context";
import type { CustomerOut } from "@/lib/types/api";

export const Route = createFileRoute("/_authenticated/dashboard")({
  head: () => ({ meta: [{ title: "Inicio · Hilo" }] }),
  component: DashboardPage,
});

const STATUS = {
  done:     { label: 'Atendida',   color: 'var(--ink-3)',  dim: true  },
  now:      { label: 'En curso',   color: 'var(--wine)',   dim: false },
  next:     { label: 'Sigue',      color: 'var(--clay)',   dim: false },
  upcoming: { label: 'Programada', color: 'var(--ink-2)',  dim: false },
};

function StatCard({ eyebrow, value, unit, sub, delta, icon, accent = 'var(--wine)' }: {
  eyebrow: string; value: string | number; unit?: string; sub: string;
  delta?: number; icon: string; accent?: string;
}) {
  return (
    <div className="card" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span className="eyebrow">{eyebrow}</span>
        <span style={{ width: 30, height: 30, borderRadius: 'var(--r-sm)', display: 'grid', placeItems: 'center', background: `color-mix(in srgb, ${accent} 12%, var(--surface))`, color: accent }}>
          <Icon name={icon} size={16} />
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
        <span className="tnum" style={{ font: '500 30px/1 var(--font-sans)', letterSpacing: '-0.03em', color: 'var(--ink-1)' }}>{value}</span>
        {unit && <span style={{ font: '400 14px/1 var(--font-sans)', color: 'var(--ink-3)' }}>{unit}</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {delta != null && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 2, font: '500 12px/1 var(--font-sans)', color: delta >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            <Icon name={delta >= 0 ? 'arrowUp' : 'arrowDn'} size={13} />{Math.abs(delta)}%
          </span>
        )}
        <span style={{ font: '400 12.5px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>{sub}</span>
      </div>
    </div>
  );
}

function ThreadItem({ a, isLast }: { a: HiloAppointment; isLast: boolean }) {
  const st = STATUS[a.status];
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '58px 28px 1fr', columnGap: 0, position: 'relative' }}>
      <div style={{ textAlign: 'right', paddingRight: 14, paddingTop: 14 }}>
        <div className="tnum" style={{ font: '500 14px/1 var(--font-sans)', color: st.dim ? 'var(--ink-3)' : 'var(--ink-1)' }}>{a.time}</div>
        <div className="tnum" style={{ font: '400 11px/1.4 var(--font-mono)', color: 'var(--ink-4)' }}>{a.end}</div>
      </div>
      <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
        {!isLast && <span style={{ position: 'absolute', top: 14, bottom: -2, width: 2, background: st.dim ? 'var(--line-strong)' : 'var(--wine-200)', borderRadius: 2 }} />}
        <span style={{
          position: 'relative', marginTop: 14, width: 14, height: 14, borderRadius: '50%',
          background: a.status === 'done' ? 'var(--surface)' : st.color,
          border: `2px solid ${a.status === 'done' ? 'var(--line-strong)' : st.color}`,
          display: 'grid', placeItems: 'center',
          boxShadow: a.status === 'now' ? '0 0 0 5px color-mix(in srgb, var(--wine) 18%, transparent)' : 'none',
          animation: a.status === 'now' ? 'hilo-pulse 1.8s var(--ease-std) infinite' : 'none',
        }}>
          {a.status === 'done' && <Icon name="check" size={9} style={{ color: 'var(--ink-3)' }} strokeWidth={2.4} />}
        </span>
      </div>
      <div style={{ padding: '8px 0 14px' }}>
        <div style={{
          background: a.status === 'now' ? 'var(--wine-50)' : 'var(--surface)',
          border: `1px solid ${a.status === 'now' ? 'color-mix(in srgb, var(--wine) 26%, transparent)' : 'var(--line)'}`,
          borderRadius: 'var(--r-md)', padding: '11px 13px',
          opacity: st.dim ? 0.72 : 1,
          display: 'flex', alignItems: 'center', gap: 12,
        }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ font: '500 14.5px/1.2 var(--font-sans)', color: 'var(--ink-1)', whiteSpace: 'nowrap' }}>{a.client}</span>
              {a.via === 'wa' && <Icon name="whatsapp" size={14} style={{ color: 'var(--wa-ink)' }} />}
              {a.home && <Tag hue="sage" style={{ padding: '2px 7px', fontSize: 11 }}><Icon name="pin" size={11} />Domicilio</Tag>}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 5 }}>
              <Tag hue="wine" style={{ padding: '2px 8px', fontSize: 11.5 }}>{a.svc}</Tag>
              {a.pro && <span style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>· {a.pro}</span>}
            </div>
          </div>
          {a.status === 'now'
            ? <Tag hue="wine" tone="solid" style={{ fontSize: 11 }}><Dot color="#fff" size={6} />En curso</Tag>
            : <span style={{ font: '400 11.5px/1 var(--font-sans)', color: st.color }}>{st.label}</span>}
        </div>
      </div>
    </div>
  );
}

function AgentPanel() {
  const { workspaceId } = useAuth();
  const navigate = useNavigate();
  const [typing, setTyping] = useState(false);

  const { data: conversations = [] } = useConversations();

  const conv = [...conversations]
    .filter(c => c.last_message_at)
    .sort((a, b) => (b.last_message_at! > a.last_message_at! ? 1 : -1))[0] ?? null;

  const { data: messages = [] } = useMessages(conv?.id ?? '');

  const { data: rawCustomers = [] } = useQuery<CustomerOut[]>({
    queryKey: ['customers-raw', workspaceId],
    queryFn: () => listCustomers(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (!conv) return;
    const t = setInterval(() => setTyping(v => !v), 3200);
    return () => clearInterval(t);
  }, [conv?.id]);

  if (!conv) {
    return (
      <div className="card" style={{ padding: '24px 16px', textAlign: 'center' }}>
        <span style={{ color: 'var(--ink-3)', font: '400 13px/1.4 var(--font-sans)' }}>Sin conversaciones activas</span>
      </div>
    );
  }

  const customer = rawCustomers.find(c => c.id === conv.customer_id);
  const clientName = customer?.name || customer?.phone || 'Cliente';
  const displayPhone = customer?.phone ?? '';
  const recentMsgs = messages.slice(-6);

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 11, borderBottom: '1px solid var(--line)' }}>
        <span style={{ width: 34, height: 34, borderRadius: 'var(--r-full)', background: 'color-mix(in srgb, var(--wa-ink) 14%, var(--surface))', display: 'grid', placeItems: 'center', color: 'var(--wa-ink)' }}>
          <Icon name="whatsapp" size={18} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Tu agente, ahora</span>
            <Dot color="var(--wa)" pulse size={7} />
          </div>
          <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {clientName} · {conv.current_intent || 'conversación activa'}
          </div>
        </div>
        {displayPhone && <Tag hue="wine" style={{ fontSize: 11 }}>{displayPhone.slice(-4)}</Tag>}
      </div>

      <div style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 9, background: 'var(--surface-tint)', flex: 1, maxHeight: 288, overflowY: 'auto' }}>
        {recentMsgs.length === 0 && (
          <span style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-4)', alignSelf: 'center' }}>Sin mensajes</span>
        )}
        {recentMsgs.map((m) => (
          <div key={m.id} style={{ alignSelf: m.direction === 'outbound' ? 'flex-end' : 'flex-start', maxWidth: '82%' }}>
            <div style={{
              padding: '8px 12px',
              borderRadius: m.direction === 'outbound' ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
              background: m.direction === 'outbound' ? 'var(--wine)' : 'var(--surface-2)',
              color: m.direction === 'outbound' ? 'var(--wine-fg)' : 'var(--ink-1)',
              border: m.direction === 'outbound' ? '1px solid transparent' : '1px solid var(--line)',
              font: '400 13px/1.4 var(--font-sans)', boxShadow: 'var(--shadow-sm)',
            }}>{m.content || '…'}</div>
            <div style={{ font: '400 10px/1 var(--font-mono)', color: 'var(--ink-4)', marginTop: 3, textAlign: m.direction === 'outbound' ? 'right' : 'left' }}>
              {m.sent_at ? format(parseISO(m.sent_at), 'HH:mm') : ''}{m.direction === 'outbound' && m.sender_type === 'agent' ? ' · agente' : ''}
            </div>
          </div>
        ))}
        {typing && (
          <div style={{ alignSelf: 'flex-end', padding: '10px 14px', borderRadius: '14px 14px 4px 14px', background: 'var(--wine)', display: 'flex', gap: 4 }}>
            {[0, 1, 2].map(i => <span key={i} style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--wine-fg)', opacity: 0.85, animation: `hilo-typing 1s ${i * 0.15}s var(--ease-std) infinite` }} />)}
          </div>
        )}
      </div>

      <div style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 11, borderTop: '1px solid var(--line)' }}>
        <span style={{ width: 30, height: 30, borderRadius: 'var(--r-sm)', background: conv.needs_review ? 'var(--warning-bg)' : 'color-mix(in srgb, var(--success) 14%, var(--surface))', display: 'grid', placeItems: 'center', color: conv.needs_review ? 'var(--warning)' : 'var(--success)' }}>
          <Icon name={conv.needs_review ? 'bell' : 'checkCircle'} size={17} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ font: '500 13px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>
            {conv.needs_review ? 'Necesita revisión' : 'Atendida por el agente'}
          </div>
          <div style={{ font: '400 11.5px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>
            {conv.current_intent || conv.last_agent_state || 'Sin intent activo'}
          </div>
        </div>
        <Button variant="ghost" size="sm" iconRight="chev" onClick={() => navigate({ to: '/messages' })}>Ver</Button>
      </div>
    </div>
  );
}

function fmtResponse(s: number | null | undefined): string {
  if (!s) return '—';
  return s < 60 ? `${s} s` : `${Math.round(s / 60)} min`;
}

function DashboardPage() {
  const navigate = useNavigate();
  const { me, workspaceId } = useAuth();
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 880;

  const today = format(new Date(), 'yyyy-MM-dd');
  const { data: todayAppointments = [], isLoading, isError } = useAppointments({ from_date: today, to_date: today });

  const { data: stats } = useQuery({
    queryKey: ['workspace-stats', workspaceId],
    queryFn: () => getWorkspaceStats(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });

  const { data: channels = [] } = useQuery({
    queryKey: ['channels', workspaceId],
    queryFn: () => listChannels(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60 * 1000,
  });

  const { data: calendars = [] } = useQuery({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60 * 1000,
  });

  const { data: conversations = [] } = useConversations();

  useEffect(() => {
    if (isError) toast.error('No se pudieron cargar las citas del día.');
  }, [isError]);

  const todayCount    = todayAppointments.length;
  const doneCount     = todayAppointments.filter(a => a.status === 'done').length;
  const upcomingCount = todayAppointments.filter(a => a.status === 'upcoming' || a.status === 'next' || a.status === 'now').length;

  const revDelta = stats && stats.revenue_prev_month > 0
    ? Math.round((stats.revenue_month - stats.revenue_prev_month) / stats.revenue_prev_month * 100)
    : undefined;

  const activeChannel  = channels.find(c => c.status === 'active') ?? channels[0] ?? null;
  const activeCalendar = calendars.find(c => c.sync_status === 'active') ?? calendars[0] ?? null;
  const reviewConvs    = conversations.filter(c => c.needs_review);

  const ownerName = me?.email?.split('@')[0] ?? '';
  const hour      = new Date().getHours();
  const greeting  = hour < 12 ? 'Buenos días' : hour < 18 ? 'Buenas tardes' : 'Buenas noches';
  const todayLabel = format(new Date(), "EEEE d 'de' MMMM", { locale: es });

  return (
    <div style={{ maxWidth: 1180, margin: '0 auto', padding: isMobile ? '18px 16px 28px' : '26px 30px 40px', animation: 'hilo-fade-up var(--dur-3) var(--ease-out)' }}>

      {/* ── Encabezado ── */}
      <div style={{ marginBottom: 22 }}>
        <div className="eyebrow" style={{ marginBottom: 8, textTransform: 'capitalize' }}>{todayLabel}</div>
        <h2 style={{ margin: 0, font: '400 clamp(26px,4vw,34px)/1.08 var(--font-serif)', letterSpacing: '-0.01em', color: 'var(--ink-1)' }}>
          {greeting}, <span className="serif-i">{ownerName}</span>.
        </h2>
        <p style={{ margin: '8px 0 0', font: '400 15.5px/1.5 var(--font-sans)', color: 'var(--ink-2)', maxWidth: 560 }}>
          {isLoading
            ? 'Cargando datos del día…'
            : todayCount === 0
              ? 'Sin citas para hoy.'
              : `Quedan ${upcomingCount} cita${upcomingCount !== 1 ? 's' : ''} por atender hoy.`}
        </p>
      </div>

      {/* ── KPIs ── */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(auto-fit, minmax(${isMobile ? '150px' : '200px'}, 1fr))`, gap: 14, marginBottom: 18 }}>
        <StatCard
          eyebrow="Citas de hoy"
          value={isLoading ? '—' : todayCount}
          sub={isLoading ? 'Cargando…' : `${doneCount} atendidas · ${upcomingCount} por venir`}
          icon="calendar"
        />
        <StatCard
          eyebrow="Ingresos del mes"
          value={stats ? fmtCOP(stats.revenue_month) : '—'}
          delta={revDelta}
          sub="vs. mes anterior"
          icon="money"
          accent="var(--clay)"
        />
        <StatCard
          eyebrow="Chats atendidos"
          value={stats ? stats.chats_month : '—'}
          sub="conversaciones este mes"
          icon="chat"
          accent="var(--steel)"
        />
        <StatCard
          eyebrow="Respuesta media"
          value={stats ? fmtResponse(stats.response_avg_seconds) : '—'}
          sub="del agente en WhatsApp"
          icon="bolt"
          accent="var(--sage)"
        />
      </div>

      {/* ── Grid principal ── */}
      <div style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : '1.45fr 1fr', gap: 18, alignItems: 'start' }}>

        {/* El día como historia */}
        <div className="card" style={{ padding: '18px 20px 6px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div>
              <h3 style={{ margin: 0, font: '400 21px/1.1 var(--font-serif)', color: 'var(--ink-1)' }}>El día como <span className="serif-i">historia</span></h3>
              <div style={{ font: '400 12.5px/1 var(--font-sans)', color: 'var(--ink-3)', marginTop: 4 }}>Cada nudo es una cita en tu hilo de hoy</div>
            </div>
            <Button variant="ghost" size="sm" iconRight="arrowR" onClick={() => navigate({ to: '/agenda' })}>Agenda</Button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '58px 28px 1fr', alignItems: 'center', margin: '6px 0' }}>
            <span className="tnum" style={{ textAlign: 'right', paddingRight: 14, font: '500 11px/1 var(--font-mono)', color: 'var(--wine)' }}>{format(new Date(), 'HH:mm')}</span>
            <span />
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ flex: 1, height: 1, background: 'repeating-linear-gradient(90deg, var(--wine-300) 0 5px, transparent 5px 10px)' }} />
              <span style={{ font: '500 10px/1 var(--font-sans)', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--wine)' }}>ahora</span>
            </span>
          </div>

          {isLoading ? (
            <div style={{ padding: '24px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[1, 2, 3].map(i => (
                <div key={i} style={{ display: 'grid', gridTemplateColumns: '58px 28px 1fr', gap: 0 }}>
                  <div style={{ height: 14, margin: '14px 14px 0 0', background: 'var(--line)', borderRadius: 4 }} />
                  <div />
                  <div style={{ height: 56, margin: '8px 0 14px', background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)' }} />
                </div>
              ))}
            </div>
          ) : todayAppointments.length === 0 ? (
            <div style={{ padding: '24px 0', textAlign: 'center', color: 'var(--ink-3)', font: '400 13px/1.4 var(--font-sans)' }}>
              Sin citas para hoy
            </div>
          ) : (
            <div>
              {todayAppointments.map((a, i) => (
                <ThreadItem key={a.id} a={a} isLast={i === todayAppointments.length - 1} />
              ))}
            </div>
          )}
        </div>

        {/* Columna derecha */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          <AgentPanel />

          {/* Conversaciones que necesitan atención */}
          {reviewConvs.length > 0 && (
            <div className="card" style={{ padding: '4px 0' }}>
              <div className="eyebrow" style={{ padding: '12px 16px 8px' }}>Necesita tu atención</div>
              {reviewConvs.slice(0, 3).map((c, i) => (
                <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '10px 16px', borderTop: i ? '1px solid var(--line)' : 'none' }}>
                  <span style={{ width: 30, height: 30, borderRadius: 'var(--r-sm)', display: 'grid', placeItems: 'center', background: 'var(--warning-bg)', color: 'var(--warning)' }}>
                    <Icon name="bell" size={16} />
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ font: '500 13px/1.25 var(--font-sans)', color: 'var(--ink-1)' }}>El agente necesita ayuda</div>
                    <div style={{ font: '400 11.5px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>{c.current_intent || 'Conversación sin resolver'}</div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => navigate({ to: '/messages' })}>Revisar</Button>
                </div>
              ))}
            </div>
          )}

          {/* Canal WhatsApp */}
          {activeChannel && (
            <div className="card" style={{ padding: '14px 16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ width: 32, height: 32, borderRadius: 'var(--r-sm)', background: 'var(--wa-bg)', display: 'grid', placeItems: 'center', color: 'var(--wa-ink)' }}>
                    <Icon name="whatsapp" size={18} />
                  </span>
                  <div>
                    <div className="tnum" style={{ font: '500 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{activeChannel.phone_number}</div>
                    <div style={{ font: '400 11.5px/1.2 var(--font-sans)', color: 'var(--ink-3)' }}>
                      {activeChannel.coexistence_enabled ? 'Coexistencia activa' : 'WhatsApp Business'} · {activeChannel.provider}
                    </div>
                  </div>
                </div>
                <Tag hue="sage" style={{ fontSize: 11 }}><Dot color="var(--wa)" size={6} />Activo</Tag>
              </div>
              {activeCalendar && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--line)', font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>
                  <Icon name="sync" size={14} style={{ color: 'var(--success)' }} />
                  Google Calendar · {activeCalendar.last_synced_at
                    ? formatDistanceToNow(parseISO(activeCalendar.last_synced_at), { locale: es, addSuffix: true })
                    : 'nunca sincronizado'}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
