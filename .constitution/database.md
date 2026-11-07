# Base de Datos — Estándar de Acceso 

> Lectura **obligatoria** antes de cualquier tarea que implique acceso a datos, definición de modelos, queries o conexiones a base de datos.

---

## Regla fundamental

**Ningún proyecto accede directamente a PostgreSQL con queries crudas en el código de negocio.**
Todo acceso a datos operacionales pasa por un ORM o un backend encapsulador que use ORM.

## LEY — Bases de datos nuevas

**Supabase NO se usa para crear bases de datos de proyectos nuevos.**

Toda base de datos nueva del ecosistema es PostgreSQL gestionada por el **equipo BI **.
El agente nunca crea ni configura una base de datos por su cuenta.

Cuando un proyecto necesita una base de datos nueva:
1. El agente se detiene y le pide al usuario que solicite la DB a  / equipo BI.
2. El usuario proporciona el `DATABASE_URL` una vez que BI lo entrega.
3. El agente continúa solo con el connection string confirmado en el `.env`.

```env
# Entregado por Mosquera / equipo BI — nunca hardcodeado en código
DATABASE_URL=postgresql://usuario:contraseña@host:5432/nombre_db
```

> Ver `.constitution/new_project.md` para el proceso completo de arranque.

---

## 1. Mapa de tecnologías por tipo de proyecto

### Proyectos operacionales (datos de negocio, CRUD, usuarios, permisos)

| Stack del proyecto | Base de datos | ORM / Acceso | Paquete |
|---|---|---|---|
| **PHP / Laravel** | PostgreSQL (Supabase) | **Eloquent ORM** | `illuminate/database` |
| **Python / FastAPI** | PostgreSQL (Supabase) | **SQLAlchemy** | `sqlalchemy` + `psycopg2-binary` |
| **Node.js / Express** | PostgreSQL (Supabase) | **Drizzle ORM** | `drizzle-orm` + `drizzle-kit` |
| **NestJS** | PostgreSQL (Supabase) | **Drizzle ORM** | `drizzle-orm` + `drizzle-kit` |

### Proyectos analíticos (datos históricos, datalake, BI)

| Fuente de datos | Tecnología | Librería | ORM |
|---|---|---|---|
| Microsoft Fabric / OneLake (Delta) | Delta Lake | `deltalake` + `pyarrow` + `pandas` | ❌ No aplica |
| Microsoft Fabric SQL Endpoint | T-SQL via ODBC | `pyodbc` + `pandas` | ❌ No aplica |
| SharePoint / Excel | Microsoft Graph API | `requests` + `pandas` | ❌ No aplica |

> Los proyectos analíticos son **lectura masiva de datos históricos**. No usan ORM porque trabajan con columnas, no con registros OLTP. El ORM en este contexto sería contraproducente.

---

## 2. Regla para frontends React sin backend propio

**Si un frontend React accede directamente a Supabase mediante `@supabase/supabase-js`, debe encapsularse con un backend Express + Drizzle.**

```
❌ Incorrecto
  React → Supabase SDK → PostgreSQL

✅ Correcto
  React → Express API + Drizzle ORM → PostgreSQL
```

**Por qué:**
- Las credenciales de Supabase quedan expuestas en el cliente.
- No hay validación de negocio entre el frontend y la base de datos.
- Inconsistente con el patrón del ecosistema (Clarity → Atlas → PostgreSQL).
- Row Level Security de Supabase no reemplaza lógica de negocio en el servidor.

**Excepción:** Supabase JS client se puede usar en frontend solo para **autenticación pública** (signup/login) si el proyecto no tiene backend propio y no expone datos sensibles. Para cualquier consulta de datos de negocio, debe pasar por Express.

---

## 3. Patrón Express + Drizzle (Node.js)

### Estructura de carpetas

```
backend/
├── src/
│   ├── db/
│   │   ├── index.ts          ← instancia única del cliente Drizzle
│   │   └── schema/
│   │       ├── users.ts      ← definición de tabla y tipos
│   │       └── index.ts      ← exporta todos los schemas
│   ├── routes/
│   │   └── users.ts          ← endpoints Express
│   └── services/
│       └── users.service.ts  ← lógica de negocio, usa db
├── drizzle.config.ts
└── package.json
```

