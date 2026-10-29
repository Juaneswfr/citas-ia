import { createFileRoute } from "@tanstack/react-router";
import { useAuth } from "@/lib/auth-context";
import { useTypography } from "@/lib/typography-context";
import { toast } from "sonner";
import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Icon } from "@/components/hilo/icons";
import { Button } from "@/components/hilo/primitives";
import { listChannels, updateChannelStatus, listCalendars, createKapsoOnboardingLink, createSandboxSession, getSandboxSession, type SandboxSession } from "@/lib/api/channels";
import { getGoogleCalendarUrl } from "@/lib/api/auth";
import { apiFetch } from "@/lib/api/client";
import type { ChannelOut, CalendarOut, WorkspaceOut } from "@/lib/types/api";

export const Route = createFileRoute("/_authenticated/settings")({
  head: () => ({ meta: [{ title: "Ajustes · Hilo" }] }),
  component: SettingsPage,
});

// ── Estilos reutilizables ─────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '9px 11px', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--line-strong)', background: 'var(--surface-2)',
  font: '400 14px/1.3 var(--font-sans)', color: 'var(--ink-1)', outline: 'none',
};

const labelStyle: React.CSSProperties = {
  font: '500 12px/1 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 6, display: 'block',
};

// ── Sección WhatsApp ──────────────────────────────────────────────────────────

function WhatsAppSection({ workspaceId }: { workspaceId: string }) {
  const qc = useQueryClient();
  const [connecting, setConnecting] = useState(false);

  const { data: channels = [], isLoading } = useQuery<ChannelOut[]>({
    queryKey: ['channels', workspaceId],
    queryFn: () => listChannels(workspaceId),
    staleTime: 30_000,
  });

  const connectViaKapso = async () => {
    setConnecting(true);
    try {
      const { url } = await createKapsoOnboardingLink(workspaceId);
      window.open(url, '_blank');
    } catch (err: any) {
      toast.error(err?.detail ?? err?.message ?? 'Error generando enlace de conexión.');
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async (ch: ChannelOut) => {
    try {
      await updateChannelStatus(workspaceId, ch.id, 'disconnected');
      toast.success('Canal desconectado.');
      qc.invalidateQueries({ queryKey: ['channels', workspaceId] });
    } catch {
      toast.error('Error al desconectar el canal.');
    }
  };

  if (isLoading) return <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>Cargando...</span>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {channels.map(ch => (
        <div key={ch.id} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 14px', borderRadius: 'var(--r-md)',
          background: 'var(--surface)', border: '1px solid var(--line)',
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: ch.status === 'active' ? 'var(--success)' : 'var(--ink-4)',
          }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>
              {ch.display_name ?? ch.phone_number}
            </div>
            <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>
              {ch.phone_number} · {ch.status === 'active' ? 'Activo' : ch.status === 'paused' ? 'Pausado' : 'Desconectado'}
              {ch.coexistence_enabled ? ' · coexistente' : ''}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            <Button variant="ghost" size="sm" icon="sync" onClick={connectViaKapso} disabled={connecting} style={{ padding: 7 }} />
            {ch.status === 'active' && (
              <Button variant="ghost" size="sm" onClick={() => handleDisconnect(ch)}>Desconectar</Button>
            )}
          </div>
        </div>
      ))}

      {channels.length === 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px', borderRadius: 'var(--r-md)',
          border: '1px dashed var(--line-strong)', background: 'var(--surface-tint)',
        }}>
          <Icon name="whatsapp" size={20} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ font: '500 13px/1.2 var(--font-sans)', color: 'var(--ink-2)' }}>Sin canal conectado</div>
            <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>
              Conecta tu WhatsApp Business para activar el agente
            </div>
          </div>
          <Button variant="primary" size="sm" onClick={connectViaKapso} disabled={connecting}>
            {connecting ? 'Conectando…' : 'Conectar'}
          </Button>
        </div>
      )}

      {channels.length > 0 && (
        <Button variant="ghost" size="sm" icon="plus" onClick={connectViaKapso} disabled={connecting} style={{ alignSelf: 'flex-start' }}>
          Agregar número
        </Button>
      )}
    </div>
  );
}

// ── Sección Google Calendar ───────────────────────────────────────────────────

