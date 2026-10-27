import React, { useState } from 'react';
import { Icon } from './icons';
import HILO from '@/lib/hilo-data';

// ── Button ───────────────────────────────────────────────────────
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'tonal' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  icon?: string;
  iconRight?: string;
  children?: React.ReactNode;
}

export function Button({ variant = 'primary', size = 'md', icon, iconRight, children, style, ...p }: ButtonProps) {
  const pad = size === 'sm' ? '7px 12px' : size === 'lg' ? '12px 20px' : '9px 15px';
  const fs = size === 'sm' ? 13 : size === 'lg' ? 16 : 14;
  const skins: Record<ButtonVariant, React.CSSProperties> = {
    primary:  { background: 'var(--wine)',      color: 'var(--wine-fg)', border: '1px solid transparent' },
    secondary:{ background: 'var(--surface-2)', color: 'var(--ink-1)',  border: '1px solid var(--line-strong)' },
    ghost:    { background: 'transparent',      color: 'var(--ink-2)',  border: '1px solid transparent' },
    tonal:    { background: 'var(--wine-100)',   color: 'var(--wine)',   border: '1px solid transparent' },
    danger:   { background: 'var(--danger-bg)', color: 'var(--danger)', border: '1px solid transparent' },
  };
  const [h, setH] = useState(false);
  const hoverMap: Record<ButtonVariant, React.CSSProperties> = {
    primary:  { background: 'var(--wine-600)' },
    secondary:{ background: 'var(--surface-tint)' },
    ghost:    { background: 'var(--wine-50)', color: 'var(--ink-1)' },
    tonal:    { background: 'var(--wine-200)' },
    danger:   { background: 'var(--danger-bg)' },
  };
  return (
    <button
      {...p}
      onMouseEnter={() => setH(true)}
      onMouseLeave={() => setH(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 7,
        padding: pad, font: `500 ${fs}px/1 var(--font-sans)`, borderRadius: 'var(--r-md)',
        cursor: 'pointer', whiteSpace: 'nowrap', letterSpacing: '-0.01em',
        transition: 'all var(--dur-2) var(--ease-std)',
        ...skins[variant],
        ...(h ? hoverMap[variant] : {}),
        ...style,
      }}
    >
      {icon && <Icon name={icon} size={fs + 3} />}
      {children}
      {iconRight && <Icon name={iconRight} size={fs + 2} />}
    </button>
  );
}

// ── Avatar ───────────────────────────────────────────────────────
interface AvatarProps {
  name?: string;
  initials?: string;
  hue?: string;
  size?: number;
}

export function Avatar({ name, initials, hue = 'wine', size = 34 }: AvatarProps) {
  const ini = initials || (name || '?').split(' ').map(w => w[0]).slice(0, 2).join('');
  const c = HILO.hueVar(hue);
  return (
    <span style={{
      width: size, height: size, borderRadius: 'var(--r-full)', flexShrink: 0,
      background: `color-mix(in srgb, ${c} 16%, var(--surface))`,
      color: c,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      font: `500 ${Math.round(size * 0.4)}px/1 var(--font-sans)`, letterSpacing: '0.01em',
      border: `1px solid color-mix(in srgb, ${c} 24%, transparent)`,
    }}>{ini}</span>
  );
}

// ── Tag ──────────────────────────────────────────────────────────
interface TagProps {
  children: React.ReactNode;
  hue?: string;
  tone?: 'soft' | 'solid';
  style?: React.CSSProperties;
}

export function Tag({ children, hue, tone = 'soft', style }: TagProps) {
  const c = hue ? HILO.hueVar(hue) : 'var(--ink-2)';
  const skin: React.CSSProperties = tone === 'solid'
    ? { background: c, color: '#fff', border: '1px solid transparent' }
    : { background: `color-mix(in srgb, ${c} 13%, var(--surface))`, color: c, border: `1px solid color-mix(in srgb, ${c} 22%, transparent)` };
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 9px',
      borderRadius: 'var(--r-full)', font: '500 12px/1.3 var(--font-sans)', whiteSpace: 'nowrap',
      ...skin, ...style,
    }}>{children}</span>
  );
}

// ── Dot ──────────────────────────────────────────────────────────
interface DotProps {
  color?: string;
  pulse?: boolean;
  size?: number;
}

export function Dot({ color = 'var(--wa)', pulse = false, size = 8 }: DotProps) {
  return (
    <span style={{
      width: size, height: size, borderRadius: '50%', background: color,
      boxShadow: `0 0 0 3px color-mix(in srgb, ${color} 22%, transparent)`,
      animation: pulse ? 'hilo-pulse 1.6s var(--ease-std) infinite' : 'none',
      flexShrink: 0,
      display: 'inline-block',
    }} />
  );
}

// ── Segmented ────────────────────────────────────────────────────
interface SegOption { value: string; label: string; }

interface SegmentedProps {
  options: (string | SegOption)[];
  value: string;
  onChange: (v: string) => void;
  size?: 'sm' | 'md';
}

export function Segmented({ options, value, onChange, size = 'md' }: SegmentedProps) {
  const fs = size === 'sm' ? 12 : 13;
  return (
    <div style={{
      display: 'inline-flex', background: 'var(--surface-tint)', border: '1px solid var(--line)',
      borderRadius: 'var(--r-md)', padding: 3, gap: 2,
    }}>
      {options.map(o => {
        const v = typeof o === 'string' ? o : o.value;
        const l = typeof o === 'string' ? o : o.label;
        const on = v === value;
        return (
          <button key={v} onClick={() => onChange(v)} style={{
            padding: size === 'sm' ? '5px 11px' : '6px 14px', border: 0, cursor: 'pointer',
            borderRadius: 'calc(var(--r-md) - 3px)', font: `500 ${fs}px/1 var(--font-sans)`,
            background: on ? 'var(--surface-2)' : 'transparent',
            color: on ? 'var(--wine)' : 'var(--ink-2)',
            boxShadow: on ? 'var(--shadow-sm)' : 'none',
            transition: 'all var(--dur-2) var(--ease-std)', whiteSpace: 'nowrap',
          }}>{l}</button>
        );
      })}
    </div>
  );
}
