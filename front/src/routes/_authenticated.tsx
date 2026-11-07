import { createFileRoute, Outlet, redirect, useNavigate, useRouterState } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/auth-context';
import { apiFetch } from '@/lib/api/client';
import { listChannels, listCalendars, listSandboxSessions } from '@/lib/api/channels';
import { listServices } from '@/lib/api/services';
import { getAgentConfig, getAgentHours } from '@/lib/api/agent';
import { countAgentAlerts } from '@/lib/api/alerts';
import type { AgentHoursOut } from '@/lib/types/api';
import { PATH_TO_ID, TITLES } from '@/lib/nav';
import { useIsMobile } from '@/hooks/use-is-mobile';
import { Sidebar } from '@/components/layout/Sidebar';
import { TopBar } from '@/components/layout/TopBar';
import { BottomTabs } from '@/components/layout/BottomTabs';
import type { WorkspaceOut } from '@/lib/types/api';
import styles from '@/components/layout/PanelLayout.module.css';

const JWT_KEY = 'hilo_jwt';

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async () => {
    if (typeof window === 'undefined') return;
    const stored = localStorage.getItem(JWT_KEY);
    if (!stored) throw redirect({ to: '/login' });
    try {
      const [, b64] = stored.split('.');
      const payload = JSON.parse(atob(b64.replace(/-/g, '+').replace(/_/g, '/')));
      if ((payload.exp || 0) * 1000 < Date.now()) {
        localStorage.removeItem(JWT_KEY);
        throw redirect({ to: '/login' });
      }
    } catch {
      throw redirect({ to: '/login' });
    }
  },
  component: PanelLayout,
});