function CalendarSection({ workspaceId }: { workspaceId: string }) {
  const qc = useQueryClient();
  const [connecting, setConnecting] = useState(false);

  const { data: calendars = [], isLoading } = useQuery<CalendarOut[]>({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId),
    staleTime: 30_000,
  });

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const { url } = await getGoogleCalendarUrl(workspaceId, 'settings');
      window.location.href = url;
    } catch {
      toast.error('No se pudo iniciar la conexión con Google Calendar.');
      setConnecting(false);
    }
  };

  if (isLoading) return <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>Cargando...</span>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {calendars.map(cal => (
        <div key={cal.id} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '12px 14px', borderRadius: 'var(--r-md)',
          background: 'var(--surface)', border: '1px solid var(--line)',
        }}>
          <span style={{
            width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
            background: cal.sync_status === 'active' ? 'var(--success)' : 'var(--ink-4)',
          }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{cal.name}</div>
            <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>
              {cal.google_calendar_id}
              {cal.last_synced_at ? ` · sync ${new Date(cal.last_synced_at).toLocaleDateString('es-CO')}` : ''}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              font: '500 11px/1 var(--font-sans)', padding: '3px 8px',
              borderRadius: 'var(--r-full)', letterSpacing: '0.02em',
              background: cal.sync_status === 'active' ? 'var(--success-bg, #ecfdf5)' : 'var(--surface-2)',
              color: cal.sync_status === 'active' ? 'var(--success)' : 'var(--ink-3)',
              border: `1px solid ${cal.sync_status === 'active' ? 'color-mix(in srgb, var(--success) 25%, transparent)' : 'var(--line)'}`,
            }}>
              {cal.sync_status === 'active' ? 'Sincronizado' : 'Desconectado'}
            </span>
            <Button variant="ghost" size="sm" icon="sync" onClick={handleConnect} disabled={connecting} style={{ padding: 7 }} />
          </div>
        </div>
      ))}

      {calendars.length === 0 && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px', borderRadius: 'var(--r-md)',
          border: '1px dashed var(--line-strong)', background: 'var(--surface-tint)',
        }}>
          <Icon name="calendar" size={20} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ font: '500 13px/1.2 var(--font-sans)', color: 'var(--ink-2)' }}>Sin calendario conectado</div>
            <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>
              Conecta Google Calendar para sincronizar citas automáticamente
            </div>
          </div>
          <Button variant="primary" size="sm" onClick={handleConnect} disabled={connecting}>
            {connecting ? 'Conectando…' : 'Conectar'}
          </Button>
        </div>
      )}

      {calendars.length > 0 && (
        <Button variant="ghost" size="sm" icon="plus" onClick={handleConnect} disabled={connecting} style={{ alignSelf: 'flex-start' }}>
          Agregar calendario
        </Button>
      )}
    </div>
  );
}

// ── Sandbox Kapso ────────────────────────────────────────────────────────────

