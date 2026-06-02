// hilo/dashboard.jsx — Inicio: editorial greeting + operational cards + "día como historia" + agente vivo
const { useState: useStateD, useEffect: useEffectD } = React;

/* status meta for the day thread */
const STATUS = {
  done:     { label:'Atendida',   color:'var(--ink-3)',  dim:true },
  now:      { label:'En curso',   color:'var(--wine)',   dim:false },
  next:     { label:'Sigue',      color:'var(--clay)',   dim:false },
  upcoming: { label:'Programada', color:'var(--ink-2)',  dim:false },
};

function StatCard({ eyebrow, value, unit, sub, delta, icon, accent='var(--wine)' }) {
  return (
    <div className="card" style={{ padding:'16px 18px', display:'flex', flexDirection:'column', gap:10, minWidth:0 }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <span className="eyebrow">{eyebrow}</span>
        <span style={{ width:30, height:30, borderRadius:'var(--r-sm)', display:'grid', placeItems:'center',
          background:`color-mix(in srgb, ${accent} 12%, var(--surface))`, color:accent }}>
          <Icon name={icon} size={16}/>
        </span>
      </div>
      <div style={{ display:'flex', alignItems:'baseline', gap:6 }}>
        <span className="tnum" style={{ font:'500 30px/1 var(--font-sans)', letterSpacing:'-0.03em', color:'var(--ink-1)' }}>{value}</span>
        {unit && <span style={{ font:'400 14px/1 var(--font-sans)', color:'var(--ink-3)' }}>{unit}</span>}
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        {delta!=null && (
          <span style={{ display:'inline-flex', alignItems:'center', gap:2, font:'500 12px/1 var(--font-sans)',
            color: delta>=0?'var(--success)':'var(--danger)' }}>
            <Icon name={delta>=0?'arrowUp':'arrowDn'} size={13}/>{Math.abs(delta)}%
          </span>
        )}
        <span style={{ font:'400 12.5px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>{sub}</span>
      </div>
    </div>
  );
}

/* one bead on the day thread */
function ThreadItem({ a, isLast }) {
  const st = STATUS[a.status];
  const svc = HILO.services.find(s=>s.name===a.svc);
  const hue = svc ? svc.hue : 'wine';
  return (
    <div style={{ display:'grid', gridTemplateColumns:'58px 28px 1fr', columnGap:0, position:'relative' }}>
      {/* time */}
      <div style={{ textAlign:'right', paddingRight:14, paddingTop:14 }}>
        <div className="tnum" style={{ font:'500 14px/1 var(--font-sans)', color: st.dim?'var(--ink-3)':'var(--ink-1)' }}>{a.time}</div>
        <div className="tnum" style={{ font:'400 11px/1.4 var(--font-mono)', color:'var(--ink-4)' }}>{a.end}</div>
      </div>
      {/* thread + knot */}
      <div style={{ position:'relative', display:'flex', justifyContent:'center' }}>
        {!isLast && <span style={{ position:'absolute', top:14, bottom:-2, width:2,
          background: st.dim?'var(--line-strong)':'var(--wine-200)', borderRadius:2 }}/>}
        <span style={{ position:'relative', marginTop:14, width:14, height:14, borderRadius:'50%',
          background: a.status==='done' ? 'var(--surface)' : st.color,
          border:`2px solid ${a.status==='done'?'var(--line-strong)':st.color}`,
          display:'grid', placeItems:'center',
          boxShadow: a.status==='now' ? '0 0 0 5px color-mix(in srgb, var(--wine) 18%, transparent)':'none',
          animation: a.status==='now' ? 'hilo-pulse 1.8s var(--ease-std) infinite':'none' }}>
          {a.status==='done' && <Icon name="check" size={9} style={{ color:'var(--ink-3)' }} strokeWidth={2.4}/>}
        </span>
      </div>
      {/* card */}
      <div style={{ padding:'8px 0 14px' }}>
        <div style={{
          background: a.status==='now' ? 'var(--wine-50)' : 'var(--surface)',
          border:`1px solid ${a.status==='now'?'color-mix(in srgb, var(--wine) 26%, transparent)':'var(--line)'}`,
          borderRadius:'var(--r-md)', padding:'11px 13px',
          opacity: st.dim?0.72:1, transition:'all var(--dur-2)',
          display:'flex', alignItems:'center', gap:12,
        }}>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ display:'flex', alignItems:'center', gap:8, flexWrap:'wrap' }}>
              <span style={{ font:'500 14.5px/1.2 var(--font-sans)', color:'var(--ink-1)', whiteSpace:'nowrap' }}>{a.client}</span>
              {a.via==='wa' && <Icon name="whatsapp" size={14} style={{ color:'var(--wa-ink)' }}/>}
              {a.home && <Tag hue="sage" style={{ padding:'2px 7px', fontSize:11 }}><Icon name="pin" size={11}/>Domicilio</Tag>}
            </div>
            <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:5 }}>
              <Tag hue={hue} style={{ padding:'2px 8px', fontSize:11.5 }}>{a.svc}</Tag>
              <span style={{ font:'400 12px/1 var(--font-sans)', color:'var(--ink-3)' }}>· {a.pro}</span>
            </div>
          </div>
          {a.status==='now'
            ? <Tag hue="wine" tone="solid" style={{ fontSize:11 }}><Dot color="#fff" size={6}/>En curso</Tag>
            : <span style={{ font:'400 11.5px/1 var(--font-sans)', color:st.color }}>{st.label}</span>}
        </div>
      </div>
    </div>
  );
}

