import { useIsMobile } from '@/hooks/use-is-mobile';
import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState, useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { Icon, HiloMark } from '@/components/hilo/icons';
import { Button, Tag } from '@/components/hilo/primitives';
import { useAuth } from '@/lib/auth-context';
import { getGoogleCalendarUrl } from '@/lib/api/auth';
import { patchWorkspace, getBusinessHours, updateBusinessHours, listMembers } from '@/lib/api/workspaces';
import { listChannels, listCalendars } from '@/lib/api/channels';
import { listServices } from '@/lib/api/services';
import { apiFetch } from '@/lib/api/client';
import { StepBusiness } from '@/components/onboarding/StepBusiness';
import { StepWhatsApp } from '@/components/onboarding/StepWhatsApp';
import { StepCalendar } from '@/components/onboarding/StepCalendar';
import { StepServices } from '@/components/onboarding/StepServices';
import { StepTeam } from '@/components/onboarding/StepTeam';
import { StepTest } from '@/components/onboarding/StepTest';
import type { WorkspaceOut, ChannelOut, CalendarOut, ServiceOut, MemberOut, BusinessHoursOut } from '@/lib/types/api';
import type { BusinessTypeId } from '@/lib/business-types';
import s from '@/components/onboarding/onboarding.module.css';

export const Route = createFileRoute('/_authenticated/onboarding')({
  head: () => ({ meta: [{ title: 'Configuración inicial · Hilo' }] }),
  component: OnboardingPage,
});

const STEPS = [
  { id: 0, icon: 'gear',     title: 'Tu negocio',       sub: 'Nombre, horario y tipo de negocio' },
  { id: 1, icon: 'whatsapp', title: 'WhatsApp Business', sub: 'Coexistencia · conserva tu número' },
  { id: 2, icon: 'calendar', title: 'Google Calendar',   sub: 'Tu disponibilidad real' },
  { id: 3, icon: 'layers',   title: 'Servicios',         sub: 'Qué ofreces y a qué precio' },
  { id: 4, icon: 'user',     title: 'Equipo',            sub: 'Quién gestiona el negocio' },
  { id: 5, icon: 'sparkle',  title: 'Prueba el agente',  sub: 'Agenda tu primera cita de prueba' },
];

