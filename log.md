# Cambios por agente

### [AGENTE: security] [FECHA: 2026-10-28 12:58 UTC]
**Cambios:**
- front/drizzle.config.ts: se quita la URL de PostgreSQL con credenciales como valor por defecto (FR-105). Ahora lee solo `process.env.DATABASE_URL` y lanza un error explícito si falta.
- Verificado: sin DATABASE_URL el config falla (exit 1, mensaje explícito); con valor ficticio carga y expone dbCredentials.url.
- git grep de credenciales en el working tree: 0 archivos. Historial: 1 commit (c1a5e31) la introdujo. La rotación NO se hizo (pregunta abierta 8 de la spec); la hace el usuario.

**Archivos modificados:** front/drizzle.config.ts, log.md, claude.md
**Commit:** ver git log (mensaje "fix(security): quita credencial por defecto de front/drizzle.config.ts (FR-105)")

**Actualizaciones a claude.md:**
- Se crea claude.md con la decisión: drizzle.config.ts sin credenciales por defecto.
