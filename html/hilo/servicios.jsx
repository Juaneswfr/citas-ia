// hilo/servicios.jsx — Servicios: fichas editables + hoja de edición
const { useState: useStateS } = React;

function Toggle({ on, onChange }){
  return (
    <button onClick={()=>onChange(!on)} style={{
      width:42, height:25, borderRadius:99, border:0, cursor:'pointer', padding:2, flexShrink:0,
      background: on?'var(--success)':'var(--line-strong)', transition:'background var(--dur-2) var(--ease-std)',
      display:'flex', justifyContent: on?'flex-end':'flex-start', alignItems:'center',
    }}>
      <span style={{ width:21, height:21, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px rgba(0,0,0,0.2)',
        transition:'all var(--dur-2) var(--ease-emph)' }}/>
    </button>
  );
}

function Field({ label, children, hint }){
  return (
    <label style={{ display:'flex', flexDirection:'column', gap:6 }}>
      <span style={{ font:'500 12px/1 var(--font-sans)', color:'var(--ink-2)' }}>{label}</span>
      {children}
      {hint && <span style={{ font:'400 11px/1.3 var(--font-sans)', color:'var(--ink-3)' }}>{hint}</span>}
    </label>
  );
}
const inputStyle = {
  width:'100%', padding:'9px 11px', borderRadius:'var(--r-sm)', border:'1px solid var(--line-strong)',
  background:'var(--surface-2)', font:'400 14px/1.3 var(--font-sans)', color:'var(--ink-1)', outline:'none',
};

function EditSheet({ svc, onClose }){
  const [home, setHome] = useStateS(svc.home);
  const [active, setActive] = useStateS(svc.active);
  return (
    <div onClick={onClose} style={{ position:'fixed', inset:0, zIndex:60, background:'rgba(40,20,28,0.32)',
      backdropFilter:'blur(3px)', display:'flex', justifyContent:'flex-end', animation:'hilo-fade-up var(--dur-2) var(--ease-out)' }}>
      <div onClick={e=>e.stopPropagation()} style={{ width:'min(460px, 100%)', height:'100%', background:'var(--paper)',
        borderLeft:'1px solid var(--line)', boxShadow:'var(--shadow-pop)', display:'flex', flexDirection:'column',
        animation:'hilo-fade-up var(--dur-3) var(--ease-emph)' }}>
        <div style={{ padding:'18px 22px', display:'flex', alignItems:'center', gap:12, borderBottom:'1px solid var(--line)' }}>
          <span style={{ width:10, height:10, borderRadius:3, background:HILO.hueVar(svc.hue) }}/>
          <h3 style={{ margin:0, flex:1, font:'500 18px/1.1 var(--font-sans)', color:'var(--ink-1)' }}>Editar servicio</h3>
          <Button variant="ghost" size="sm" icon="x" onClick={onClose} style={{ padding:'7px' }}/>
        </div>
        <div style={{ flex:1, overflowY:'auto', padding:'20px 22px', display:'flex', flexDirection:'column', gap:16 }}>
          <Field label="Nombre"><input style={inputStyle} defaultValue={svc.name}/></Field>
          <Field label="Descripción"><textarea style={{ ...inputStyle, minHeight:64, resize:'vertical' }} defaultValue={`Servicio de ${svc.name.toLowerCase()} con productos premium.`}/></Field>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
            <Field label="Duración" hint="minutos"><input style={inputStyle} defaultValue={svc.dur} type="number"/></Field>
            <Field label="Buffer" hint="entre citas"><input style={inputStyle} defaultValue={svc.buffer} type="number"/></Field>
          </div>
          <Field label="Precio" hint="COP"><input style={inputStyle} defaultValue={svc.price} type="number"/></Field>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 0', borderTop:'1px solid var(--line)' }}>
            <div><div style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>Disponible a domicilio</div>
              <div style={{ font:'400 12px/1.2 var(--font-sans)', color:'var(--ink-3)' }}>El cliente puede pedirlo en casa</div></div>
            <Toggle on={home} onChange={setHome}/>
          </div>
          {home && <Field label="Cargo extra por domicilio" hint="COP"><input style={inputStyle} defaultValue={svc.extra}/></Field>}
          <Field label="Barberos habilitados">
            <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
              {HILO.team.map(b=>{
                const en = svc.pros.includes(b.name.split(' ')[0]);
                return <span key={b.id} style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'5px 11px 5px 5px',
                  borderRadius:'var(--r-full)', cursor:'pointer',
                  background: en?'var(--wine-50)':'var(--surface)', border:`1px solid ${en?'var(--wine-200)':'var(--line)'}`,
                  color: en?'var(--wine)':'var(--ink-3)' }}>
                  <Avatar name={b.name} initials={b.initials} hue={b.hue} size={20}/>
                  <span style={{ font:'500 12.5px/1 var(--font-sans)' }}>{b.name.split(' ')[0]}</span>
                  {en && <Icon name="check" size={13}/>}
                </span>;
              })}
            </div>
          </Field>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'12px 0', borderTop:'1px solid var(--line)' }}>
            <div style={{ font:'500 14px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>Servicio activo</div>
            <Toggle on={active} onChange={setActive}/>
          </div>
        </div>
        <div style={{ padding:'16px 22px', borderTop:'1px solid var(--line)', display:'flex', gap:10, background:'var(--surface)' }}>
          <Button variant="ghost" onClick={onClose} style={{ flex:1 }}>Cancelar</Button>
          <Button variant="primary" onClick={onClose} icon="check" style={{ flex:1 }}>Guardar cambios</Button>
        </div>
      </div>
    </div>
  );
}

