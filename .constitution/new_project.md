# Proyecto Nuevo — Guía de Arranque 

> Lectura **obligatoria** al iniciar cualquier proyecto nuevo dentro del ecosistema .
> El agente DEBE completar este checklist **antes de escribir una sola línea de código**.

---

## Preguntas obligatorias de arranque

Antes de cualquier implementación, el agente hace estas preguntas al usuario y espera respuesta:

1. **¿El proyecto es completamente nuevo o ya existe código / infraestructura?**
   - Nuevo desde cero → seguir esta guía de principio a fin.
   - Ya existe código → leer `context/project.md` y verificar cuáles pasos ya están cubiertos.

2. **¿El proyecto necesita base de datos propia?**
   - Ver sección **Base de datos** más abajo.

3. **¿El proyecto tiene Python, IA, modelos ML o conexiones con lago de datos?**
   - Ver sección **Stack tecnológico** más abajo.

4. **¿El proyecto maneja archivos o documentos (fotos, PDFs, comprobantes)?**
   - Sí → leer `.constitution/storage.md` antes de implementar. Ver resumen al final de este archivo.

---

## Stack tecnológico — árbol de decisión

```
¿El proyecto necesita Python, IA, modelos ML, lago de datos (Fabric/OneLake)
o algún motor de backend con mayor peso computacional?

  ├─ SÍ → Backend: Python (FastAPI) + Frontend: React
  │         Usar SQLAlchemy como ORM
  │         Ejemplos: dashboards analíticos, agentes IA, conexiones a datalake
  │
  └─ NO → Backend: Express (Node.js) + Frontend: React
            Usar Drizzle ORM
            Ejemplos: CRUD operacional, herramientas internas, portales
```

### Cuándo usar cada stack

| Criterio | Express + React | Python (FastAPI) + React |
|---|---|---|
| CRUD operacional, gestión de usuarios | ✅ | — |
| Dashboard interno, herramienta comercial | ✅ | — |
| IA, LLM, embeddings, agentes | — | ✅ |
| Conexión a Microsoft Fabric / OneLake / Delta Lake | — | ✅ |
| Análisis masivo de datos, pandas, numpy | — | ✅ |
| Integración con scripts Python existentes | — | ✅ |

> **Regla**: Si hay cualquier componente Python o IA, todo el backend es Python. No se mezclan
> Express y FastAPI en el mismo proyecto salvo decisión explícita del equipo.

---

## Base de datos

### LEY CRÍTICA — No usar Supabase en proyectos nuevos

**Supabase NO se usa para proyectos nuevos.** Toda base de datos del ecosistema 
es PostgreSQL gestionada por el **equipo BI (Mosquera)**. El agente nunca crea ni configura
una base de datos por su cuenta.

### Flujo del agente

El agente pregunta al usuario:

> "¿El proyecto ya tiene una base de datos PostgreSQL?
> A) Sí, ya tengo el connection string → pégalo aquí y lo agrego al `.env`
> B) No todavía → debes pedírsela a **Mosquera / equipo BI** indicando el nombre del proyecto,
>    el stack (Express/Drizzle o Python/SQLAlchemy) y los ambientes que necesitas.
>    Una vez que la tengas, la configuramos juntos. ¿Quieres omitir este paso por ahora?
> C) Omitir por ahora → el proyecto arrancará sin BD; recordarme cuando la tengas."

**Si el usuario elige A:** agregar el `DATABASE_URL` al `.env` y continuar.

**Si el usuario elige B o C:** continuar sin BD. El agente no bloquea el avance.
Cuando el usuario regrese con el connection string, configurar el ORM en ese momento.

### Variables de entorno de base de datos

```env
# Entregado por Mosquera / equipo BI — nunca hardcodeado en código
DATABASE_URL=postgresql://usuario:contraseña@host:5432/nombre_db
```

El ORM a usar según el stack:

| Stack | ORM | Paquetes |
|---|---|---|
| Express / Node.js | Drizzle | `drizzle-orm` + `drizzle-kit` + `pg` |
| Python / FastAPI | SQLAlchemy | `sqlalchemy` + `psycopg2-binary` |

> Ver `.constitution/database.md` para los patrones de implementación completos.

---

## Variables de entorno de Atlas (obligatorias en todo proyecto)

### Backend

```env
# Conexión service-to-service con Atlas (solo backend, nunca exponer al frontend)
ATLAS_SERVICE_URL=https://atlas.enterprise.com/service/v1
ATLAS_SERVICE_KEY=sk_b7290638581058b90d68f8147a9c8d1fdc2edc4f1696a8bf22c49b576734e74a
```

### Frontend (React)

```env
# URL base del API de Atlas
VITE_API_BASE_URL=https://atlas.profesional.com/api

# URL de login en Clarity (portal central de autenticación)
VITE_CLARITY_LOGIN_URL=https://clarity.profesional.com/login

# Key única de esta herramienta — obtener al registrar en Clarity
VITE_TOOL_KEY=<tool-key-del-proyecto>

# Dominio del ecosistema (para manejo de cookies)
VITE_ECOSYSTEM_DOMAIN=profesional.com

# Solo para apps internas que muestran directorio de usuarios (panel admin)
# NUNCA en apps públicas o externas
VITE_ATLAS_SERVICE_KEY=sk_b7290638581058b90d68f8147a9c8d1fdc2edc4f1696a8bf22c49b576734e74a
```

> `VITE_ATLAS_SERVICE_KEY` embebe la llave en el bundle JS. Usar **exclusivamente** en herramientas
> internas donde todos los usuarios son empleados de  con acceso a Clarity.

---

## Registrar la herramienta en Clarity

Antes de hacer login con la herramienta nueva, deben existir estos objetos en Clarity:

1. **Tool** — crear en Clarity → Tools:
   - `key`: identificador único en kebab-case (ej. `project-flow`, `canal-institucional`)
   - `name`: nombre legible
   - `url`: URL de la herramienta en producción

2. **Permisos** — crear al menos:
   - `panel_access` → puede iniciar sesión y ver el panel
   - `admin_access` → puede gestionar usuarios y configuración
   - Agregar permisos adicionales según el negocio

3. **Roles** — crear roles y asignar permisos:
   - Ejemplo mínimo: `usuario` → `panel_access` · `admin` → `panel_access` + `admin_access`

4. **Asignar usuarios** — en Clarity → Users → {usuario} → Tools → asignar rol

> Sin estos 4 pasos el `validate` de sesión retorna `permissions: {}` y el usuario no puede entrar.

---

## Storage (archivos)

Si el proyecto maneja cualquier tipo de archivo (fotos, PDFs, comprobantes, adjuntos):

**Lectura obligatoria:** `.constitution/storage.md`

Variables de entorno mínimas para SharePoint:

```env

```


---

## Checklist final — no escribir código sin completarlo

```
[ ] 1. Stack definido: Express+React  o  Python+React
[ ] 2. Base de datos: ¿ya existe? → connection string en .env | ¿no? → solicitar a Mosquera/BI o omitir por ahora
[ ] 3. ATLAS_SERVICE_KEY y ATLAS_SERVICE_URL en el .env del backend
[ ] 4. VITE_API_BASE_URL y VITE_TOOL_KEY en el .env del frontend
[ ] 5. Tool registrada en Clarity (key, permisos, roles, usuarios)
[ ] 6. Variables de SharePoint en .env (solo si el proyecto maneja archivos)
[ ] 7. context/project.md completado con stack, estado y nivel del desarrollador
[ ] 8. .gitignore incluye .env y .env.*
```

Solo cuando todos los ítems tienen ✅ el agente puede comenzar a generar código de negocio.
