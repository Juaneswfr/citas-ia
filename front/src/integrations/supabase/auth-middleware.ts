// Middleware de autenticación para server functions — valida JWT del FastAPI.
import { createMiddleware } from '@tanstack/react-start'
import { getRequest } from '@tanstack/react-start/server'
import { jwtVerify } from 'jose'

export const requireAuth = createMiddleware({ type: 'function' }).server(
  async ({ next }) => {
    const request = getRequest()
    if (!request?.headers) throw new Error('Unauthorized: No request headers')

    const authHeader = request.headers.get('authorization')
    if (!authHeader?.startsWith('Bearer ')) throw new Error('Unauthorized: No Bearer token')

    const token = authHeader.slice(7)
    const secret = new TextEncoder().encode(process.env.JWT_SECRET)

    try {
      const { payload } = await jwtVerify(token, secret)
      return next({
        context: {
          userId: payload.sub as string,
          email: payload.email as string,
          role: payload.role as string,
          workspaceId: payload.workspace_id as string,
          claims: payload,
        },
      })
    } catch {
      throw new Error('Unauthorized: Invalid or expired token')
    }
  },
)

// Alias para compatibilidad con código existente que usaba requireSupabaseAuth
export { requireAuth as requireSupabaseAuth }
