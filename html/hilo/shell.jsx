// hilo/shell.jsx — responsive shell + shared primitives
const { useState, useEffect, useRef } = React;

/* ───────── primitives ───────── */
function Button({ variant='primary', size='md', icon, iconRight, children, style, ...p }) {
  const pad = size==='sm' ? '7px 12px' : size==='lg' ? '12px 20px' : '9px 15px';
  const fs  = size==='sm' ? 13 : size==='lg' ? 16 : 14;
  const skin = {
    primary:  { background:'var(--wine)', color:'var(--wine-fg)', border:'1px solid transparent' },
    secondary:{ background:'var(--surface-2)', color:'var(--ink-1)', border:'1px solid var(--line-strong)' },
    ghost:    { background:'transparent', color:'var(--ink-2)', border:'1px solid transparent' },
    tonal:    { background:'var(--wine-100)', color:'var(--wine)', border:'1px solid transparent' },
    danger:   { background:'var(--danger-bg)', color:'var(--danger)', border:'1px solid transparent' },
  }[variant];
  const [h,setH]=useState(false);
  return (
    <button {...p} onMouseEnter={()=>setH(true)} onMouseLeave={()=>setH(false)}
      style={{
        display:'inline-flex', alignItems:'center', justifyContent:'center', gap:7, padding:pad,
        font:`500 ${fs}px/1 var(--font-sans)`, borderRadius:'var(--r-md)', cursor:'pointer',
        whiteSpace:'nowrap', letterSpacing:'-0.01em',
        transition:'all var(--dur-2) var(--ease-std)',
        ...skin,
        ...(h && variant==='primary'   ? { background:'var(--wine-600)' } : {}),
        ...(h && variant==='secondary' ? { background:'var(--surface-tint)' } : {}),
        ...(h && variant==='ghost'     ? { background:'var(--wine-50)', color:'var(--ink-1)' } : {}),
        ...(h && variant==='tonal'     ? { background:'var(--wine-200)' } : {}),
        ...style,
      }}>
      {icon && <Icon name={icon} size={fs+3}/>}
      {children}
      {iconRight && <Icon name={iconRight} size={fs+2}/>}
    </button>
  );
}

function Avatar({ name, initials, hue='wine', size=34 }) {
  const ini = initials || (name||'?').split(' ').map(w=>w[0]).slice(0,2).join('');
  return (
    <span style={{
      width:size, height:size, borderRadius:'var(--r-full)', flexShrink:0,
      background:`color-mix(in srgb, ${HILO.hueVar(hue)} 16%, var(--surface))`,
      color:HILO.hueVar(hue),
      display:'inline-flex', alignItems:'center', justifyContent:'center',
      font:`500 ${size*0.4}px/1 var(--font-sans)`, letterSpacing:'0.01em',
      border:`1px solid color-mix(in srgb, ${HILO.hueVar(hue)} 24%, transparent)`,
    }}>{ini}</span>
  );
}

function Tag({ children, hue, tone='soft', style }) {
  const c = hue ? HILO.hueVar(hue) : 'var(--ink-2)';
  const skin = tone==='solid'
    ? { background:c, color:'#fff', border:'1px solid transparent' }
    : { background:`color-mix(in srgb, ${c} 13%, var(--surface))`, color:c,
        border:`1px solid color-mix(in srgb, ${c} 22%, transparent)` };
  return <span style={{
    display:'inline-flex', alignItems:'center', gap:5, padding:'3px 9px',
    borderRadius:'var(--r-full)', font:'500 12px/1.3 var(--font-sans)', whiteSpace:'nowrap',
    ...skin, ...style }}>{children}</span>;
}

function Dot({ color='var(--wa)', pulse=false, size=8 }) {
  return <span style={{ width:size, height:size, borderRadius:'50%', background:color,
    boxShadow:`0 0 0 3px color-mix(in srgb, ${color} 22%, transparent)`,
    animation: pulse ? 'hilo-pulse 1.6s var(--ease-std) infinite' : 'none', flexShrink:0 }}/>;
}

function Segmented({ options, value, onChange, size='md' }) {
  const fs = size==='sm'?12:13;
  return (
    <div style={{ display:'inline-flex', background:'var(--surface-tint)', border:'1px solid var(--line)',
      borderRadius:'var(--r-md)', padding:3, gap:2 }}>
      {options.map(o=>{
        const v = typeof o==='string'?o:o.value, l = typeof o==='string'?o:o.label;
        const on = v===value;
        return <button key={v} onClick={()=>onChange(v)} style={{
          padding: size==='sm'?'5px 11px':'6px 14px', border:0, cursor:'pointer',
          borderRadius:'calc(var(--r-md) - 3px)', font:`500 ${fs}px/1 var(--font-sans)`,
          background: on?'var(--surface-2)':'transparent',
          color: on?'var(--wine)':'var(--ink-2)',
          boxShadow: on?'var(--shadow-sm)':'none',
          transition:'all var(--dur-2) var(--ease-std)', whiteSpace:'nowrap',
        }}>{l}</button>;
      })}
    </div>
  );
}

