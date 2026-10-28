import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState, useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Icon, HiloMark } from "@/components/hilo/icons";
import { Button, Tag } from "@/components/hilo/primitives";
import { useAuth } from "@/lib/auth-context";
import {
  BUSINESS_TYPES,
  BUSINESS_PRESETS,
  type BusinessTypeId,
} from "@/lib/hilo-data";
import { getGoogleCalendarUrl } from "@/lib/api/auth";
import { patchWorkspace } from "@/lib/api/workspaces";
import { listChannels, listCalendars, createKapsoOnboardingLink } from "@/lib/api/channels";
import { listServices, createService } from "@/lib/api/services";
import { apiFetch } from "@/lib/api/client";
import type { WorkspaceOut, ChannelOut, CalendarOut, ServiceOut } from "@/lib/types/api";

export const Route = createFileRoute("/_authenticated/onboarding")({
  head: () => ({ meta: [{ title: "Configuración inicial · Hilo" }] }),
  component: OnboardingPage,
});

const STEPS = [
  { id: 0, icon: 'gear',     title: 'Tu negocio',        sub: 'Nombre, ciudad y tipo de negocio' },
  { id: 1, icon: 'whatsapp', title: 'WhatsApp Business',  sub: 'Coexistencia · conserva tu número' },
  { id: 2, icon: 'calendar', title: 'Google Calendar',    sub: 'Tu disponibilidad real' },
  { id: 3, icon: 'layers',   title: 'Servicios',          sub: 'Qué ofreces y a qué precio' },
  { id: 4, icon: 'sparkle',  title: 'Prueba el agente',   sub: 'Agenda tu primera cita de prueba' },
];

// ── Shared input style ─────────────────────────────────────────────────────────

const oInput: React.CSSProperties = {
  width: '100%', padding: '11px 13px', borderRadius: 'var(--r-md)',
  border: '1px solid var(--line-strong)', background: 'var(--surface-2)',
  font: '400 15px/1.3 var(--font-sans)', color: 'var(--ink-1)', outline: 'none',
};

// ── ConnectCard ───────────────────────────────────────────────────────────────

