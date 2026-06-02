// hilo/icons.jsx — thin line icon set (SF/Lucide flavor) + brand mark
const { useState: _us, useEffect: _ue, useRef: _ur } = React;

const HILO_ICONS = {
  home:    'M3 10.5 12 3l9 7.5M5 9v11h5v-6h4v6h5V9',
  calendar:'M3 5h18v16H3zM3 9.5h18M8 2.5v4M16 2.5v4',
  clock:   'M12 7v5l3.5 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z',
  scissors:'M6 6.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zm0 11a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM8.5 9 20 4M8.5 15 20 20M9 12l11 0',
  users:   'M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M17 11a3.5 3.5 0 0 0 0-7M21.5 20a6.5 6.5 0 0 0-4-6',
  user:    'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 20a7.5 7.5 0 0 1 15 0',
  chat:    'M21 12a8 8 0 0 1-11.5 7.2L4 20.5l1.3-5A8 8 0 1 1 21 12z',
  whatsapp:'M20 11.5a8 8 0 0 1-11.8 7L4 20l1.6-4A8 8 0 1 1 20 11.5zM8.8 8.2c.3-.6.5-.4.9-.4.3 0 .5.1.7.6l.5 1.1c.1.3 0 .5-.1.7l-.4.5c-.1.2-.2.4 0 .7.3.5.9 1.2 1.6 1.6.3.2.5.1.7-.1l.4-.5c.2-.2.4-.2.7-.1l1.1.6c.3.2.4.4.4.6 0 .9-.8 1.4-1.5 1.4-1 0-2.6-.7-3.9-2s-2-2.9-2-3.9c0-.4.1-.7.4-1z',
  layers:  'M12 3 3 8l9 5 9-5-9-5zM3 13l9 5 9-5M3 17.5l9 5 9-5',
  link:    'M9 14.5 14.5 9M10 6.5l1.5-1.5a4 4 0 0 1 5.6 5.6L16 12M14 17.5 12.5 19a4 4 0 0 1-5.6-5.6L8 12',
  gear:    'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm7.5 3c0 .6-.1 1.1-.2 1.6l1.9 1.5-2 3.4-2.3-.9a7 7 0 0 1-2.7 1.6l-.3 2.4h-3.8l-.3-2.4A7 7 0 0 1 7 18.7l-2.3.9-2-3.4 1.9-1.5a7 7 0 0 1 0-3.2L2.7 9.9l2-3.4 2.3.9a7 7 0 0 1 2.7-1.6l.3-2.4h3.8l.3 2.4a7 7 0 0 1 2.7 1.6l2.3-.9 2 3.4-1.9 1.5c.1.5.2 1 .2 1.6z',
  card:    'M3 6h18v12H3zM3 10h18M7 15h4',
  search:  'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm9.5 16.5L16.5 16.5',
  plus:    'M12 5v14M5 12h14',
  bell:    'M6 9a6 6 0 0 1 12 0c0 6 2.5 7 2.5 7h-17S6 15 6 9zM9.5 20a2.5 2.5 0 0 0 5 0',
  chev:    'M9 5l7 7-7 7',
  chevDn:  'M6 9l6 6 6-6',
  chevUp:  'M6 15l6-6 6 6',
  chevL:   'M15 5l-7 7 7 7',
  check:   'M20 6 9 17l-5-5',
  checkCircle:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8.5 12l2.5 2.5 4.5-5',
  x:       'M6 6l12 12M18 6 6 18',
  dots:    'M5 12h.01M12 12h.01M19 12h.01',
  dotsV:   'M12 5h.01M12 12h.01M12 19h.01',
  arrowR:  'M5 12h14M13 6l6 6-6 6',
  arrowUp: 'M12 19V5M6 11l6-6 6 6',
  arrowDn: 'M12 5v14M6 13l6 6 6-6',
  sync:    'M20 8a8 8 0 0 0-14-2M4 6v3h3M4 16a8 8 0 0 0 14 2M20 18v-3h-3',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM18.5 15l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z',
  pin:     'M12 21s7-6.3 7-11a7 7 0 1 0-14 0c0 4.7 7 11 7 11zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  phone:   'M5 3h3l2 5-2.5 1.5a11 11 0 0 0 5 5L19 17l2 5v-2 2h-3A15 15 0 0 1 3 6V3z',
  block:   'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM5.6 5.6l12.8 12.8',
  edit:    'M4 20h4L18.5 9.5a2 2 0 0 0-2.8-2.8L5 17.2zM14.5 6.5l3 3',
  trash:   'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
  filter:  'M3 5h18l-7 8v6l-4-2v-4z',
  money:   'M12 3v18M16 7.5c0-1.5-1.8-2.5-4-2.5s-4 1-4 2.5S9.8 10 12 10s4 1 4 2.5S14.2 15 12 15s-4-1-4-2.5',
  star:    'M12 3.5l2.6 5.7 6.2.7-4.6 4.2 1.3 6.1L12 17.2 6.5 20.2l1.3-6.1L3.2 9.9l6.2-.7z',
  logout:  'M15 4h4v16h-4M11 8l-4 4 4 4M7 12h11',
  more:    'M12 5v14M5 12h14',
  thread:  'M12 2v3M12 19v3M12 5a3.5 3.5 0 0 1 0 7 3.5 3.5 0 0 0 0 7',
  bolt:    'M13 2 4 14h7l-1 8 9-12h-7z',
  shield:  'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
};

function Icon({ name, size = 20, strokeWidth = 1.7, fill = false, style, ...p }) {
  const d = HILO_ICONS[name] || HILO_ICONS.dots;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24"
      fill={fill ? 'currentColor' : 'none'}
      stroke={fill ? 'none' : 'currentColor'}
      strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, ...style }} {...p}>
      <path d={d} />
    </svg>
  );
}

/* Brand mark — a continuous thread that loops into a knot (the "hilo") */
function HiloMark({ size = 26, color = 'var(--wine-fg)', bg = 'var(--wine)' }) {
  return (
    <span style={{
      width: size, height: size, borderRadius: size * 0.32, background: bg,
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      boxShadow: '0 1px 2px rgba(58,40,40,0.25)',
    }}>
      <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none"
        stroke={color} strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 3v6a4 4 0 0 0 8 0 4 4 0 0 1 4 4v8" />
        <circle cx="6" cy="3" r="1.4" fill={color} stroke="none" />
        <circle cx="18" cy="21" r="1.4" fill={color} stroke="none" />
      </svg>
    </span>
  );
}

Object.assign(window, { Icon, HiloMark, HILO_ICONS });
