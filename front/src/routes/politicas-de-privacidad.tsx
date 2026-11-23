import { createFileRoute, Link } from "@tanstack/react-router";
import { LegalLayout, LEGAL_HEAD_LINKS } from "@/components/legal/LegalLayout";

export const Route = createFileRoute("/politicas-de-privacidad")({
  head: () => ({
    links: LEGAL_HEAD_LINKS,
    meta: [
      { title: "Política de Privacidad · Zumit" },
      { name: "description", content: "Conoce cómo Zumit recopila, usa y protege tu información personal." },
    ],
  }),
  component: PrivacyPage,
});

const LAST_UPDATED = "21 de noviembre de 2026";
const COMPANY = "Juan Esteban Ramírez Ávila";
const COMPANY_ID = "C.C. 1007298045";
const COMPANY_ADDRESS = "Calle 39 # 43a-109, Colombia";
const EMAIL_PRIVACY = "contacto@zumit.app";
const DOMAIN = "zumit.app";

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

function PrivacyPage() {
  return (
    <LegalLayout title="Política de Privacidad" updated={LAST_UPDATED} current="/politicas-de-privacidad">

        <p style={{ ...pStyle, font: '400 17px/1.65 var(--font-sans)', color: 'var(--ink-1)', marginBottom: 40, padding: '20px 24px', background: 'var(--wine-50)', border: '1px solid var(--wine-100)', borderRadius: 'var(--r-lg)' }}>
          En <strong>{COMPANY}</strong> operamos la plataforma <strong>Zumit</strong> disponible en <strong>{DOMAIN}</strong>. Esta Política de Privacidad explica cómo recopilamos, usamos, almacenamos y protegemos tu información cuando usas nuestro servicio.
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
            <li style={liStyle}><strong>Datos de conversación:</strong> mensajes intercambiados entre el agente de Zumit y los clientes finales a través de WhatsApp.</li>
          </ul>

          <h3 style={h3Style}>2.3 Información de terceros</h3>
          <ul style={ulStyle}>
            <li style={liStyle}><strong>Meta (WhatsApp):</strong> datos de la cuenta de WhatsApp Business y métricas de mensajería entregados por la API de Meta.</li>
            <li style={liStyle}><strong>Google:</strong> información básica de perfil (nombre y correo) si creas tu cuenta o inicias sesión con Google, y datos de calendario si conectas Google Calendar.</li>
            <li style={liStyle}><strong>Facebook (Meta):</strong> nombre, identificador y correo electrónico si creas tu cuenta o inicias sesión con Facebook. No accedemos a tus publicaciones, contactos ni amistades.</li>
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
            Algunos de nuestros proveedores están ubicados fuera de Colombia (Meta, Google, Anthropic). Estas transferencias se realizan bajo las garantías adecuadas previstas en la Ley 1581 de 2012 y el GDPR cuando aplica, incluyendo cláusulas contractuales estándar o escudos de privacidad reconocidos.
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
          <h3 style={h3Style}>Cómo solicitar la eliminación de tus datos</h3>
          <p style={pStyle}>
            Si creaste tu cuenta con Facebook o con Google, o quieres que borremos tu cuenta y los datos asociados, escríbenos a <a href={`mailto:${EMAIL_PRIVACY}`} style={{ color: 'var(--wine)' }}>{EMAIL_PRIVACY}</a> desde el correo de tu cuenta con el asunto «Eliminar mis datos». Verificamos que la solicitud es tuya, eliminamos tu cuenta y la información asociada en un plazo máximo de 15 días hábiles y te lo confirmamos por correo. Además, puedes quitar el acceso de Zumit desde la configuración de Facebook (Configuración › Aplicaciones y sitios web) o de tu cuenta de Google.
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
            Cuando usas Zumit, tu negocio actúa como responsable del tratamiento de los datos personales de tus clientes (números de teléfono, nombres, conversaciones). Zumit actúa como encargado del tratamiento en tu nombre.
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
            Zumit está dirigido exclusivamente a personas mayores de 18 años que actúen en calidad de comerciantes o empresarios. No recopilamos conscientemente datos de menores de edad. Si detectamos que hemos recopilado datos de un menor, los eliminaremos de inmediato.
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

    </LegalLayout>
  );
}