function ConnectCard({ icon, color, bg, title, sub, connected, onConnect, loading, foot }: {
  icon: string; color: string; bg: string; title: string; sub: string;
  connected: boolean; onConnect: () => void; loading?: boolean; foot?: React.ReactNode;
}) {
  return (
    <div style={{
      border: `1px solid ${connected ? 'color-mix(in srgb, var(--success) 35%, transparent)' : 'var(--line-strong)'}`,
      borderRadius: 'var(--r-lg)', padding: '20px',
      background: connected ? 'color-mix(in srgb, var(--success) 5%, var(--surface))' : 'var(--surface)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ width: 48, height: 48, borderRadius: 'var(--r-md)', background: bg, color, display: 'grid', placeItems: 'center' }}>
          <Icon name={icon} size={26} />
        </span>
        <div style={{ flex: 1 }}>
          <div style={{ font: '500 16px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{title}</div>
          <div style={{ font: '400 13px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 3 }}>{sub}</div>
        </div>
        {connected
          ? <Tag hue="sage"><Icon name="check" size={13} />Conectado</Tag>
          : loading
            ? <Button variant="primary" disabled>Conectando…</Button>
            : <Button variant="primary" onClick={onConnect}>Conectar</Button>
        }
      </div>
      {foot && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--line)', font: '400 12.5px/1.5 var(--font-sans)', color: 'var(--ink-2)' }}>
          {foot}
        </div>
      )}
    </div>
  );
}

// ── Step 0: Tu negocio ────────────────────────────────────────────────────────

function StepBusiness({
  businessType, setBusinessType, businessName, setBusinessName, city, setCity,
}: {
  businessType: BusinessTypeId | null;
  setBusinessType: (t: BusinessTypeId) => void;
  businessName: string;
  setBusinessName: (n: string) => void;
  city: string;
  setCity: (c: string) => void;
}) {
  const [tone, setTone] = useState(0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          <span style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)' }}>Nombre del negocio</span>
          <input
            style={oInput}
            value={businessName}
            onChange={e => setBusinessName(e.target.value)}
            placeholder="ej: Barbería El Patrón"
          />
        </label>
        <label style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
          <span style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)' }}>Ciudad / zona</span>
          <input
            style={oInput}
            value={city}
            onChange={e => setCity(e.target.value)}
            placeholder="ej: Medellín · El Poblado"
          />
        </label>
      </div>

      <div>
        <span style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)', display: 'block', marginBottom: 10 }}>
          Tipo de negocio <span style={{ color: 'var(--wine)', marginLeft: 2 }}>*</span>
        </span>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
          {BUSINESS_TYPES.map(bt => {
            const sel = businessType === bt.id;
            return (
              <button
                key={bt.id}
                onClick={() => setBusinessType(bt.id)}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                  padding: '16px 10px', borderRadius: 'var(--r-lg)', cursor: 'pointer',
                  border: `1.5px solid ${sel ? 'var(--wine)' : 'var(--line-strong)'}`,
                  background: sel ? 'var(--wine-50)' : 'var(--surface-2)',
                  color: sel ? 'var(--wine)' : 'var(--ink-2)',
                  transition: 'all var(--dur-2)', outline: 'none',
                  font: '500 12.5px/1.3 var(--font-sans)', textAlign: 'center',
                }}
              >
                <Icon name={bt.icon} size={22} strokeWidth={sel ? 2 : 1.6} />
                {bt.label}
              </button>
            );
          })}
        </div>
        {!businessType && (
          <p style={{ margin: '8px 0 0', font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>
            Selecciona el tipo de negocio para continuar.
          </p>
        )}
      </div>

      <label style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        <span style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)' }}>Tono del agente</span>
        <div style={{ display: 'flex', gap: 8 }}>
          {['Cercano', 'Neutral', 'Formal'].map((t, i) => (
            <span key={t} onClick={() => setTone(i)} style={{
              flex: 1, textAlign: 'center', padding: '9px', borderRadius: 'var(--r-md)', cursor: 'pointer',
              border: `1px solid ${i === tone ? 'var(--wine)' : 'var(--line-strong)'}`,
              background: i === tone ? 'var(--wine-50)' : 'var(--surface-2)',
              color: i === tone ? 'var(--wine)' : 'var(--ink-2)',
              font: '500 13.5px/1 var(--font-sans)',
            }}>{t}</span>
          ))}
        </div>
      </label>
    </div>
  );
}

// ── Step 1: WhatsApp ──────────────────────────────────────────────────────────

