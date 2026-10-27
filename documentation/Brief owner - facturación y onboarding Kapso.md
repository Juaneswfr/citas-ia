# Brief para el dueño — facturación y onboarding con Kapso

**Fecha:** 27-10-2026 · **Tasa usada:** 3.157,94 COP por USD (TRM Banco de la República, 27/10/2026; dato entregado al PM, no lo verifiqué en la fuente).

## En una línea

Podemos empezar a probar en sandbox ya. **No podemos vender todavía**: faltan tarifas oficiales de Meta, rotar una clave expuesta y terminar el agente que agenda citas.

## Decisión tomada

- **Moneda:** cobramos en COP.
- **Modelo:** mensualidad con mensajes incluidos y cobro de excedente con margen.
- **Facturación de Kapso:** `partner_managed`. Los cargos de Meta se descuentan de los créditos de nuestro proyecto Kapso, y nosotros cobramos al negocio. Es decir, **nosotros pagamos a Meta primero**.
- **Arranque:** sandbox de Kapso (solo pruebas, no clientes reales). Luego piloto con un barbero.
- **Conexión del cliente:** coexistencia (el barbero conserva su app de WhatsApp Business).

## Planes propuestos (a confirmar por el dueño)

| Plan | Precio mensual | Equivalente USD | Mensajes incluidos |
|---|---|---|---|
| Esencial | 50.000 COP | 15,83 | por definir |
| Profesional | 90.000 COP | 28,50 | por definir |
| Profesional+ (opcional) | 100.000 COP | 31,67 | por definir |

- **Oferta de lanzamiento:** 50.000 COP al mes durante los 3 primeros meses, y luego el precio del plan. Supuesto mío: aplica a cualquier plan; confirmar. Costo de la oferta por cliente: 120.000 COP (plan de 90.000) o 150.000 COP (plan de 100.000) en los 3 meses.
- **Mensajes incluidos y excedente:** no los fijé porque dependen de la tarifa de Meta, que sigue sin confirmar (ver abajo). No invento cifras.
- Los precios y la cantidad de planes son una propuesta de trabajo; no hay una decisión final registrada de los planes concretos.

## Costos de referencia

| Concepto | Valor | Nota |
|---|---|---|
| Plataforma Kapso | 299 USD/mes ≈ **944.223 COP/mes** | Fijo, se paga con o sin clientes. Cifra entregada al PM; no la verifiqué en la página de precios |
| Mensajes de Meta | **Sin confirmar** | Ver "Qué falta confirmar" |
| IA (DeepSeek V4.1 Flash) | ≈ **4.000 COP/mes** por barbería con 300 citas al mes, sin caché | Estimación entregada al PM; no la recalculé |

**Cuántos clientes cubren la plataforma** (solo plataforma + IA, **antes de Meta**; cálculo propio con la tasa de arriba):

| Precio del plan | Margen por cliente tras IA | Clientes para cubrir 944.223 COP |
|---|---|---|
| 50.000 COP | 46.000 COP | 21 |
| 90.000 COP | 86.000 COP | 11 |
| 100.000 COP | 96.000 COP | 10 |

Durante la oferta de 50.000 COP, cada cliente aporta como un plan Esencial: hacen falta 21 clientes solo para cubrir la plataforma. Cualquier cargo de Meta que paguemos reduce estos márgenes.

## Qué falta confirmar antes de vender

1. **Tarifas oficiales de Meta para Colombia.** Las fuentes se contradicen sobre cómo se cobran los mensajes de servicio y de utilidad desde el 1-oct-2026. Sin esto no se pueden fijar mensajes incluidos ni excedente. Acción: validar con la tabla oficial de Meta o con Kapso.
2. **Que el managed billing de Kapso aplique a coexistencia.** El plan de implementación lo asume; no está comprobado. Acción: confirmarlo con Kapso o probarlo en el sandbox y mirar el descuento de créditos.
3. **Plantillas de recordatorio:** nombre e idioma aprobados por Meta. Aún no existen en el proyecto.
4. **Mensajes incluidos por plan** y precio del excedente (depende del punto 1).

## Riesgos

- **Clave de Kapso expuesta (crítico).** Estuvo en un archivo versionado de un repositorio público (`.mcp.json`, commit `4d462a7`). Ya se quitó del código actual y el archivo se ignora, pero **sigue en el historial**. Debe rotarse en Kapso; hasta entonces hay que tratarla como comprometida. La rotación no está hecha.
- **El agente que agenda citas aún no está terminado.** Conectar el número no basta; hoy no hay reservas automáticas de punta a punta. No se debe vender como funcional.
- **Riesgo de caja por `partner_managed`:** pagamos Meta antes de cobrar. Un negocio con mucho tráfico puede consumir créditos. Conviene monitorear consumo por cliente y definir el excedente.
- **Servidor público caído:** `hilo.esjuanez.com` devolvía HTTP 503 según el plan de implementación (no lo reverifiqué hoy). Sin eso no se prueban webhooks reales.
- **Costo fijo:** 944.223 COP al mes desde el primer día; con la oferta de 50.000 COP el punto de equilibrio exige unos 21 clientes.
- **Tasa de cambio:** el costo de plataforma está en USD; si el dólar sube, sube el costo en COP. La tasa usada es la del 27/10/2026.

## Decisiones que necesito del dueño

1. ¿Aprueba `partner_managed` (pagamos Meta y cobramos al negocio)?
2. ¿Aprueba coexistencia como única opción de conexión al inicio?
3. ¿Qué planes y precios finales (50.000 / 90.000 / 100.000)? ¿La oferta de 50.000 aplica a todos?
4. Autorizar la rotación de la clave de Kapso (no hace falta enviarme el valor).
5. Autorizar el piloto con un barbero cuando el agente y el servidor estén listos.
