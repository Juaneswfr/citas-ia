# Frontend — Estándares de Desarrollo

> Este documento es lectura **obligatoria** para cualquier agente que trabaje en tareas de frontend.
> Complementa `.constitution/base-standards.md`.

---

## 1. Organización y estructura de archivos

### Estructura base
```
src/
├── components/       # Componentes reutilizables (UI puro, sin lógica de negocio)
├── pages/ (o views/) # Vistas completas que ensamblan componentes
├── services/         # Toda comunicación con APIs externas
├── hooks/ (o composables/) # Lógica reutilizable y stateful
├── store/ (o context/) # Estado global de la aplicación
├── utils/            # Funciones puras utilitarias
├── types/ (o models/) # Definiciones de tipos e interfaces
└── assets/           # Imágenes, fuentes, estilos globales
```

### Regla de responsabilidad única por archivo
- Un componente = una responsabilidad visual.
- Un service = un dominio de API (ej. `userService.ts`, `productService.ts`).
- No mezcles lógica de negocio, llamadas a API y renderizado en el mismo archivo.

---

## 2. Programación Orientada a Objetos en Frontend

### Clases y objetos para modelos de dominio
- Usa clases o interfaces para representar entidades del dominio (User, Product, Order).
- Encapsula la lógica de transformación de datos dentro del modelo.
- Ejemplo de patrón:

```ts
class User {
  constructor(
    public readonly id: string,
    public readonly name: string,
    private email: string
  ) {}

  getDisplayName(): string {
    return this.name || this.email.split('@')[0];
  }

  static fromApiResponse(data: ApiUser): User {
    return new User(data.id, data.full_name, data.email);
  }
}
```

### Encapsulamiento
- Los datos internos no deben ser modificados directamente desde fuera.
- Exponer solo lo necesario. Si algo es de solo lectura, márcalo así.

### Composición sobre herencia
- Prefiere combinar comportamientos (hooks, mixins, composables) a largas cadenas de herencia.

---

## 3. Llamadas a API — Service Layer

### Todo acceso a API va en `services/`
- **Nunca** hagas `fetch` o llamadas HTTP directamente en un componente o vista.
- Centraliza en un servicio por dominio.

### Estructura de un servicio
```ts
// services/userService.ts
const BASE_URL = '/api/users';

export const userService = {
  async getById(id: string): Promise<User> {
    const response = await apiClient.get(`${BASE_URL}/${id}`);
    return User.fromApiResponse(response.data);
  },

  async update(id: string, data: UpdateUserDto): Promise<User> {
    const response = await apiClient.put(`${BASE_URL}/${id}`, data);
    return User.fromApiResponse(response.data);
  },
};
```

### Manejo de errores en llamadas API
- Siempre maneja errores: `try/catch` o `.catch()`.
- Distingue errores de red, errores 4xx (cliente) y errores 5xx (servidor).
- Muestra feedback al usuario: loading state, mensaje de error, estado vacío.
- Nunca dejes un error silencioso sin notificar al usuario.

### Estados de una llamada async
Todo llamado asíncrono tiene tres estados que deben representarse en la UI:
- **Loading**: indicador visual mientras espera respuesta.
- **Success**: muestra el resultado.
- **Error**: muestra mensaje significativo y opción de reintentar.

### Patrón de error global (React Query)

El `QueryClient` en `src/router.tsx` registra un `QueryCache.onError` global que muestra
un toast para cualquier query que falle. Esto es la red de seguridad mínima.

```ts
// router.tsx — no tocar sin razón
queryCache: new QueryCache({
  onError: (error) => toast.error(extractErrorMessage(error)),
}),
defaultOptions: {
  queries: { retry: 1, staleTime: 60_000, refetchOnWindowFocus: false },
},
```

**Reglas:**
1. **Queries** (`useQuery`): el `QueryCache.onError` global muestra el toast. No duplicar
   `onError` en cada hook salvo que necesites UI de error inline (skeleton + botón reintentar).
2. **Mutations** (`useMutation`): siempre incluyen `onError` propio con mensaje específico.
   No dependen del handler global porque el contexto importa ("Error al crear cita", no genérico).
3. **`ApiError`** (de `src/lib/api/client.ts`): tiene `.detail` (mensaje del backend) y `.status`.
   Usar `.detail` en los mensajes al usuario. El status 503 = backend caído / servicio externo
   fallido. Status 409 = conflicto de negocio (horario ocupado, etc.).