function ServiceCard({ svc, onEdit }){
  const [active, setActive] = useStateS(svc.active);
  const hue = HILO.hueVar(svc.hue);
  return (
    <div className="card" style={{ padding:0, overflow:'hidden', display:'flex', flexDirection:'column',
      opacity: active?1:0.66, transition:'opacity var(--dur-2)' }}>
      <div style={{ height:4, background:hue }}/>
      <div style={{ padding:'15px 17px', display:'flex', flexDirection:'column', gap:12, flex:1 }}>
        <div style={{ display:'flex', alignItems:'flex-start', gap:10 }}>
          <div style={{ flex:1 }}>
            <h3 style={{ margin:0, font:'500 16.5px/1.2 var(--font-sans)', color:'var(--ink-1)' }}>{svc.name}</h3>
            <div className="tnum" style={{ font:'500 19px/1 var(--font-sans)', color:hue, marginTop:7 }}>{HILO.fmtCOP(svc.price)}</div>
          </div>
          <Toggle on={active} onChange={setActive}/>
        </div>
        <div style={{ display:'flex', gap:14, font:'400 12.5px/1 var(--font-sans)', color:'var(--ink-2)' }}>
          <span style={{ display:'inline-flex', alignItems:'center', gap:5 }}><Icon name="clock" size={14} style={{color:'var(--ink-3)'}}/>{svc.dur} min</span>
          <span style={{ display:'inline-flex', alignItems:'center', gap:5 }}><Icon name="sync" size={14} style={{color:'var(--ink-3)'}}/>+{svc.buffer} buffer</span>
        </div>
        {svc.home && <Tag hue="sage" style={{ fontSize:11.5, alignSelf:'flex-start' }}><Icon name="pin" size={12}/>Domicilio · +{HILO.fmtCOP(svc.extra)}</Tag>}
        <div style={{ marginTop:'auto', display:'flex', alignItems:'center', justifyContent:'space-between', paddingTop:12, borderTop:'1px solid var(--line)' }}>
          <div style={{ display:'flex', alignItems:'center' }}>
            {svc.pros.map((p,i)=>{
              const b = HILO.team.find(t=>t.name.split(' ')[0]===p);
              return <span key={p} style={{ marginLeft: i?-8:0, borderRadius:'50%', border:'2px solid var(--surface)' }}>
                <Avatar name={p} initials={b?b.initials:p.slice(0,2)} hue={b?b.hue:'wine'} size={24}/></span>;
            })}
            <span style={{ font:'400 11.5px/1 var(--font-sans)', color:'var(--ink-3)', marginLeft:8 }}>{svc.book} este mes</span>
          </div>
          <Button variant="ghost" size="sm" icon="edit" onClick={()=>onEdit(svc)} style={{ padding:'6px 8px' }}/>
        </div>
      </div>
    </div>
  );
}

function Servicios({ isMobile }){
  const [edit, setEdit] = useStateS(null);
  const active = HILO.services.filter(s=>s.active).length;
  return (
    <div style={{ maxWidth:1180, margin:'0 auto', padding: isMobile?'16px 14px 28px':'24px 30px 40px',
      animation:'hilo-fade-up var(--dur-3) var(--ease-out)' }}>
      <div style={{ display:'flex', alignItems:'flex-end', gap:12, marginBottom:20 }}>
        <div style={{ flex:1 }}>
          <h2 style={{ margin:0, font:'400 26px/1.05 var(--font-serif)', color:'var(--ink-1)' }}>Tu <span className="serif-i">carta</span> de servicios</h2>
          <p style={{ margin:'7px 0 0', font:'400 14px/1.4 var(--font-sans)', color:'var(--ink-2)' }}>
            {active} activos · el agente solo ofrece lo que esté encendido aquí.
          </p>
        </div>
        <Button variant="primary" icon="plus">Nuevo servicio</Button>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:`repeat(auto-fill, minmax(${isMobile?'100%':'250px'}, 1fr))`, gap:16 }}>
        {HILO.services.map(s=><ServiceCard key={s.id} svc={s} onEdit={setEdit}/>)}
        <button style={{ minHeight:180, borderRadius:'var(--r-lg)', border:'1.5px dashed var(--line-strong)',
          background:'transparent', cursor:'pointer', display:'flex', flexDirection:'column', alignItems:'center',
          justifyContent:'center', gap:10, color:'var(--ink-3)', transition:'all var(--dur-2)' }}
          onMouseEnter={e=>{e.currentTarget.style.borderColor='var(--wine)';e.currentTarget.style.color='var(--wine)';e.currentTarget.style.background='var(--wine-50)';}}
          onMouseLeave={e=>{e.currentTarget.style.borderColor='var(--line-strong)';e.currentTarget.style.color='var(--ink-3)';e.currentTarget.style.background='transparent';}}>
          <Icon name="plus" size={26}/>
          <span style={{ font:'500 13.5px/1 var(--font-sans)' }}>Agregar servicio</span>
        </button>
      </div>

      {edit && <EditSheet svc={edit} onClose={()=>setEdit(null)}/>}
    </div>
  );
}

window.Servicios = Servicios;
