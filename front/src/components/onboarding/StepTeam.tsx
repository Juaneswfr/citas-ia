import { useState } from 'react';
import { toast } from 'sonner';
import { Button, Avatar, Tag } from '@/components/hilo/primitives';
import { inviteMember, removeMember } from '@/lib/api/workspaces';
import type { MemberOut } from '@/lib/types/api';
import s from './onboarding.module.css';

const ROLE_LABELS: Record<string, string> = {
  workspace_owner: 'Dueño',
  manager: 'Manager',
  staff: 'Staff',
  viewer: 'Lector',
};

interface StepTeamProps {
  members: MemberOut[];
  workspaceId: string | null;
  currentUserId: string | undefined;
  onChanged: () => void;
}

export function StepTeam({ members, workspaceId, currentUserId, onChanged }: StepTeamProps) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('staff');
  const [inviting, setInviting] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState('');

  const handleInvite = async () => {
    if (!workspaceId || !email.trim()) return;
    setInviting(true);
    setError('');
    try {
      await inviteMember(workspaceId, email.trim(), role);
      toast.success(`Invitación enviada a ${email.trim()}.`);
      setEmail('');
      onChanged();
    } catch (err: any) {
      setError(err?.detail ?? err?.message ?? 'Error al invitar. Verifica el email.');
    } finally {
      setInviting(false);
    }
  };

  const handleRemove = async (member: MemberOut) => {
    if (!workspaceId) return;
    setRemoving(member.user_id);
    try {
      await removeMember(workspaceId, member.user_id);
      toast.success('Miembro eliminado.');
      onChanged();
    } catch {
      toast.error('No se pudo eliminar el miembro.');
    } finally {
      setRemoving(null);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {members.length > 0 && (
        <div className={s['team__members']}>
          {members.map(m => {
            const isMe = m.user_id === currentUserId;
            const displayName = m.name ?? m.email ?? m.user_id;
            return (
              <div key={m.user_id} className={s['team__member']}>
                <Avatar name={displayName} size={34} />
                <div className={s['team__member-info']}>
                  <div className={s['team__member-name']}>{displayName}</div>
                  {m.email && m.name && (
                    <div className={s['team__member-email']}>{m.email}</div>
                  )}
                </div>
                <Tag>{ROLE_LABELS[m.member_role] ?? m.member_role}</Tag>
                {!isMe && (
                  <Button
                    variant="ghost" size="sm"
                    disabled={removing === m.user_id}
                    onClick={() => handleRemove(m)}
                  >
                    {removing === m.user_id ? '…' : 'Eliminar'}
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div>
        <div style={{ font: '500 12.5px/1 var(--font-sans)', color: 'var(--ink-2)', marginBottom: 12 }}>
          Invitar persona
        </div>
        <div className={s['team__invite-form']}>
          <div className={s['team__invite-row']}>
            <label className={s['team__invite-label']}>
              <span className={s['team__invite-label-text']}>Email</span>
              <input
                className={s['team__invite-input']}
                type="email"
                placeholder="correo@ejemplo.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleInvite()}
              />
            </label>
            <label className={s['team__invite-label']}>
              <span className={s['team__invite-label-text']}>Rol</span>
              <select
                className={s['team__invite-select']}
                value={role}
                onChange={e => setRole(e.target.value)}
              >
                <option value="manager">Manager</option>
                <option value="staff">Staff</option>
                <option value="viewer">Lector</option>
              </select>
            </label>
            <Button
              variant="primary"
              disabled={inviting || !email.trim()}
              onClick={handleInvite}
              style={{ alignSelf: 'flex-end' }}
            >
              {inviting ? 'Enviando…' : 'Invitar'}
            </Button>
          </div>
          {error && <p className={s['team__error']}>{error}</p>}
        </div>
      </div>
    </div>
  );
}
