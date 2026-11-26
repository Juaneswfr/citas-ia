import { createFileRoute, Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { LegalLayout, LEGAL_HEAD_LINKS } from "@/components/legal/LegalLayout";
import styles from "./condiciones-de-pago.module.css";

export const Route = createFileRoute("/condiciones-de-pago")({
  head: () => ({
    links: LEGAL_HEAD_LINKS,
    meta: [
      { title: "Condiciones de Pago · Zumit" },
      { name: "description", content: "Planes, precios, ciclos de cobro, citas adicionales, mora y cancelación de Zumit." },
    ],
  }),
  component: PaymentTermsPage,
});

const LAST_UPDATED = "21 de noviembre de 2026";
const COMPANY = "Juan Esteban Ramírez Ávila";
const EMAIL = "contacto@zumit.app";
const DOMAIN = "zumit.app";

type Block = { title: string; body: ReactNode };

const Mail = () => <a href={`mailto:${EMAIL}`}>{EMAIL}</a>;

const PAY_FAQS: [string, string][] = [
  ["¿Necesito tarjeta para la prueba?", "No. La prueba es de 7 días, gratis y sin tarjeta."],
  ["¿Qué pasa cuando termina la prueba?", "Si no activas un plan, tu cuenta queda en pausa y tus datos se conservan 30 días."],
  ["¿Cuándo termina el descuento de lanzamiento?", "Después de 3 ciclos de facturación, contados desde que el asistente empieza a atender clientes reales por tu número. Desde el cuarto ciclo se cobra el valor real."],
  ["¿Qué cuenta como una cita?", "Solo las que crea el asistente. Las que registras a mano en el panel y los reagendamientos no cuentan, y cancelar una cita no la devuelve al saldo."],
  ["¿Qué pasa si me paso del límite de citas?", "Te avisamos al llegar al 80 %. El asistente sigue agendando hasta 20 citas más de margen y luego deja de agendar y les indica a tus clientes que los atenderás directamente. Retomas cargando citas adicionales o al iniciar el siguiente ciclo."],
  ["¿Cuánto cuesta WhatsApp?", "Las conversaciones que inicia tu cliente no tienen costo de plantilla. Los recordatorios y seguimientos los cobra Meta: no están en el plan, los ves en el panel y se cobran al costo."],
  ["¿Cómo pago?", "Con cuenta de cobro, mensual y por adelantado. Te avisamos por correo 3 días antes de cada cobro y te indicamos cómo pagar cuando te la entregamos."],
  ["¿Puedo cambiar de plan?", "Sí. Al subir pagas solo la diferencia proporcional a los días que quedan del ciclo; al bajar, aplica en el siguiente ciclo."],
  ["¿Puedo cancelar cuando quiera?", "Sí. La cancelación aplica al final del ciclo pagado y conservas tus datos 30 días para exportarlos."],
  ["¿Qué pasa si dejo de pagar?", "Te avisamos, tienes 5 días de gracia y luego el asistente se pausa. El panel sigue disponible y tus datos se conservan 30 días. Al pagar lo adeudado, el servicio se reactiva."],
  ["¿Qué pasa si me cobraron de más?", "Tienes 15 días desde el cobro para reclamar un cobro duplicado o mal hecho."],
];

const BLOCKS: Block[] = [
  {
    title: "1. Alcance",
    body: (
      <>
        <p>
          Estas Condiciones de Pago regulan el cobro del servicio Zumit disponible en <strong>{DOMAIN}</strong>, operado por{" "}
          <strong>{COMPANY}</strong> («Zumit»). Forman parte de las <Link to="/condiciones-del-servicio">Condiciones del Servicio</Link>; en
          materia de pagos prevalecen sobre ellas. El «Cliente» es el negocio que contrata el servicio.
        </p>
        <p>Todos los valores están en pesos colombianos (COP).</p>
      </>
    ),
  },
  {
    title: "2. Planes",
    body: (
      <>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr><th></th><th>Emprendedor</th><th>Equipo</th></tr>
            </thead>
            <tbody>
              <tr><td>Citas reservadas por el asistente al mes</td><td>hasta 250</td><td>hasta 550</td></tr>
              <tr><td>Profesionales</td><td>hasta 3</td><td>hasta 6</td></tr>
              <tr><td>Valor real al mes</td><td>$120.000</td><td>$285.000</td></tr>
              <tr><td>Precio de lanzamiento (3 primeros ciclos, 58 % menos)</td><td>$50.000</td><td>$120.000</td></tr>
              <tr><td>Prueba</td><td>7 días gratis</td><td>7 días gratis</td></tr>
            </tbody>
          </table>
        </div>
        <p>Los dos planes incluyen el asistente de agendamiento por WhatsApp, la agenda con un calendario por profesional, el historial de citas, la caja, la lectura de comprobantes de pago y los recordatorios.</p>
        <p>El plan Equipo incluye además liquidaciones y pagos a profesionales (comisión, alquiler de silla y propinas) y el informe semanal de ingresos.</p>
      </>
    ),
  },
  {
    title: "3. Qué cuenta como cita reservada",
    body: (
      <>
        <p>Cuenta la cita que <strong>crea el asistente</strong> de Zumit. No cuentan las citas que el Cliente o su equipo crean a mano en el panel, ni reagendar una cita.</p>
        <p>La cita se cuenta cuando se crea. Si después se cancela, no se devuelve al saldo. Las citas incluidas en el plan no se acumulan: se reinician en cada ciclo.</p>
      </>
    ),
  },
  {
    title: "4. Prueba gratuita",
    body: (
      <ul>
        <li>La prueba dura 7 días, es gratis y no pide tarjeta.</li>
        <li>Se realiza en un entorno de pruebas, sin conectar el número real de WhatsApp, y permite hasta 3 profesionales.</li>
        <li>Al día 8, si no hay un plan pago, la cuenta queda en pausa y los datos se conservan 30 días.</li>
        <li>Meta exige 7 días de actividad para conectar un número a WhatsApp Business; el Cliente debe hacer ese cambio el primer día de la prueba.</li>
      </ul>
    ),
  },
  {
    title: "5. Descuento de lanzamiento",
    body: (
      <ul>
        <li>58 % menos en el valor del plan durante los <strong>3 primeros ciclos de facturación</strong>.</li>
        <li>Los 3 ciclos empiezan a contar desde la activación, que es el día en que el asistente empieza a atender clientes reales por el número del Cliente; no desde el registro ni desde la prueba.</li>
        <li>Si el Cliente cambia de plan durante esos ciclos, los que le falten siguen con descuento en el plan nuevo.</li>
        <li>El descuento aplica solo al plan: no aplica a citas adicionales, profesionales adicionales ni mensajes de WhatsApp.</li>
        <li>Desde el cuarto ciclo se cobra el valor real. No se acumula con otros descuentos.</li>
        <li>La prueba y el descuento se otorgan una sola vez por número de WhatsApp: quien cancela y se registra de nuevo con el mismo número paga el valor real.</li>
      </ul>
    ),
  },
  {
    title: "6. Ciclo de facturación y cobro",
    body: (
      <ul>
        <li><strong>Mensual y por adelantado.</strong> El primer cobro es el día de la activación y los siguientes, el mismo día de cada mes. Si el mes no tiene ese día, se cobra el último día del mes.</li>
        <li><strong>Renovación automática.</strong> El plan se renueva cada ciclo hasta que el Cliente cancele. Zumit avisa por correo 3 días antes de cada cobro.</li>
        <li><strong>Documento de cobro.</strong> Zumit emite una cuenta de cobro por cada ciclo. El Cliente debe entregar su nombre o razón social, cédula o NIT y un correo de cobro (en Ajustes › Plan y facturación).</li>
        <li><strong>Medio de pago.</strong> Zumit indica al Cliente cómo pagar cuando le entrega la cuenta de cobro. El Cliente debe enviar el comprobante por el canal que Zumit indique.</li>
        <li><strong>Pagos confirmados por Zumit.</strong> El plan se activa o renueva cuando Zumit confirma el pago.</li>
        <li><strong>Impuestos.</strong> Los valores se cobran mediante cuenta de cobro y no discriminan IVA. Si la ley exige otro tratamiento tributario, se informará al Cliente con antelación.</li>
      </ul>
    ),
  },
  {
    title: "7. Citas adicionales",
    body: (
      <>
        <p>Cuando el Cliente necesite más citas que las de su plan, puede sumar un bloque a su mensualidad: <strong>$500 por cita</strong>, sin descuento de lanzamiento.</p>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead><tr><th>Bloque</th><th>Precio al mes</th></tr></thead>
            <tbody>
              <tr><td>50 citas</td><td>$25.000</td></tr>
              <tr><td>100 citas</td><td>$50.000</td></tr>
              <tr><td>200 citas</td><td>$100.000</td></tr>
              <tr><td>300 citas</td><td>$150.000</td></tr>
            </tbody>
          </table>
        </div>
        <ul>
          <li>El bloque se reinicia cada ciclo. Las citas no usadas vencen al cierre del ciclo y no se acumulan.</li>
          <li>El Cliente puede cambiar o quitar el bloque para el ciclo siguiente en cualquier momento antes del cierre del ciclo en curso.</li>
          <li>Si necesita citas a mitad de ciclo, puede cargar una recarga puntual al mismo precio por cita, que vence al cierre de ese ciclo.</li>
          <li>Las citas adicionales no tienen reembolso.</li>
        </ul>
      </>
    ),
  },
  {
    title: "8. Cuando se acaban las citas",
    body: (
      <ul>
        <li>Al llegar al 80 % de las citas del plan más las adicionales, Zumit avisa al Cliente por el panel.</li>
        <li>Si el Cliente se pasa del total, el asistente sigue agendando hasta 20 citas más como margen y se lo informa.</li>
        <li>Pasado ese margen, el asistente deja de agendar y a los clientes finales les indica que el negocio los atenderá directamente. El asistente sigue pudiendo mover, cancelar y consultar citas.</li>
        <li>El Cliente retoma el agendamiento cargando citas adicionales o al iniciar el siguiente ciclo.</li>
      </ul>
    ),
  },
  {
    title: "9. Profesional adicional",
    body: (
      <>
        <p>Cada profesional por encima del límite del plan cuesta <strong>$40.000 al mes</strong>, sin descuento de lanzamiento. Se cobra desde el día en que se crea, proporcional a los días que le quedan al ciclo; en los ciclos siguientes se cobra completo.</p>
        <p>Por ahora no existe un plan superior a Equipo.</p>
      </>
    ),
  },
  {
    title: "10. Mensajes de WhatsApp",
    body: (
      <ul>
        <li>El costo de los mensajes de plantilla de WhatsApp (recordatorios, seguimientos y mensajes para que el cliente vuelva) es <strong>variable y lo define Meta</strong>. No está incluido en el precio del plan.</li>
        <li>Zumit muestra en el panel cuántos mensajes de plantilla se enviaron en el ciclo y la tarifa de Meta vigente.</li>
        <li>Zumit cobra esos mensajes al costo, al cierre de cada ciclo, y avisará al Cliente antes de aplicar el cobro.</li>
        <li>Los mensajes que inicia el cliente final y la conversación dentro de las 24 horas siguientes no tienen costo de plantilla.</li>
        <li>Si el Cliente no paga lo que debe por estos mensajes, Zumit podrá pausar solo el envío de plantillas, sin pausar el resto del servicio.</li>
      </ul>
    ),
  },
  {
    title: "11. Cambios de plan",
    body: (
      <>
        <p><strong>Subir de plan.</strong> Se aplica de inmediato y se cobra la diferencia proporcional a los días que quedan del ciclo:</p>
        <p className={styles.formula}>(precio del plan nuevo − precio del plan actual) × días restantes del ciclo ÷ días del ciclo</p>
        <p>Ejemplo: un Cliente en Emprendedor con descuento, a los 15 días de un ciclo de 30, sube a Equipo con descuento. Paga ($120.000 − $50.000) × 15 ÷ 30 = $35.000. Las citas ya usadas cuentan contra el límite del plan nuevo.</p>
        <p><strong>Bajar de plan.</strong> Se aplica en el siguiente ciclo. Antes, el Cliente debe ajustarse a los límites del plan menor (profesionales y citas del ciclo); Zumit le avisa si no cumple. Conserva los ciclos con descuento que le falten.</p>
      </>
    ),
  },
  {
    title: "12. Ejemplos de cobro",
    body: (
      <ul>
        <li><strong>Emprendedor con descuento, activado el 5 de enero:</strong> $50.000 el 5 de enero, el 5 de febrero y el 5 de marzo; desde el 5 de abril, $120.000.</li>
        <li><strong>Con citas adicionales:</strong> si ese mismo Cliente suma 100 citas en febrero, paga $50.000 del plan + $50.000 del bloque = $100.000. Si mantiene el bloque en marzo, $100.000; si lo quita antes del cierre, $50.000.</li>
        <li><strong>Equipo sin descuento, con bloque de 100 citas y un profesional adicional:</strong> $285.000 + $50.000 + $40.000 = $375.000, más los mensajes de Meta del ciclo.</li>
      </ul>
    ),
  },
  {
    title: "13. Mora, suspensión y reactivación",
    body: (
      <ul>
        <li>El cobro vence el día del ciclo. Si no se recibe el pago, Zumit avisa al Cliente por correo y en el panel.</li>
        <li>Si pasan 5 días sin pago, el asistente se pausa y deja de atender a los clientes finales. El panel sigue disponible.</li>
        <li>Los datos se conservan 30 días desde la suspensión; en ese tiempo el Cliente puede exportarlos. Zumit no elimina datos automáticamente: la eliminación la decide y confirma una persona.</li>
        <li>El servicio se reactiva al pagar lo adeudado. Mientras esté pausado no hay descuento ni congelamiento nuevo.</li>
      </ul>
    ),
  },
  {
    title: "14. Cancelación y reembolsos",
    body: (
      <ul>
        <li>El Cliente puede cancelar en cualquier momento, desde el panel o escribiendo a <Mail />.</li>
        <li>La cancelación tiene efecto al final del ciclo pagado: el Cliente conserva el servicio hasta esa fecha.</li>
        <li>No hay reembolso del ciclo en curso, de las citas adicionales ni de los mensajes de Meta, salvo que la ley lo exija o Zumit haya incumplido materialmente el servicio.</li>
        <li>El Cliente que cancela conserva sus datos 30 días para exportarlos; después se eliminan.</li>
      </ul>
    ),
  },
  {
    title: "15. Errores de cobro",
    body: (
      <p>El Cliente tiene 15 días desde el cobro para reclamar un cobro duplicado o mal hecho, escribiendo a <Mail />. Zumit corregirá el error o devolverá lo cobrado de más.</p>
    ),
  },
  {
    title: "16. Cambios de precio",
    body: (
      <>
        <p>Zumit puede cambiar el valor real de los planes y de los extras avisando con 30 días de antelación por correo y por el panel. El cambio no afecta el ciclo ya pagado.</p>
        <p>Como los costos de algunos proveedores (infraestructura, inteligencia artificial y WhatsApp) están en dólares, Zumit podrá revisar los precios si la tasa de cambio varía de forma significativa y, de cambiarlos, avisará con el mismo plazo.</p>
      </>
    ),
  },
  {
    title: "17. Miembros Zumit Member",
    body: (
      <ul>
        <li>El cupo es de 30 negocios. Es miembro Zumit Member el Cliente que se registre y active su plan dentro del cupo.</li>
        <li>Recibe, sin costo adicional: insignia Member, canal directo con Zumit, entrada anticipada a nuevas etapas y el kit de miembro.</li>
        <li>Pierde estos beneficios si incumple las Condiciones o cae en mora de más de 30 días.</li>
      </ul>
    ),
  },
  {
    title: "18. Preguntas frecuentes sobre pagos",
    body: (
      <>
        {PAY_FAQS.map(([q, a]) => (
          <div key={q} className={styles.qa}>
            <h3 className={styles.q}>{q}</h3>
            <p>{a}</p>
          </div>
        ))}
      </>
    ),
  },
  {
    title: "19. Contacto",
    body: (
      <p>Para preguntas sobre cobros, cuentas de cobro o planes escribe a <Mail />. Responsable: <strong>{COMPANY}</strong>, Colombia.</p>
    ),
  },
];

function PaymentTermsPage() {
  return (
    <LegalLayout title="Condiciones de Pago" updated={LAST_UPDATED} current="/condiciones-de-pago">
      {BLOCKS.map((b) => (
        <section key={b.title} className={styles.block}>
          <h2 className={styles.h2}>{b.title}</h2>
          {b.body}
        </section>
      ))}
    </LegalLayout>
  );
}
