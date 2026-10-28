# Auditoría git — stash@{0} y rama feature/citas-ia-agent-p5-backend (2026-10-28)

Solo lectura. Master en `f0e97b0`. Stash `817b29f` (base `c1a5e31`, anterior a Kapso y al agente real). Rama P5: commit `167cc22` (base `0519013`).

## Recomendación final
1. **Integrar** (como parches por archivo, nunca `stash apply`): redacción de tokens en `ChannelOut`, `decrypt_token` + token por canal para Meta (whatsapp_service / reminder_worker / agent_service), `connectWhatsAppEmbeddedSignup` en el front, ruta `front/dist` en docker-compose, pin `bcrypt<5`.
2. **Descartar**: commit `167cc22` completo (duplica `8e26176`/`e3b890f`, mismo kanban t_d43e2fb2), y del stash `uv.lock`, `package-lock.json`, `logs.md` y los cambios que revierten Kapso/agente en `agent_service.py` y `whatsapp_service.py`.
3. **Decisión del usuario**: (a) ¿se prefiere la arquitectura LangGraph de `167cc22` (agents/citas, falla cerrado sin LLM key) sobre `services/appointment_agent.py` de master?; (b) rotar la credencial de `.mcp.json` (sigue en el historial); (c) vitest + `CLAUDE.md`/`.env.example` (reescritura de arquitectura "sin Supabase").

## Stash — tabla por archivo
| Archivo | Clasificación | Motivo |
|---|---|---|
| `backend-lang/src/schemas/channel.py` | UNICO-NECESARIO | Master devuelve `metadata` completo (`schemas/channel.py:40`) y `routes/channels.py:158` guarda `waba_access_token_encrypted` ahí: se filtra en la API. El stash añade `field_serializer` que quita claves token/secret. |
| `backend-lang/src/services/embedded_signup_service.py` | UNICO-NECESARIO | Master solo tiene `encrypt_token`; falta `decrypt_token` (stash +11 líneas al final, tras `encrypt_token`). Necesario para usar el token por canal. Aplica limpio. |
| `backend-lang/src/workers/reminder_worker.py` | UNICO-NECESARIO | Master usa token global: consulta `reminder_worker.py:71` solo trae `phone_number_id`. Stash lee `metadata`, descifra y pasa `access_token`. Depende de la fila `whatsapp_service` de abajo. Solo añade líneas, aplica limpio. |
| `backend-lang/src/services/whatsapp_service.py` | CONFLICTO (integrar a mano solo el parámetro) | El stash borra `send_text`/`provider`/`KapsoProvider` (master `whatsapp_service.py:93`) y devuelve bool. Hay que portar solo `access_token` opcional a `send_message` (`:69`) y `send_template` (`:159`), conservando Kapso. |
| `backend-lang/src/services/agent_service.py` | CONFLICTO (integrar a mano solo lectura/descifrado del token) | El stash restaura el placeholder "Recibido, en un momento te atiendo.", quita `run_agent`, `agent_alerts`, `provider`, `timezone` y `provider_message_id` (master `agent_service.py:165`). Solo sirve la idea del token por canal, y solo para canales Meta (no Kapso). |
| `backend-lang/pyproject.toml` | UNICO-NECESARIO (parcial) | Añade `bcrypt>=4.3,<5` (passlib falla con bcrypt 5, según `logs.md` del stash). Master solo tiene `passlib[bcrypt]>=1.7`. Quitar `supabase` y subir asyncpg: SUPERSEDED/no verificado (commit `0cbb3c6` dejó lock mínimo a propósito); pytest ya está en master. |
| `backend-lang/requirements.txt` | UNICO-NECESARIO | Añade `bcrypt>=4.3,<5`; master solo tiene `passlib[bcrypt]==1.7.4` (`:13`). |
| `backend-lang/uv.lock` | SUPERSEDED | Lock del stash contradice `0cbb3c6`/`c014b58` (lock mínimo). Regenerar con `uv lock` tras editar pyproject; no copiar. |
| `front/src/lib/api/channels.ts` | UNICO-NECESARIO | Falta `connectWhatsAppEmbeddedSignup` en master (+10 líneas). Aplica limpio. |
| `front/src/routes/_authenticated/settings.tsx` | UNICO-NECESARIO | Master hace `fetch` sin JWT a `/channels/embedded-signup` (`settings.tsx:101`); el stash usa el cliente autenticado `apiFetch`. Depende de `channels.ts`. |
| `docker-compose.yml` | UNICO-NECESARIO | Master monta `./front-app/dist` (`docker-compose.yml:4,12`); el código vive en `front/`. Verificar que `front-app/` no exista antes de aplicar. |
| `front/package.json` | UNICO-NECESARIO (decisión) | Añade vitest y script `test`; el test que lo usa es untracked (en el .tgz) y no pude leerlo. Sin test no aporta: dejar para el usuario. |
| `front/package-lock.json` | SUPERSEDED | Regenerar con `npm install` si se aplica `package.json`. |
| `front/.env.example` | UNICO-NECESARIO (decisión) | Master aún pide `VITE_SUPABASE_*`; el stash documenta `DATABASE_URL`/`JWT_SECRET` y Meta. Solo si el front ya usa PostgreSQL directo (parece, hay `front/src/db`). |
| `CLAUDE.md` | CONFLICTO | Stash reescribe "Active Technologies" por "Arquitectura vigente" (sin Supabase); master conserva el texto anterior y es el archivo de instrucciones: requiere decisión del usuario. No aplicar automático. |
| `logs.md` | CONFLICTO | Textual: stash reescribe líneas 22-45 de un `logs.md` anterior a Kapso/agente. No aplicar; añadir entrada nueva en master. |

