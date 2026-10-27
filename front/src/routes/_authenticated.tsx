import { createFileRoute, Outlet, redirect, useNavigate, useRouterState } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Icon, HiloMark } from "@/components/hilo/icons";
import { Button, Avatar, Tag, Dot } from "@/components/hilo/primitives";
import HILO from "@/lib/hilo-data";
import { useAuth } from "@/lib/auth-context";
import { apiFetch } from "@/lib/api/client";
import type { WorkspaceOut } from "@/lib/types/api";

const JWT_KEY = "hilo_jwt";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: async () => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(JWT_KEY);
    if (!stored) throw redirect({ to: "/login" });
    try {
      const [, b64] = stored.split(".");
      const payload = JSON.parse(atob(b64.replace(/-/g, "+").replace(/_/g, "/")));
      if ((payload.exp || 0) * 1000 < Date.now()) {
        localStorage.removeItem(JWT_KEY);
        throw redirect({ to: "/login" });
      }
    } catch {
      throw redirect({ to: "/login" });
    }
  },
  component: PanelLayout,
});

const NAV = [
  { group: 'Operación', items: [
    { id: 'inicio',    path: '/dashboard', icon: 'home',     label: 'Inicio' },
    { id: 'agenda',    path: '/agenda',    icon: 'calendar', label: 'Agenda' },
    { id: 'servicios', path: '/services',  icon: 'scissors', label: 'Servicios' },
    { id: 'clientes',  path: '/clients',   icon: 'users',    label: 'Clientes' },
  ]},
  { group: 'Canal', items: [
    { id: 'conversaciones', path: '/messages', icon: 'chat',     label: 'Conversaciones' },
    { id: 'canales',        path: '#',         icon: 'whatsapp', label: 'Canales',        soon: true },
    { id: 'calendarios',    path: '#',         icon: 'layers',   label: 'Calendarios',   soon: true },
  ]},
  { group: 'Cuenta', items: [
    { id: 'equipo',      path: '#',         icon: 'user', label: 'Equipo',      soon: true },
    { id: 'suscripcion', path: '#',         icon: 'card', label: 'Suscripción', soon: true },
    { id: 'config',      path: '/settings', icon: 'gear', label: 'Configuración' },
  ]},
];

const PATH_TO_ID: Record<string, string> = {
  '/dashboard': 'inicio', '/agenda': 'agenda',
  '/services': 'servicios', '/clients': 'clientes', '/onboarding': 'onboarding',
  '/messages': 'conversaciones', '/settings': 'config',
};

function useIsMobile(bp = 880) {
  const [m, setM] = useState(typeof window !== 'undefined' && window.innerWidth < bp);
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', () => setM(window.innerWidth < bp));
  }
  return m;
}

