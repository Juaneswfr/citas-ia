# Nodo: Auth

**Rol:** Autenticación del usuario contra Atlas antes de cualquier interacción.  
**Modelo:** Sin LLM — lógica Python pura.  
**Flujo:** `START → auth → dispatcher (éxito) | END (falla)`

---

## Estado general

| Ítem | Estado |
|---|---|
| Login vía Atlas API | ✅ |
| Caché de sesión en MemorySaver | ✅ |
| Re-auth forzado en conversación nueva | ✅ |
| Corte en `__end__` si no autorizado | ✅ |
| Refresh de token expirado | ⏳ Pendiente |
| Manejo de error 5xx en Atlas | ⚠️ Parcial |

---

## Lógica implementada

```
1. Si hay sesión cacheada Y no es conversación nueva → reutiliza, salta Atlas
2. Si no → POST /api/whatsapp/login { phone } con X-Internal-Secret
3. Atlas devuelve { success, user, access_token, refresh_token, expires_in, tools }
4. Guarda en state: user, session, atlas_tools
5. Enruta a "dispatcher" o "__end__"
```

---

## Variables de entorno

| Variable | Descripción |
|---|---|
| `ATLAS_AUTH_URL` | Base URL de Atlas API |
| `ATLAS_INTERNAL_SECRET` | Header de seguridad túnel |

---

## Checklist pendiente

- [ ] Implementar refresh de `access_token` usando `refresh_token` cuando `expires_in` se agote
- [ ] Manejar reintentos en error 5xx de Atlas (backoff exponencial)
- [ ] Log de eventos de auth para auditoría (sin datos sensibles)
- [ ] Test unitario: usuario no registrado en Atlas
