// hilo/agenda.jsx — Agenda: day (thread) / week (grid) / month
const { useState: useStateAg } = React;

const DAYS = ['Lun','Mar','Mié','Jue','Vie','Sáb'];
const DATES = [25,26,27,28,29,30];
const TODAY_IDX = 3; // jueves 28

// week appointments: {day(0-5), start(hour float), dur(min), client, svc, pro}
const WEEK = [
  { d:0, s:9.5,  m:60, client:'Juan P.',     svc:'s2', pro:'Andrés' },
  { d:0, s:11.5, m:40, client:'Carlos M.',   svc:'s1', pro:'Julián' },
  { d:0, s:15,   m:25, client:'Luis F.',     svc:'s3', pro:'Samuel' },
  { d:1, s:10,   m:60, client:'David R.',    svc:'s2', pro:'Julián' },
  { d:1, s:14,   m:35, client:'Iván T.',     svc:'s4', pro:'Andrés' },
  { d:1, s:16.5, m:50, client:'Pablo G.',    svc:'s5', pro:'Samuel' },
  { d:2, s:9,    m:40, client:'Hugo L.',     svc:'s1', pro:'Andrés' },
  { d:2, s:12,   m:60, client:'Marco A.',    svc:'s2', pro:'Julián' },
  { d:2, s:17,   m:25, client:'Saúl B.',     svc:'s3', pro:'Samuel' },
  // thursday = today
  { d:3, s:9,    m:40, client:'Mateo Gómez',    svc:'s1', pro:'Andrés' },
  { d:3, s:9.75, m:60, client:'Daniel Ospina',  svc:'s2', pro:'Julián' },
  { d:3, s:11,   m:25, client:'Sebastián Ruiz', svc:'s3', pro:'Samuel' },
  { d:3, s:12,   m:35, client:'Tomás Cardona',  svc:'s4', pro:'Andrés' },
  { d:3, s:14.5, m:60, client:'Felipe Arango',  svc:'s2', pro:'Julián' },
  { d:3, s:16,   m:50, client:'Nicolás Bedoya', svc:'s5', pro:'Samuel' },
  { d:3, s:18,   m:60, client:'Esteban Lopera', svc:'s2', pro:'Andrés' },
  { d:4, s:10,   m:60, client:'Andrés C.',   svc:'s2', pro:'Julián' },
  { d:4, s:13,   m:40, client:'Bruno V.',    svc:'s1', pro:'Andrés' },
  { d:4, s:16,   m:90, client:'Óscar P.',    svc:'s6', pro:'Julián' },
  { d:5, s:9.5,  m:40, client:'Raúl S.',     svc:'s1', pro:'Andrés' },
  { d:5, s:11,   m:60, client:'Diego N.',    svc:'s2', pro:'Samuel' },
];
const BLOCKS = [{ d:3, s:13, m:90, label:'Almuerzo' }, { d:1, s:9, m:60, label:'Inventario' }];

const HOURS = [9,10,11,12,13,14,15,16,17,18,19];
const PX_PER_HOUR = 64;

function svcHue(id){ const s = HILO.services.find(x=>x.id===id); return s?s.hue:'wine'; }
function svcName(id){ const s = HILO.services.find(x=>x.id===id); return s?s.name:'Servicio'; }

