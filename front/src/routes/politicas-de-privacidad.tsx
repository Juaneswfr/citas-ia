import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/politicas-de-privacidad")({
  head: () => ({
    meta: [
      { title: "Política de Privacidad · Hilo" },
      { name: "description", content: "Conoce cómo Hilo recopila, usa y protege tu información personal." },
    ],
  }),
  component: PrivacyPage,
});

const LAST_UPDATED = "10 de junio de 2026";
const COMPANY = "Juan Esteban Ramírez Ávila";
const COMPANY_ID = "C.C. 1007298045";
const COMPANY_ADDRESS = "Calle 39 # 43a-109, Colombia";
const EMAIL_PRIVACY = "contacto@hilo.esjuanez.com";
const DOMAIN = "hilo.esjuanez.com";

const sectionStyle: React.CSSProperties = {
  marginBottom: 48,
};
const h2Style: React.CSSProperties = {
  font: '700 22px/1.2 var(--font-serif)',
  letterSpacing: '-0.02em',
  color: 'var(--ink-1)',
  margin: '0 0 14px',
  paddingTop: 8,
};
const h3Style: React.CSSProperties = {
  font: '600 16px/1.3 var(--font-sans)',
  color: 'var(--ink-1)',
  margin: '24px 0 8px',
};
const pStyle: React.CSSProperties = {
  font: '400 15.5px/1.65 var(--font-sans)',
  color: 'var(--ink-2)',
  margin: '0 0 12px',
};
const ulStyle: React.CSSProperties = {
  margin: '8px 0 12px',
  paddingLeft: 22,
  display: 'flex',
  flexDirection: 'column',
  gap: 6,
};
const liStyle: React.CSSProperties = {
  font: '400 15.5px/1.6 var(--font-sans)',
  color: 'var(--ink-2)',
};
const dividerStyle: React.CSSProperties = {
  borderTop: '1px solid var(--line)',
  margin: '40px 0',
};

function NavBar() {
  const [menuOpen, setMenuOpen] = useState(false);
  return (
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
        <div style={{ position: 'absolute', top: 68, left: 0, right: 0, background: '#fff', display: 'flex', flexDirection: 'column', padding: '12px 18px', borderBottom: '1px solid var(--line)', gap: 8, boxShadow: 'var(--shadow-md)' }}>
          <Link className="btn btn-ghost btn-sm" to="/login" onClick={() => setMenuOpen(false)}>Iniciar sesión</Link>
          <Link className="btn btn-dark btn-sm" to="/signup" onClick={() => setMenuOpen(false)}>Empieza gratis</Link>
        </div>
      )}
    </nav>
  );
}

function Footer() {
  return (
    <footer className="l-footer">
      <div className="l-container">
        <div className="foot-grid">
          <div className="foot-brand">
            <span className="l-brand-name" style={{ color: '#fff', font: '800 21px/1 var(--font-serif)', letterSpacing: '-0.03em' }}>Hilo</span>
            <p className="foot-tag">Tu agenda vive en WhatsApp. El agente que agenda, reagenda y confirma por ti.</p>
          </div>
          <div className="foot-col">
            <h4>Producto</h4>
            <Link to="/" style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>Inicio</Link>
            <Link to="/login" style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>Iniciar sesión</Link>
            <Link to="/signup" style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>Registrarse</Link>
          </div>
          <div className="foot-col">
            <h4>Legal</h4>
            <Link to="/politicas-de-privacidad" style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>Política de Privacidad</Link>
            <Link to="/condiciones-del-servicio" style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>Condiciones del Servicio</Link>
          </div>
          <div className="foot-col">
            <h4>Contacto</h4>
            <a href={`mailto:${EMAIL_PRIVACY}`} style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>{EMAIL_PRIVACY}</a>
          </div>
        </div>
        <div className="foot-bottom">
          <span>© {new Date().getFullYear()} {COMPANY}. Todos los derechos reservados.</span>
          <span style={{ display: 'flex', gap: 20 }}>
            <Link to="/politicas-de-privacidad" style={{ color: 'rgba(255,255,255,0.5)', textDecoration: 'none' }}>Privacidad</Link>
            <Link to="/condiciones-del-servicio" style={{ color: 'rgba(255,255,255,0.5)', textDecoration: 'none' }}>Términos</Link>
          </span>
        </div>
      </div>
    </footer>
  );
}