/* live agent conversation panel */
function AgentPanel() {
  const c = HILO.conversation;
  const [typing, setTyping] = useStateD(true);
  useEffectD(()=>{ const t=setInterval(()=>setTyping(v=>!v), 3200); return ()=>clearInterval(t); },[]);
  return (
    <div className="card" style={{ display:'flex', flexDirection:'column', overflow:'hidden' }}>
      <div style={{ padding:'14px 16px', display:'flex', alignItems:'center', gap:11, borderBottom:'1px solid var(--line)' }}>
        <span style={{ width:34, height:34, borderRadius:'var(--r-full)', background:'color-mix(in srgb, var(--wa-ink) 14%, var(--surface))',
          display:'grid', placeItems:'center', color:'var(--wa-ink)' }}><Icon name="whatsapp" size={18}/></span>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:7 }}>
            <span style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>Tu agente, ahora</span>
            <Dot color="var(--wa)" pulse size={7}/>
          </div>
          <div style={{ font:'400 12px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>{c.client} · {c.intent}</div>
        </div>
        <Tag hue="wine" style={{ fontSize:11 }}>{c.phone.slice(-4)}</Tag>
      </div>

      {/* messages */}
      <div style={{ padding:'14px 16px', display:'flex', flexDirection:'column', gap:9,
        background:'var(--surface-tint)', flex:1, maxHeight:288, overflowY:'auto' }}>
        {c.msgs.map((m,i)=>(
          <div key={i} style={{ alignSelf: m.from==='agent'?'flex-end':'flex-start', maxWidth:'82%' }}>
            <div style={{
              padding:'8px 12px', borderRadius: m.from==='agent'?'14px 14px 4px 14px':'14px 14px 14px 4px',
              background: m.from==='agent'?'var(--wine)':'var(--surface-2)',
              color: m.from==='agent'?'var(--wine-fg)':'var(--ink-1)',
              border: m.from==='agent'?'1px solid transparent':'1px solid var(--line)',
              font:'400 13px/1.4 var(--font-sans)', boxShadow:'var(--shadow-sm)',
            }}>{m.text}</div>
            <div style={{ font:'400 10px/1 var(--font-mono)', color:'var(--ink-4)', marginTop:3,
              textAlign: m.from==='agent'?'right':'left' }}>{m.t}{m.from==='agent'?' · agente':''}</div>
          </div>
        ))}
        {typing && (
          <div style={{ alignSelf:'flex-end', padding:'10px 14px', borderRadius:'14px 14px 4px 14px',
            background:'var(--wine)', display:'flex', gap:4 }}>
            {[0,1,2].map(i=><span key={i} style={{ width:6, height:6, borderRadius:'50%', background:'var(--wine-fg)',
              opacity:.85, animation:`hilo-typing 1s ${i*0.15}s var(--ease-std) infinite` }}/>)}
          </div>
        )}
      </div>

      {/* outcome — the thread closes into an appointment */}
      <div style={{ padding:'12px 16px', display:'flex', alignItems:'center', gap:11, borderTop:'1px solid var(--line)' }}>
        <span style={{ width:30, height:30, borderRadius:'var(--r-sm)', background:'color-mix(in srgb, var(--success) 14%, var(--surface))',
          display:'grid', placeItems:'center', color:'var(--success)' }}><Icon name="checkCircle" size={17}/></span>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ font:'500 13px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{c.action.label}</div>
          <div style={{ font:'400 11.5px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>{c.action.sub}</div>
        </div>
        <Button variant="ghost" size="sm" iconRight="chev">Ver</Button>
      </div>
    </div>
  );
}

function MiniCard({ children, style }) {
  return <div className="card" style={{ padding:'14px 16px', ...style }}>{children}</div>;
}

function Dashboard({ isMobile, onNav }) {
  const m = HILO.metrics;
  const hour = 'Buenos días';
  return (
    <div style={{ maxWidth:1180, margin:'0 auto', padding: isMobile?'18px 16px 28px':'26px 30px 40px',
      animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      {/* editorial greeting */}
      <div style={{ marginBottom:22 }}>
        <div className="eyebrow" style={{ marginBottom:8 }}>Miércoles 28 de mayo · {HILO.business.city}</div>
        <h2 style={{ margin:0, font:'400 clamp(26px,4vw,34px)/1.08 var(--font-serif)', letterSpacing:'-0.01em', color:'var(--ink-1)' }}>
          {hour}, <span className="serif-i">Camilo</span>.
        </h2>
        <p style={{ margin:'8px 0 0', font:'400 15.5px/1.5 var(--font-sans)', color:'var(--ink-2)', maxWidth:560 }}>
          Tu agente lleva <strong style={{ color:'var(--ink-1)', fontWeight:500 }}>9 conversaciones</strong> hoy y agendó
          <strong style={{ color:'var(--ink-1)', fontWeight:500 }}> 4 citas</strong> sin que tocaras nada. Quedan {m.upcomingCount} por atender.
        </p>
      </div>

      {/* operational stat cards */}
      <div style={{ display:'grid', gridTemplateColumns:`repeat(auto-fit, minmax(${isMobile?'150px':'200px'}, 1fr))`, gap:14, marginBottom:18 }}>
        <StatCard eyebrow="Citas de hoy" value={m.todayCount} sub={`${m.doneCount} atendidas · ${m.upcomingCount} por venir`} icon="calendar"/>
        <StatCard eyebrow="Ingresos del mes" value={HILO.fmtCOP(m.revenueMonth)} delta={13} sub="vs. mes anterior" icon="money" accent="var(--clay)"/>
        <StatCard eyebrow="Automatización" value={m.automation} unit="%" sub="citas sin intervención" icon="sparkle" accent="var(--sage)"/>
        <StatCard eyebrow="Respuesta media" value={m.responseAvg} sub="del agente en WhatsApp" icon="bolt" accent="var(--steel)"/>
      </div>

      {/* main split */}
      <div style={{ display:'grid', gridTemplateColumns: isMobile?'1fr':'1.45fr 1fr', gap:18, alignItems:'start' }}>
        {/* day as a story */}
        <div className="card" style={{ padding:'18px 20px 6px' }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6 }}>
            <div>
              <h3 style={{ margin:0, font:'400 21px/1.1 var(--font-serif)', color:'var(--ink-1)' }}>El día como <span className="serif-i">historia</span></h3>
              <div style={{ font:'400 12.5px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:4 }}>Cada nudo es una cita en tu hilo de hoy</div>
            </div>
            <Button variant="ghost" size="sm" iconRight="arrowR" onClick={()=>onNav('agenda')}>Agenda</Button>
          </div>

          {/* now marker */}
          <div style={{ display:'grid', gridTemplateColumns:'58px 28px 1fr', alignItems:'center', margin:'6px 0' }}>
            <span className="tnum" style={{ textAlign:'right', paddingRight:14, font:'500 11px/1 var(--font-mono)', color:'var(--wine)' }}>10:01</span>
            <span/>
            <span style={{ display:'flex', alignItems:'center', gap:8 }}>
              <span style={{ flex:1, height:1, background:'repeating-linear-gradient(90deg, var(--wine-300) 0 5px, transparent 5px 10px)' }}/>
              <span style={{ font:'500 10px/1 var(--font-sans)', textTransform:'uppercase', letterSpacing:'0.1em', color:'var(--wine)' }}>ahora</span>
            </span>
          </div>

          <div>
            {HILO.today.map((a,i)=><ThreadItem key={a.id} a={a} isLast={i===HILO.today.length-1}/>)}
          </div>
        </div>

        {/* right column */}
        <div style={{ display:'flex', flexDirection:'column', gap:18 }}>
          <AgentPanel/>

          {/* alerts */}
          <MiniCard style={{ padding:'4px 0' }}>
            <div className="eyebrow" style={{ padding:'12px 16px 8px' }}>Necesita tu atención</div>
            {HILO.alerts.map((al,i)=>(
              <div key={al.id} style={{ display:'flex', alignItems:'center', gap:11, padding:'10px 16px',
                borderTop: i?'1px solid var(--line)':'none' }}>
                <span style={{ width:30, height:30, borderRadius:'var(--r-sm)', display:'grid', placeItems:'center',
                  background: al.kind==='warning'?'var(--warning-bg)':'var(--wine-50)',
                  color: al.kind==='warning'?'var(--warning)':'var(--wine)' }}><Icon name={al.icon} size={16}/></span>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ font:'500 13px/1.25 var(--font-sans)', color:'var(--ink-1)' }}>{al.text}</div>
                  <div style={{ font:'400 11.5px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>{al.sub}</div>
                </div>
                <Button variant="ghost" size="sm">{al.cta}</Button>
              </div>
            ))}
          </MiniCard>

          {/* channel + sync */}
          <MiniCard>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
              <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                <span style={{ width:32, height:32, borderRadius:'var(--r-sm)', background:'var(--wa-bg)',
                  display:'grid', placeItems:'center', color:'var(--wa-ink)' }}><Icon name="whatsapp" size={18}/></span>
                <div>
                  <div className="tnum" style={{ font:'500 13.5px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{HILO.channel.number}</div>
                  <div style={{ font:'400 11.5px/1.2 var(--font-sans)', color:'var(--ink-3)' }}>Coexistencia activa · {HILO.channel.provider}</div>
                </div>
              </div>
              <Tag hue="sage" style={{ fontSize:11 }}><Dot color="var(--wa)" size={6}/>Activo</Tag>
            </div>
            <div style={{ display:'flex', alignItems:'center', gap:7, marginTop:12, paddingTop:12, borderTop:'1px solid var(--line)',
              font:'400 12px/1 var(--font-sans)', color:'var(--ink-3)' }}>
              <Icon name="sync" size={14} style={{ color:'var(--success)' }}/>
              Google Calendar sincronizado · {HILO.channel.lastSync}
            </div>
          </MiniCard>
        </div>
      </div>
    </div>
  );
}

window.Dashboard = Dashboard;