4. **Componentes con datos críticos**: si el query falla y el componente quedaría en blanco,
   renderizar un estado de error explícito con `isError`:

```tsx
const { data, isLoading, isError, refetch } = useAppointments(...);

if (isError) return (
  <div className="error-state">
    <p>No se pudieron cargar las citas.</p>
    <button onClick={() => refetch()}>Reintentar</button>
  </div>
);
```

5. **`try/catch` en handlers de formulario**: siempre envolver `mutateAsync` en try/catch
   o manejar el rechazo — de lo contrario React reporta una promesa rechazada sin handler.

```tsx
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();
  try {
    await mutation.mutateAsync(payload);
    onClose();
  } catch {
    // onError del mutation ya mostró el toast — solo evitamos unhandled rejection
  }
};
```

---

## 4. Anti-patrones a evitar (código espagueti)

### Lo que NUNCA debes hacer

| Anti-patrón | Por qué es malo | Solución |
|-------------|-----------------|----------|
| Lógica de negocio en el template/JSX | Ilegible, no reutilizable, difícil de testear | Mover a función en el componente o hook |
| `fetch` directamente en un componente | Acoplamiento fuerte, difícil de mockear | Usar service layer |
| Estado global para todo | Complejidad innecesaria, over-engineering | Estado local cuando sea suficiente |
| Componentes de 500+ líneas | Hace demasiado, imposible de mantener | Dividir en componentes más pequeños |
| Variables con nombres genéricos (`data`, `res`, `obj`) | Ilegible, ambiguo | Nombres descriptivos del dominio (`userData`, `orderResponse`) |
| Callback hell anidado | Ilegible, difícil de debuggear | Usar async/await |
| Copiar y pegar bloques de código | Duplicación = bugs duplicados | Extraer en función o componente reutilizable |
| Lógica de UI mezclada con lógica de datos | Viola SRP, difícil de testear | Separar en capas |

### Variables de entorno — sin fallbacks

**Nunca agregues un valor por defecto (`||`, `??`, `?.`) a una variable de entorno.**

```ts
// ❌ Incorrecto — el error queda silenciado, el proyecto corre con configuración falsa
const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:3000'
const toolKey = import.meta.env.VITE_TOOL_KEY ?? 'default-tool'

// ✅ Correcto — si la variable no está, falla en arranque y el desarrollador lo sabe
const apiUrl = import.meta.env.VITE_API_BASE_URL
const toolKey = import.meta.env.VITE_TOOL_KEY
```

Si una variable de entorno no está definida, el proyecto **debe fallar visiblemente** —
no continuar con un valor inventado. Un fallback silencia un error de configuración y puede
causar bugs difíciles de rastrear en producción.

Las variables requeridas deben estar documentadas en un `.env.example` en la raíz del proyecto.

### Señales de alerta (code smells)
- Un componente recibe más de 5-6 props → probablemente hace demasiado.
- Un archivo tiene más de 300 líneas → candidato a dividir.
- Copias el mismo bloque de código más de 2 veces → extrae a función.
- Usas `any` como tipo → define el tipo correctamente.

---

## 5. Estado de la aplicación

### Regla del estado mínimo necesario
- Estado **local** (useState, ref): para datos que solo afectan un componente.
- Estado **compartido entre hermanos**: elevar al padre común (lifting state up).
- Estado **global** (store, context): solo para datos que necesitan múltiples partes no relacionadas de la app (usuario autenticado, tema, carrito).

### Estado derivado
- No guardes en el estado algo que puedes calcular a partir de otro estado.
- Mal: guardar `fullName` cuando ya tienes `firstName` y `lastName`.
- Bien: calcular `fullName` en el momento de renderizar.

---

## 6. Componentes

### Principios de diseño de componentes
- **Componente presentacional**: recibe props, renderiza UI. Sin lógica de negocio.
- **Componente contenedor/inteligente**: maneja estado, llama servicios, pasa datos a presentacionales.
- Favorece componentes pequeños y composables.

### Props y contratos
- Define el tipo de cada prop explícitamente (TypeScript interfaces / PropTypes).
- Documenta props no obvias con un comentario breve.
- Usa valores por defecto para props opcionales.

