// hilo/clientes.jsx — Clientes: master list + detail (historial, notas, mensajes)
const { useState: useStateC } = React;

const STATUS_HUE = { VIP:'mustard', frecuente:'wine', activo:'sage', nuevo:'steel' };

function ClientRow({ c, active, onClick }){
  return (
    <button onClick={onClick} style={{
      display:'flex', alignItems:'center', gap:12, padding:'11px 14px', width:'100%', textAlign:'left',
      border:0, borderRadius:'var(--r-md)', cursor:'pointer',
      background: active?'var(--surface)':'transparent',
      boxShadow: active?'var(--shadow-sm)':'none',
      transition:'all var(--dur-2) var(--ease-std)',
    }}
    onMouseEnter={e=>{ if(!active) e.currentTarget.style.background='var(--wine-50)'; }}
    onMouseLeave={e=>{ if(!active) e.currentTarget.style.background='transparent'; }}>
      <Avatar name={c.name} hue={STATUS_HUE[c.status]} size={38}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <span style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)', whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{c.name}</span>
          {c.status==='VIP' && <Icon name="star" size={12} style={{ color:'var(--mustard)' }} fill/>}
        </div>
        <div style={{ font:'400 12px/1.2 var(--font-sans)', color:'var(--ink-3)', marginTop:2 }}>{c.next!=='—'?`Próx: ${c.next}`:`Última: ${c.last}`}</div>
      </div>
      <span className="tnum" style={{ font:'400 11px/1 var(--font-mono)', color:'var(--ink-4)' }}>{c.visits}</span>
    </button>
  );
}