function PrivacyPage() {
  return (
    <div className="l-wrap">
      <NavBar />

      {/* Header */}
      <div style={{ background: 'var(--wine)', padding: '64px 0 56px' }}>
        <div className="l-container">
          <div style={{ font: '600 13px/1 var(--font-sans)', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.65)', marginBottom: 16 }}>
            Legal
          </div>
          <h1 style={{ font: '800 clamp(34px,5vw,52px)/1.05 var(--font-serif)', letterSpacing: '-0.03em', color: '#fff', margin: '0 0 16px' }}>
            Política de Privacidad
          </h1>
          <p style={{ font: '400 17px/1.5 var(--font-sans)', color: 'rgba(255,255,255,0.72)', margin: 0, maxWidth: 560 }}>
            Última actualización: <strong style={{ color: '#fff' }}>{LAST_UPDATED}</strong>
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="l-container" style={{ maxWidth: 780, padding: '64px 28px 96px' }}>

        <p style={{ ...pStyle, font: '400 17px/1.65 var(--font-sans)', color: 'var(--ink-1)', marginBottom: 40, padding: '20px 24px', background: 'var(--wine-50)', border: '1px solid var(--wine-100)', borderRadius: 'var(--r-lg)' }}>
          En <strong>{COMPANY}</strong> operamos la plataforma <strong>Hilo</strong> disponible en <strong>{DOMAIN}</strong>. Esta Política de Privacidad explica cómo recopilamos, usamos, almacenamos y protegemos tu información cuando usas nuestro servicio.
        </p>

        {/* 1 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>1. Responsable del tratamiento</h2>
          <p style={pStyle}>
            El responsable del tratamiento de tus datos personales es <strong>{COMPANY}</strong>, con domicilio en Colombia. Para cualquier consulta relacionada con esta política puedes contactarnos en <a href={`mailto:${EMAIL_PRIVACY}`} style={{ color: 'var(--wine)' }}>{EMAIL_PRIVACY}</a>.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 2 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>2. Información que recopilamos</h2>

          <h3 style={h3Style}>2.1 Información que tú nos proporcionas</h3>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Datos de registro:</strong> nombre, correo electrónico, contraseña y nombre del negocio al crear una cuenta.</li>
            <li style={liStyle}><strong>Datos del negocio:</strong> nombre comercial, zona horaria, país, servicios ofrecidos y tarifas.</li>
            <li style={liStyle}><strong>Datos de conexión de WhatsApp:</strong> número de teléfono de WhatsApp Business, WABA ID y token de acceso de Meta.</li>
            <li style={liStyle}><strong>Datos de Google Calendar:</strong> credenciales OAuth para sincronizar citas con tu calendario.</li>
          </ul>

          <h3 style={h3Style}>2.2 Información generada por el uso del servicio</h3>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Datos de clientes:</strong> números de teléfono, nombres y conversaciones de los clientes de tu negocio que interactúan con el agente de WhatsApp.</li>
            <li style={liStyle}><strong>Citas y servicios:</strong> registros de citas agendadas, reagendadas y canceladas.</li>
            <li style={liStyle}><strong>Registros de uso:</strong> logs de acceso, direcciones IP, tipo de navegador y páginas visitadas.</li>
            <li style={liStyle}><strong>Datos de conversación:</strong> mensajes intercambiados entre el agente de Hilo y los clientes finales a través de WhatsApp.</li>
          </ul>

          <h3 style={h3Style}>2.3 Información de terceros</h3>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Meta (WhatsApp):</strong> datos de la cuenta de WhatsApp Business y métricas de mensajería entregados por la API de Meta.</li>
            <li style={liStyle}><strong>Google:</strong> información básica de perfil y datos de calendario si conectas Google Calendar.</li>
            <li style={liStyle}><strong>Supabase:</strong> proveedor de autenticación y base de datos. Consulta la política de privacidad de Supabase en supabase.com/privacy.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 3 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>3. Finalidades del tratamiento</h2>
          <p style={pStyle}>Usamos tu información para:</p>
          <ul style={ulStyle}>
            <li style={liStyle}>Prestar y mantener el servicio de agendamiento por WhatsApp.</li>
            <li style={liStyle}>Gestionar tu cuenta y autenticar tu identidad.</li>
            <li style={liStyle}>Procesar y confirmar citas en nombre de tu negocio.</li>
            <li style={liStyle}>Enviar recordatorios automáticos de citas a tus clientes.</li>
            <li style={liStyle}>Sincronizar eventos con Google Calendar.</li>
            <li style={liStyle}>Mejorar el servicio mediante análisis de uso agregado y anónimo.</li>
            <li style={liStyle}>Enviarte comunicaciones sobre actualizaciones, nuevas funciones o información relevante del servicio (puedes cancelar la suscripción en cualquier momento).</li>
            <li style={liStyle}>Cumplir con obligaciones legales y reglamentarias aplicables.</li>
            <li style={liStyle}>Prevenir fraudes y garantizar la seguridad del servicio.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 4 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>4. Base legal del tratamiento</h2>
          <p style={pStyle}>Tratamos tu información en virtud de:</p>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Ejecución del contrato:</strong> el tratamiento es necesario para prestarte el servicio contratado.</li>
            <li style={liStyle}><strong>Interés legítimo:</strong> para mejorar el servicio, garantizar la seguridad y prevenir fraudes.</li>
            <li style={liStyle}><strong>Obligación legal:</strong> cuando la ley colombiana o aplicable nos obligue a conservar o revelar información.</li>
            <li style={liStyle}><strong>Consentimiento:</strong> para comunicaciones de marketing, que puedes revocar en cualquier momento.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 5 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>5. Compartición de datos con terceros</h2>
          <p style={pStyle}>No vendemos tu información personal. Podemos compartirla con:</p>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Meta Platforms:</strong> para enviar y recibir mensajes a través de la API de WhatsApp Business. Meta actúa como subencargado del tratamiento.</li>
            <li style={liStyle}><strong>Google LLC:</strong> para la sincronización de citas si conectas Google Calendar.</li>
            <li style={liStyle}><strong>Supabase Inc.:</strong> para almacenamiento de datos y autenticación.</li>
            <li style={liStyle}><strong>Anthropic PBC:</strong> el modelo de lenguaje (Claude) puede procesar texto de conversaciones para generar respuestas del agente. Los datos no se usan para entrenar modelos.</li>
            <li style={liStyle}><strong>Proveedores de infraestructura:</strong> servidores de alojamiento ubicados dentro del Espacio Económico Europeo o en países con nivel adecuado de protección.</li>
            <li style={liStyle}><strong>Autoridades competentes:</strong> cuando sea requerido por ley, orden judicial o para proteger derechos legítimos.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 6 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>6. Transferencias internacionales</h2>
          <p style={pStyle}>
            Algunos de nuestros proveedores están ubicados fuera de Colombia (Meta, Google, Supabase, Anthropic). Estas transferencias se realizan bajo las garantías adecuadas previstas en la Ley 1581 de 2012 y el GDPR cuando aplica, incluyendo cláusulas contractuales estándar o escudos de privacidad reconocidos.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 7 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>7. Retención de datos</h2>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Datos de cuenta:</strong> mientras tu cuenta esté activa. Tras la cancelación, se eliminan en un plazo máximo de 90 días, salvo obligación legal de conservación.</li>
            <li style={liStyle}><strong>Datos de conversación y citas:</strong> se conservan durante 2 años desde su creación para fines de historial y auditoría.</li>
            <li style={liStyle}><strong>Logs de acceso:</strong> máximo 12 meses.</li>
            <li style={liStyle}><strong>Datos de facturación:</strong> 5 años conforme a la normativa tributaria colombiana.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 8 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>8. Tus derechos</h2>
          <p style={pStyle}>Conforme a la Ley 1581 de 2012 (Colombia) y el GDPR (si eres residente en la UE), tienes derecho a:</p>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Acceso:</strong> conocer qué datos personales tenemos sobre ti.</li>
            <li style={liStyle}><strong>Rectificación:</strong> corregir datos inexactos o incompletos.</li>
            <li style={liStyle}><strong>Supresión:</strong> solicitar la eliminación de tus datos cuando ya no sean necesarios.</li>
            <li style={liStyle}><strong>Portabilidad:</strong> recibir tus datos en formato estructurado y legible por máquina.</li>
            <li style={liStyle}><strong>Oposición:</strong> oponerte al tratamiento basado en interés legítimo.</li>
            <li style={liStyle}><strong>Limitación:</strong> solicitar la restricción del tratamiento en determinadas circunstancias.</li>
            <li style={liStyle}><strong>Revocación del consentimiento:</strong> en cualquier momento para tratamientos basados en tu consentimiento.</li>
          </ul>
          <p style={pStyle}>
            Para ejercer cualquiera de estos derechos escríbenos a <a href={`mailto:${EMAIL_PRIVACY}`} style={{ color: 'var(--wine)' }}>{EMAIL_PRIVACY}</a>. Responderemos en un plazo máximo de 15 días hábiles.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 9 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>9. Seguridad de los datos</h2>
          <p style={pStyle}>Aplicamos medidas técnicas y organizativas apropiadas para proteger tu información:</p>
          <ul style={ulStyle}>
            <li style={liStyle}>Transmisión cifrada mediante TLS/HTTPS en todas las comunicaciones.</li>
            <li style={liStyle}>Cifrado en reposo de datos sensibles (tokens de acceso, credenciales).</li>
            <li style={liStyle}>Control de acceso basado en roles (RBAC) con Row Level Security (RLS) en base de datos.</li>
            <li style={liStyle}>Registros de auditoría de acciones críticas.</li>
            <li style={liStyle}>Revisiones periódicas de seguridad.</li>
          </ul>
          <p style={pStyle}>
            En caso de violación de seguridad que afecte tus datos personales, te notificaremos conforme a los plazos establecidos por la ley aplicable.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 10 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>10. Datos de clientes finales</h2>
          <p style={pStyle}>
            Cuando usas Hilo, tu negocio actúa como responsable del tratamiento de los datos personales de tus clientes (números de teléfono, nombres, conversaciones). Hilo actúa como encargado del tratamiento en tu nombre.
          </p>
          <p style={pStyle}>
            Eres responsable de contar con la base legal adecuada para tratar los datos de tus clientes y de informarles sobre el uso de sistemas automatizados de atención por WhatsApp.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 11 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>11. Cookies y tecnologías similares</h2>
          <p style={pStyle}>
            Usamos cookies esenciales para el funcionamiento del servicio (autenticación, sesión). No usamos cookies de seguimiento publicitario de terceros.
          </p>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Cookies de sesión:</strong> necesarias para mantener tu sesión iniciada.</li>
            <li style={liStyle}><strong>Almacenamiento local:</strong> guardamos el token de acceso de forma segura en el navegador.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 12 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>12. Menores de edad</h2>
          <p style={pStyle}>
            Hilo está dirigido exclusivamente a personas mayores de 18 años que actúen en calidad de comerciantes o empresarios. No recopilamos conscientemente datos de menores de edad. Si detectamos que hemos recopilado datos de un menor, los eliminaremos de inmediato.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 13 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>13. Cambios en esta política</h2>
          <p style={pStyle}>
            Podemos actualizar esta Política de Privacidad periódicamente. Cuando realicemos cambios materiales, te notificaremos por correo electrónico o mediante un aviso visible en la plataforma con al menos 15 días de antelación. El uso continuado del servicio tras la entrada en vigor de los cambios implica la aceptación de la política actualizada.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 14 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>14. Ley aplicable y resolución de disputas</h2>
          <p style={pStyle}>
            Esta política se rige por la legislación colombiana, en particular la Ley Estatutaria 1581 de 2012 y el Decreto 1377 de 2013. Cualquier disputa será sometida a los tribunales competentes de Colombia, salvo que la normativa de la UE obligue a someter la disputa a las autoridades de protección de datos del país del usuario.
          </p>
          <p style={pStyle}>
            Si consideras que el tratamiento de tus datos no cumple con la normativa aplicable, puedes presentar una queja ante la Superintendencia de Industria y Comercio (SIC) en Colombia (<a href="https://www.sic.gov.co" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--wine)' }}>www.sic.gov.co</a>).
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 15 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>15. Contacto</h2>
          <p style={pStyle}>
            Para cualquier consulta, solicitud o reclamación relacionada con el tratamiento de tus datos personales:
          </p>
          <div style={{ padding: '20px 24px', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)' }}>
            <p style={{ ...pStyle, margin: '0 0 6px' }}><strong>{COMPANY}</strong></p>
            <p style={{ ...pStyle, margin: '0 0 6px' }}>{COMPANY_ID}</p>
            <p style={{ ...pStyle, margin: '0 0 6px' }}>{COMPANY_ADDRESS}</p>
            <p style={{ ...pStyle, margin: 0 }}>
              Correo: <a href={`mailto:${EMAIL_PRIVACY}`} style={{ color: 'var(--wine)' }}>{EMAIL_PRIVACY}</a>
            </p>
          </div>
        </div>

        <div style={{ marginTop: 48, padding: '16px 0', borderTop: '1px solid var(--line)', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <Link to="/" style={{ color: 'var(--wine)', font: '500 14px/1 var(--font-sans)', textDecoration: 'none' }}>← Volver al inicio</Link>
          <Link to="/condiciones-del-servicio" style={{ color: 'var(--ink-3)', font: '500 14px/1 var(--font-sans)', textDecoration: 'none' }}>Condiciones del Servicio →</Link>
        </div>
      </div>

      <Footer />
    </div>
  );
}