function Sidebar({
  active,
  onNav,
  onboardPct = 75,
  businessName = HILO.business.name,
  ownerName = HILO.owner.name,
  ownerInitials = HILO.owner.initials,
  ownerRole = HILO.owner.role,
  onLogout,
}: {
  active: string;
  onNav: (path: string) => void;
  onboardPct?: number;
  businessName?: string;
  ownerName?: string;
  ownerInitials?: string;
  ownerRole?: string;
  onLogout?: () => void;
}) {
  return (
    <aside style={{
      width: 244, flexShrink: 0, background: 'var(--paper-2)',
      borderRight: '1px solid var(--line)', display: 'flex', flexDirection: 'column',
      padding: '16px 12px 12px', gap: 18, height: '100%', overflowY: 'auto',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '2px 6px 4px' }}>
        <HiloMark size={30} />
        <div style={{ lineHeight: 1.05, minWidth: 0 }}>
          <div style={{ font: '700 17px/1 var(--font-sans)', letterSpacing: '-0.02em', color: 'var(--ink-1)' }}>Hilo</div>
          <div style={{ font: '400 11px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>{businessName}</div>
        </div>
      </div>

      {NAV.map(g => (
        <div key={g.group}>
          <div className="eyebrow" style={{ padding: '0 8px 8px' }}>{g.group}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {g.items.map(it => {
              const on = it.id === active;
              return (
                <button key={it.id} onClick={() => onNav(it.path)} style={{
                  position: 'relative', display: 'flex', alignItems: 'center', gap: 11,
                  padding: '8px 10px', border: 0, borderRadius: 'var(--r-sm)', cursor: 'pointer',
                  textAlign: 'left', width: '100%',
                  background: on ? 'var(--wine-50)' : 'transparent',
                  color: on ? 'var(--wine)' : 'var(--ink-2)',
                  font: '500 14px/1 var(--font-sans)', letterSpacing: '-0.01em',
                  transition: 'all var(--dur-2) var(--ease-std)',
                }}
                  onMouseEnter={e => { if (!on) { (e.currentTarget as HTMLElement).style.background = 'var(--surface-tint)'; (e.currentTarget as HTMLElement).style.color = 'var(--ink-1)'; } }}
                  onMouseLeave={e => { if (!on) { (e.currentTarget as HTMLElement).style.background = 'transparent'; (e.currentTarget as HTMLElement).style.color = 'var(--ink-2)'; } }}
                >
                  {on && <span style={{ position: 'absolute', left: -12, top: '50%', transform: 'translateY(-50%)', width: 3, height: 20, borderRadius: '0 3px 3px 0', background: 'var(--wine)' }} />}
                  <Icon name={it.icon} size={18} strokeWidth={on ? 1.9 : 1.7} />
                  <span style={{ flex: 1 }}>{it.label}</span>
                  {it.soon && <span style={{ font: '500 9px/1 var(--font-sans)', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--ink-4)', border: '1px solid var(--line)', padding: '2px 5px', borderRadius: 'var(--r-full)' }}>pronto</span>}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <button onClick={() => onNav('/onboarding')} style={{
        marginTop: 'auto', textAlign: 'left', cursor: 'pointer', width: '100%',
        background: 'var(--surface-tint)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)',
        padding: 12, display: 'flex', flexDirection: 'column', gap: 8,
        transition: 'all var(--dur-2)',
      }}
        onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'var(--wine-50)'}
        onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'var(--surface-tint)'}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <Icon name="sparkle" size={15} style={{ color: 'var(--wine)' }} />
          <span style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-1)' }}>Termina de configurar</span>
        </div>
        <div style={{ height: 5, borderRadius: 99, background: 'var(--wine-100)', overflow: 'hidden' }}>
          <div style={{ width: `${onboardPct}%`, height: '100%', background: 'var(--wine)', borderRadius: 99 }} />
        </div>
        <span style={{ font: '400 11px/1 var(--font-sans)', color: 'var(--ink-3)' }}>{onboardPct}% · faltan 2 pasos</span>
      </button>

      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 6px 2px', borderTop: '1px solid var(--line)' }}>
        <Avatar name={ownerName} initials={ownerInitials} hue="wine" size={32} />
        <div style={{ flex: 1, minWidth: 0, lineHeight: 1.15 }}>
          <div style={{ font: '500 13px/1.2 var(--font-sans)', color: 'var(--ink-1)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{ownerName}</div>
          <div style={{ font: '400 11px/1.2 var(--font-sans)', color: 'var(--ink-3)' }}>{ownerRole}</div>
        </div>
        <Icon name="dotsV" size={16} style={{ color: 'var(--ink-3)', cursor: 'pointer' }} onClick={onLogout} title="Cerrar sesión" />
      </div>
    </aside>
  );
}

function TopBar({ title, isMobile, onCompose }: { title: string; isMobile: boolean; onCompose: () => void }) {
  return (
    <header style={{
      height: 56, padding: '0 16px', display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0,
      background: 'var(--mat-toolbar)', backdropFilter: 'var(--blur-thin)',
      WebkitBackdropFilter: 'var(--blur-thin)',
      borderBottom: '1px solid var(--line)', position: 'sticky', top: 0, zIndex: 20,
    }}>
      {isMobile && <HiloMark size={28} />}
      <h1 style={{ margin: 0, font: '500 19px/1 var(--font-sans)', letterSpacing: '-0.02em', color: 'var(--ink-1)' }}>{title}</h1>

      {!isMobile && (
        <button style={{
          display: 'flex', alignItems: 'center', gap: 9, padding: '8px 12px', marginLeft: 10,
          background: 'var(--surface-tint)', border: '1px solid var(--line)', borderRadius: 'var(--r-md)',
          flex: '1 1 0', maxWidth: 360, cursor: 'pointer', textAlign: 'left',
        }}>
          <Icon name="search" size={15} style={{ color: 'var(--ink-3)' }} />
          <span style={{ flex: 1, font: '400 13px/1 var(--font-sans)', color: 'var(--ink-3)' }}>Buscar cliente, cita, servicio…</span>
          <kbd style={{ font: '500 11px/1 var(--font-mono)', color: 'var(--ink-3)', padding: '3px 6px', background: 'var(--surface)', borderRadius: 5, border: '1px solid var(--line)' }}>⌘K</kbd>
        </button>
      )}

      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 'var(--r-full)', background: 'var(--wa-bg)', border: '1px solid color-mix(in srgb, var(--wa-ink) 22%, transparent)' }}>
          <Dot color="var(--wa)" pulse />
          <span style={{ font: '500 12px/1 var(--font-sans)', color: 'var(--wa-ink)' }}>{isMobile ? 'WA' : 'WhatsApp activo'}</span>
        </span>
        {!isMobile && <Button variant="secondary" size="sm" icon="bell" aria-label="Alertas" style={{ padding: 8 }} />}
        <Button variant="primary" size="sm" icon="plus" onClick={onCompose}>{isMobile ? '' : 'Nueva cita'}</Button>
      </div>
    </header>
  );
}

function BottomTabs({ active, onNav }: { active: string; onNav: (path: string) => void }) {
  const items = NAV[0].items;
  return (
    <nav style={{
      position: 'sticky', bottom: 0, zIndex: 20, flexShrink: 0,
      display: 'flex', justifyContent: 'space-around', alignItems: 'stretch',
      background: 'var(--mat-toolbar)', backdropFilter: 'var(--blur-thin)',
      WebkitBackdropFilter: 'var(--blur-thin)', borderTop: '1px solid var(--line)',
      padding: '6px 8px',
    }}>
      {items.map(it => {
        const on = it.id === active;
        return (
          <button key={it.id} onClick={() => onNav(it.path)} style={{
            flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
            background: 'transparent', border: 0, cursor: 'pointer', padding: '4px 0',
            color: on ? 'var(--wine)' : 'var(--ink-3)',
          }}>
            <Icon name={it.icon} size={22} strokeWidth={on ? 1.9 : 1.7} />
            <span style={{ font: `${on ? 500 : 400} 10px/1 var(--font-sans)` }}>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

const TITLES: Record<string, string> = {
  inicio: 'Inicio', agenda: 'Agenda', servicios: 'Servicios', clientes: 'Clientes',
  onboarding: 'Configuración inicial', conversaciones: 'Conversaciones', config: 'Ajustes',
};

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

  const businessName = workspace?.name ?? HILO.business.name;
  const rawOwnerName = me?.email?.split('@')[0] ?? HILO.owner.name;
  const ownerInitials = rawOwnerName.slice(0, 2).toUpperCase();
  const ownerRole = me?.role ?? HILO.owner.role;

  const nav = (path: string) => {
    if (path === '#') return;
    navigate({ to: path as never });
  };

  if (isOnboarding) {
    return (
      <div style={{ height: '100vh', overflow: 'hidden', background: 'var(--paper)' }}>
        <main style={{ height: '100%', overflowY: 'auto' }}>
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--paper)' }}>
      {!isMobile && (
        <Sidebar
          active={activeId}
          onNav={nav}
          onboardPct={75}
          businessName={businessName}
          ownerName={rawOwnerName}
          ownerInitials={ownerInitials}
          ownerRole={ownerRole}
          onLogout={logout}
        />
      )}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, height: '100%' }}>
        <TopBar title={title} isMobile={isMobile} onCompose={() => nav('/agenda')} />
        <main style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          <Outlet />
        </main>
        {isMobile && <BottomTabs active={activeId} onNav={nav} />}
      </div>
    </div>
  );
}