function OnboardingPage() {
  const navigate          = useNavigate();
  const { workspaceId, me } = useAuth();
  const qc                = useQueryClient();

  // ── Queries ──────────────────────────────────────────────────────────────────

  const { data: workspace,     isLoading: wsLoading    } = useQuery<WorkspaceOut | null>({
    queryKey: ['workspace', workspaceId],
    queryFn: async () => {
      if (!workspaceId) return null;
      try { return await apiFetch<WorkspaceOut>(`/workspaces/${workspaceId}`); }
      catch { return null; }
    },
    enabled: !!workspaceId, staleTime: 30_000,
  });

  const { data: channels  = [], isLoading: chLoading    } = useQuery<ChannelOut[]>({
    queryKey: ['channels',  workspaceId],
    queryFn: () => listChannels(workspaceId!),
    enabled: !!workspaceId, staleTime: 30_000,
  });

  const { data: calendars = [], isLoading: calLoading   } = useQuery<CalendarOut[]>({
    queryKey: ['calendars', workspaceId],
    queryFn: () => listCalendars(workspaceId!),
    enabled: !!workspaceId, staleTime: 30_000,
  });

  const { data: services  = [], isLoading: svcLoading   } = useQuery<ServiceOut[]>({
    queryKey: ['services',  workspaceId],
    queryFn: () => listServices(workspaceId!),
    enabled: !!workspaceId, staleTime: 30_000,
  });

  const { data: members   = [], isLoading: memLoading   } = useQuery<MemberOut[]>({
    queryKey: ['team',      workspaceId],
    queryFn: () => listMembers(workspaceId!),
    enabled: !!workspaceId, staleTime: 30_000,
  });

  const { data: hoursApi  = [], isLoading: hoursLoading } = useQuery<BusinessHoursOut[]>({
    queryKey: ['business-hours', workspaceId],
    queryFn: () => getBusinessHours(workspaceId!),
    enabled: !!workspaceId, staleTime: 60_000,
  });

  const allLoaded = !wsLoading && !chLoading && !calLoading && !svcLoading && !memLoading && !hoursLoading;

  // ── Local form state ──────────────────────────────────────────────────────────

  const [businessType,  setBusinessType ] = useState<BusinessTypeId | null>(null);
  const [businessName,  setBusinessName ] = useState('');
  const [city,          setCity         ] = useState('');
  const [businessHours, setBusinessHours] = useState<BusinessHoursOut[]>([]);
  const [step,          setStep         ] = useState(0);
  const [saving,        setSaving       ] = useState(false);
  const initializedRef = useRef(false);

  // Sync hours from API into local state once loaded
  useEffect(() => {
    if (hoursApi.length > 0 && businessHours.length === 0) {
      setBusinessHours(hoursApi);
    }
  }, [hoursApi]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step completion ───────────────────────────────────────────────────────────

  const stepDone = [
    !!(workspace?.name && (workspace as any)?.business_type),
    channels.some(c => c.status === 'active'),
    calendars.some(c => c.sync_status === 'active'),
    services.length > 0,
    true, // equipo — siempre completable
    false,
  ];

  // ── Init once: pre-populate + navigate to first incomplete step ───────────────

  useEffect(() => {
    if (!allLoaded || initializedRef.current) return;
    initializedRef.current = true;

    if (workspace?.name)                        setBusinessName(workspace.name);
    if ((workspace as any)?.business_type)      setBusinessType((workspace as any).business_type as BusinessTypeId);

    const params  = new URLSearchParams(window.location.search);
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

    const done = [
      !!(workspace?.name && (workspace as any)?.business_type),
      channels.some(c => c.status === 'active'),
      calendars.some(c => c.sync_status === 'active'),
      services.length > 0,
    ];
    const first = done.findIndex(d => !d);
    setStep(first === -1 ? STEPS.length - 1 : first);
  }, [allLoaded]); // eslint-disable-line react-hooks/exhaustive-deps

  const isMobile = useIsMobile();
  const last     = step === STEPS.length - 1;

  // ── Continuar ─────────────────────────────────────────────────────────────────

  const handleContinue = async () => {
    if (step === 0 && workspaceId) {
      setSaving(true);
      try {
        await patchWorkspace(workspaceId, {
          ...(businessName ? { name: businessName } : {}),
          ...(businessType ? { business_type: businessType } : {}),
        });
        if (businessHours.length > 0) {
          await updateBusinessHours(workspaceId, businessHours);
          qc.invalidateQueries({ queryKey: ['business-hours', workspaceId] });
        }
        qc.invalidateQueries({ queryKey: ['workspace', workspaceId] });
      } catch (e) {
        console.warn('[onboarding] error guardando negocio:', e);
      } finally {
        setSaving(false);
      }
    }
    if (last) navigate({ to: '/dashboard' });
    else setStep(n => n + 1);
  };

  // ── Loading ───────────────────────────────────────────────────────────────────

  if (!allLoaded) {
    return (
      <div className={s['wizard__loading']}>
        <div className={s['wizard__loading-inner']}>
          <div className={`animate-spin ${s['wizard__spinner']}`} />
          <span className={s['wizard__loading-text']}>Cargando tu configuración…</span>
        </div>
      </div>
    );
  }

  // ── Step bodies ───────────────────────────────────────────────────────────────

  const bodyMap = [
    <StepBusiness
      businessType={businessType}   setBusinessType={setBusinessType}
      businessName={businessName}   setBusinessName={setBusinessName}
      city={city}                   setCity={setCity}
      businessHours={businessHours} onHoursChange={setBusinessHours}
    />,
    <StepWhatsApp
      channels={channels}
      onConnected={() => qc.invalidateQueries({ queryKey: ['channels', workspaceId] })}
    />,
    <StepCalendar calendars={calendars} workspaceId={workspaceId} />,
    <StepServices
      businessType={businessType} services={services} workspaceId={workspaceId}
      onCreated={() => qc.invalidateQueries({ queryKey: ['services', workspaceId] })}
    />,
    <StepTeam
      members={members} workspaceId={workspaceId} currentUserId={me?.user_id}
      onChanged={() => qc.invalidateQueries({ queryKey: ['team', workspaceId] })}
    />,
    <StepTest />,
  ];

  const continueDisabled = (step === 0 && !businessType) || saving;

  return (
    <div className={`${s.wizard} ${isMobile ? s['wizard--mobile'] : ''}`}>

      {/* ── Sidebar ──────────────────────────────────────────────────────────── */}
      <div className={`${s.wizard__sidebar} ${isMobile ? s['wizard__sidebar--mobile'] : ''}`}>
        <div className={`${s.wizard__brand} ${isMobile ? s['wizard__brand--mobile'] : ''}`}>
          <HiloMark size={32} />
          <div>
            <div className={s['wizard__brand-name']}>Hilo</div>
            <div className={s['wizard__brand-sub']}>Configuración inicial</div>
          </div>
        </div>

        {!isMobile && (
          <div className={s.wizard__steps}>
            {STEPS.map((st, i) => {
              const done   = stepDone[i];
              const active = i === step;
              return (
                <button key={st.id} className={s['wizard__step-btn']} onClick={() => setStep(i)}>
                  <div className={s['wizard__step-track']}>
                    {i < STEPS.length - 1 && (
                      <span className={`${s['wizard__step-line']} ${done ? s['wizard__step-line--done'] : ''}`} />
                    )}
                    <span className={`${s['wizard__step-dot']} ${done ? s['wizard__step-dot--done'] : active ? s['wizard__step-dot--active'] : ''}`}>
                      {done ? <Icon name="check" size={15} strokeWidth={2.4} /> : <Icon name={st.icon} size={15} />}
                    </span>
                  </div>
                  <div className={s['wizard__step-info']}>
                    <div className={`${s['wizard__step-title']} ${active ? s['wizard__step-title--active'] : done ? s['wizard__step-title--done'] : ''}`}>
                      {st.title}
                    </div>
                    <div className={s['wizard__step-sub']}>{st.sub}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}

        {isMobile && (
          <div className={s['wizard__progress']}>
            {STEPS.map((_st, i) => (
              <span
                key={i}
                className={`${s['wizard__progress-bar']} ${stepDone[i] || i <= step ? s['wizard__progress-bar--fill'] : ''}`}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Content ──────────────────────────────────────────────────────────── */}
      <div className={s.wizard__content}>
        <div className={`${s.wizard__scroll} ${isMobile ? s['wizard__scroll--mobile'] : ''}`}>
          <div key={step} className={s.wizard__body}>
            <div className={s.wizard__eyebrow}>
              <span className="eyebrow">Paso {step + 1} de {STEPS.length}</span>
              {stepDone[step] && (
                <Tag hue="sage"><Icon name="check" size={11} />Completado</Tag>
              )}
            </div>
            <h1 className={s.wizard__title}>{STEPS[step].title}</h1>
            <p className={s.wizard__subtitle}>{STEPS[step].sub}.</p>
            {bodyMap[step]}
          </div>
        </div>

        <div className={s.wizard__footer}>
          <Button variant="ghost" onClick={() => navigate({ to: '/dashboard' })}>Saltar por ahora</Button>
          <div className={s['wizard__footer-actions']}>
            {step > 0 && (
              <Button variant="secondary" icon="chevL" onClick={() => setStep(n => n - 1)}>Atrás</Button>
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
