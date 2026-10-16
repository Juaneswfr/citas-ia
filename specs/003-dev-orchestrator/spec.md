# Feature Specification: Orquestador de Desarrollo Local

**Feature Branch**: `003-dev-orchestrator`

**Created**: 2026-10-16

**Status**: Draft

**Input**: User description: "Orquestador de desarrollo local en la raíz del proyecto: un comando único que levante backend y frontend en paralelo, con variante que incluya el servidor del agente (langgraph), logs prefijados y coloreados por servicio, detención en cascada si un proceso muere, apagado limpio con Ctrl+C sin procesos huérfanos, y un dashboard de estado de solo lectura con endpoint JSON, accesible únicamente desde la máquina local. No debe romper docker-compose ni la estructura existente; el frontend es un submódulo git y no se modifica."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Levantar el entorno de desarrollo con un solo comando (Priority: P1)

Como desarrollador, desde la raíz del repositorio ejecuto un único comando (`npm run dev`) y se inician en paralelo el frontend (puerto 5173) y el backend (puerto 8000). Veo en una sola terminal los logs de ambos, cada línea prefijada con el nombre del servicio y con un color distinto.

**Why this priority**: Es el valor central: eliminar abrir varias terminales y recordar comandos distintos por servicio.

**Independent Test**: Ejecutar el comando en un repo recién clonado con dependencias instaladas; verificar que el frontend responde en el puerto 5173 y el backend en el 8000, y que cada línea de log lleva el prefijo de su servicio.

**Acceptance Scenarios**:

1. **Given** dependencias instaladas y puertos libres, **When** ejecuto `npm run dev` en la raíz, **Then** frontend y backend arrancan en paralelo y ambos quedan accesibles en sus puertos.
2. **Given** ambos servicios emitiendo logs, **When** observo la terminal, **Then** cada línea está prefijada con el nombre del servicio y los servicios se distinguen por color.
3. **Given** que quiero incluir el servidor del agente, **When** ejecuto `npm run dev:all`, **Then** además de frontend y backend se inicia el servidor del agente (puerto 8123) con su propio prefijo y color.

---

### User Story 2 - Fallo de un servicio detiene el resto con diagnóstico claro (Priority: P1)

Como desarrollador, si cualquiera de los procesos termina inesperadamente, el orquestador me indica qué servicio murió y con qué código de salida o señal, y detiene los demás servicios para no dejar un entorno a medias.

**Why this priority**: Un entorno parcialmente levantado produce errores confusos; el diagnóstico inmediato ahorra tiempo de depuración.

**Independent Test**: Matar manualmente un servicio (o provocar un error de arranque) y verificar el mensaje con servicio y código/señal, y que los demás procesos terminan.

**Acceptance Scenarios**:

1. **Given** el entorno corriendo, **When** un servicio termina con código distinto de cero, **Then** se muestra un mensaje con el nombre del servicio y el código, y se detienen los demás servicios.
2. **Given** el entorno corriendo, **When** un servicio es terminado por una señal, **Then** el mensaje indica el servicio y la señal.
3. **Given** un servicio que falla al arrancar (p. ej. puerto ocupado), **When** ocurre, **Then** el orquestador termina con código de salida distinto de cero.

---

### User Story 3 - Apagado limpio con Ctrl+C (Priority: P1)

Como desarrollador, al pulsar Ctrl+C se detiene todo el árbol de procesos (incluidos subprocesos que cada servicio haya lanzado, como recargadores o workers) y no quedan procesos huérfanos ocupando puertos.

**Why this priority**: Los huérfanos bloquean puertos y causan fallos en el siguiente arranque, degradando la confianza en la herramienta.

**Independent Test**: Iniciar el entorno, pulsar Ctrl+C, y verificar que los puertos 5173/8000/8123 quedan libres y no hay procesos residuales de los servicios.

**Acceptance Scenarios**:

1. **Given** el entorno corriendo, **When** pulso Ctrl+C, **Then** todos los servicios y sus subprocesos terminan y los puertos quedan libres en pocos segundos.
2. **Given** un apagado reciente, **When** vuelvo a ejecutar el comando, **Then** arranca sin errores de puerto ocupado.
3. **Given** un servicio que no responde a la solicitud de cierre, **When** transcurre un tiempo de gracia, **Then** se fuerza su terminación.

---

### User Story 4 - Dashboard de estado local (Priority: P2)

Como desarrollador, abro una página local que muestra de un vistazo si cada servicio (frontend, backend, agente) está activo o caído, y puedo consultar la misma información en formato JSON para scripts o herramientas.

**Why this priority**: Aporta visibilidad rápida, pero el entorno es utilizable sin ella.

**Independent Test**: Con el entorno levantado, abrir la raíz del dashboard y consultar el endpoint JSON; detener un servicio y verificar que el estado cambia a caído.

**Acceptance Scenarios**:

1. **Given** el entorno corriendo, **When** abro el dashboard, **Then** veo cada servicio con su puerto y estado (activo/caído).
2. **Given** el entorno corriendo, **When** consulto `/api/status`, **Then** recibo JSON con el estado de cada servicio.
3. **Given** un servicio detenido, **When** consulto el estado, **Then** ese servicio aparece como caído sin que el dashboard falle.
4. **Given** el dashboard en ejecución, **When** intento acceder desde otra máquina de la red, **Then** la conexión no es posible (solo acepta conexiones locales).
5. **Given** el dashboard, **When** envío cualquier método que no sea de lectura, **Then** es rechazado; el dashboard no puede iniciar, detener ni modificar servicios.

---

### User Story 5 - Convivencia con la infraestructura existente (Priority: P2)

Como equipo, necesitamos que esta herramienta no altere el despliegue con docker-compose ni el código de `front-app/` (submódulo git) ni de `backend-lang/`.

**Why this priority**: Es una restricción de no regresión; romper el despliegue tendría costo alto.

**Independent Test**: Revisar que el cambio solo añade archivos en la raíz y que `docker compose config` produce el mismo resultado antes y después; el estado del submódulo no cambia.

**Acceptance Scenarios**:

1. **Given** el cambio aplicado, **When** valido el compose, **Then** su configuración es idéntica a la previa.
2. **Given** el cambio aplicado, **When** reviso el estado del submódulo `front-app`, **Then** no tiene modificaciones.

---

### Edge Cases

