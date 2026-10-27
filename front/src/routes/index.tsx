import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { HiloMark, Icon } from "@/components/hilo/icons";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [{ title: "Hilo · Tu agenda vive en WhatsApp" }],
  }),
  component: LandingPage,
});

function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>('.reveal');
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { threshold: 0.05, rootMargin: '0px 0px -8% 0px' });
    els.forEach(el => io.observe(el));
    setTimeout(() => document.querySelectorAll<HTMLElement>('.reveal:not(.in)').forEach(el => el.classList.add('in')), 1600);
    return () => io.disconnect();
  }, []);
}

function LandingPage() {
  useReveal();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="l-wrap">
      {/* NAV */}
      <nav className="l-nav">
        <div className="l-container l-nav-inner">
          <Link className="l-brand" to="/">
            <span style={{ width: 32, height: 32, borderRadius: 10, background: 'var(--wine)', display: 'grid', placeItems: 'center', boxShadow: '0 1px 2px rgba(20,22,28,0.25)' }}>
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
                <path d="M6 3v6a4 4 0 0 0 8 0 4 4 0 0 1 4 4v8" />
                <circle cx="6" cy="3" r="1.4" fill="#fff" stroke="none" />
                <circle cx="18" cy="21" r="1.4" fill="#fff" stroke="none" />
              </svg>
            </span>
            <span className="l-brand-name">Hilo</span>
          </Link>
          <div className="l-nav-links">
            <a className="l-nav-link" href="#producto">Producto</a>
            <a className="l-nav-link" href="#features">Soluciones</a>
            <a className="l-nav-link" href="#precios">Precios</a>
            <a className="l-nav-link" href="#recursos">Recursos</a>
          </div>
          <div className="l-nav-cta">
            <Link className="btn btn-ghost btn-sm" to="/login">Iniciar sesión</Link>
            <Link className="btn btn-dark btn-sm" to="/signup">Empieza gratis</Link>
            <button className="l-burger" onClick={() => setMenuOpen(v => !v)} aria-label="Menú">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
                <path d="M4 7h16M4 12h16M4 17h16" />
              </svg>
            </button>
          </div>
        </div>
        {menuOpen && (
          <div style={{ display: 'flex', position: 'absolute', top: 68, left: 0, right: 0, background: '#fff', flexDirection: 'column', alignItems: 'stretch', padding: '12px 18px', borderBottom: '1px solid var(--line)', gap: 2, boxShadow: 'var(--shadow-md)' }}>
            <a className="l-nav-link" href="#producto" onClick={() => setMenuOpen(false)}>Producto</a>
            <a className="l-nav-link" href="#features" onClick={() => setMenuOpen(false)}>Soluciones</a>
            <a className="l-nav-link" href="#precios" onClick={() => setMenuOpen(false)}>Precios</a>
            <a className="l-nav-link" href="#recursos" onClick={() => setMenuOpen(false)}>Recursos</a>
            <Link className="btn btn-ghost btn-sm" to="/login" style={{ marginTop: 8 }}>Iniciar sesión</Link>
            <Link className="btn btn-dark btn-sm" to="/signup">Empieza gratis</Link>
          </div>
        )}
      </nav>

      {/* HERO */}
      <header className="hero" id="producto">
        <svg className="sparkle" style={{ top: 90, left: '46%', width: 34, height: 34 }} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7z" /></svg>
        <svg className="sparkle" style={{ bottom: 40, left: '38%', width: 20, height: 20, color: 'var(--wine-300)' }} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7z" /></svg>
        <div className="l-container hero-grid">
          <div>
            <span className="eyebrow-pill"><span className="tagdot">Nuevo</span> Agente de citas por WhatsApp</span>
            <h1 className="display">Tu agenda<br />se llena sola.<br /><span className="wine">Por WhatsApp.</span></h1>
            <p className="lede">Hilo es un agente que conversa con tus clientes por WhatsApp y agenda, reagenda y confirma citas — sin que dejes de atender.</p>
            <ul className="checklist">
              <li><span className="check"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span><span><b>Conserva tu número.</b> Coexistencia: sigues usando tu WhatsApp de siempre.</span></li>
              <li><span className="check"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span><span><b>Sincronizado con Google Calendar.</b> Nunca dos citas a la misma hora.</span></li>
              <li><span className="check"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></span><span><b>Listo en minutos.</b> Sin instalar nada, sin que tus clientes bajen una app.</span></li>
            </ul>
            <div className="hero-actions">
              <Link className="btn btn-dark btn-lg" to="/signup">Empieza gratis</Link>
              <Link className="btn btn-ghost btn-lg" to="/dashboard">Ver el panel
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
              </Link>
            </div>
            <p className="hero-note" style={{ marginTop: 18 }}><b>Gratis 14 días</b> · Sin tarjeta · Cancela cuando quieras</p>
          </div>

          {/* phone mock */}
          <div className="hero-visual">
            <svg className="sparkle" style={{ top: -14, right: '6%', width: 26, height: 26 }} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7z" /></svg>
            <div className="phone">
              <div className="phone-screen">
                <div className="phone-bar">
                  <span className="pa">N&amp;T</span>
                  <div>
                    <div className="pn">Navaja &amp; Tinta</div>
                    <div className="ps">
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 11.5a8 8 0 0 1-11.8 7L4 20l1.6-4A8 8 0 1 1 20 11.5z" /></svg>
                      en línea · responde al instante
                    </div>
                  </div>
                </div>
                <div className="chat">
                  <div className="bub in">Hola! Tienen cupo mañana para corte y barba?<span className="bt">4:32 p.m.</span></div>
                  <div className="bub out">¡Hola! 💈 Mañana con Andrés tengo 10:00, 11:30 o 4:00 p.m. ¿Cuál te queda mejor?<span className="bt">4:32 p.m. · Hilo</span></div>
                  <div className="bub in">4:00 porfa<span className="bt">4:33 p.m.</span></div>
                  <div className="bub out">Listo ✅ Te agendé <b>Corte + barba</b> con Andrés mañana 4:00 p.m. Te llega recordatorio el día de la cita.<span className="bt">4:33 p.m. · Hilo</span></div>
                </div>
              </div>
            </div>
            {/* float cards */}
            <div className="float-card fc-top">
              <span className="fi" style={{ background: 'var(--wa-bg)', color: 'var(--wa-ink)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM8.5 12l2.5 2.5 4.5-5" /></svg>
              </span>
              <div>
                <div style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Cita confirmada</div>
                <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>Mañana 16:00 · Corte + barba</div>
              </div>
            </div>
            <div className="float-card fc-bottom">
              <span className="fi" style={{ background: 'var(--wine-50)', color: 'var(--wine)' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M20 8a8 8 0 0 0-14-2M4 6v3h3M4 16a8 8 0 0 0 14 2M20 18v-3h-3" /></svg>
              </span>
              <div>
                <div style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Calendar actualizado</div>
                <div style={{ font: '400 12px/1.3 var(--font-sans)', color: 'var(--ink-3)' }}>Sin choques de horario</div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* STATS */}
      <section className="section" style={{ paddingTop: 24 }}>
        <div className="l-container">
          <div className="sec-head" style={{ marginBottom: 32 }}>
            <div className="sec-eyebrow">El cambio que se nota</div>
            <h2 className="sec-title">Negocios que dejaron de <span className="muted">contestar a mano.</span></h2>
          </div>
          <div className="stats">
            <div className="stat"><div className="stat-k">Citas automatizadas</div><div className="stat-v">86%</div><div className="stat-d">Reservadas por el agente sin que toques el teléfono.</div></div>
            <div className="stat"><div className="stat-k">Respuesta media</div><div className="stat-v">41s</div><div className="stat-d">El cliente recibe respuesta aunque estés con tijera en mano.</div></div>
            <div className="stat"><div className="stat-k">Horas al mes</div><div className="stat-v">+30</div><div className="stat-d">Recuperadas al no coordinar citas por chat manualmente.</div></div>
            <div className="stat"><div className="stat-k">Menos inasistencias</div><div className="stat-v">−38%</div><div className="stat-d">Con recordatorios automáticos antes de cada cita.</div></div>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="section alt" id="features">
        <div className="l-container">
          <div className="sec-head">
            <div className="sec-eyebrow">Un solo hilo</div>
            <h2 className="sec-title">Todo tu negocio, <span className="muted">un solo agente.</span></h2>
            <p className="sec-sub">Desde la conversación hasta la cita, el cliente y el cobro. Hilo conecta cada punto sin que cambies tu forma de trabajar.</p>
          </div>
          <div className="features">
            {/* Agenda */}
            <div className="feature reveal">
              <div className="mock">
                <svg className="sparkle" style={{ top: 18, right: 22, width: 22, height: 22 }} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7z" /></svg>
                <div className="mini-card" style={{ width: '84%', padding: '16px 18px' }}>
                  <div style={{ font: '700 15px/1 var(--font-serif)', color: 'var(--ink-1)', marginBottom: 14 }}>El día de hoy</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '44px 16px 1fr', alignItems: 'start' }}>
                      <div style={{ textAlign: 'right', paddingRight: 10, font: '600 12px/1 var(--font-mono)', color: 'var(--ink-3)' }}>09:00</div>
                      <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}><span style={{ position: 'absolute', top: 10, bottom: -10, width: 2, background: 'var(--line-strong)' }}></span><span style={{ marginTop: 3, width: 10, height: 10, borderRadius: '50%', background: 'var(--surface)', border: '2px solid var(--line-strong)', zIndex: 1 }}></span></div>
                      <div style={{ paddingBottom: 12, font: '500 13px/1.2 var(--font-sans)', color: 'var(--ink-2)' }}>Mateo · Corte clásico</div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '44px 16px 1fr', alignItems: 'start' }}>
                      <div style={{ textAlign: 'right', paddingRight: 10, font: '600 12px/1 var(--font-mono)', color: 'var(--wine)' }}>11:00</div>
                      <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}><span style={{ position: 'absolute', top: 10, bottom: -10, width: 2, background: 'var(--wine-200)' }}></span><span style={{ marginTop: 3, width: 12, height: 12, borderRadius: '50%', background: 'var(--wine)', boxShadow: '0 0 0 4px var(--wine-100)', zIndex: 1 }}></span></div>
                      <div style={{ paddingBottom: 12 }}><div style={{ font: '600 13px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Sebastián · En curso</div></div>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '44px 16px 1fr', alignItems: 'start' }}>
                      <div style={{ textAlign: 'right', paddingRight: 10, font: '600 12px/1 var(--font-mono)', color: 'var(--ink-3)' }}>14:30</div>
                      <div style={{ position: 'relative', display: 'flex', justifyContent: 'center' }}><span style={{ marginTop: 3, width: 10, height: 10, borderRadius: '50%', background: 'var(--clay)', zIndex: 1 }}></span></div>
                      <div style={{ font: '500 13px/1.2 var(--font-sans)', color: 'var(--ink-2)' }}>Felipe · Corte + barba</div>
                    </div>
                  </div>
                </div>
              </div>
              <h3>Una agenda que se ordena sola</h3>
              <p>El día como una historia: cada cita es un nudo en tu hilo. Ve, mueve y bloquea horarios desde un solo lugar, siempre en sincronía con Google Calendar.</p>
              <Link className="more" to="/dashboard">Conoce la agenda <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5l7 7-7 7" /></svg></Link>
            </div>

            {/* Servicios */}
            <div className="feature reveal">
              <div className="mock">
                <svg className="sparkle" style={{ bottom: 20, left: 24, width: 20, height: 20 }} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7z" /></svg>
                <div style={{ display: 'flex', gap: 14 }}>
                  <div className="mini-card" style={{ width: 148, overflow: 'hidden' }}>
                    <div style={{ height: 4, background: 'var(--clay)' }}></div>
                    <div style={{ padding: '13px 14px' }}>
                      <div style={{ font: '600 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Corte clásico</div>
                      <div style={{ font: '700 17px/1 var(--font-serif)', color: 'var(--clay)', margin: '8px 0' }}>$38.000</div>
                      <div style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>40 min · activo</div>
                    </div>
                  </div>
                  <div className="mini-card" style={{ width: 148, overflow: 'hidden', marginTop: 24 }}>
                    <div style={{ height: 4, background: 'var(--wine)' }}></div>
                    <div style={{ padding: '13px 14px' }}>
                      <div style={{ font: '600 14px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Corte + barba</div>
                      <div style={{ font: '700 17px/1 var(--font-serif)', color: 'var(--wine)', margin: '8px 0' }}>$55.000</div>
                      <div style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>60 min · activo</div>
                    </div>
                  </div>
                </div>
              </div>
              <h3>Tu carta de servicios, clara</h3>
              <p>Define nombre, duración, precio y domicilio. El agente solo ofrece lo que tengas activo — y cobra el extra de domicilio cuando aplica.</p>
              <Link className="more" to="/services">Conoce los servicios <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5l7 7-7 7" /></svg></Link>
            </div>

            {/* Clientes */}
            <div className="feature reveal">
              <div className="mock">
                <div className="mini-card" style={{ width: '84%', padding: '16px 18px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{ width: 44, height: 44, borderRadius: '50%', background: 'var(--wine-50)', color: 'var(--wine)', display: 'grid', placeItems: 'center', font: '600 16px/1 var(--font-sans)', border: '1px solid var(--wine-100)' }}>FA</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ font: '600 15px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Felipe Arango</div>
                      <div style={{ font: '400 12.5px/1.2 var(--font-sans)', color: 'var(--ink-3)' }}>Cliente frecuente · 14 visitas</div>
                    </div>
                    <span style={{ padding: '4px 10px', borderRadius: 99, background: 'var(--wine-50)', color: 'var(--wine)', font: '600 11px/1 var(--font-sans)' }}>VIP</span>
                  </div>
                  <div style={{ marginTop: 14, padding: '11px 13px', background: 'var(--surface-tint)', borderRadius: 10, font: '400 12.5px/1.5 var(--font-sans)', color: 'var(--ink-2)' }}>"Prefiere a Julián. Tijera, no máquina en los lados."</div>
                </div>
              </div>
              <h3>Clientes con memoria</h3>
              <p>Historial, notas y servicios frecuentes de cada persona. Tu agente recuerda a quién atiende — y tú también.</p>
              <Link className="more" to="/clients">Conoce los clientes <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5l7 7-7 7" /></svg></Link>
            </div>

            {/* Conexión */}
            <div className="feature reveal">
              <div className="mock">
                <svg className="sparkle" style={{ top: 24, left: 26, width: 18, height: 18, color: 'var(--wine-300)' }} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l1.7 6.3L20 10l-6.3 1.7L12 18l-1.7-6.3L4 10l6.3-1.7z" /></svg>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, width: '74%' }}>
                  <div className="mini-card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px' }}>
                    <span style={{ width: 38, height: 38, borderRadius: 10, background: 'var(--wa-bg)', color: 'var(--wa-ink)', display: 'grid', placeItems: 'center' }}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M20 11.5a8 8 0 0 1-11.8 7L4 20l1.6-4A8 8 0 1 1 20 11.5z" /></svg></span>
                    <div style={{ flex: 1 }}><div style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>WhatsApp</div><div style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>Coexistencia activa</div></div>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--wa)' }}></span>
                  </div>
                  <div className="mini-card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 15px' }}>
                    <span style={{ width: 38, height: 38, borderRadius: 10, background: 'color-mix(in srgb, var(--steel) 14%, #fff)', color: 'var(--steel)', display: 'grid', placeItems: 'center' }}><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3 3 8l9 5 9-5-9-5zM3 13l9 5 9-5" /></svg></span>
                    <div style={{ flex: 1 }}><div style={{ font: '600 13.5px/1.2 var(--font-sans)', color: 'var(--ink-1)' }}>Google Calendar</div><div style={{ font: '400 12px/1 var(--font-sans)', color: 'var(--ink-3)' }}>Sincronizado hace 1 min</div></div>
                    <span style={{ width: 9, height: 9, borderRadius: '50%', background: 'var(--success)' }}></span>
                  </div>
                </div>
              </div>
              <h3>Conectado a tu mundo</h3>
              <p>WhatsApp coexistente y Google Calendar como fuente de verdad. Conectas una vez y todo conversa entre sí, en tiempo real.</p>
              <Link className="more" to="/onboarding">Cómo se conecta <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5l7 7-7 7" /></svg></Link>
            </div>
          </div>
        </div>
      </section>

      {/* AI DARK */}
      <section className="section">
        <div className="l-container">
          <div className="ai-dark reveal">
            <div className="ai-glow"></div>
            <span className="ai-ghost-word" style={{ top: 64, left: '8%' }}>Agenda cita</span>
            <span className="ai-ghost-word" style={{ top: 120, right: '9%' }}>Reagenda</span>
            <span className="ai-ghost-word" style={{ bottom: 90, left: '12%' }}>Confirma</span>
            <span className="ai-ghost-word" style={{ bottom: 120, right: '11%' }}>Recuerda</span>
            <div className="ai-mark">
              <svg width="42" height="42" viewBox="0 0 24 24" fill="#fff"><path d="M12 2l1.9 6.6L20.5 10l-6.6 1.9L12 18.5l-1.9-6.6L3.5 10l6.6-1.4z" /></svg>
            </div>
            <div className="ai-eyebrow">Agente Hilo</div>
            <h2 className="ai-title">El único agente que<br />vive <span className="muted">donde tus clientes ya están.</span></h2>
            <p className="ai-sub">No es un chatbot es un agente. Entiende lenguaje natural, consulta tu disponibilidad real y ejecuta la acción correcta — en español, con el tono de tu negocio.</p>
            <Link className="btn btn-wine btn-lg" to="/signup" style={{ position: 'relative', zIndex: 1 }}>Pruébalo hoy</Link>
          </div>
        </div>
      </section>

      {/* BENTO */}
      <section className="section alt" id="recursos">
        <div className="l-container">
          <div className="sec-head">
            <div className="sec-eyebrow">Por qué Hilo</div>
            <h2 className="sec-title">Menos chats. <span className="muted">Más citas.</span></h2>
          </div>
          <div className="bento">
            <div className="bento-card fill wide reveal">
              <div className="bento-round" style={{ background: 'rgba(255,255,255,0.16)' }}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12a8 8 0 0 1-11.5 7.2L4 20.5l1.3-5A8 8 0 1 1 21 12z" /></svg></div>
              <div>
                <h3 className="bento-h" style={{ fontSize: 28 }}>Tus clientes escriben como siempre.<br />Hilo entiende y agenda.</h3>
                <p className="bento-p" style={{ maxWidth: 440 }}>Sin formularios, sin links raros, sin enseñarle a nadie a usar una app nueva. Conversación natural que termina en una cita real.</p>
              </div>
            </div>
            <div className="bento-card soft reveal">
              <div className="bento-round" style={{ background: 'var(--wine-50)', color: 'var(--wine)' }}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 7v5l3.5 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" /></svg></div>
              <div><h3 className="bento-h">Atiende 24/7</h3><p className="bento-p" style={{ color: 'var(--ink-2)' }}>Responde a la 1 a.m. o un domingo. La cita queda lista para cuando abras.</p></div>
            </div>
            <div className="bento-card soft reveal">
              <div className="bento-round" style={{ background: 'var(--wa-bg)', color: 'var(--wa-ink)' }}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg></div>
              <div><h3 className="bento-h">Cero dobles citas</h3><p className="bento-p" style={{ color: 'var(--ink-2)' }}>Lee tu calendario antes de reservar. Imposible chocar dos clientes.</p></div>
            </div>
            <div className="bento-card soft wide reveal">
              <div className="bento-round" style={{ background: 'color-mix(in srgb, var(--clay) 14%, #fff)', color: 'var(--clay)' }}><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v18M16 7.5c0-1.5-1.8-2.5-4-2.5s-4 1-4 2.5S9.8 10 12 10s4 1 4 2.5S14.2 15 12 15s-4-1-4-2.5" /></svg></div>
              <div><h3 className="bento-h" style={{ fontSize: 24 }}>Cada conversación es una venta posible</h3><p className="bento-p" style={{ color: 'var(--ink-2)', maxWidth: 420 }}>Recupera al cliente que escribía y se quedaba sin respuesta. Hilo no deja mensajes sin contestar.</p></div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section" id="precios">
        <div className="l-container cta-band reveal">
          <h2 className="cta-title">Tu próxima cita ya está<br />escribiéndote.</h2>
          <p className="cta-sub">Empieza gratis hoy y deja que Hilo conteste por ti. 14 días, sin tarjeta.</p>
          <div style={{ display: 'flex', gap: 14, justifyContent: 'center', flexWrap: 'wrap' }}>
            <Link className="btn btn-dark btn-lg" to="/signup">Empieza gratis</Link>
            <Link className="btn btn-ghost btn-lg" to="/login">Iniciar sesión</Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="l-footer">
        <div className="l-container">
          <div className="foot-grid">
            <div className="foot-brand">
              <div className="l-brand" style={{ color: '#fff' }}>
                <span style={{ width: 30, height: 30, borderRadius: 9, background: 'var(--wine)', display: 'grid', placeItems: 'center' }}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d="M6 3v6a4 4 0 0 0 8 0 4 4 0 0 1 4 4v8" /><circle cx="6" cy="3" r="1.4" fill="#fff" stroke="none" /><circle cx="18" cy="21" r="1.4" fill="#fff" stroke="none" /></svg>
                </span>
                <span className="l-brand-name">Hilo</span>
              </div>
              <p className="foot-tag">El agente de citas por WhatsApp para barberías, spas, estéticas y consultorios.</p>
            </div>
            <div className="foot-col"><h4>Producto</h4><Link to="/dashboard">Agenda</Link><Link to="/services">Servicios</Link><Link to="/clients">Clientes</Link><Link to="/dashboard">Ver panel</Link></div>
            <div className="foot-col"><h4>Empresa</h4><a href="#recursos">Sobre Hilo</a><a href="#precios">Precios</a><a href="#">Contacto</a><a href="#">Soporte</a></div>
            <div className="foot-col"><h4>Cuenta</h4><Link to="/login">Iniciar sesión</Link><Link to="/signup">Crear cuenta</Link><a href="#">Privacidad</a><a href="#">Términos</a></div>
          </div>
          <div className="foot-bottom">
            <span>© 2026 Hilo. Hecho en Medellín.</span>
            <span>Tu agenda vive en WhatsApp.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