### Ejemplo de schema

```ts
// src/db/schema/users.ts
import { pgTable, uuid, text, boolean, timestamp } from 'drizzle-orm/pg-core'

export const users = pgTable('users', {
  id:         uuid('id').primaryKey().defaultRandom(),
  email:      text('email').notNull().unique(),
  name:       text('name').notNull(),
  isActive:   boolean('is_active').default(true),
  createdAt:  timestamp('created_at').defaultNow(),
})
```

### Query ORM (caso normal)

```ts
// src/services/users.service.ts
import { db } from '../db'
import { users } from '../db/schema'
import { eq } from 'drizzle-orm'

export async function getUserById(id: string) {
  return db.select().from(users).where(eq(users.id, id))
}
```

### Raw SQL (cuando la query lo requiere)

```ts
import { sql } from 'drizzle-orm'

const result = await db.execute(
  sql`SELECT u.id, COUNT(o.id) as total_orders
      FROM users u
      LEFT JOIN orders o ON o.user_id = u.id
      WHERE u.is_active = true
      GROUP BY u.id`
)
```

---

## 4. Patrón SQLAlchemy (Python / FastAPI)

### Estructura de carpetas

```
app/
├── core/
│   └── database.py       ← engine + SessionLocal + Base
├── models/
│   └── users.py          ← modelos ORM (tablas)
├── schemas/
│   └── users.py          ← Pydantic schemas (validación)
└── services/
    └── users_service.py  ← lógica de negocio, usa Session
```

### Configuración de conexión

```python
# app/core/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass
```

### Modelo ORM

```python
# app/models/users.py
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid

class User(Base):
    __tablename__ = "users"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email     = Column(String, nullable=False, unique=True)
    name      = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
```

### Query ORM (caso normal)

```python
# app/services/users_service.py
def get_user_by_id(db: Session, user_id: str):
    return db.query(User).filter(User.id == user_id).first()
```

### Raw SQL (cuando la query lo requiere)

```python
from sqlalchemy import text

result = db.execute(
    text("SELECT id, COUNT(*) as total FROM orders WHERE user_id = :uid GROUP BY id"),
    {"uid": user_id}
).fetchall()
```

---

## 5. Proyectos del workspace y su estándar

| Proyecto | Stack actual | ORM requerido | Estado |
|---|---|---|---|
| **Atlas** | Laravel 12 / PHP | Eloquent | ✅ Correcto |
| **product_imasd** | FastAPI / Python | SQLAlchemy | ✅ Correcto |
| **git** | Express / Node.js | Drizzle | 🔄 Migrar de `pg` raw |
| **SABII** | FastAPI / Python | SQLAlchemy | 🔄 Migrar de `psycopg2` raw |
| **verus** (backend) | NestJS | Drizzle | 🔄 Agregar cuando tenga BD |
| **Supply-chain** | React (sin back) | Express + Drizzle | 🔄 Encapsular con backend |
| **Cobrobot** | React (sin back) | Express + Drizzle | 🔄 Encapsular con backend |
| **Project-Flow** | React (sin back) | Express + Drizzle | 🔄 Encapsular con backend |
| **Clarity** | React (sin back) | — (usa Atlas) | ✅ Correcto |
| **app_dashboards** (operacional) | FastAPI / Python | SQLAlchemy | — |
| **app_dashboards** (datalake) | FastAPI / Python | `deltalake` + pandas | ✅ Correcto — no aplica ORM |

---

## 6. Lo que nunca debe ocurrir

- ❌ SQL concatenado con strings: `"SELECT * FROM users WHERE id = " + id`
- ❌ Credenciales de PostgreSQL en el código fuente
- ❌ Queries de negocio en controllers/routes (van en services)
- ❌ `@supabase/supabase-js` consultando tablas de negocio desde el frontend
- ❌ Usar ORM para fuentes analíticas (Fabric, Delta Lake, Excel)
- ❌ Múltiples instancias del cliente de BD por archivo (usar singleton)