---

## 7. Accesibilidad y calidad

- Usa elementos HTML semánticos (`<button>`, `<nav>`, `<main>`, `<header>`).
- Imágenes con `alt` descriptivo.
- Formularios con `<label>` asociado a cada input.
- Contraste de color suficiente (WCAG AA mínimo).
- Navegación por teclado funcional.

---

## 8. Performance

- No hagas llamadas API innecesarias: cachea resultados cuando tenga sentido.
- Evita re-renders innecesarios: memoriza cálculos costosos.
- Lazy load de componentes y rutas pesadas.
- Imágenes optimizadas y con dimensiones definidas.

---

## 9. Adaptación por nivel del usuario

El agente ajusta la profundidad de las explicaciones según el nivel detectado en `/context/project.md`:

| Nivel | Enfoque del agente |
|-------|--------------------|
| **1 — Básico** | Explica qué es un componente, qué es un estado, qué es una API antes de escribir código. Usa analogías visuales. Muestra el flujo completo. |
| **2 — Intermedio** | Aplica patrones directamente. Señala por qué se elige ese patrón sobre la alternativa. Menciona los trade-offs. |
| **3 — Avanzado** | Solo código y decisiones de arquitectura. Discute patrones (Compound Components, Render Props, etc.) y cuándo usarlos. |

---

## 10. CSS — Metodología BEM (obligatoria)

### Regla fundamental

**Todo selector CSS debe seguir la convención BEM:** `bloque__elemento--modificador`.

Los estilos inline (`style=""`) están **prohibidos**. Si un valor puede expresarse en CSS, va en CSS.
La única excepción son valores genuinamente dinámicos calculados en runtime (ej. posición exacta
en píxeles desde JavaScript, color generado por el usuario). Si hay duda, va en CSS.

### Estructura BEM

```
bloque            → componente autónomo
bloque__elemento  → parte interna del bloque (separado con __)
bloque--modificador     → variación del bloque (separado con --)
bloque__elemento--modificador → variación de un elemento
```

### Ejemplos

```css
/* ✅ Correcto — BEM */
.tarjeta { }
.tarjeta__titulo { }
.tarjeta__imagen { }
.tarjeta__boton { }
.tarjeta__boton--deshabilitado { }
.tarjeta--destacada { }

/* ❌ Incorrecto — nombres genéricos, anidamiento sin convención */
.card .title { }
.btn-disabled { }
.container > div { }
```

```jsx
/* ✅ Correcto — clase en CSS, sin inline */
<div className="tarjeta tarjeta--destacada">
  <h2 className="tarjeta__titulo">Título</h2>
  <button className="tarjeta__boton tarjeta__boton--deshabilitado">Acción</button>
</div>

/* ❌ Incorrecto — estilos inline */
<div style={{ padding: '16px', backgroundColor: '#fff', borderRadius: '8px' }}>
  <h2 style={{ fontSize: '18px', fontWeight: 'bold' }}>Título</h2>
</div>

/* ✅ Excepción válida — valor dinámico imposible de expresar en CSS */
<div
  className="avatar"
  style={{ backgroundColor: usuario.colorHex }}   {/* color elegido por el usuario */}
/>
```

### Por qué BEM

| Problema con estilos sin convención | Solución BEM |
|---|---|
| Colisiones de nombres entre componentes | Cada bloque tiene su namespace |
| Difícil saber qué afecta qué | La jerarquía es explícita en el nombre |
| Inline styles no son reutilizables ni testeables | Todo en archivos CSS/SCSS |
| Especificidad difícil de manejar | BEM usa selectores de clase de un solo nivel |

### En módulos CSS o SCSS con React

```scss
// tarjeta.module.scss
.tarjeta {
  padding: 16px;

  &__titulo {
    font-size: 18px;
  }

  &__boton {
    cursor: pointer;

    &--deshabilitado {
      opacity: 0.5;
      pointer-events: none;
    }
  }

  &--destacada {
    border: 2px solid var(--color-primary);
  }
}
```

```jsx
import styles from './tarjeta.module.scss'

<div className={`${styles.tarjeta} ${destacada ? styles['tarjeta--destacada'] : ''}`}>
  <h2 className={styles.tarjeta__titulo}>{titulo}</h2>
</div>
```
