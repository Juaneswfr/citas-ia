// hilo/onboarding.jsx — guided setup (full-screen, no chrome)
const { useState: useStateO } = React;

const STEPS = [
  { id:0, icon:'scissors', title:'Tu negocio',       sub:'Lo básico para empezar' },
  { id:1, icon:'whatsapp', title:'Conecta WhatsApp',  sub:'Coexistencia · conserva tu número' },
  { id:2, icon:'layers',   title:'Google Calendar',   sub:'Tu disponibilidad real' },
  { id:3, icon:'clock',    title:'Servicios y horarios', sub:'Qué ofreces y cuándo' },
  { id:4, icon:'sparkle',  title:'Prueba el agente',  sub:'Agenda tu primera cita de prueba' },
];

const oInput = {
  width:'100%', padding:'11px 13px', borderRadius:'var(--r-md)', border:'1px solid var(--line-strong)',
  background:'var(--surface-2)', font:'400 15px/1.3 var(--font-sans)', color:'var(--ink-1)', outline:'none',
};

function StepBusiness(){
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:18 }}>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <label style={{ display:'flex', flexDirection:'column', gap:7 }}>
          <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-2)' }}>Nombre del negocio</span>
          <input style={oInput} defaultValue="Navaja & Tinta"/>
        </label>
        <label style={{ display:'flex', flexDirection:'column', gap:7 }}>
          <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-2)' }}>Tipo</span>
          <input style={oInput} defaultValue="Barbería"/>
        </label>
      </div>
      <label style={{ display:'flex', flexDirection:'column', gap:7 }}>
        <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-2)' }}>Ciudad / zona</span>
        <input style={oInput} defaultValue="Medellín · El Poblado"/>
      </label>
      <label style={{ display:'flex', flexDirection:'column', gap:7 }}>
        <span style={{ font:'500 12.5px/1 var(--font-sans)', color:'var(--ink-2)' }}>Tono del agente</span>
        <div style={{ display:'flex', gap:8 }}>
          {['Cercano','Neutral','Formal'].map((t,i)=>(
            <span key={t} style={{ flex:1, textAlign:'center', padding:'9px', borderRadius:'var(--r-md)', cursor:'pointer',
              border:`1px solid ${i===0?'var(--wine)':'var(--line-strong)'}`, background:i===0?'var(--wine-50)':'var(--surface-2)',
              color:i===0?'var(--wine)':'var(--ink-2)', font:'500 13.5px/1 var(--font-sans)' }}>{t}</span>
          ))}
        </div>
      </label>
    </div>
  );
}

