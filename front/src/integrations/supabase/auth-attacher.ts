// Adjunta el JWT del backend a todas las server function RPCs.
import { createMiddleware } from '@tanstack/react-start'

const JWT_KEY = 'hilo_jwt'

export const attachSupabaseAuth = createMiddleware({ type: 'function' }).client(
  async ({ next }) => {
    const token = typeof window !== 'undefined' ? localStorage.getItem(JWT_KEY) : null
    return next({
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
  },
)
