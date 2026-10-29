import { createFileRoute } from "@tanstack/react-router";
import { Avatar } from "@/components/hilo/primitives";
import { useTeamMembers } from "@/hooks/use-team";

export const Route = createFileRoute("/_authenticated/equipo")({
  head: () => ({ meta: [{ title: "Equipo · Hilo" }] }),
  component: EquipoPage,
});

const HUES = ['clay','wine','mustard','steel','sage','plum','teal'];
const memberHue = (id: string) => HUES[id.charCodeAt(0) % HUES.length];

const ROLE_LABEL: Record<string, string> = {
  owner: 'Propietario',
  manager: 'Manager',
  staff: 'Staff',
  viewer: 'Observador',
};

function EquipoPage() {
  const { data: team = [], isLoading } = useTeamMembers();

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', padding: '24px 20px 40px', animation: 'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ margin: 0, font: '500 22px/1.1 var(--font-sans)', letterSpacing: '-0.02em', color: 'var(--ink-1)' }}>
          Equipo
        </h2>
        <p style={{ margin: '4px 0 0', font: '400 13px/1.4 var(--font-sans)', color: 'var(--ink-3)' }}>
          Miembros con acceso al workspace.
        </p>
      </div>

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
              display: 'flex', alignItems: 'center', gap: 13,
              padding: '13px 20px',
              borderBottom: i < team.length - 1 ? '1px solid var(--line-soft)' : 'none',
            }}>
              <Avatar name={m.name ?? m.email ?? '?'} hue={memberHue(m.id)} size={38} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ font: '500 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>
                  {m.name ?? m.email ?? '—'}
                </div>
                {m.name && (
                  <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)', marginTop: 2 }}>
                    {m.email}
                  </div>
                )}
              </div>
              <span style={{
                font: '500 11px/1 var(--font-sans)', padding: '3px 9px',
                borderRadius: 'var(--r-full)', letterSpacing: '0.02em',
                background: 'var(--surface-2)', color: 'var(--ink-2)',
                border: '1px solid var(--line)',
              }}>
                {ROLE_LABEL[m.member_role] ?? m.member_role}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
