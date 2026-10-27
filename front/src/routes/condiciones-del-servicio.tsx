import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";

export const Route = createFileRoute("/condiciones-del-servicio")({
  head: () => ({
    meta: [
      { title: "Condiciones del Servicio · Hilo" },
      { name: "description", content: "Lee los términos y condiciones que rigen el uso de la plataforma Hilo." },
    ],
  }),
  component: TermsPage,
});

const LAST_UPDATED = "10 de junio de 2026";
const COMPANY = "Juan Esteban Ramírez Ávila";
const COMPANY_ID = "C.C. 1007298045";
const COMPANY_ADDRESS = "Calle 39 # 43a-109, Colombia";
const EMAIL_LEGAL = "contacto@hilo.esjuanez.com";
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
            <a href={`mailto:${EMAIL_LEGAL}`} style={{ display: 'block', font: '400 14.5px/1 var(--font-sans)', color: 'rgba(255,255,255,0.78)', textDecoration: 'none', padding: '7px 0' }}>{EMAIL_LEGAL}</a>
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

function TermsPage() {
  return (
    <div className="l-wrap">
      <NavBar />

      {/* Header */}
      <div style={{ background: 'var(--ink-1)', padding: '64px 0 56px' }}>
        <div className="l-container">
          <div style={{ font: '600 13px/1 var(--font-sans)', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.45)', marginBottom: 16 }}>
            Legal
          </div>
          <h1 style={{ font: '800 clamp(34px,5vw,52px)/1.05 var(--font-serif)', letterSpacing: '-0.03em', color: '#fff', margin: '0 0 16px' }}>
            Condiciones del Servicio
          </h1>
          <p style={{ font: '400 17px/1.5 var(--font-sans)', color: 'rgba(255,255,255,0.6)', margin: 0, maxWidth: 560 }}>
            Última actualización: <strong style={{ color: '#fff' }}>{LAST_UPDATED}</strong>
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="l-container" style={{ maxWidth: 780, padding: '64px 28px 96px' }}>

        <p style={{ ...pStyle, font: '400 17px/1.65 var(--font-sans)', color: 'var(--ink-1)', marginBottom: 40, padding: '20px 24px', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)' }}>
          Bienvenido a <strong>Hilo</strong>, operado por <strong>{COMPANY}</strong>. Al registrarte o usar cualquier parte de nuestro servicio disponible en <strong>{DOMAIN}</strong>, aceptas quedar vinculado por estas Condiciones del Servicio. Lee este documento detenidamente antes de usar la plataforma.
        </p>

        {/* 1 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>1. Descripción del servicio</h2>
          <p style={pStyle}>
            Hilo es una plataforma SaaS (Software como Servicio) que permite a negocios de servicios —especialmente barberías, salones de belleza y similares— automatizar el agendamiento de citas a través de WhatsApp mediante un agente de inteligencia artificial.
          </p>
          <p style={pStyle}>El servicio incluye, entre otros:</p>
          <ul style={ulStyle}>
            <li style={liStyle}>Agente conversacional por WhatsApp que agenda, reagenda y cancela citas de forma autónoma.</li>
            <li style={liStyle}>Panel de administración web para gestionar servicios, clientes, citas y configuración.</li>
            <li style={liStyle}>Integración con WhatsApp Business API a través de Meta.</li>
            <li style={liStyle}>Integración con Google Calendar para sincronización de disponibilidad.</li>
            <li style={liStyle}>Envío de recordatorios automáticos de citas.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 2 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>2. Aceptación de las condiciones</h2>
          <p style={pStyle}>
            Al crear una cuenta, acceder o usar Hilo, declaras que:
          </p>
          <ul style={ulStyle}>
            <li style={liStyle}>Tienes al menos 18 años y capacidad legal para celebrar contratos.</li>
            <li style={liStyle}>Actúas en nombre de un negocio legalmente constituido o como comerciante independiente.</li>
            <li style={liStyle}>Has leído, comprendido y aceptas estas Condiciones y nuestra <Link to="/politicas-de-privacidad" style={{ color: 'var(--wine)' }}>Política de Privacidad</Link>.</li>
            <li style={liStyle}>La información que proporcionas es veraz, exacta y actualizada.</li>
          </ul>
          <p style={pStyle}>
            Si actúas en nombre de una empresa u organización, declaras que tienes la autoridad para vincularla a estas Condiciones.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 3 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>3. Registro y cuenta</h2>
          <h3 style={h3Style}>3.1 Creación de cuenta</h3>
          <p style={pStyle}>
            Para usar Hilo debes crear una cuenta con un correo electrónico válido y una contraseña segura. Cada cuenta corresponde a un único espacio de trabajo (workspace) vinculado a un negocio.
          </p>
          <h3 style={h3Style}>3.2 Seguridad de la cuenta</h3>
          <p style={pStyle}>
            Eres responsable de mantener la confidencialidad de tus credenciales de acceso y de todas las actividades que ocurran en tu cuenta. Debes notificarnos inmediatamente en caso de uso no autorizado a <a href={`mailto:${EMAIL_LEGAL}`} style={{ color: 'var(--wine)' }}>{EMAIL_LEGAL}</a>.
          </p>
          <h3 style={h3Style}>3.3 Una cuenta por negocio</h3>
          <p style={pStyle}>
            Cada cuenta está asociada a un único número de WhatsApp Business. No puedes compartir una cuenta entre múltiples negocios independientes.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 4 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>4. Uso de WhatsApp Business API</h2>
          <p style={pStyle}>
            Hilo utiliza la API oficial de WhatsApp Business de Meta. Al conectar tu número de WhatsApp, también aceptas los <a href="https://www.whatsapp.com/legal/business-policy" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--wine)' }}>Términos de Servicio de WhatsApp Business</a> y las <a href="https://developers.facebook.com/policy/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--wine)' }}>Políticas de Plataforma de Meta</a>.
          </p>
          <h3 style={h3Style}>4.1 Responsabilidades del usuario</h3>
          <ul style={ulStyle}>
            <li style={liStyle}>Eres el único responsable del contenido de los mensajes enviados a través del agente.</li>
            <li style={liStyle}>Debes cumplir con la política de mensajería de WhatsApp y no usar el servicio para enviar spam, mensajes no solicitados o contenido prohibido.</li>
            <li style={liStyle}>Debes informar a tus clientes sobre el uso de un agente automatizado en las conversaciones.</li>
            <li style={liStyle}>Eres responsable de obtener el consentimiento adecuado de tus clientes para recibir mensajes de WhatsApp.</li>
          </ul>
          <h3 style={h3Style}>4.2 Suspensión por incumplimiento de Meta</h3>
          <p style={pStyle}>
            Meta puede suspender o cancelar el acceso a la API de WhatsApp Business si se detecta incumplimiento de sus políticas. {COMPANY} no es responsable de dichas suspensiones.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 5 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>5. Planes, precios y pagos</h2>
          <h3 style={h3Style}>5.1 Período de prueba</h3>
          <p style={pStyle}>
            Hilo ofrece un período de prueba gratuito de 14 días sin necesidad de tarjeta de crédito. Al finalizar el período de prueba, deberás suscribirte a un plan de pago para continuar usando el servicio.
          </p>
          <h3 style={h3Style}>5.2 Facturación</h3>
          <p style={pStyle}>
            Los planes de pago se facturan mensualmente o anualmente según la opción elegida. Los precios están expresados en pesos colombianos (COP) o en dólares estadounidenses (USD) según se indique. Los precios pueden variar y serán comunicados con 30 días de antelación.
          </p>
          <h3 style={h3Style}>5.3 Reembolsos</h3>
          <p style={pStyle}>
            Los pagos realizados no son reembolsables salvo que la ley aplicable lo exija o que Hilo haya incumplido materialmente el servicio. En caso de cancelación antes del fin del período facturado, el acceso continuará hasta el final de dicho período.
          </p>
          <h3 style={h3Style}>5.4 Impuestos</h3>
          <p style={pStyle}>
            Los precios pueden no incluir impuestos aplicables (IVA, etc.). El usuario es responsable del pago de los impuestos correspondientes según la legislación de su país.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 6 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>6. Conducta del usuario y usos prohibidos</h2>
          <p style={pStyle}>Al usar Hilo te comprometes a <strong>no</strong>:</p>
          <ul style={ulStyle}>
            <li style={liStyle}>Violar leyes o regulaciones aplicables, incluyendo las de protección de datos.</li>
            <li style={liStyle}>Usar el servicio para enviar mensajes de spam, phishing o cualquier comunicación no solicitada masiva.</li>
            <li style={liStyle}>Intentar acceder sin autorización a sistemas, cuentas o datos de otros usuarios.</li>
            <li style={liStyle}>Realizar ingeniería inversa, descompilar o desensamblar el software de Hilo.</li>
            <li style={liStyle}>Revender, sublicenciar o transferir el acceso al servicio a terceros sin autorización expresa.</li>
            <li style={liStyle}>Usar el servicio para actividades ilegales, fraudulentas o que perjudiquen a terceros.</li>
            <li style={liStyle}>Sobrecargar intencionalmente la infraestructura del servicio (ataques DoS/DDoS).</li>
            <li style={liStyle}>Falsificar identidades o representar erróneamente tu afiliación con alguna persona u organización.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 7 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>7. Propiedad intelectual</h2>
          <h3 style={h3Style}>7.1 Propiedad de Hilo</h3>
          <p style={pStyle}>
            Hilo y todo su contenido (software, diseño, logotipos, textos, gráficos) son propiedad exclusiva de {COMPANY} o sus licenciantes y están protegidos por las leyes de propiedad intelectual aplicables. Nada en estas Condiciones te transfiere propiedad sobre dichos elementos.
          </p>
          <h3 style={h3Style}>7.2 Licencia de uso</h3>
          <p style={pStyle}>
            Sujeto al cumplimiento de estas Condiciones y al pago de las tarifas aplicables, {COMPANY} te otorga una licencia limitada, no exclusiva, intransferible y revocable para acceder y usar el servicio únicamente para los fines comerciales previstos.
          </p>
          <h3 style={h3Style}>7.3 Contenido del usuario</h3>
          <p style={pStyle}>
            Conservas la propiedad de los datos e información que introduces en Hilo (datos de tu negocio, servicios, información de clientes). Nos otorgas una licencia limitada para procesar dicha información únicamente con el fin de prestar el servicio.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 8 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>8. Disponibilidad y nivel de servicio</h2>
          <p style={pStyle}>
            Hilo se presta "tal como está" y nos esforzamos por mantener una disponibilidad del 99,5% mensual, excluidos los mantenimientos programados. No garantizamos que el servicio sea ininterrumpido, libre de errores o que cumpla todos los requisitos específicos de tu negocio.
          </p>
          <p style={pStyle}>
            Podemos realizar mantenimientos programados con al menos 24 horas de aviso previo. En casos de emergencia, podemos interrumpir el servicio sin previo aviso si es necesario para proteger la seguridad o integridad del sistema.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 9 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>9. Limitación de responsabilidad</h2>
          <p style={pStyle}>
            En la máxima medida permitida por la ley aplicable:
          </p>
          <ul style={ulStyle}>
            <li style={liStyle}>{COMPANY} no será responsable de daños indirectos, incidentales, especiales, punitivos o consecuentes, incluyendo pérdida de beneficios, datos o clientes.</li>
            <li style={liStyle}>La responsabilidad total acumulada de {COMPANY} frente a ti no excederá el importe pagado por el servicio durante los 3 meses anteriores al evento que dio origen a la reclamación.</li>
            <li style={liStyle}>{COMPANY} no es responsable de errores, omisiones o inexactitudes en las respuestas generadas por el agente de inteligencia artificial.</li>
            <li style={liStyle}>{COMPANY} no es responsable de interrupciones del servicio causadas por terceros (Meta, Google, proveedores de internet, etc.).</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 10 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>10. Indemnización</h2>
          <p style={pStyle}>
            Aceptas defender, indemnizar y eximir de responsabilidad a {COMPANY}, sus directivos, empleados y socios frente a cualquier reclamación, daño, obligación, pérdida o gasto (incluidos honorarios de abogados) que surjan de: (i) tu uso del servicio; (ii) tu incumplimiento de estas Condiciones; (iii) tu violación de derechos de terceros; o (iv) el contenido que publiques o transmitas a través del servicio.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 11 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>11. Cancelación y terminación</h2>
          <h3 style={h3Style}>11.1 Cancelación por el usuario</h3>
          <p style={pStyle}>
            Puedes cancelar tu cuenta en cualquier momento desde el panel de configuración o escribiendo a <a href={`mailto:${EMAIL_LEGAL}`} style={{ color: 'var(--wine)' }}>{EMAIL_LEGAL}</a>. La cancelación surte efecto al final del período facturado en curso.
          </p>
          <h3 style={h3Style}>11.2 Terminación por Hilo</h3>
          <p style={pStyle}>
            Podemos suspender o cancelar tu cuenta con efecto inmediato si: (i) incumples estas Condiciones; (ii) realizas actividades fraudulentas o ilegales; (iii) violas las políticas de Meta; o (iv) no pagas las tarifas correspondientes.
          </p>
          <h3 style={h3Style}>11.3 Efectos de la terminación</h3>
          <p style={pStyle}>
            Tras la cancelación, tendrás 30 días para exportar tus datos. Transcurrido ese plazo, eliminaremos tus datos conforme a nuestra Política de Privacidad. Las cláusulas de estas Condiciones que por su naturaleza deban sobrevivir a la terminación continuarán vigentes.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 12 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>12. Inteligencia artificial y limitaciones del agente</h2>
          <p style={pStyle}>
            El agente de Hilo está impulsado por modelos de inteligencia artificial. Debes entender que:
          </p>
          <ul style={ulStyle}>
            <li style={liStyle}>El agente puede cometer errores, malinterpretar solicitudes o generar respuestas imprecisas.</li>
            <li style={liStyle}>No debes confiar exclusivamente en el agente para decisiones críticas de negocio sin supervisión humana.</li>
            <li style={liStyle}>Eres responsable de revisar y corregir cualquier error que el agente pueda cometer en la gestión de citas.</li>
            <li style={liStyle}>El agente opera dentro de los límites que configures (servicios, horarios, instrucciones). Su comportamiento depende de la calidad de la configuración que realices.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 13 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>13. Modificaciones del servicio y de las condiciones</h2>
          <p style={pStyle}>
            Nos reservamos el derecho de modificar, suspender o descontinuar cualquier aspecto del servicio en cualquier momento. También podemos actualizar estas Condiciones periódicamente. Te notificaremos de cambios materiales por correo electrónico o aviso en la plataforma con al menos 15 días de antelación. El uso continuado del servicio tras la entrada en vigor de los cambios implica tu aceptación.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 14 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>14. Servicios de terceros</h2>
          <p style={pStyle}>
            Hilo se integra con servicios de terceros (Meta/WhatsApp, Google Calendar, Supabase, Anthropic). Estas integraciones están sujetas a los términos y condiciones de dichos terceros. {COMPANY} no es responsable del funcionamiento, disponibilidad o cambios en los servicios de terceros.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 15 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>15. Confidencialidad</h2>
          <p style={pStyle}>
            Cada parte se compromete a mantener la confidencialidad de la información no pública de la otra parte. Esta obligación no aplica a información que: (i) sea públicamente conocida sin incumplimiento de esta cláusula; (ii) sea legítimamente recibida de un tercero; (iii) deba revelarse por obligación legal.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 16 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>16. Ley aplicable y resolución de disputas</h2>
          <p style={pStyle}>
            Estas Condiciones se rigen por las leyes de la República de Colombia. Cualquier disputa que surja en relación con estas Condiciones se someterá primero a negociación directa de buena fe. Si no se resuelve en 30 días, las partes acuerdan someter la disputa a los tribunales competentes de la ciudad de Medellín, Colombia, renunciando a cualquier otro fuero.
          </p>
          <p style={pStyle}>
            Si eres consumidor residente en la Unión Europea, también puedes acudir a la plataforma de resolución de litigios en línea de la Comisión Europea.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 17 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>17. Disposiciones generales</h2>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Acuerdo completo:</strong> Estas Condiciones, junto con la Política de Privacidad, constituyen el acuerdo completo entre las partes respecto al servicio.</li>
            <li style={liStyle}><strong>Divisibilidad:</strong> Si alguna cláusula de estas Condiciones es declarada inválida, el resto continuará en vigor.</li>
            <li style={liStyle}><strong>No renuncia:</strong> El hecho de que {COMPANY} no ejerza algún derecho no implica la renuncia al mismo.</li>
            <li style={liStyle}><strong>Cesión:</strong> No puedes ceder estos derechos sin el consentimiento previo por escrito de {COMPANY}. Podemos ceder estas Condiciones a una filial o en el contexto de una fusión o adquisición.</li>
            <li style={liStyle}><strong>Fuerza mayor:</strong> Ninguna de las partes será responsable por retrasos o incumplimientos causados por circunstancias fuera de su control razonable.</li>
          </ul>
        </div>

        <div style={dividerStyle} />

        {/* 18 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>18. Contacto</h2>
          <p style={pStyle}>
            Para consultas sobre estas Condiciones del Servicio:
          </p>
          <div style={{ padding: '20px 24px', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)' }}>
            <p style={{ ...pStyle, margin: '0 0 6px' }}><strong>{COMPANY}</strong></p>
            <p style={{ ...pStyle, margin: '0 0 6px' }}>{COMPANY_ID}</p>
            <p style={{ ...pStyle, margin: '0 0 6px' }}>{COMPANY_ADDRESS}</p>
            <p style={{ ...pStyle, margin: 0 }}>
              Correo: <a href={`mailto:${EMAIL_LEGAL}`} style={{ color: 'var(--wine)' }}>{EMAIL_LEGAL}</a>
            </p>
          </div>
        </div>

        <div style={{ marginTop: 48, padding: '16px 0', borderTop: '1px solid var(--line)', display: 'flex', gap: 20, flexWrap: 'wrap' }}>
          <Link to="/" style={{ color: 'var(--wine)', font: '500 14px/1 var(--font-sans)', textDecoration: 'none' }}>← Volver al inicio</Link>
          <Link to="/politicas-de-privacidad" style={{ color: 'var(--ink-3)', font: '500 14px/1 var(--font-sans)', textDecoration: 'none' }}>Política de Privacidad →</Link>
        </div>
      </div>

      <Footer />
    </div>
  );
}