function PanelLayout() {
  const navigate = useNavigate();
  const { location } = useRouterState();
  const isMobile = useIsMobile(880);
  const { me, logout } = useAuth();

  const activeId = PATH_TO_ID[location.pathname] || 'inicio';
  const isOnboarding = location.pathname === '/onboarding';
  const title = TITLES[activeId] || 'Hilo';

  const { data: workspace } = useQuery<WorkspaceOut | null>({
    queryKey: ['workspace', me?.workspace_id],
    queryFn: async () => {
      try { return await apiFetch<WorkspaceOut>(`/workspaces/${me!.workspace_id}`); }
      catch { return null; }
    },
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  const { data: channels = [] } = useQuery({
    queryKey: ['channels', me?.workspace_id],
    queryFn: () => listChannels(me!.workspace_id!),
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  const { data: calendars = [] } = useQuery({
    queryKey: ['calendars', me?.workspace_id],
    queryFn: () => listCalendars(me!.workspace_id!),
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  const { data: services = [] } = useQuery({
    queryKey: ['services', me?.workspace_id],
    queryFn: () => listServices(me!.workspace_id!),
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  const { data: agentCfg } = useQuery({
    queryKey: ['agent-config', me?.workspace_id],
    queryFn: () => getAgentConfig(me!.workspace_id!),
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  const { data: agentHours = [] } = useQuery<AgentHoursOut[]>({
    queryKey: ['agent-hours', me?.workspace_id],
    queryFn: () => getAgentHours(me!.workspace_id!),
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });

  const { data: alertCountData } = useQuery({
    queryKey: ['agent-alerts-count', me?.workspace_id],
    queryFn: () => countAgentAlerts(me!.workspace_id!),
    enabled: !!me?.workspace_id,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  const alertCount = alertCountData?.count ?? 0;

  const { data: rawSandbox } = useQuery({
    queryKey: ['sandbox-sessions', me?.workspace_id],
    queryFn: () => listSandboxSessions(me!.workspace_id!).catch(() => []),
    enabled: !!me?.workspace_id,
    staleTime: 60_000,
  });
  const sandboxSessions = Array.isArray(rawSandbox) ? rawSandbox : [];

  // ── Status chips para TopBar ──────────────────────────────────────────────
  const sandboxActive = sandboxSessions.some(
    (s: any) => s.status === 'active' && new Date(s.expires_at) > new Date(),
  );
  const activeChannel = channels.find((c: any) => c.status === 'active');
  const pausedChannel = channels.some((c: any) => c.status === 'paused') && !activeChannel;

  let waChip: { key: string; label: string; short: string; dotColor: string; chipBg: string; chipBorder: string; pulse: boolean } | null = null;
  if (activeChannel) {
    waChip = { key: 'wa', label: 'WA activo', short: 'WA', dotColor: 'var(--wa)', chipBg: 'var(--wa-bg)', chipBorder: 'color-mix(in srgb, var(--wa-ink) 22%, transparent)', pulse: true };
  } else if (sandboxActive) {
    waChip = { key: 'sandbox', label: 'Sandbox activo', short: 'Sandbox', dotColor: 'var(--mustard)', chipBg: 'color-mix(in srgb, var(--mustard) 10%, var(--surface))', chipBorder: 'color-mix(in srgb, var(--mustard) 30%, transparent)', pulse: true };
  } else if (pausedChannel) {
    waChip = { key: 'wa-paused', label: 'WA pausado', short: 'WA', dotColor: 'var(--ink-3)', chipBg: 'var(--surface-tint)', chipBorder: 'var(--line)', pulse: false };
  }

  const calActive = calendars.some((c: any) => c.sync_status === 'active');
  const calError  = !calActive && calendars.some((c: any) => c.sync_status === 'error');
  const calChip = calActive
    ? { key: 'cal', label: 'Calendar conectado', short: 'Cal', dotColor: 'var(--success)', chipBg: 'color-mix(in srgb, var(--success) 10%, var(--surface))', chipBorder: 'color-mix(in srgb, var(--success) 25%, transparent)', pulse: false }
    : calError
      ? { key: 'cal-err', label: 'Token vencido', short: 'Cal!', dotColor: 'var(--error, #c0392b)', chipBg: 'color-mix(in srgb, var(--error, #c0392b) 8%, var(--surface))', chipBorder: 'color-mix(in srgb, var(--error, #c0392b) 25%, transparent)', pulse: false }
      : null;

  let agentChip: typeof waChip | null = null;
  if (waChip && agentCfg !== undefined) {
    const agentOn = agentCfg?.agent_enabled ?? false;
    const appDay  = (new Date().getDay() + 6) % 7; // lunes=0
    const nowMins = new Date().getHours() * 60 + new Date().getMinutes();
    const todayH  = agentHours.find((h: AgentHoursOut) => h.day_of_week === appDay);
    const inSched = todayH?.is_active && (() => {
      const [oh, om] = todayH.open_time.split(':').map(Number);
      const [ch, cm] = todayH.close_time.split(':').map(Number);
      return nowMins >= oh * 60 + om && nowMins < ch * 60 + cm;
    })();

    if (agentOn && inSched) {
      agentChip = { key: 'agent', label: 'Agente activo', short: 'Bot', dotColor: 'var(--wine)', chipBg: 'var(--wine-50)', chipBorder: 'color-mix(in srgb, var(--wine) 25%, transparent)', pulse: true };
    } else if (agentOn) {
      agentChip = { key: 'agent-ooh', label: 'Agente · fuera de horario', short: 'Bot', dotColor: 'var(--ink-3)', chipBg: 'var(--surface-tint)', chipBorder: 'var(--line)', pulse: false };
    } else {
      agentChip = { key: 'agent-off', label: 'Agente desactivado', short: 'Bot↓', dotColor: 'var(--ink-3)', chipBg: 'var(--surface-tint)', chipBorder: 'var(--line)', pulse: false };
    }
  }

  const statusChips = [waChip, calChip, agentChip].filter(Boolean) as NonNullable<typeof waChip>[];

  const stepsDone = [
    !!(workspace?.name && (workspace as any)?.business_type),
    channels.some((c: any) => c.status === 'active'),
    calendars.some((c: any) => c.sync_status === 'active'),
    services.length > 0,
  ].filter(Boolean).length;
  const onboardPct      = Math.round(stepsDone / 4 * 100);
  const onboardStepsLeft = 4 - stepsDone;

  const nav = (path: string) => {
    if (path === '#') return;
    navigate({ to: path as never });
  };

  const businessName  = workspace?.name ?? '';
  const ownerName     = me?.email?.split('@')[0] ?? '';
  const ownerInitials = ownerName.slice(0, 2).toUpperCase();
  const ownerRole     = me?.role ?? '';

  if (isOnboarding) {
    return (
      <div className={styles['panel--onboarding']}>
        <main>
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {!isMobile && (
        <Sidebar
          active={activeId}
          onNav={nav}
          onboardPct={onboardPct}
          onboardStepsLeft={onboardStepsLeft}
          businessName={businessName}
          ownerName={ownerName}
          ownerInitials={ownerInitials}
          ownerRole={ownerRole}
          onLogout={logout}
          alertCount={alertCount}
        />
      )}
      <div className={styles.panel__content}>
        <TopBar title={title} isMobile={isMobile} onCompose={() => nav('/agenda')} statusChips={statusChips} />
        <main className={styles.panel__main}>
          <Outlet />
        </main>
        {isMobile && <BottomTabs active={activeId} onNav={nav} />}
      </div>
    </div>
  );
}