function Stat({ k, v, hue }){
  return (
    <div style={{ flex:1, padding:'12px 14px', background:'var(--surface)', border:'1px solid var(--line)', borderRadius:'var(--r-md)' }}>
      <div className="tnum" style={{ font:'500 20px/1 var(--font-sans)', color: hue||'var(--ink-1)' }}>{v}</div>
      <div style={{ font:'400 11.5px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:5 }}>{k}</div>
    </div>
  );
}

function ClientDetail({ c, isMobile, onBack }){
  const [note, setNote] = useStateC(c.note);
  const history = [
    { d:'Hoy · 09:00', s:c.fav, pro:'Andrés', via:'wa' },
    { d:'12 may · 10:30', s:'Corte clásico', pro:'Julián', via:'wa' },
    { d:'28 abr · 16:00', s:c.fav, pro:'Andrés', via:'manual' },
    { d:'14 abr · 11:15', s:'Arreglo de barba', pro:'Samuel', via:'wa' },
  ];
  const msgs = [
    { from:'client', t:'Hoy 09:58', text:'Listo, gracias!' },
    { from:'agent',  t:'Hoy 09:58', text:'¡De nada! Te esperamos. 💈' },
  ];
  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflowY:'auto' }}>
      {/* header */}
      <div style={{ padding:'20px 22px', borderBottom:'1px solid var(--line)', display:'flex', alignItems:'center', gap:14 }}>
        {isMobile && <Button variant="ghost" size="sm" icon="chevL" onClick={onBack} style={{ padding:'7px' }}/>}
        <Avatar name={c.name} hue={STATUS_HUE[c.status]} size={52}/>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:9 }}>
            <h2 style={{ margin:0, font:'500 21px/1.1 var(--font-sans)', color:'var(--ink-1)' }}>{c.name}</h2>
            <Tag hue={STATUS_HUE[c.status]} style={{ fontSize:11 }}>{c.status}</Tag>
          </div>
          <div className="tnum" style={{ font:'400 13px/1 var(--font-sans)', color:'var(--ink-3)', marginTop:5 }}>{c.phone}</div>
        </div>
        <Button variant="secondary" size="sm" icon="whatsapp" style={{ color:'var(--wa-ink)' }}>{!isMobile&&'Escribir'}</Button>
      </div>

      <div style={{ padding:'20px 22px', display:'flex', flexDirection:'column', gap:20 }}>
        {/* stats */}
        <div style={{ display:'flex', gap:10 }}>
          <Stat k="Visitas" v={c.visits}/>
          <Stat k="Gasto total" v={HILO.fmtCOP(c.spend)} hue="var(--clay)"/>
          <Stat k="Próxima" v={c.next==='—'?'—':c.next.replace('Hoy · ','')} hue="var(--wine)"/>
        </div>

        {/* notes */}
        <div>
          <div className="eyebrow" style={{ marginBottom:8 }}>Nota interna</div>
          <textarea value={note} onChange={e=>setNote(e.target.value)} placeholder="Preferencias, alergias, recordatorios…"
            style={{ width:'100%', minHeight:60, padding:'11px 13px', borderRadius:'var(--r-md)', resize:'vertical',
              border:'1px solid var(--line)', background:'var(--surface-tint)', color:'var(--ink-1)',
              font:'400 13.5px/1.5 var(--font-sans)', outline:'none' }}/>
        </div>

        {/* frequent service */}
        <div>
          <div className="eyebrow" style={{ marginBottom:8 }}>Servicio frecuente</div>
          <Tag hue={HILO.services.find(s=>s.name===c.fav)?.hue||'wine'} style={{ fontSize:13, padding:'5px 12px' }}>{c.fav}</Tag>
        </div>

        {/* history */}
        <div>
          <div className="eyebrow" style={{ marginBottom:10 }}>Historial de citas</div>
          <div style={{ display:'flex', flexDirection:'column' }}>
            {history.map((h,i)=>{
              const hue = HILO.hueVar(HILO.services.find(s=>s.name===h.s)?.hue||'wine');
              return (
                <div key={i} style={{ display:'grid', gridTemplateColumns:'18px 1fr', gap:12 }}>
                  <div style={{ position:'relative', display:'flex', justifyContent:'center' }}>
                    {i<history.length-1 && <span style={{ position:'absolute', top:12, bottom:-8, width:2, background:'var(--line)' }}/>}
                    <span style={{ marginTop:6, width:9, height:9, borderRadius:'50%', background:hue, zIndex:1 }}/>
                  </div>
                  <div style={{ paddingBottom:14 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <span style={{ font:'500 13.5px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{h.s}</span>
                      {h.via==='wa' && <Icon name="whatsapp" size={13} style={{ color:'var(--wa-ink)' }}/>}
                    </div>
                    <div className="tnum" style={{ font:'400 12px/1.3 var(--font-sans)', color:'var(--ink-3)', marginTop:2 }}>{h.d} · {h.pro}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* last messages */}
        <div>
          <div className="eyebrow" style={{ marginBottom:10 }}>Últimos mensajes</div>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {msgs.map((m,i)=>(
              <div key={i} style={{ alignSelf: m.from==='agent'?'flex-end':'flex-start', maxWidth:'80%',
                padding:'8px 12px', borderRadius: m.from==='agent'?'13px 13px 4px 13px':'13px 13px 13px 4px',
                background: m.from==='agent'?'var(--wine)':'var(--surface-2)',
                color: m.from==='agent'?'var(--wine-fg)':'var(--ink-1)',
                border: m.from==='agent'?'0':'1px solid var(--line)',
                font:'400 13px/1.4 var(--font-sans)' }}>{m.text}</div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Clientes({ isMobile }){
  const [sel, setSel] = useStateC(HILO.clients[0]);
  const [q, setQ] = useStateC('');
  const list = HILO.clients.filter(c=>c.name.toLowerCase().includes(q.toLowerCase()));
  const showDetail = !isMobile || sel?.__open;

  const ListPane = (
    <div style={{ width:isMobile?'100%':338, flexShrink:0, borderRight: isMobile?'none':'1px solid var(--line)',
      display:'flex', flexDirection:'column', height:'100%', background:'var(--paper)' }}>
      <div style={{ padding:'18px 16px 12px' }}>
        <h2 style={{ margin:'0 0 14px', font:'400 24px/1 var(--font-serif)', color:'var(--ink-1)' }}>Clientes</h2>
        <div style={{ display:'flex', alignItems:'center', gap:9, padding:'9px 12px', background:'var(--surface-2)',
          border:'1px solid var(--line-strong)', borderRadius:'var(--r-md)' }}>
          <Icon name="search" size={15} style={{ color:'var(--ink-3)' }}/>
          <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Buscar por nombre…"
            style={{ flex:1, border:0, background:'transparent', outline:'none', font:'400 13.5px/1 var(--font-sans)', color:'var(--ink-1)' }}/>
        </div>
      </div>
      <div style={{ flex:1, overflowY:'auto', padding:'0 10px 16px', display:'flex', flexDirection:'column', gap:2 }}>
        {list.map(c=><ClientRow key={c.id} c={c} active={!isMobile && sel?.id===c.id}
          onClick={()=>setSel(isMobile?{...c,__open:true}:c)}/>)}
        {!list.length && <div style={{ padding:'40px 16px', textAlign:'center', color:'var(--ink-3)', font:'400 13px/1.4 var(--font-sans)' }}>Sin resultados para “{q}”.</div>}
      </div>
    </div>
  );

  return (
    <div style={{ height:'100%', display:'flex', animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      {(!isMobile || !showDetail) && ListPane}
      {(!isMobile || showDetail) && (
        <div style={{ flex:1, minWidth:0, height:'100%' }}>
          {sel ? <ClientDetail c={sel} isMobile={isMobile} onBack={()=>setSel({...sel,__open:false})}/>
               : <div style={{ display:'grid', placeItems:'center', height:'100%', color:'var(--ink-3)' }}>Selecciona un cliente</div>}
        </div>
      )}
    </div>
  );
}

window.Clientes = Clientes;
