import { createFileRoute, Link } from "@tanstack/react-router";
import { LegalLayout, LEGAL_HEAD_LINKS } from "@/components/legal/LegalLayout";

export const Route = createFileRoute("/condiciones-del-servicio")({
  head: () => ({
    links: LEGAL_HEAD_LINKS,
    meta: [
      { title: "Condiciones del Servicio · Zumit" },
      { name: "description", content: "Lee los términos y condiciones que rigen el uso de la plataforma Zumit." },
    ],
  }),
  component: TermsPage,
});

const LAST_UPDATED = "21 de noviembre de 2026";
const COMPANY = "Juan Esteban Ramírez Ávila";
const COMPANY_ID = "C.C. 1007298045";
const COMPANY_ADDRESS = "Calle 39 # 43a-109, Colombia";
const EMAIL_LEGAL = "contacto@zumit.app";
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

function TermsPage() {
  return (
    <LegalLayout title="Condiciones del Servicio" updated={LAST_UPDATED} current="/condiciones-del-servicio">

        <p style={{ ...pStyle, font: '400 17px/1.65 var(--font-sans)', color: 'var(--ink-1)', marginBottom: 40, padding: '20px 24px', background: 'var(--paper)', border: '1px solid var(--line)', borderRadius: 'var(--r-lg)' }}>
          Bienvenido a <strong>Zumit</strong>, operado por <strong>{COMPANY}</strong>. Al registrarte o usar cualquier parte de nuestro servicio disponible en <strong>{DOMAIN}</strong>, aceptas quedar vinculado por estas Condiciones del Servicio. Lee este documento detenidamente antes de usar la plataforma.
        </p>

        {/* 1 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>1. Descripción del servicio</h2>
          <p style={pStyle}>
            Zumit es una plataforma SaaS (Software como Servicio) que permite a negocios de servicios —como barberías, salones, spas, consultorios, veterinarias y similares que atienden con cita— automatizar el agendamiento de citas a través de WhatsApp mediante un agente de inteligencia artificial.
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
            Al crear una cuenta, acceder o usar Zumit, declaras que:
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
            Para usar Zumit debes crear una cuenta con un correo electrónico válido y una contraseña segura. Cada cuenta corresponde a un único espacio de trabajo (workspace) vinculado a un negocio.
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
            Zumit utiliza la API oficial de WhatsApp Business de Meta. Al conectar tu número de WhatsApp, también aceptas los <a href="https://www.whatsapp.com/legal/business-policy" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--wine)' }}>Términos de Servicio de WhatsApp Business</a> y las <a href="https://developers.facebook.com/policy/" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--wine)' }}>Políticas de Plataforma de Meta</a>.
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
          <p style={pStyle}>
            Los planes, precios, ciclos de facturación, citas y profesionales adicionales, mensajes de WhatsApp, mora, cancelación y reembolsos se rigen por las <Link to="/condiciones-de-pago" style={{ color: 'var(--wine)' }}>Condiciones de Pago</Link>, que forman parte de estas Condiciones. Si hay diferencia entre ambos documentos sobre pagos, prevalecen las Condiciones de Pago.
          </p>
          <p style={pStyle}>
            En resumen: la prueba es de 7 días, gratis y sin tarjeta; los precios están en pesos colombianos (COP); el cobro es mensual por adelantado mediante cuenta de cobro; y la cancelación tiene efecto al final del ciclo pagado.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 6 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>6. Conducta del usuario y usos prohibidos</h2>
          <p style={pStyle}>Al usar Zumit te comprometes a <strong>no</strong>:</p>
          <ul style={ulStyle}>
            <li style={liStyle}>Violar leyes o regulaciones aplicables, incluyendo las de protección de datos.</li>
            <li style={liStyle}>Usar el servicio para enviar mensajes de spam, phishing o cualquier comunicación no solicitada masiva.</li>
            <li style={liStyle}>Intentar acceder sin autorización a sistemas, cuentas o datos de otros usuarios.</li>
            <li style={liStyle}>Realizar ingeniería inversa, descompilar o desensamblar el software de Zumit.</li>
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
          <h3 style={h3Style}>7.1 Propiedad de Zumit</h3>
          <p style={pStyle}>
            Zumit y todo su contenido (software, diseño, logotipos, textos, gráficos) son propiedad exclusiva de {COMPANY} o sus licenciantes y están protegidos por las leyes de propiedad intelectual aplicables. Nada en estas Condiciones te transfiere propiedad sobre dichos elementos.
          </p>
          <h3 style={h3Style}>7.2 Licencia de uso</h3>
          <p style={pStyle}>
            Sujeto al cumplimiento de estas Condiciones y al pago de las tarifas aplicables, {COMPANY} te otorga una licencia limitada, no exclusiva, intransferible y revocable para acceder y usar el servicio únicamente para los fines comerciales previstos.
          </p>
          <h3 style={h3Style}>7.3 Contenido del usuario</h3>
          <p style={pStyle}>
            Conservas la propiedad de los datos e información que introduces en Zumit (datos de tu negocio, servicios, información de clientes). Nos otorgas una licencia limitada para procesar dicha información únicamente con el fin de prestar el servicio.
          </p>
        </div>

        <div style={dividerStyle} />

        {/* 8 */}
        <div style={sectionStyle}>
          <h2 style={h2Style}>8. Disponibilidad y nivel de servicio</h2>
          <p style={pStyle}>
            Zumit se presta "tal como está" y nos esforzamos por mantener una disponibilidad del 99,5% mensual, excluidos los mantenimientos programados. No garantizamos que el servicio sea ininterrumpido, libre de errores o que cumpla todos los requisitos específicos de tu negocio.
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
          <h3 style={h3Style}>11.2 Terminación por Zumit</h3>
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
            El agente de Zumit está impulsado por modelos de inteligencia artificial. Debes entender que:
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
            Zumit se integra con servicios de terceros (Meta/WhatsApp, Google Calendar, Anthropic). Estas integraciones están sujetas a los términos y condiciones de dichos terceros. {COMPANY} no es responsable del funcionamiento, disponibilidad o cambios en los servicios de terceros.
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

    </LegalLayout>
  );
}
