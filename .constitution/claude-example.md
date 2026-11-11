# CLAUDE.md — [Nombre del proyecto]
# Plantilla canónica — copiar y adaptar al proyecto

# ──────────────────────────────────────────
# 1. ARCHIVOS DE CONSTITUCIÓN
# Incluir solo los que aplican al proyecto
# ──────────────────────────────────────────
.constitution/base-standards.md          # SIEMPRE obligatorio
.constitution/new_project.md           # Proyecto nuevo sin context/project.md completo
.constitution/front.md                 # Frontend React
.constitution/backend.md               # Backend Express o FastAPI
.constitution/database.md              # Base de datos / ORM / queries
.constitution/users.md                 # Usuarios internos (Clarity / Atlas)

# ──────────────────────────────────────────
# 2. INICIO DE SESIÓN — CHECKLIST OBLIGATORIO
# ──────────────────────────────────────────

Comprueba que `.constitution` esté en el último commit de su rama remota.
Si hay cambios nuevos, informa al usuario antes de continuar.

### 2. Leer `context/project.md`

Lee el archivo para conocer el stack, módulos activos y estado del proyecto.
Si no existe o está vacío → ejecutar guía de `.constitution/new_project.md`.

### 3. Verificar que este `CLAUDE.md` está actualizado

Compara este archivo contra `.constitution/claude-example.md`.
Verificar dos cosas:

**a) Estructura:** este `CLAUDE.md` debe tener las secciones:
- Checklist de inicio de sesión (esta sección)
- Reglas permanentes
- Formato de registro de cambios (`logs.md`)

**b) Archivos de constitución:** según el stack declarado en `context/project.md`,
este `CLAUDE.md` debe incluir los archivos relevantes (ver tabla en `claude-example.md`).

Si falta algo → avisar al usuario indicando exactamente qué falta y ofrecer corregirlo.

### 4. Leer `logs.md`

Revisar el registro de cambios para tener contexto del estado actual del proyecto.

---

## Reglas permanentes

Antes de proponer o implementar cualquier cambio, lee y sigue los archivos de
constitución declarados arriba. Si hay conflicto entre una solicitud y lo establecido
ahí, priorizar lo establecido y avisar al usuario.

---

## Registro de cambios

El log de cambios vive en `logs.md` (no en este archivo).
Cada vez que se confirmen cambios, agrega una nueva entrada al tope de `logs.md`
con el formato:

```
### YYYY-MM-DD — Actor
**Descripción breve**
- archivo.js — qué cambió y por qué
```

Lo más reciente va arriba.