function WeekView(){
  return (
    <div className="card" style={{ overflow:'hidden' }}>
      {/* day headers */}
      <div style={{ display:'grid', gridTemplateColumns:`56px repeat(6, 1fr)`, borderBottom:'1px solid var(--line)' }}>
        <div/>
        {DAYS.map((d,i)=>(
          <div key={d} style={{ padding:'12px 8px', textAlign:'center', borderLeft:'1px solid var(--line)',
            background: i===TODAY_IDX?'var(--wine-50)':'transparent' }}>
            <div style={{ font:'500 11px/1 var(--font-sans)', textTransform:'uppercase', letterSpacing:'0.08em',
              color: i===TODAY_IDX?'var(--wine)':'var(--ink-3)' }}>{d}</div>
            <div className="tnum" style={{ font:'500 19px/1.2 var(--font-sans)', marginTop:4,
              color: i===TODAY_IDX?'var(--wine)':'var(--ink-1)' }}>{DATES[i]}</div>
          </div>
        ))}
      </div>
      {/* grid */}
      <div style={{ display:'grid', gridTemplateColumns:`56px repeat(6, 1fr)`, position:'relative', overflowX:'auto' }}>
        {/* hour gutter */}
        <div>
          {HOURS.map(h=>(
            <div key={h} style={{ height:PX_PER_HOUR, position:'relative' }}>
              <span className="tnum" style={{ position:'absolute', top:-7, right:8, font:'400 11px/1 var(--font-mono)', color:'var(--ink-4)' }}>{h}:00</span>
            </div>
          ))}
        </div>
        {/* day columns */}
        {DAYS.map((d,di)=>(
          <div key={d} style={{ position:'relative', borderLeft:'1px solid var(--line)',
            background: di===TODAY_IDX?'color-mix(in srgb, var(--wine) 3%, transparent)':'transparent' }}>
            {HOURS.map(h=><div key={h} style={{ height:PX_PER_HOUR, borderBottom:'1px solid var(--line-soft)' }}/>)}
            {/* now line on today */}
            {di===TODAY_IDX && (
              <div style={{ position:'absolute', left:0, right:0, top:(10.02-9)*PX_PER_HOUR, height:2, background:'var(--wine)', zIndex:3 }}>
                <span style={{ position:'absolute', left:-4, top:-3, width:8, height:8, borderRadius:'50%', background:'var(--wine)' }}/>
              </div>
            )}
            {BLOCKS.filter(b=>b.d===di).map((b,i)=>(
              <div key={i} style={{ position:'absolute', left:3, right:3, top:(b.s-9)*PX_PER_HOUR, height:b.m/60*PX_PER_HOUR,
                borderRadius:'var(--r-sm)', background:'repeating-linear-gradient(45deg, var(--surface-tint) 0 6px, var(--paper-2) 6px 12px)',
                border:'1px dashed var(--line-strong)', display:'flex', alignItems:'center', justifyContent:'center',
                font:'500 11px/1 var(--font-sans)', color:'var(--ink-3)' }}>{b.label}</div>
            ))}
            {WEEK.filter(a=>a.d===di).map((a,i)=>{
              const hue = HILO.hueVar(svcHue(a.svc));
              return (
                <div key={i} title={`${a.client} · ${svcName(a.svc)}`} style={{
                  position:'absolute', left:3, right:3, top:(a.s-9)*PX_PER_HOUR+1, height:a.m/60*PX_PER_HOUR-2,
                  borderRadius:'var(--r-sm)', padding:'5px 7px', overflow:'hidden', cursor:'pointer', zIndex:2,
                  background:`color-mix(in srgb, ${hue} 13%, var(--surface))`,
                  borderLeft:`2.5px solid ${hue}`, boxShadow:'var(--shadow-sm)',
                  transition:'transform var(--dur-1)',
                }}
                onMouseEnter={e=>e.currentTarget.style.transform='scale(1.015)'}
                onMouseLeave={e=>e.currentTarget.style.transform='scale(1)'}>
                  <div style={{ font:'500 11.5px/1.15 var(--font-sans)', color:'var(--ink-1)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{a.client}</div>
                  {a.m>=40 && <div style={{ font:'400 10.5px/1.3 var(--font-sans)', color:hue, marginTop:2 }}>{svcName(a.svc)}</div>}
                  {a.m>=55 && <div style={{ font:'400 10px/1 var(--font-mono)', color:'var(--ink-3)', marginTop:3 }}>{a.pro}</div>}
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function DayView(){
  return (
    <div className="card" style={{ padding:'8px 20px 6px', maxWidth:760 }}>
      <div style={{ padding:'12px 0 6px' }}>
        <h3 style={{ margin:0, font:'400 20px/1 var(--font-serif)', color:'var(--ink-1)' }}>Jueves 28 · <span className="serif-i">hoy</span></h3>
      </div>
      {HILO.today.map((a,i)=>{
        const hue = HILO.hueVar(svcHue(HILO.services.find(s=>s.name===a.svc)?.id));
        return (
          <div key={a.id} style={{ display:'grid', gridTemplateColumns:'62px 24px 1fr', alignItems:'start' }}>
            <div style={{ textAlign:'right', paddingRight:14, paddingTop:12 }}>
              <div className="tnum" style={{ font:'500 13px/1 var(--font-sans)', color:'var(--ink-1)' }}>{a.time}</div>
              <div className="tnum" style={{ font:'400 11px/1.4 var(--font-mono)', color:'var(--ink-4)' }}>{a.end}</div>
            </div>
            <div style={{ position:'relative', display:'flex', justifyContent:'center' }}>
              {i<HILO.today.length-1 && <span style={{ position:'absolute', top:14, bottom:-2, width:2, background:'var(--wine-200)' }}/>}
              <span style={{ marginTop:13, width:11, height:11, borderRadius:'50%', background:hue, zIndex:1 }}/>
            </div>
            <div style={{ padding:'8px 0 12px' }}>
              <div style={{ background:'var(--surface)', border:'1px solid var(--line)', borderRadius:'var(--r-md)',
                borderLeft:`3px solid ${hue}`, padding:'10px 13px', display:'flex', alignItems:'center', gap:10 }}>
                <div style={{ flex:1 }}>
                  <div style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{a.client}</div>
                  <div style={{ font:'400 12px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:3 }}>{a.svc} · {a.pro}</div>
                </div>
                {a.via==='wa' && <Icon name="whatsapp" size={15} style={{ color:'var(--wa-ink)' }}/>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function MonthView(){
  const start = -3; // offset so day 1 lands correctly-ish
  const cells = Array.from({length:35},(_,i)=> i+start);
  const withAppt = {4:2,8:3,11:1,12:4,15:2,18:5,19:3,20:1,22:2,25:4,26:1,27:3,28:6,29:2};
  return (
    <div className="card" style={{ overflow:'hidden' }}>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(7,1fr)' }}>
        {['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'].map(d=>(
          <div key={d} style={{ padding:'10px', textAlign:'center', font:'500 11px/1 var(--font-sans)',
            textTransform:'uppercase', letterSpacing:'0.07em', color:'var(--ink-3)', borderBottom:'1px solid var(--line)' }}>{d}</div>
        ))}
        {cells.map((n,i)=>{
          const valid = n>=1 && n<=31;
          const isToday = n===28;
          const cnt = withAppt[n];
          return (
            <div key={i} style={{ minHeight:92, padding:'8px', borderLeft: i%7?'1px solid var(--line-soft)':'none',
              borderBottom:'1px solid var(--line-soft)', background: isToday?'var(--wine-50)':'transparent' }}>
              {valid && (
                <React.Fragment>
                  <div className="tnum" style={{ font:`${isToday?500:400} 13px/1 var(--font-sans)`,
                    color: isToday?'var(--wine)':'var(--ink-2)', marginBottom:6,
                    display:'inline-grid', placeItems:'center', width:24, height:24, borderRadius:'50%',
                    background: isToday?'var(--wine)':'transparent', ...(isToday?{color:'var(--wine-fg)'}:{}) }}>{n}</div>
                  {cnt && (
                    <div style={{ display:'flex', flexWrap:'wrap', gap:3 }}>
                      {Array.from({length:Math.min(cnt,5)}).map((_,k)=>(
                        <span key={k} style={{ width:6, height:6, borderRadius:'50%', background:'var(--wine-300)' }}/>
                      ))}
                      {cnt>5 && <span style={{ font:'400 10px/1 var(--font-mono)', color:'var(--ink-3)' }}>+{cnt-5}</span>}
                    </div>
                  )}
                </React.Fragment>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Agenda({ isMobile }){
  const [view, setView] = useStateAg(isMobile?'day':'week');
  return (
    <div style={{ maxWidth:1180, margin:'0 auto', padding: isMobile?'16px 14px 28px':'24px 30px 40px',
      animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      <div style={{ display:'flex', alignItems:'center', gap:12, flexWrap:'wrap', marginBottom:18 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6 }}>
          <Button variant="secondary" size="sm" icon="chevL" style={{ padding:'8px' }}/>
          <h2 style={{ margin:0, font:'400 22px/1 var(--font-serif)', color:'var(--ink-1)', minWidth:160 }}>25 – 30 mayo</h2>
          <Button variant="secondary" size="sm" icon="chev" style={{ padding:'8px' }}/>
          <Button variant="ghost" size="sm">Hoy</Button>
        </div>
        <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:10 }}>
          <Segmented options={[{value:'day',label:'Día'},{value:'week',label:'Semana'},{value:'month',label:'Mes'}]} value={view} onChange={setView}/>
          {!isMobile && <Button variant="secondary" size="sm" icon="block">Bloquear</Button>}
          <Button variant="primary" size="sm" icon="plus">{isMobile?'':'Nueva cita'}</Button>
        </div>
      </div>

      {/* team filter */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:16, flexWrap:'wrap' }}>
        <span className="eyebrow">Barberos</span>
        {HILO.team.map(b=>(
          <span key={b.id} style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'4px 11px 4px 5px',
            borderRadius:'var(--r-full)', background:'var(--surface)', border:'1px solid var(--line)', cursor:'pointer' }}>
            <Avatar name={b.name} initials={b.initials} hue={b.hue} size={22}/>
            <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-1)' }}>{b.name.split(' ')[0]}</span>
          </span>
        ))}
      </div>

      {view==='day' && <DayView/>}
      {view==='week' && <WeekView/>}
      {view==='month' && <MonthView/>}
    </div>
  );
}

window.Agenda = Agenda;
