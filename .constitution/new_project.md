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
[ ] 3. Variables de entorno del backend y del frontend definidas en sus .env
[ ] 4. Variables de SharePoint en .env (solo si el proyecto maneja archivos)
[ ] 5. context/project.md completado con stack, estado y nivel del desarrollador
[ ] 6. .gitignore incluye .env y .env.*
```

Solo cuando todos los ítems tienen ✅ el agente puede comenzar a generar código de negocio.