/* ───────── nav model ───────── */
const NAV = [
  { group:'Operación', items:[
    { id:'inicio',   icon:'home',     label:'Inicio' },
    { id:'agenda',   icon:'calendar', label:'Agenda' },
    { id:'servicios',icon:'scissors', label:'Servicios' },
    { id:'clientes', icon:'users',    label:'Clientes' },
  ]},
  { group:'Canal', items:[
    { id:'conversaciones', icon:'chat',  label:'Conversaciones', soon:true },
    { id:'canales',        icon:'whatsapp', label:'Canales', soon:true },
    { id:'calendarios',    icon:'layers', label:'Calendarios', soon:true },
  ]},
  { group:'Cuenta', items:[
    { id:'equipo',      icon:'user', label:'Equipo', soon:true },
    { id:'suscripcion', icon:'card', label:'Suscripción', soon:true },
    { id:'config',      icon:'gear', label:'Configuración', soon:true },
  ]},
];
const PRIMARY = ['inicio','agenda','servicios','clientes'];

/* ───────── Sidebar (desktop) ───────── */
function Sidebar({ active, onNav, onboardPct }) {
  return (
    <aside style={{
      width:244, flexShrink:0, background:'var(--paper-2)',
      borderRight:'1px solid var(--line)', display:'flex', flexDirection:'column',
      padding:'16px 12px 12px', gap:18, height:'100%', overflowY:'auto',
    }}>
      {/* brand */}
      <div style={{ display:'flex', alignItems:'center', gap:10, padding:'2px 6px 4px' }}>
        <HiloMark size={30}/>
        <div style={{ lineHeight:1.05, minWidth:0 }}>
          <div style={{ font:'700 17px/1 var(--font-sans)', letterSpacing:'-0.02em', color:'var(--ink-1)' }}>Hilo</div>
          <div style={{ font:'400 11px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>{HILO.business.name}</div>
        </div>
      </div>

      {NAV.map(g=>(
        <div key={g.group}>
          <div className="eyebrow" style={{ padding:'0 8px 8px' }}>{g.group}</div>
          <div style={{ display:'flex', flexDirection:'column', gap:2 }}>
            {g.items.map(it=>{
              const on = it.id===active;
              return (
                <button key={it.id} onClick={()=>onNav(it.id)} style={{
                  position:'relative', display:'flex', alignItems:'center', gap:11,
                  padding:'8px 10px', border:0, borderRadius:'var(--r-sm)', cursor:'pointer',
                  textAlign:'left', width:'100%',
                  background: on?'var(--wine-50)':'transparent',
                  color: on?'var(--wine)':'var(--ink-2)',
                  font:`500 14px/1 var(--font-sans)`, letterSpacing:'-0.01em',
                  boxShadow:'none',
                  transition:'all var(--dur-2) var(--ease-std)',
                }}
                onMouseEnter={e=>{ if(!on){ e.currentTarget.style.background='var(--surface-tint)'; e.currentTarget.style.color='var(--ink-1)';}}}
                onMouseLeave={e=>{ if(!on){ e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--ink-2)';}}}>
                  {on && <span style={{ position:'absolute', left:-12, top:'50%', transform:'translateY(-50%)',
                    width:3, height:20, borderRadius:'0 3px 3px 0', background:'var(--wine)' }}/>}
                  <Icon name={it.icon} size={18} strokeWidth={on?1.9:1.7}/>
                  <span style={{ flex:1 }}>{it.label}</span>
                  {it.soon && <span style={{ font:'500 9px/1 var(--font-sans)', textTransform:'uppercase',
                    letterSpacing:'0.08em', color:'var(--ink-4)', border:'1px solid var(--line)',
                    padding:'2px 5px', borderRadius:'var(--r-full)' }}>pronto</span>}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      {/* onboarding nudge */}
      <button onClick={()=>onNav('onboarding')} style={{
        marginTop:'auto', textAlign:'left', cursor:'pointer', width:'100%',
        background:'var(--surface-tint)', border:'1px solid var(--line)', borderRadius:'var(--r-md)',
        padding:'12px', display:'flex', flexDirection:'column', gap:8,
        boxShadow:'none', transition:'all var(--dur-2)',
      }}
      onMouseEnter={e=>e.currentTarget.style.background='var(--wine-50)'}
      onMouseLeave={e=>e.currentTarget.style.background='var(--surface-tint)'}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <Icon name="sparkle" size={15} style={{ color:'var(--wine)' }}/>
          <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-1)' }}>Termina de configurar</span>
        </div>
        <div style={{ height:5, borderRadius:99, background:'var(--wine-100)', overflow:'hidden' }}>
          <div style={{ width:`${onboardPct}%`, height:'100%', background:'var(--wine)', borderRadius:99 }}/>
        </div>
        <span style={{ font:'400 11px/1 var(--font-sans)', color:'var(--ink-3)' }}>{onboardPct}% · faltan 2 pasos</span>
      </button>

      {/* user */}
      <div style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 6px 2px',
        borderTop:'1px solid var(--line)' }}>
        <Avatar name={HILO.owner.name} initials={HILO.owner.initials} hue="wine" size={32}/>
        <div style={{ flex:1, minWidth:0, lineHeight:1.15 }}>
          <div style={{ font:'500 13px/1.2 var(--font-sans)', color:'var(--ink-1)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{HILO.owner.name}</div>
          <div style={{ font:'400 11px/1.2 var(--font-sans)', color:'var(--ink-3)' }}>{HILO.owner.role}</div>
        </div>
        <Icon name="dotsV" size={16} style={{ color:'var(--ink-3)', cursor:'pointer' }}/>
      </div>
    </aside>
  );
}

/* ───────── TopBar ───────── */
function TopBar({ title, isMobile, onMenu, onCompose, syncOk=true }) {
  return (
    <header style={{
      height:56, padding:'0 16px', display:'flex', alignItems:'center', gap:12, flexShrink:0,
      background:'var(--mat-toolbar)', backdropFilter:'var(--blur-thin)',
      WebkitBackdropFilter:'var(--blur-thin)',
      borderBottom:'1px solid var(--line)', position:'sticky', top:0, zIndex:20,
    }}>
      {isMobile && <HiloMark size={28}/>}
      <h1 style={{ margin:0, font:'500 19px/1 var(--font-sans)', letterSpacing:'-0.02em', color:'var(--ink-1)' }}>{title}</h1>

      {!isMobile && (
        <button style={{
          display:'flex', alignItems:'center', gap:9, padding:'8px 12px', marginLeft:10,
          background:'var(--surface-tint)', border:'1px solid var(--line)', borderRadius:'var(--r-md)',
          flex:'1 1 0', maxWidth:360, cursor:'pointer', textAlign:'left',
        }}>
          <Icon name="search" size={15} style={{ color:'var(--ink-3)' }}/>
          <span style={{ flex:1, font:'400 13px/1 var(--font-sans)', color:'var(--ink-3)' }}>Buscar cliente, cita, servicio…</span>
          <kbd style={{ font:'500 11px/1 var(--font-mono)', color:'var(--ink-3)', padding:'3px 6px',
            background:'var(--surface)', borderRadius:5, border:'1px solid var(--line)' }}>⌘K</kbd>
        </button>
      )}

      <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ display:'inline-flex', alignItems:'center', gap:6, padding:'5px 10px',
          borderRadius:'var(--r-full)', background:'var(--wa-bg)', border:'1px solid color-mix(in srgb, var(--wa-ink) 22%, transparent)' }}>
          <Dot color="var(--wa)" pulse/>
          <span style={{ font:'500 12px/1 var(--font-sans)', color:'var(--wa-ink)' }}>{isMobile?'WA':'WhatsApp activo'}</span>
        </span>
        {!isMobile && <Button variant="secondary" size="sm" icon="bell" aria-label="Alertas" style={{ padding:'8px' }}/>}
        <Button variant="primary" size="sm" icon="plus" onClick={onCompose}>{isMobile?'Cita':'Nueva cita'}</Button>
      </div>
    </header>
  );
}

/* ───────── Bottom tabs (mobile) ───────── */
function BottomTabs({ active, onNav }) {
  const items = NAV[0].items;
  return (
    <nav style={{
      position:'sticky', bottom:0, zIndex:20, flexShrink:0,
      display:'flex', justifyContent:'space-around', alignItems:'stretch',
      background:'var(--mat-toolbar)', backdropFilter:'var(--blur-thin)',
      WebkitBackdropFilter:'var(--blur-thin)', borderTop:'1px solid var(--line)',
      padding:'6px 8px calc(6px + env(safe-area-inset-bottom))',
    }}>
      {items.map(it=>{
        const on = it.id===active;
        return (
          <button key={it.id} onClick={()=>onNav(it.id)} style={{
            flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:3,
            background:'transparent', border:0, cursor:'pointer', padding:'4px 0',
            color: on?'var(--wine)':'var(--ink-3)',
          }}>
            <Icon name={it.icon} size={22} strokeWidth={on?1.9:1.7}/>
            <span style={{ font:`${on?500:400} 10px/1 var(--font-sans)` }}>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function useIsMobile(bp=880){
  const [m,setM]=useState(typeof window!=='undefined' && window.innerWidth<bp);
  useEffect(()=>{ const f=()=>setM(window.innerWidth<bp); window.addEventListener('resize',f); return ()=>window.removeEventListener('resize',f); },[bp]);
  return m;
}

Object.assign(window, { Button, Avatar, Tag, Dot, Segmented, Sidebar, TopBar, BottomTabs, useIsMobile, NAV, PRIMARY });
