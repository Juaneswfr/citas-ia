// hilo/app.jsx — router + state + mount
const { useState: useStateA, useEffect: useEffectA } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#593240",
  "editorial": true,
  "density": "regular"
}/*EDITMODE-END*/;

const ACCENTS = {
  "#593240": { name:'Vino',    v700:'#3F2330', v600:'#6E3F4F', v400:'#8C5D6A', v300:'#B98E98', v200:'#E4D2D7', v100:'#F1E5E8', v50:'#FAF4F5' },
  "#1F6F5C": { name:'Verde',   v700:'#154E40', v600:'#2A8068', v400:'#4FA189', v300:'#8FC4B5', v200:'#CDE6DE', v100:'#E5F2EE', v50:'#F2F9F6' },
  "#2B4C7E": { name:'Azul',    v700:'#1D3658', v600:'#365C95', v400:'#5C7DB0', v300:'#9BB0D0', v200:'#D2DCEC', v100:'#E7EDF6', v50:'#F3F6FB' },
  "#1E1E24": { name:'Tinta',   v700:'#0E0E12', v600:'#33333C', v400:'#56565F', v300:'#9A9AA2', v200:'#D6D6DB', v100:'#E9E9ED', v50:'#F4F4F6' },
};

function applyTweaks(t){
  const root = document.documentElement;
  const a = ACCENTS[t.accent] || ACCENTS["#593240"];
  root.style.setProperty('--wine', t.accent);
  root.style.setProperty('--wine-700', a.v700);
  root.style.setProperty('--wine-600', a.v600);
  root.style.setProperty('--wine-400', a.v400);
  root.style.setProperty('--wine-300', a.v300);
  root.style.setProperty('--wine-200', a.v200);
  root.style.setProperty('--wine-100', a.v100);
  root.style.setProperty('--wine-50', a.v50);
  root.style.setProperty('--font-serif', t.editorial
    ? '"Schibsted Grotesk","Hanken Grotesk",sans-serif'
    : 'var(--font-sans)');
}

function ComingSoon({ id }){
  const item = NAV.flatMap(g=>g.items).find(i=>i.id===id) || {label:id, icon:'sparkle'};
  return (
    <div style={{ maxWidth:560, margin:'0 auto', padding:'80px 24px', textAlign:'center' }}>
      <span style={{ width:64, height:64, borderRadius:'var(--r-xl)', background:'var(--wine-50)', color:'var(--wine)',
        display:'inline-grid', placeItems:'center', marginBottom:20 }}><Icon name={item.icon} size={30}/></span>
      <h2 style={{ margin:'0 0 10px', font:'400 28px/1.1 var(--font-serif)', color:'var(--ink-1)' }}>{item.label}</h2>
      <p style={{ margin:'0 auto', maxWidth:380, font:'400 15px/1.55 var(--font-sans)', color:'var(--ink-2)' }}>
        Esta sección llega en la próxima entrega. Por ahora exploramos <span className="serif-i" style={{fontFamily:'var(--font-serif)'}}>Inicio, Agenda, Servicios, Clientes</span> y el onboarding.
      </p>
    </div>
  );
}

function App(){
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [route, setRoute] = useStateA(()=> location.hash.replace('#','') || 'inicio');
  const isMobile = useIsMobile(880);

  useEffectA(()=>applyTweaks(t),[t]);
  useEffectA(()=>{ location.hash = route; }, [route]);
  const nav = (id)=>{ setRoute(id); };

  const titles = { inicio:'Inicio', agenda:'Agenda', servicios:'Servicios', clientes:'Clientes',
    onboarding:'Configuración inicial' };
  const built = { inicio:true, agenda:true, servicios:true, clientes:true, onboarding:true };

  let screen;
  if (route==='inicio') screen = <Dashboard isMobile={isMobile} onNav={nav}/>;
  else if (route==='agenda') screen = <Agenda isMobile={isMobile} onNav={nav}/>;
  else if (route==='servicios') screen = <Servicios isMobile={isMobile} onNav={nav}/>;
  else if (route==='clientes') screen = <Clientes isMobile={isMobile} onNav={nav}/>;
  else if (route==='onboarding') screen = <Onboarding isMobile={isMobile} onNav={nav}/>;
  else screen = <ComingSoon id={route}/>;

  const showChrome = route!=='onboarding';

  return (
    <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--paper)' }}>
      {showChrome && !isMobile && <Sidebar active={route} onNav={nav} onboardPct={75}/>}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0, height:'100%' }}>
        {showChrome && <TopBar title={titles[route]||'Hilo'} isMobile={isMobile} onMenu={()=>{}} onCompose={()=>nav('agenda')}/>}
        <main style={{ flex:1, overflowY:'auto', minHeight:0 }}>{screen}</main>
        {showChrome && isMobile && <BottomTabs active={route} onNav={nav}/>}
      </div>

      <TweaksPanel title="Tweaks">
        <TweakSection label="Acento de marca"/>
        <TweakColor label="Color" value={t.accent}
          options={Object.keys(ACCENTS)} onChange={v=>setTweak('accent', v)}/>
        <TweakSection label="Tipografía"/>
        <TweakToggle label="Títulos con carácter" value={t.editorial} onChange={v=>setTweak('editorial', v)}/>
      </TweaksPanel>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
