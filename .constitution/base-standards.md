#  — Base Standards

## Inicio de sesión — checklist obligatorio

Antes de cualquier acción, ejecuta estos pasos en orden:

### 1. Verificar submódulos actualizados

```bash
git pull
```

### 3. Verificar que `CLAUDE.md` del proyecto está actualizado

Lee el `CLAUDE.md` del proyecto y compáralo contra `.constitution/claude-example.md`.
Verificar dos cosas:

**a) Estructura:** el `CLAUDE.md` debe tener las secciones que define `claude-example.md`:
- Checklist de inicio de sesión
- Reglas permanentes
- Formato de registro de cambios (`logs.md`)

**b) Archivos de constitución:** todos los archivos listados en `claude-example.md` son
**obligatorios** en el `CLAUDE.md` de cualquier proyecto :

- `.constitution/base-standards.md`
- `.constitution/front.md`
- `.constitution/backend.md`
- `.constitution/database.md`

Si falta alguno → avisar al usuario indicando exactamente cuál falta y ofrecer agregarlo.
Si `CLAUDE.md` no existe → crearlo copiando `.constitution/claude-example.md` como base.

### 4. Leer `logs.md`

Revisar el registro de cambios para tener contexto del estado actual.

---

## Autoridad

Este archivo es el punto de entrada de la constitución .

La constitución completa está en `.constitution/constitution.md`. Es **NON-NEGOCIABLE**.
Antes de proponer cualquier cambio, léela.

## Estructura de carpetas del proyecto (OBLIGATORIA)

Todo proyecto del ecosistema  usa esta estructura en la raíz del repositorio:

```
[nombre-del-proyecto]/
├── backend/
│   ├── ...       ← todo el código del backend (Express o FastAPI)
│   └── .env      ← variables del backend (DATABASE_URL, ATLAS_SERVICE_KEY, SharePoint, etc.)
├── frontend/
│   ├── ...       ← todo el código del frontend (React)
│   └── .env      ← variables del frontend (VITE_API_BASE_URL, VITE_TOOL_KEY, etc.)
└── context/
    └── project.md
```

- Si el proyecto solo tiene backend → solo existe la carpeta `backend/` con su `.env`.
- Si el proyecto solo tiene frontend → solo existe la carpeta `frontend/` con su `.env`.
- Si tiene ambos → ambas carpetas en la raíz, cada una con su propio `.env`.
- **Nunca mezclar código de backend y frontend en la misma carpeta.**
- **Nunca usar un `.env` único en la raíz** — cada entorno maneja sus propias variables.
- Ambos `.env` van en `.gitignore`. Nunca se suben al repositorio.

---

## Flujo de trabajo obligatorio

Cada paso depende del anterior. No saltar pasos.

## Ventana de Contexto del Proyecto (OBLIGATORIO)

**Al inicio de cualquier flujo de trabajo**, el agente DEBE leer `project.md`.

Este archivo contiene:
- Descripción y objetivo del proyecto
- Stack tecnológico elegido
- Estado actual del proyecto
- Restricciones y decisiones ya tomadas
- **Nivel del desarrollador** (ver sección siguiente)
- Preferencias de trabajo

Si `project.md` está vacío o sin completar, el agente debe:
1. Indicarle al usuario que lo complete antes de continuar.
2. Hacer las preguntas mínimas necesarias para determinar el nivel del usuario y el contexto básico.

---

## Especialización de Contexto (OBLIGATORIO)

Para garantizar la precisión en la implementación, los agentes DEBEN cargar contexto específico según el área de trabajo:

- **Front-end**: Leer `.constitution/front.md` antes de cualquier tarea de frontend.
- **Back-end**: Leer `.constitution/backend.md` antes de cualquier tarea de backend.
- **Base de datos / ORM**: Antes de cualquier tarea que implique acceso a datos, modelos, queries o conexiones, leer `.constitution/database.md`. Define qué ORM usar según el stack (Eloquent/SQLAlchemy/Drizzle), cuándo encapsular un frontend React sin backend con Express + Drizzle, y cómo tratar fuentes analíticas (Fabric/datalake).

## Reglas de análisis

- Detecta: duplicaciones, ambigüedades, gaps de cobertura
- Severidad: CRITICAL > HIGH > MEDIUM > LOW
- Conflictos con la constitución = siempre CRITICAL