function ConnectCard({ icon, color, bg, title, sub, connected, onConnect, foot }){
  return (
    <div style={{ border:`1px solid ${connected?'color-mix(in srgb, var(--success) 35%, transparent)':'var(--line-strong)'}`,
      borderRadius:'var(--r-lg)', padding:'20px', background: connected?'color-mix(in srgb, var(--success) 5%, var(--surface))':'var(--surface)' }}>
      <div style={{ display:'flex', alignItems:'center', gap:14 }}>
        <span style={{ width:48, height:48, borderRadius:'var(--r-md)', background:bg, color, display:'grid', placeItems:'center' }}><Icon name={icon} size={26}/></span>
        <div style={{ flex:1 }}>
          <div style={{ font:'500 16px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{title}</div>
          <div style={{ font:'400 13px/1.3 var(--font-sans)', color:'var(--ink-3)', marginTop:3 }}>{sub}</div>
        </div>
        {connected
          ? <Tag hue="sage"><Icon name="check" size={13}/>Conectado</Tag>
          : <Button variant="primary" onClick={onConnect}>Conectar</Button>}
      </div>
      {foot && <div style={{ marginTop:14, paddingTop:14, borderTop:'1px solid var(--line)', font:'400 12.5px/1.5 var(--font-sans)', color:'var(--ink-2)' }}>{foot}</div>}
    </div>
  );
}

function StepWhatsApp(){
  const [c,setC]=useStateO(false);
  return <ConnectCard icon="whatsapp" color="var(--wa-ink)" bg="var(--wa-bg)"
    title="WhatsApp Business · Coexistencia" sub={c?HILO.channel.number:'Vincula tu número actual'}
    connected={c} onConnect={()=>setC(true)}
    foot={<span><strong style={{fontWeight:500,color:'var(--ink-1)'}}>Coexistencia</strong> deja que sigas usando WhatsApp en tu celular mientras el agente responde en paralelo. No pierdes tu historial ni tu número.</span>}/>;
}
function StepCalendar(){
  const [c,setC]=useStateO(false);
  return <ConnectCard icon="layers" color="var(--steel)" bg="color-mix(in srgb, var(--steel) 14%, var(--surface))"
    title="Google Calendar" sub={c?'camilo@navajaytinta.co':'Fuente principal de disponibilidad'}
    connected={c} onConnect={()=>setC(true)}
    foot={<span>El agente lee tu calendario para no agendar sobre citas existentes y escribe las nuevas reservas ahí mismo.</span>}/>;
}

function StepServices(){
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
      <div style={{ font:'400 13.5px/1.5 var(--font-sans)', color:'var(--ink-2)', marginBottom:4 }}>Cargamos servicios típicos de barbería. Edítalos o agrega los tuyos.</div>
      {HILO.services.slice(0,4).map(s=>(
        <div key={s.id} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px', background:'var(--surface)',
          border:'1px solid var(--line)', borderRadius:'var(--r-md)' }}>
          <span style={{ width:8, height:8, borderRadius:2, background:HILO.hueVar(s.hue) }}/>
          <span style={{ flex:1, font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{s.name}</span>
          <span style={{ font:'400 12.5px/1 var(--font-sans)', color:'var(--ink-3)' }}>{s.dur} min</span>
          <span className="tnum" style={{ font:'500 13.5px/1 var(--font-sans)', color:HILO.hueVar(s.hue), minWidth:70, textAlign:'right' }}>{HILO.fmtCOP(s.price)}</span>
        </div>
      ))}
      <Button variant="secondary" icon="plus" style={{ alignSelf:'flex-start', marginTop:4 }}>Agregar servicio</Button>
    </div>
  );
}

function StepTest(){
  return (
    <div style={{ background:'var(--surface-tint)', border:'1px solid var(--line)', borderRadius:'var(--r-lg)', padding:'18px', display:'flex', flexDirection:'column', gap:10 }}>
      <div style={{ alignSelf:'flex-start', maxWidth:'85%', padding:'9px 13px', borderRadius:'13px 13px 13px 4px', background:'var(--surface-2)', border:'1px solid var(--line)', font:'400 13.5px/1.4 var(--font-sans)' }}>Hola! Quiero un corte para mañana 🙌</div>
      <div style={{ alignSelf:'flex-end', maxWidth:'85%', padding:'9px 13px', borderRadius:'13px 13px 4px 13px', background:'var(--wine)', color:'var(--wine-fg)', font:'400 13.5px/1.4 var(--font-sans)' }}>¡Claro! Para mañana tengo con Andrés a las 10:00, 11:30 o 4:00 pm. ¿Cuál prefieres?</div>
      <div style={{ alignSelf:'flex-end', maxWidth:'85%', padding:'9px 13px', borderRadius:'13px 13px 4px 13px', background:'var(--wine)', color:'var(--wine-fg)', font:'400 13.5px/1.4 var(--font-sans)', display:'flex', gap:6 }}>
        <Icon name="checkCircle" size={16}/> Cita creada en Google Calendar.
      </div>
    </div>
  );
}

function Onboarding({ isMobile, onNav }){
  const [step, setStep] = useStateO(1);
  const body = [<StepBusiness/>, <StepWhatsApp/>, <StepCalendar/>, <StepServices/>, <StepTest/>][step];
  const last = step===STEPS.length-1;
  return (
    <div style={{ minHeight:'100%', display:'flex', flexDirection: isMobile?'column':'row', background:'var(--paper)' }}>
      {/* left rail — the thread of steps */}
      <div style={{ width:isMobile?'auto':320, flexShrink:0, background:'var(--paper-2)', borderRight: isMobile?'none':'1px solid var(--line)',
        borderBottom: isMobile?'1px solid var(--line)':'none', padding: isMobile?'18px 18px 8px':'30px 28px' }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom: isMobile?16:34 }}>
          <HiloMark size={32}/>
          <div><div style={{ font:'700 18px/1 var(--font-sans)', letterSpacing:'-0.02em' }}>Hilo</div>
            <div style={{ font:'400 11px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>Configuración inicial</div></div>
        </div>
        {!isMobile && (
          <div>
            {STEPS.map((s,i)=>{
              const done = i<step, on = i===step;
              return (
                <button key={s.id} onClick={()=>setStep(i)} style={{ display:'grid', gridTemplateColumns:'34px 1fr', gap:12, width:'100%',
                  textAlign:'left', border:0, background:'transparent', cursor:'pointer', padding:0 }}>
                  <div style={{ position:'relative', display:'flex', justifyContent:'center' }}>
                    {i<STEPS.length-1 && <span style={{ position:'absolute', top:30, bottom:-4, width:2,
                      background: done?'var(--wine)':'var(--line-strong)' }}/>}
                    <span style={{ width:30, height:30, borderRadius:'50%', display:'grid', placeItems:'center', zIndex:1,
                      background: done?'var(--wine)':on?'var(--surface)':'var(--paper-2)',
                      border:`2px solid ${done||on?'var(--wine)':'var(--line-strong)'}`,
                      color: done?'var(--wine-fg)':on?'var(--wine)':'var(--ink-3)' }}>
                      {done?<Icon name="check" size={15} strokeWidth={2.4}/>:<Icon name={s.icon} size={15}/>}
                    </span>
                  </div>
                  <div style={{ paddingBottom:22 }}>
                    <div style={{ font:`${on?500:400} 14px/1.2 var(--font-sans)`, color: on||done?'var(--ink-1)':'var(--ink-3)' }}>{s.title}</div>
                    <div style={{ font:'400 11.5px/1.3 var(--font-sans)', color:'var(--ink-3)', marginTop:3 }}>{s.sub}</div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
        {isMobile && (
          <div style={{ display:'flex', gap:5 }}>
            {STEPS.map((s,i)=><span key={s.id} style={{ flex:1, height:4, borderRadius:99, background: i<=step?'var(--wine)':'var(--line-strong)' }}/>)}
          </div>
        )}
      </div>

      {/* right content */}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0 }}>
        <div style={{ flex:1, overflowY:'auto', padding: isMobile?'24px 20px':'56px 64px', display:'flex', justifyContent:'center' }}>
          <div style={{ width:'100%', maxWidth:520, animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
            <div className="eyebrow" style={{ marginBottom:10 }}>Paso {step+1} de {STEPS.length}</div>
            <h1 style={{ margin:'0 0 8px', font:'400 clamp(26px,3.5vw,33px)/1.1 var(--font-serif)', color:'var(--ink-1)' }}>{STEPS[step].title}</h1>
            <p style={{ margin:'0 0 28px', font:'400 15px/1.5 var(--font-sans)', color:'var(--ink-2)' }}>{STEPS[step].sub}.</p>
            {body}
          </div>
        </div>
        <div style={{ borderTop:'1px solid var(--line)', padding:'16px 24px', display:'flex', alignItems:'center', gap:12,
          background:'var(--surface)' }}>
          <Button variant="ghost" onClick={()=>onNav('inicio')}>Saltar por ahora</Button>
          <div style={{ marginLeft:'auto', display:'flex', gap:10 }}>
            {step>0 && <Button variant="secondary" icon="chevL" onClick={()=>setStep(step-1)}>Atrás</Button>}
            <Button variant="primary" iconRight={last?'check':'chev'} onClick={()=>last?onNav('inicio'):setStep(step+1)}>
              {last?'Publicar y empezar':'Continuar'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

window.Onboarding = Onboarding;