function StepWhatsApp({ channels, onConnected }: { channels: ChannelOut[]; onConnected: () => void }) {
  const { workspaceId } = useAuth();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const connected = channels.some(c => c.status === 'active');
  const activeChannel = channels.find(c => c.status === 'active');

  const connectViaKapso = async () => {
    if (!workspaceId) return;
    setLoading(true);
    setErrorMsg('');
    try {
      const { url } = await createKapsoOnboardingLink(workspaceId);
      window.open(url, '_blank');
      onConnected();
    } catch (err: any) {
      setErrorMsg(err?.detail ?? err?.message ?? 'Error generando enlace de conexión.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ConnectCard
      icon="whatsapp" color="var(--wa-ink)" bg="var(--wa-bg)"
      title="WhatsApp Business · Coexistencia"
      sub={connected && activeChannel ? (activeChannel.display_name ?? activeChannel.phone_number) : 'Vincula tu número actual'}
      connected={connected} onConnect={connectViaKapso} loading={loading}
      foot={
        <span>
          <strong style={{ fontWeight: 500, color: 'var(--ink-1)' }}>Coexistencia</strong>{' '}
          deja que sigas usando WhatsApp en tu celular mientras el agente responde en paralelo.
          {errorMsg && <span style={{ display: 'block', marginTop: 8, color: 'var(--error, #c0392b)', fontSize: 12.5 }}>{errorMsg}</span>}
        </span>
      }
    />
  );
}

// ── Step 2: Google Calendar ───────────────────────────────────────────────────

function StepCalendar({ calendars, workspaceId }: { calendars: CalendarOut[]; workspaceId: string | null }) {
  const [loading, setLoading] = useState(false);
  const connected = calendars.some(c => c.sync_status === 'active');
  const activeCalendar = calendars.find(c => c.sync_status === 'active');

  const handleConnect = async () => {
    if (!workspaceId) { toast.error('No se encontró el workspace. Recarga la página.'); return; }
    setLoading(true);
    try {
      const { url } = await getGoogleCalendarUrl(workspaceId, 'onboarding');
      window.location.href = url;
    } catch {
      toast.error('No se pudo iniciar la conexión con Google. Intenta de nuevo.');
      setLoading(false);
    }
  };

  return (
    <ConnectCard
      icon="calendar" color="var(--steel)" bg="color-mix(in srgb, var(--steel) 14%, var(--surface))"
      title="Google Calendar"
      sub={connected && activeCalendar ? activeCalendar.name : 'Fuente principal de disponibilidad'}
      connected={connected} onConnect={handleConnect} loading={loading}
      foot="El agente lee tu calendario para no agendar sobre citas existentes y escribe las nuevas reservas ahí mismo."
    />
  );
}

// ── Step 3: Servicios ─────────────────────────────────────────────────────────

function StepServices({
  businessType, services, workspaceId, onCreated,
}: {
  businessType: BusinessTypeId | null;
  services: ServiceOut[];
  workspaceId: string | null;
  onCreated: () => void;
}) {
  const typeId: BusinessTypeId = businessType ?? 'barberia';
  const preset = BUSINESS_PRESETS[typeId];
  const typeLabel = BUSINESS_TYPES.find(bt => bt.id === typeId)?.label ?? 'tu negocio';
  const [creating, setCreating] = useState(false);

  const handleCreatePreset = async () => {
    if (!workspaceId) return;
    setCreating(true);
    try {
      await Promise.all(
        preset.services.map(s =>
          createService(workspaceId, {
            name: s.name,
            duration_minutes: s.dur,
            price_cop: s.price,
          })
        )
      );
      toast.success('Servicios creados correctamente.');
      onCreated();
    } catch {
      toast.error('Error creando servicios. Intenta de nuevo.');
    } finally {
      setCreating(false);
    }
  };

  if (services.length > 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 4 }}>
          Tienes <strong style={{ color: 'var(--ink-1)' }}>{services.length} servicio{services.length !== 1 ? 's' : ''}</strong> configurados.
          Puedes editarlos en detalle desde la sección Servicios.
        </div>
        {services.slice(0, 6).map(s => (
          <div key={s.id} style={{
            display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px',
            background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)',
          }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--wine)', flexShrink: 0 }} />
            <span style={{ flex: 1, font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{s.name}</span>
            <span style={{ font: '400 12.5px/1 var(--font-sans)', color: 'var(--ink-3)', minWidth: 52 }}>{s.duration_minutes} min</span>
            <span className="tnum" style={{ font: '500 13.5px/1 var(--font-sans)', color: 'var(--wine)', minWidth: 80, textAlign: 'right' }}>
              ${s.price_cop.toLocaleString('es-CO')}
            </span>
          </div>
        ))}
        {services.length > 6 && (
          <div style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)', paddingLeft: 14 }}>
            +{services.length - 6} más
          </div>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <div style={{ font: '400 13.5px/1.5 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 12 }}>
          Servicios típicos de {typeLabel}. Confirma y los crearemos automáticamente.
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {preset.services.map((s, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '11px 14px',
              background: 'var(--surface)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)',
            }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: 'var(--wine)', flexShrink: 0 }} />
              <span style={{ flex: 1, font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>{s.name}</span>
              <span style={{ font: '400 12.5px/1 var(--font-sans)', color: 'var(--ink-3)', minWidth: 52 }}>{s.dur} min</span>
              <span className="tnum" style={{ font: '500 13.5px/1 var(--font-sans)', color: 'var(--wine)', minWidth: 80, textAlign: 'right' }}>
                ${s.price.toLocaleString('es-CO')}
              </span>
            </div>
          ))}
        </div>
        <Button
          variant="primary" icon="check" style={{ alignSelf: 'flex-start', marginTop: 12 }}
          onClick={handleCreatePreset} disabled={creating}
        >
          {creating ? 'Creando…' : 'Crear estos servicios'}
        </Button>
      </div>

      <div>
        <div style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 12 }}>
          Horarios de atención sugeridos
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {preset.hours.map(h => (
            <div key={h.day} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '9px 14px',
              background: h.active ? 'var(--surface)' : 'var(--surface-2)',
              border: '1px solid var(--line)', borderRadius: 'var(--r-md)',
              opacity: h.active ? 1 : 0.5,
            }}>
              <span style={{ width: 80, font: '500 13px/1 var(--font-sans)', color: 'var(--ink-2)' }}>{h.day}</span>
              {h.active
                ? <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-1)' }}>{h.open} — {h.close}</span>
                : <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-4)' }}>Cerrado</span>
              }
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Step 4: Prueba ────────────────────────────────────────────────────────────

function StepTest() {
  return (
    <div style={{ background: 'var(--surface-tint)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)', padding: '18px', display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ alignSelf: 'flex-start', maxWidth: '85%', padding: '9px 13px', borderRadius: '13px 13px 13px 4px', background: 'var(--surface-2)', border: '1px solid var(--line)', font: '400 13.5px/1.4 var(--font-sans)' }}>
        Hola! Quiero un corte para mañana
      </div>
      <div style={{ alignSelf: 'flex-end', maxWidth: '85%', padding: '9px 13px', borderRadius: '13px 13px 4px 13px', background: 'var(--wine)', color: 'var(--wine-fg)', font: '400 13.5px/1.4 var(--font-sans)' }}>
        Para mañana tengo con Andrés a las 10:00, 11:30 o 4:00 pm. ¿Cuál prefieres?
      </div>
      <div style={{ alignSelf: 'flex-end', maxWidth: '85%', padding: '9px 13px', borderRadius: '13px 13px 4px 13px', background: 'var(--wine)', color: 'var(--wine-fg)', font: '400 13.5px/1.4 var(--font-sans)', display: 'flex', gap: 6, alignItems: 'center' }}>
        <Icon name="checkCircle" size={16} /> Cita creada en Google Calendar.
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

function OnboardingPage() {
  const navigate = useNavigate();
  const { workspaceId } = useAuth();
  const qc = useQueryClient();

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: workspace, isLoading: wsLoading } = useQuery<WorkspaceOut | null>({
    queryKey: ['workspace', workspaceId],
    queryFn: async () => {
      if (!workspaceId) return null;
      try { return await apiFetch<WorkspaceOut>(`/workspaces/${workspaceId}`); }
      catch { return null; }
    },
    enabled: !!workspaceId,
    staleTime: 30_000,
  });

  const { data: channels = [], isLoading: chLoading } = useQuery<ChannelOut[]>({
    queryKey: ['channels', workspaceId],
    queryFn: () => listChannels(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });

  const { data: calendars = [], isLoading: calLoading } = useQuery<CalendarOut[]>({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });

  const { data: services = [], isLoading: svcLoading } = useQuery<ServiceOut[]>({
    queryKey: ['services', workspaceId],
    queryFn: () => listServices(workspaceId!),
    enabled: !!workspaceId,
    staleTime: 30_000,
  });

  const allLoaded = !wsLoading && !chLoading && !calLoading && !svcLoading;

  // ── Local form state ───────────────────────────────────────────────────────
  const [businessType, setBusinessType] = useState<BusinessTypeId | null>(null);
  const [businessName, setBusinessName] = useState('');
  const [city, setCity] = useState('');
  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const initializedRef = useRef(false);

  // ── Derived completion per step ────────────────────────────────────────────
  const hasWorkspaceInfo = !!(workspace?.name && workspace?.business_type);
  const hasWhatsApp     = channels.some(c => c.status === 'active');
  const hasCalendar     = calendars.some(c => c.sync_status === 'active');
  const hasServices     = services.length > 0;
  const stepDone        = [hasWorkspaceInfo, hasWhatsApp, hasCalendar, hasServices, false];

  // ── Init: pre-populate from API + navigate to first incomplete step ────────
  useEffect(() => {
    if (!allLoaded || initializedRef.current) return;
    initializedRef.current = true;

    // Pre-populate business form from workspace data
    if (workspace?.name) setBusinessName(workspace.name);
    if (workspace?.business_type) setBusinessType(workspace.business_type as BusinessTypeId);

    // Handle return from Google Calendar OAuth
    const params = new URLSearchParams(window.location.search);
    const urlStep = parseInt(params.get('step') ?? '-1');

    if (urlStep >= 0) {
      setStep(urlStep);
      if (params.get('calendar_connected') === '1') {
        toast.success('Google Calendar conectado correctamente.');
        qc.invalidateQueries({ queryKey: ['calendars', workspaceId] });
      } else if (params.get('calendar_error') === '1') {
        toast.error('No se pudo conectar el calendario. Intenta de nuevo.');
      }
      window.history.replaceState({}, '', '/onboarding');
      return;
    }

    // Navigate to the first incomplete step
    const done = [
      !!(workspace?.name && workspace?.business_type),
      channels.some(c => c.status === 'active'),
      calendars.some(c => c.sync_status === 'active'),
      services.length > 0,
    ];
    const first = done.findIndex(d => !d);
    setStep(first === -1 ? STEPS.length - 1 : first);
  }, [allLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  const isMobile = typeof window !== 'undefined' && window.innerWidth < 880;
  const last = step === STEPS.length - 1;

  // ── Continuar ─────────────────────────────────────────────────────────────
  const handleContinue = async () => {
    if (step === 0 && workspaceId) {
      setSaving(true);
      try {
        await patchWorkspace(workspaceId, {
          ...(businessName ? { name: businessName } : {}),
          ...(businessType ? { business_type: businessType } : {}),
        });
        qc.invalidateQueries({ queryKey: ['workspace', workspaceId] });
      } catch (e) {
        console.warn('[onboarding] error guardando negocio:', e);
      } finally {
        setSaving(false);
      }
    }
    if (last) navigate({ to: '/dashboard' });
    else setStep(s => s + 1);
  };

  // ── Loading inicial ────────────────────────────────────────────────────────
  if (!allLoaded) {
    return (
      <div style={{ minHeight: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--paper)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          <div className="animate-spin" style={{ width: 28, height: 28, borderRadius: '50%', border: '2px solid var(--line-strong)', borderTopColor: 'var(--wine)' }} />
          <span style={{ font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>Cargando tu configuración…</span>
        </div>
      </div>
    );
  }

  const bodyMap = [
    <StepBusiness
      businessType={businessType} setBusinessType={setBusinessType}
      businessName={businessName} setBusinessName={setBusinessName}
      city={city} setCity={setCity}
    />,
    <StepWhatsApp
      channels={channels}
      onConnected={() => qc.invalidateQueries({ queryKey: ['channels', workspaceId] })}
    />,
    <StepCalendar calendars={calendars} workspaceId={workspaceId} />,
    <StepServices
      businessType={businessType}
      services={services}
      workspaceId={workspaceId}
      onCreated={() => qc.invalidateQueries({ queryKey: ['services', workspaceId] })}
    />,
    <StepTest />,
  ];

  const continueDisabled = (step === 0 && !businessType) || saving;

  return (
    <div style={{ minHeight: '100%', display: 'flex', flexDirection: isMobile ? 'column' : 'row', background: 'var(--paper)' }}>

      {/* ── Barra lateral ──────────────────────────────────────────────────── */}
      <div style={{
        width: isMobile ? 'auto' : 320, flexShrink: 0, background: 'var(--paper-2)',
        borderRight: isMobile ? 'none' : '1px solid var(--line)',
        borderBottom: isMobile ? '1px solid var(--line)' : 'none',
        padding: isMobile ? '18px 18px 8px' : '30px 28px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: isMobile ? 16 : 34 }}>
          <HiloMark size={32} />
          <div>
            <div style={{ font: '700 18px/1 var(--font-sans)', letterSpacing: '-0.02em' }}>Hilo</div>
            <div style={{ font: '400 11px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>Configuración inicial</div>
          </div>
        </div>

        {!isMobile && (
          <div>
            {STEPS.map((s, i) => {
              const done = stepDone[i];
              const on = i === step;
              return (
                <button key={s.id} onClick={() => setStep(i)} style={{
                  display: 'grid', gridTemplateColumns: '34px 1fr', gap: 12,
                  width: '100%', textAlign: 'left', border: 0, background: 'transparent', cursor: 'pointer', padding: 0,
                }}>
                  <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}>
                    {i < STEPS.length - 1 && (
                      <span style={{ position: 'absolute', top: 30, bottom: -4, width: 2, background: done ? 'var(--wine)' : 'var(--line-strong)' }} />
                    )}
                    <span style={{
                      width: 30, height: 30, borderRadius: '50%', display: 'grid', placeItems: 'center', zIndex: 1,
                      background: done ? 'var(--wine)' : on ? 'var(--surface)' : 'var(--paper-2)',
                      border: `2px solid ${done || on ? 'var(--wine)' : 'var(--line-strong)'}`,
                      color: done ? 'var(--wine-fg)' : on ? 'var(--wine)' : 'var(--ink-3)',
                    }}>
                      {done ? <Icon name="check" size={15} strokeWidth={2.4} /> : <Icon name={s.icon} size={15} />}
                    </span>
                  </div>
                  <div style={{ paddingBottom: 22 }}>
                    <div style={{ font: `${on ? 500 : 400} 14px/1.2 var(--font-sans)`, color: on || done ? 'var(--ink-1)' : 'var(--ink-3)' }}>
                      {s.title}
                    </div>
                    <div style={{ font: '400 11.5px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 3 }}>{s.sub}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {isMobile && (
          <div style={{ display: 'flex', gap: 5 }}>
            {STEPS.map((_s, i) => (
              <span key={i} style={{
                flex: 1, height: 4, borderRadius: 99,
                background: stepDone[i] || i <= step ? 'var(--wine)' : 'var(--line-strong)',
              }} />
            ))}
          </div>
        )}
      </div>

      {/* ── Contenido ──────────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: isMobile ? '24px 20px' : '56px 64px', display: 'flex', justifyContent: 'center' }}>
          <div style={{ width: '100%', maxWidth: 520, animation: 'hilo-fade-up var(--dur-3) var(--ease-out)' }}>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span className="eyebrow">Paso {step + 1} de {STEPS.length}</span>
              {stepDone[step] && (
                <Tag hue="sage"><Icon name="check" size={11} />Completado</Tag>
              )}
            </div>

            <h1 style={{ margin: '0 0 8px', font: '400 clamp(26px,3.5vw,33px)/1.1 var(--font-serif)', color: 'var(--ink-1)' }}>
              {STEPS[step].title}
            </h1>
            <p style={{ margin: '0 0 28px', font: '400 15px/1.5 var(--font-sans)', color: 'var(--ink-2)' }}>
              {STEPS[step].sub}.
            </p>

            {bodyMap[step]}
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--line)', padding: '16px 24px', display: 'flex', alignItems: 'center', gap: 12, background: 'var(--surface)' }}>
          <Button variant="ghost" onClick={() => navigate({ to: '/dashboard' })}>Saltar por ahora</Button>
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 10 }}>
            {step > 0 && (
              <Button variant="secondary" icon="chevL" onClick={() => setStep(s => s - 1)}>Atrás</Button>
            )}
            <Button
              variant="primary"
              iconRight={last ? 'check' : 'chev'}
              onClick={handleContinue}
              disabled={continueDisabled}
            >
              {saving ? 'Guardando…' : last ? 'Ir al dashboard' : 'Continuar'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