Tests untracked del respaldo (`wip-untracked.tgz`): **no comparados**. El .tgz está fuera de mi directorio permitido y `tar -tzf` fue denegado, así que no pude listar ni leer su contenido. Master ya tiene test_appointment_agent.py y los test_kapso*.py según lo indicado, pero no pude confirmarlo con `ls-tree` (el comando pidió aprobación). Quien tenga permiso debe comparar con `tar -xzOf <tgz> <ruta> | diff - <(git show HEAD:<ruta>)`, sin reemplazar nada.

## Commit 167cc22 — veredicto: DUPLICADO (descartar)
- Mismo kanban (`t_d43e2fb2`) y mismo objetivo que `8e26176`/`e3b890f`, que ya están en master. Master ya cablea el agente: `agent_service.py` llama a `services/appointment_agent.run_agent`, con 3 herramientas, confirmación solo tras INSERT, alerta en `agent_alerts` y tests (`tests/test_appointment_agent.py`).
- `167cc22` reemplaza el placeholder por otro diseño (paquete `agents/citas/*` + `AgentService._run_agent`, 944 líneas) partiendo de `0519013`, que no contiene el agente de master. Mantenerlo duplicaría el agente y chocaría en `agent_service.py`, `test_kapso_outbound.py`, `logs.md`, `CLAUDE.md`.
- `backend-lang/tests/test_citas_agent.py` (270 líneas) prueba el paquete `agents/citas`; no es integrable solo (AÑADE-TESTS no aplica porque depende de ese código).
- Archivos a integrar: **ninguno**. Si el usuario prefiere el diseño LangGraph, requiere una tarea aparte: reemplazar `appointment_agent.py` y rebasar a mano, no cherry-pick.

## Hallazgos de secretos (solo ubicación)
- **Stash (parche tracked)** y **167cc22**: sin credenciales reales. Coincidencias solo son referencias/código/placeholders: `front/.env.example` del stash (línea `JWT_SECRET=` con marcador), `test_kapso_outbound.py:22`, `agents/citas/llm.py:16,20`, `core/config.py` (campo `agent_llm_api_key`).
- **Historial de master**: `.mcp.json` línea 7 (cabecera Authorization), commit `4d462a7`; el stash^ también lo contiene. En master actual solo queda `.mcp.json.example`. Rotar la credencial.
- **.tgz de respaldo**: no revisado (acceso denegado).
- La búsqueda con `git grep` sobre `refs/stash` y `167cc22` fue denegada, así que revisé los parches (`git diff`/`git show`) y no el árbol completo de esos commits.

## Plan de integración (NO ejecutado)
```bash
cd /opt/data/proyectos/citas-ia
git status --short                       # solo debe aparecer specs/003-producto-final-citas/
git switch -c fix/rescate-wip-2026-10-28 # desde master f0e97b0

# 1) Archivos que aplican limpio
for f in backend-lang/src/schemas/channel.py backend-lang/src/services/embedded_signup_service.py \
         backend-lang/src/workers/reminder_worker.py front/src/lib/api/channels.ts \
         front/src/routes/_authenticated/settings.tsx docker-compose.yml backend-lang/requirements.txt; do
  git diff stash@{0}^ stash@{0} -- "$f" | git apply --3way || echo "REVISAR $f"
done

# 2) pyproject: solo añadir "bcrypt>=4.3,<5" en dependencies (editar a mano), luego:
cd backend-lang && uv lock && cd ..

# 3) A mano (conflictos): whatsapp_service.py (parámetro access_token opcional en send_message y send_template,
#    conservando send_text/Kapso) y agent_service.py (leer/descifrar waba_access_token_encrypted solo si channel.provider != 'kapso').

# 4) Verificar (lo corre el PM)
cd backend-lang && PYTHONPATH=src uv run --group dev pytest -q && cd ../front && npm test --if-present && npm run build

# 5) Registrar en logs.md (regla del proyecto), revisar y commitear
git diff --stat
git add -p && git commit -m "fix: rescata WIP (redaccion de tokens de canal, token por canal, front/dist, bcrypt<5)"
# Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com> al final del mensaje

# 6) Descartar 167cc22 y limpiar solo tras aprobación del usuario
#    git branch -D feature/citas-ia-agent-p5-backend ; git stash drop stash@{0}
#    (conservar el respaldo /opt/data/profiles/pm/cache/scratch/backup-citas-ia-2026-10-28/ hasta cerrar)
```