function SandboxSection({ workspaceId }: { workspaceId: string }) {
  const [phone, setPhone] = useState('');
  const [creating, setCreating] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [session, setSession] = useState<SandboxSession | null>(null);

  const { data: polled } = useQuery<SandboxSession>({
    queryKey: ['sandbox-session', workspaceId, sessionId],
    queryFn: () => getSandboxSession(workspaceId, sessionId!),
    enabled: !!sessionId && session?.status === 'pending_activation',
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (polled) setSession(polled);
  }, [polled]);

  const handleCreate = async () => {
    if (!phone.trim()) return;
    setCreating(true);
    try {
      const res = await createSandboxSession(workspaceId, phone.trim());
      setSession(res);
      setSessionId(res.id ?? null);
    } catch (err: any) {
      toast.error(err?.detail ?? 'Error creando sesión sandbox.');
    } finally {
      setCreating(false);
    }
  };

  const isExpired = session?.expires_at ? new Date(session.expires_at) < new Date() : false;
  const status = isExpired ? 'expired' : session?.status;

  // Countdown
  const [timeLeft, setTimeLeft] = useState('');
  useEffect(() => {
    if (!session?.expires_at) return;
    const tick = () => {
      const diff = new Date(session.expires_at).getTime() - Date.now();
      if (diff <= 0) { setTimeLeft('Expirada'); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      setTimeLeft(`${h}h ${m}m`);
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => clearInterval(id);
  }, [session?.expires_at]);

  if (!session || status === 'expired') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {status === 'expired' && (
          <div style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-3)', padding: '8px 0' }}>
            Sesión expirada. Crea una nueva para seguir probando.
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <label style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={labelStyle}>Tu número de WhatsApp</span>
            <input
              value={phone}
              onChange={e => setPhone(e.target.value)}
              placeholder="+573001234567"
              type="tel"
              style={inputStyle}
            />
          </label>
          <Button variant="primary" size="sm" onClick={handleCreate} disabled={creating}>
            {creating ? 'Creando…' : 'Crear sesión'}
          </Button>
        </div>
        <div style={{ font: '400 12px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>
          Formato internacional sin espacios. Las sesiones duran 24 horas.
        </div>
      </div>
    );
  }

  if (status === 'pending_activation') {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-2)' }}>
          Envía este código desde tu WhatsApp al número del sandbox para activar la sesión:
        </div>
        <div style={{
          padding: '16px 20px', borderRadius: 'var(--r-md)',
          background: 'var(--surface-2)', border: '1px solid var(--line)',
          textAlign: 'center',
        }}>
          <div style={{ font: '600 28px/1 var(--font-mono)', letterSpacing: '0.1em', color: 'var(--ink-1)' }}>
            {session.activation_code}
          </div>
        </div>
        {session.activation_link && (
          <a
            href={session.activation_link}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              font: '500 13px/1 var(--font-sans)', color: 'var(--wine)',
              textDecoration: 'none', alignSelf: 'center',
            }}
          >
            Abrir en WhatsApp
          </a>
        )}
        <div style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)', textAlign: 'center' }}>
          Esperando activación… · Expira en {timeLeft}
        </div>
      </div>
    );
  }

  // active
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%', background: 'var(--success)', flexShrink: 0,
        }} />
        <span style={{ font: '500 14px/1 var(--font-sans)', color: 'var(--ink-1)' }}>
          Sandbox activo
        </span>
        <span style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)', marginLeft: 'auto' }}>
          Expira en {timeLeft}
        </span>
      </div>
      <div style={{ font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-2)' }}>
        Envía un mensaje al <strong>+56 9 2040 3095</strong> desde tu WhatsApp para probar el agente.
      </div>
      <Button variant="ghost" size="sm" onClick={() => { setSession(null); setSessionId(null); }} style={{ alignSelf: 'flex-start' }}>
        Nueva sesión
      </Button>
    </div>
  );
}

// ── Tipografía ────────────────────────────────────────────────────────────────

