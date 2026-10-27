# El back de la aplicacion esta en 
backend-lang

Para ajustes del front siempre verifica el diseño custm de HILO

# El front end compatible de estar en 
front

## Active Technologies
- Python 3.12+ + FastAPI 0.136+, LangGraph 1.2+, supabase-py, Pydantic v2, httpx, cryptography (Fernet), google-api-python-client, pydantic-settings (master)
- Supabase + PostgreSQL — 13 tablas aplicadas, RLS activo (master)
- TypeScript 5.8+ + TanStack Start 1.x, TanStack Router 1.x, React Query 5.x, Supabase JS SDK 2.x, Zod 3.x, date-fns 4.x, Sonner 2.x (master)
- N/A (client-side; persistencia delegada al backend) (master)

## Recent Changes
- master: Added Python 3.12+ + FastAPI 0.136+, LangGraph 1.2+, supabase-py, Pydantic v2, httpx, cryptography (Fernet), google-api-python-client, pydantic-settings

Agrega cambios en los logs.md

## Agente de citas (backend-lang/src/agents/citas)
- LLM propone herramientas; el backend las ejecuta. workspace/customer/channel/conversation vienen de `CitasContext`, nunca del LLM.
- Confirmación al cliente solo tras commit; fallo de BD/Calendar → mensaje fijo de "no se pudo". Sin `AGENT_LLM_API_KEY` falla cerrado.
- Pendiente DBA: constraint de no-solapamiento en `appointments` (ver logs.md).