- Puerto requerido ya ocupado al arrancar: el servicio falla, se informa claramente y se detiene el resto.
- Herramienta requerida ausente (gestor de paquetes de Python no instalado, dependencias sin instalar): mensaje accionable indicando qué falta.
- El servidor del agente no está incluido (`npm run dev`): el dashboard lo muestra como "no incluido" y no como caído.
- Servicio arrancando (puerto aún sin responder): el dashboard lo reporta como caído transitorio sin error.
- Doble Ctrl+C: fuerza la salida inmediata sin dejar huérfanos.
- Puerto del dashboard ocupado: mensaje claro; no impide que los demás servicios funcionen.
- Cierre de la terminal (señal de hangup/terminación): se trata igual que Ctrl+C.
- Variables de entorno o secretos del backend: no se exponen en logs del orquestador ni en el dashboard.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: El proyecto MUST ofrecer en la raíz un comando `dev` que inicie frontend y backend en paralelo.
- **FR-002**: El proyecto MUST ofrecer un comando `dev:all` que inicie frontend, backend y servidor del agente.
- **FR-003**: Cada línea de salida de cada servicio MUST mostrarse prefijada con su nombre y coloreada de forma distinta por servicio.
- **FR-004**: Si cualquier proceso termina (por código o señal), el sistema MUST informar el nombre del servicio y el código o señal, y MUST detener los demás procesos.
- **FR-005**: El orquestador MUST terminar con código de salida distinto de cero cuando el cierre se debe al fallo de un servicio.
- **FR-006**: Ante Ctrl+C (y señales de terminación), el sistema MUST detener todo el árbol de procesos, incluidos descendientes, sin dejar procesos huérfanos, con un tiempo de gracia tras el cual se fuerza la terminación.
- **FR-007**: El sistema MUST incluir un dashboard de estado servido en la ruta raíz que muestre, por servicio, nombre, puerto y estado (activo/caído/no incluido).
- **FR-008**: El sistema MUST exponer `/api/status` en JSON con el mismo estado por servicio.
- **FR-009**: El estado MUST determinarse mediante comprobaciones de conectividad a los puertos de cada servicio, con tiempo de espera acotado, sin que una comprobación lenta bloquee la respuesta.
- **FR-010**: El dashboard MUST ser de solo lectura: solo aceptar consultas de lectura y MUST NOT ofrecer acciones de control sobre los servicios.
- **FR-011**: El dashboard MUST aceptar conexiones únicamente desde la máquina local (127.0.0.1).
- **FR-012**: El dashboard MUST NOT exponer variables de entorno, secretos, rutas internas ni contenido de logs.
- **FR-013**: La solución MUST NOT modificar `docker-compose.yml`, `nginx/`, el contenido de `front-app/` (submódulo git) ni la lógica de `backend-lang/`.
- **FR-014**: Los puertos de servicios y del dashboard MUST ser configurables mediante variables de entorno con valores por defecto 5173, 8000, 8123 y un puerto propio del dashboard que no colisione con ellos ni con el 7000 de nginx.
- **FR-015**: Los errores por herramientas o dependencias ausentes MUST mostrar un mensaje accionable.
- **FR-016**: El repositorio MUST incluir documentación breve de uso (comandos, puertos, dashboard, solución de problemas) conforme al principio de documentación básica.
- **FR-017**: El código MUST seguir responsabilidad única (orquestación de procesos separada del servidor de estado) y la lógica de estado y de manejo de salida de procesos MUST ser verificable con pruebas automatizadas.

### Key Entities

- **Servicio**: componente del entorno local (frontend, backend, agente) con nombre, puerto, color de log, si es opcional y estado actual.
- **Estado de servicio**: resultado de la última comprobación (activo, caído, no incluido) con marca de tiempo.
- **Evento de salida**: registro de que un proceso terminó, con servicio y código o señal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Un desarrollador levanta el entorno completo con un único comando, sin abrir más de una terminal.
- **SC-002**: Frontend y backend están accesibles en menos de 60 segundos tras ejecutar el comando, en una máquina de desarrollo estándar con dependencias instaladas.
- **SC-003**: El 100% de las líneas de log de los servicios se identifican con su servicio de origen.
- **SC-004**: Ante la caída de un servicio, el mensaje de diagnóstico aparece y el resto se detiene en menos de 10 segundos.
- **SC-005**: Tras Ctrl+C, en 10 ciclos consecutivos de arranque/parada no quedan procesos residuales ni puertos ocupados.
- **SC-006**: El dashboard refleja un cambio de estado de un servicio en menos de 5 segundos.
- **SC-007**: El dashboard no es accesible desde ninguna otra máquina de la red.
- **SC-008**: La configuración de despliegue existente y el submódulo del frontend permanecen sin cambios tras la funcionalidad.

## Assumptions

- Los desarrolladores tienen instalados Node.js y el gestor de paquetes de Python que ya usa el backend, y han instalado dependencias de `front-app/` y `backend-lang/`.
- Es una herramienta exclusivamente de desarrollo local; no se usa en producción ni en contenedores, y no sustituye a docker-compose.
- Los comandos de arranque de cada servicio son los ya existentes (frontend: modo desarrollo; backend: modo desarrollo de la API; agente: servidor de desarrollo de langgraph).
- El servidor del agente es opcional y queda fuera de `dev` por defecto.
- El dashboard no requiere autenticación porque solo acepta conexiones locales y es de solo lectura (principios de seguridad por defecto y mínima exposición).
- Fuera de alcance: reinicio automático de servicios, visualización de logs en el dashboard, control de servicios desde la web, soporte para Windows nativo (se asume Linux/macOS).
- El orquestador añade archivos únicamente en la raíz del repositorio y puede requerir un `.gitignore` para sus dependencias.