function TypographySection() {
  const { pairs, current, setPair } = useTypography();
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 10 }}>
      {pairs.map(p => {
        const sel = current.id === p.id;
        return (
          <button key={p.id} onClick={() => setPair(p.id)} style={{
            textAlign: 'left', padding: '14px 16px', borderRadius: 'var(--r-md)',
            border: `2px solid ${sel ? 'var(--wine)' : 'var(--line)'}`,
            background: sel ? 'var(--wine-50)' : 'var(--surface)',
            cursor: 'pointer', transition: 'all var(--dur-2) var(--ease-std)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <span style={{ fontSize: 22, letterSpacing: '-0.02em', lineHeight: 1, fontFamily: p.heading, color: 'var(--ink-1)' }}>
                Aa
              </span>
              {sel && <Icon name="check" size={14} style={{ color: 'var(--wine)', marginTop: 2 }} />}
            </div>
            <div style={{ marginTop: 10, fontSize: 12, fontFamily: p.body, color: 'var(--ink-2)', lineHeight: 1.4 }}>
              El zorro marrón salta sobre el perro.
            </div>
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line)' }}>
              <div style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--ink-1)' }}>{p.label}</div>
              <div style={{ font: '400 11px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 3 }}>{p.description}</div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Página ────────────────────────────────────────────────────────────────────

const roleLabel: Record<string, string> = {
  workspace_owner: 'Propietario', manager: 'Manager', staff: 'Staff', viewer: 'Viewer',
};

function SettingsPage() {
  const { me } = useAuth();
  const qc = useQueryClient();
  const [bizName, setBizName] = useState('');
  const [saving, setSaving] = useState(false);
  const displayName = me?.email?.split('@')[0] ?? '';

  // Manejar retorno desde OAuth de Google Calendar
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('calendar_connected') === '1') {
      toast.success('Google Calendar conectado correctamente.');
      if (me?.workspace_id) qc.invalidateQueries({ queryKey: ['calendars', me.workspace_id] });
      window.history.replaceState({}, '', window.location.pathname);
    } else if (params.get('calendar_error') === '1') {
      toast.error('No se pudo conectar Google Calendar. Intenta de nuevo.');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const { data: workspace } = useQuery<WorkspaceOut | null>({
    queryKey: ['workspace', me?.workspace_id],
    queryFn: async () => {
      try { return await apiFetch<WorkspaceOut>(`/workspaces/${me!.workspace_id}`); }
      catch { return null; }
    },
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  useEffect(() => {
    if (workspace?.name) setBizName(workspace.name);
  }, [workspace?.name]);

  const handleSaveBiz = async () => {
    if (!me?.workspace_id || !bizName.trim()) return;
    setSaving(true);
    try {
      await apiFetch(`/workspaces/${me.workspace_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: bizName.trim() }),
      });
      toast.success('Nombre del negocio actualizado.');
      qc.invalidateQueries({ queryKey: ['workspace', me.workspace_id] });
    } catch (err: any) {
      toast.error(err?.detail ?? 'Error al guardar.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '24px 20px', maxWidth: 860, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>

      <div>
        <h2 style={{ margin: 0, font: '500 22px/1.1 var(--font-sans)', letterSpacing: '-0.02em', color: 'var(--ink-1)' }}>
          Ajustes
        </h2>
        <p style={{ margin: '4px 0 0', font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>
          Cuenta, integraciones y apariencia del panel.
        </p>
      </div>

      {/* Cuenta */}
      <SettingsCard icon="user" title="Cuenta" description="Tu información de usuario y workspace.">
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 14 }}>
          {[
            { label: 'Nombre', value: displayName },
            { label: 'Correo', value: me?.email ?? '—' },
            { label: 'Rol', value: roleLabel[me?.role ?? ''] ?? me?.role ?? '—' },
          ].map(f => (
            <label key={f.label} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={labelStyle}>{f.label}</span>
              <input value={f.value} disabled style={{ ...inputStyle, opacity: 0.7, cursor: 'default' }} />
            </label>
          ))}
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={labelStyle}>Workspace ID</span>
            <input value={me?.workspace_id ?? '—'} disabled style={{ ...inputStyle, opacity: 0.7, cursor: 'default', fontFamily: 'var(--font-mono)', fontSize: 12 }} />
          </label>
        </div>
      </SettingsCard>

      {/* Negocio */}
      <SettingsCard icon="gear" title="Negocio" description="Nombre visible en mensajes del agente.">
        <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span style={labelStyle}>Nombre del negocio</span>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={bizName}
              onChange={e => setBizName(e.target.value)}
              placeholder="Ej: Navaja & Tinta"
              style={inputStyle}
            />
            <Button variant="primary" size="sm" onClick={handleSaveBiz} disabled={saving}>
              {saving ? 'Guardando…' : 'Guardar'}
            </Button>
          </div>
        </label>
      </SettingsCard>

      {/* WhatsApp */}
      <SettingsCard icon="whatsapp" title="WhatsApp Business" description="Canales conectados. El agente Atenea responde por estos números.">
        {me?.workspace_id
          ? <WhatsAppSection workspaceId={me.workspace_id} />
          : <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>No hay workspace activo.</span>
        }
      </SettingsCard>

      {/* Sandbox */}
      {(me?.role === 'workspace_owner' || me?.role === 'super_admin') && (
        <SettingsCard icon="whatsapp" title="Sandbox de pruebas" description="Prueba el agente con el número sandbox de Kapso. Sesiones de 24h.">
          {me?.workspace_id
            ? <SandboxSection workspaceId={me.workspace_id} />
            : <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>No hay workspace activo.</span>
          }
        </SettingsCard>
      )}

      {/* Google Calendar */}
      <SettingsCard icon="calendar" title="Google Calendar" description="Calendarios sincronizados para gestionar disponibilidad.">
        {me?.workspace_id
          ? <CalendarSection workspaceId={me.workspace_id} />
          : <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>No hay workspace activo.</span>
        }
      </SettingsCard>

      {/* Tipografía */}
      <SettingsCard icon="layers" title="Tipografía" description="Pareja tipográfica del panel. Se aplica al instante.">
        <TypographySection />
      </SettingsCard>

    </div>
  );
}

function SettingsCard({ icon, title, description, children }: {
  icon: string; title: string; description: string; children: React.ReactNode;
}) {
  return (
    <section className="card" style={{ padding: '18px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <span style={{
          width: 30, height: 30, borderRadius: 'var(--r-sm)', flexShrink: 0,
          background: 'var(--wine-50)', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon name={icon} size={15} style={{ color: 'var(--wine)' }} />
        </span>
        <div>
          <div style={{ font: '500 15px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{title}</div>
          <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>{description}</div>
        </div>
      </div>
      {children}
    </section>
  );
}
