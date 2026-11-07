# Backend — Estándares de Desarrollo

> Este documento es lectura **obligatoria** para cualquier agente que trabaje en tareas de backend.
> Complementa `.constitution/base-standards.md`

---

## 1. Principios SOLID

Toda lógica de negocio y diseño de clases/módulos DEBE respetar estos principios:

### S — Single Responsibility
- Cada clase, módulo o función tiene **una única razón para cambiar**.
- Un servicio de usuario no debe también enviar emails ni manejar pagos.
- Si una clase necesita más de ~200 líneas, es señal de que tiene demasiadas responsabilidades.

### O — Open/Closed
- El código está **abierto para extensión, cerrado para modificación**.
- Usa interfaces/contratos para agregar comportamientos sin tocar código existente.
- Prefiere composición sobre herencia para extender funcionalidad.

### L — Liskov Substitution
- Las subclases deben poder reemplazar a sus clases base **sin romper el sistema**.
- Si una subclase lanza excepciones que la base no lanza, viola este principio.
- Verifica que los contratos de la clase base se cumplan en todas las implementaciones.

### I — Interface Segregation
- **No obligues** a un cliente a depender de métodos que no usa.
- Prefiere interfaces pequeñas y específicas a una interfaz grande y genérica.
- Ejemplo: separar `IReadRepository` de `IWriteRepository` en lugar de un único `IRepository`.

### D — Dependency Inversion
- Los módulos de alto nivel **no deben depender** de módulos de bajo nivel; ambos dependen de abstracciones.
- Inyectar dependencias (bases de datos, servicios externos) en vez de instanciarlas dentro de la clase.
- Facilita el testing y el reemplazo de implementaciones.

---

## 2. Seguridad (OWASP Top 10 aplicado)

### Validación de entrada
- **NUNCA** confíes en datos del cliente. Valida en el servidor siempre.
- Usa listas de permitidos (allow-list) en lugar de listas de bloqueados.
- Sanitiza datos antes de almacenarlos o utilizarlos en queries.

### Inyección (SQL, NoSQL, Command)
- Usa **consultas parametrizadas** o ORMs con escaping automático. Nunca concatenes strings para formar queries.
- Evita pasar input del usuario directamente a comandos del sistema operativo.

### Autorización
- Verifica permisos **en cada endpoint**, no solo en el frontend.
- Principio de mínimo privilegio: cada rol accede solo a lo que necesita.
- Nunca expongas IDs secuenciales predecibles; prefiere UUIDs.

### Manejo de secretos
- Variables de entorno para credenciales, claves de API y configuración sensible.
- **Nunca** commitear secretos al repositorio.
- Rotar claves comprometidas inmediatamente.

### Exposición de datos sensibles
- Logs no deben contener contraseñas, tokens, tarjetas de crédito ni PII.
- Respuestas de API no deben filtrar campos internos (ej. `password_hash`, `internal_id`).
- Usa HTTPS en producción siempre.

### Rate limiting y protección
- Implementa rate limiting en endpoints de autenticación y APIs públicas.
- Protección contra CSRF en endpoints que modifican estado.
- Headers de seguridad: `Content-Security-Policy`, `X-Frame-Options`, `HSTS`.

---

## 3. Documentación

### Docstrings y comentarios
- **Toda función pública** debe tener docstring describiendo: qué hace, parámetros, retorno y posibles excepciones.
- Los comentarios explican el **por qué**, no el qué (el código ya dice qué hace).
- Evita comentarios obsoletos: si el código cambia, actualiza el comentario.

### Documentación de API
- Cada endpoint documenta: método HTTP, ruta, parámetros, body, respuestas posibles (incluyendo errores).
- Usa estándares como OpenAPI/Swagger para APIs REST.
- Incluye ejemplos de request y response reales.

### README de módulo/servicio
- Cada servicio backend incluye un README con: propósito, cómo ejecutar localmente, variables de entorno requeridas, y cómo correr los tests.

---

## 4. Arquitectura y estructura de capas

```
Presentación (Controllers/Routes)
    ↓
Aplicación (Use Cases / Services)
    ↓
Dominio (Entidades / Lógica de Negocio)
    ↓
Infraestructura (Repositorios / DB / APIs externas)
```

- **Controllers**: solo reciben requests, validan entrada, delegan a servicios, retornan respuesta.
- **Services**: orquestan la lógica de negocio. Sin lógica de presentación.
- **Repositorios**: abstracción del acceso a datos. Los servicios no conocen el motor de DB.
- **Evita**: lógica de negocio en controllers, queries SQL en controllers, dependencias circulares.

---

## 5. Manejo de errores

- Usa excepciones tipadas y específicas (no lanzar `Error` genérico).
- Centraliza el manejo de errores en un middleware/handler global.
- Respuestas de error con estructura consistente: `{ error: { code, message, details? } }`.
- Distingue errores del cliente (4xx) de errores del servidor (5xx).
- Loguea errores 5xx con stack trace; errores 4xx solo si son relevantes para debugging.

---

## 6. Testing

- **Unit tests**: Manual

## 7. Adaptación por nivel del usuario

El agente ajusta la profundidad de las explicaciones según el nivel detectado en `/context/project.md`:

| Nivel | Enfoque del agente |
|-------|--------------------|
| **1 — Básico** | Explica cada concepto antes de aplicarlo. Usa analogías. Evita jerga técnica sin definir. Muestra ejemplos completos paso a paso. |
| **2 — Intermedio** | Menciona el concepto, aplica directamente. Incluye el por qué de las decisiones. Señala tradeoffs relevantes. |
| **3 — Avanzado** | Solo el código y las decisiones de arquitectura. Sin explicaciones de conceptos base. Discute patrones y alternativas directamente. |
