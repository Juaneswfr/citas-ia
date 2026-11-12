import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Avatar, Button } from "@/components/hilo/primitives";
import { useAuth } from "@/lib/auth-context";
import { listMembers, inviteMember, removeMember } from "@/lib/api/workspaces";
import { CalendarDays, CalendarCheck } from "lucide-react";
import { listCalendars } from "@/lib/api/channels";
import { getGoogleCalendarUrl } from "@/lib/api/auth";
import type { MemberOut, CalendarOut } from "@/lib/types/api";
import { roleLabel } from "@/lib/roles";


export const Route = createFileRoute("/_authenticated/equipo")({
  head: () => ({ meta: [{ title: "Equipo · Hilo" }] }),
  component: EquipoPage,
});

const HUES = ['clay','wine','mustard','steel','sage','plum','teal'];
const memberHue = (id: string) => HUES[id.charCodeAt(0) % HUES.length];

const ROLES = ['staff', 'manager', 'viewer'] as const;

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', borderRadius: 'var(--r-sm)',
  border: '1px solid var(--line-strong)', background: 'var(--surface-2)',
  font: '400 14px/1.3 var(--font-sans)', color: 'var(--ink-1)', outline: 'none',
};

function EquipoPage() {
  const { workspaceId } = useAuth();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<string>('staff');

  const { data: team = [], isLoading } = useQuery<MemberOut[]>({
    queryKey: ['team', workspaceId],
    queryFn: () => listMembers(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });

  const { data: calendars = [] } = useQuery<CalendarOut[]>({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 60_000,
  });
  const [connectingId, setConnectingId] = useState<string | null>(null);

  const connectCalendar = async (memberId: string) => {
    if (!workspaceId) return;
    setConnectingId(memberId);
    try {
      const { url } = await getGoogleCalendarUrl(workspaceId, 'equipo', memberId);
      window.location.href = url;
    } catch {
      toast.error('No se pudo iniciar la conexión con Google. Intenta de nuevo.');
      setConnectingId(null);
    }
  };

  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    if (p.get('calendar_connected')) {
      toast.success('Google Calendar conectado');
      qc.invalidateQueries({ queryKey: ['calendars', workspaceId] });
    } else if (p.get('calendar_error')) {
      toast.error('No se pudo conectar Google Calendar');
    }
  }, []);

  const invite = useMutation({
    mutationFn: () => inviteMember(workspaceId!, email.trim(), role),
    onSuccess: () => {
      toast.success('Miembro agregado');
      qc.invalidateQueries({ queryKey: ['team', workspaceId] });
      setEmail(''); setRole('staff'); setShowForm(false);
    },
    onError: (err: any) => {
      toast.error(err?.detail ?? err?.message ?? 'Error al agregar miembro');
    },
  });

  const remove = useMutation({
    mutationFn: (userId: string) => removeMember(workspaceId!, userId),
    onSuccess: () => {
      toast.success('Miembro eliminado');
      qc.invalidateQueries({ queryKey: ['team', workspaceId] });
    },
    onError: (err: any) => {
      toast.error(err?.detail ?? err?.message ?? 'Error al eliminar miembro');
    },
  });

  return (
    <div className="page page-enter" style={{ maxWidth: 860 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h2 style={{ margin: 0, font: '500 22px/1.1 var(--font-sans)', letterSpacing: '-0.02em', color: 'var(--ink-1)' }}>Equipo</h2>
          <p style={{ margin: '4px 0 0', font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>
            Miembros con acceso al workspace.
          </p>
        </div>
        <Button variant="primary" size="sm" icon="plus" style={{ marginLeft: 'auto' }} onClick={() => setShowForm(v => !v)}>
          Agregar miembro
        </Button>
      </div>

      {showForm && (
        <div className="card" style={{ padding: '16px 20px', marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--ink-2)' }}>Email del usuario</span>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="usuario@ejemplo.com" style={inputStyle}
            />
          </label>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--ink-2)' }}>Rol</span>
            <select value={role} onChange={e => setRole(e.target.value)} style={inputStyle}>
              {ROLES.map(r => <option key={r} value={r}>{roleLabel(r)}</option>)}
            </select>
          </label>
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="primary" size="sm" disabled={!email.trim() || invite.isPending}
              onClick={() => invite.mutate()}>
              {invite.isPending ? 'Agregando…' : 'Agregar'}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}>Cancelar</Button>
          </div>
          <p style={{ margin: 0, font: '400 11.5px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>
            El usuario debe tener cuenta registrada en Hilo para poder ser agregado.
          </p>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        {isLoading ? (
          <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: 12 }}>
            {[1,2,3].map(i => (
              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'var(--line)' }} />
                <div style={{ flex: 1, height: 13, background: 'var(--line)', borderRadius: 4 }} />
              </div>
            ))}
          </div>
        ) : team.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--ink-3)', font: '400 13px/1.4 var(--font-sans)' }}>
            Sin miembros en el equipo.
          </div>
        ) : (
          team.map((m, i) => (
            <div key={m.id} style={{
              display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '10px 13px',
              padding: '13px 16px',
              borderBottom: i < team.length - 1 ? '1px solid var(--line-soft)' : 'none',
            }}>
              <Avatar name={m.name ?? m.email ?? '?'} hue={memberHue(m.id)} size={38} />
              <div style={{ flex: '1 1 180px', minWidth: 0, overflowWrap: 'anywhere' }}>
                <div style={{ font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>
                  {m.name ?? m.email ?? '—'}
                </div>
                {m.name && (
                  <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>
                    {m.email}
                  </div>
                )}
              </div>
              {(() => {
                const connected = calendars.some(c => c.member_id === m.id && c.sync_status === 'active');
                return (
                  <button
                    onClick={() => !connected && connectCalendar(m.id)}
                    disabled={connected || connectingId === m.id}
                    title={connected ? 'Google Calendar conectado' : 'Conectar Google Calendar'}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 6,
                      font: '500 12px/1 var(--font-sans)', padding: '6px 10px',
                      borderRadius: 'var(--r-full)', cursor: connected ? 'default' : 'pointer',
                      border: `1px solid ${connected ? '#1e8e3e' : 'var(--line-strong)'}`,
                      background: connected ? '#e6f4ea' : 'var(--surface)',
                      color: connected ? '#1e8e3e' : 'var(--ink-2)',
                    }}
                  >
                    {connected
                      ? <CalendarCheck size={16} strokeWidth={2.2} />
                      : <CalendarDays size={16} strokeWidth={2.2} color="#4285F4" />}
                    {connected ? 'Conectado ✓' : connectingId === m.id ? 'Conectando…' : 'Conectar'}
                  </button>
                );
              })()}
              <span style={{
                font: '500 11px/1 var(--font-sans)', padding: '3px 9px',
                borderRadius: 'var(--r-full)', letterSpacing: '0.02em',
                background: 'var(--surface-2)', color: 'var(--ink-2)',
                border: '1px solid var(--line)',
              }}>
                {roleLabel(m.member_role)}
              </span>
              {m.member_role !== 'workspace_owner' && (
                <button
                  onClick={() => remove.mutate(m.user_id)}
                  disabled={remove.isPending}
                  title="Eliminar miembro"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-4)', padding: '4px', borderRadius: 'var(--r-sm)' }}
                >
                  ✕
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
