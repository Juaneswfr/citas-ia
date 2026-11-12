"""Sesión falsa de SQLAlchemy async para tests: sin red y sin base de datos.

El código de la app llama `await session.execute(text(sql), {params})` y lee el resultado con
`.mappings().fetchone()`, `.mappings().fetchall()`, `.scalar_one_or_none()` o `.scalar_one()`.
Cada test hereda de `FakeSession` y define `handle(sql, params)`, que devuelve:

- una lista de dicts → filas;
- un dict → una sola fila;
- cualquier otro valor (incluido `None`) → un escalar.
"""


class FakeResult:
    def __init__(self, value):
        if isinstance(value, list):
            self._rows, self._scalar = value, (next(iter(value[0].values())) if value else None)
        elif isinstance(value, dict):
            self._rows, self._scalar = [value], next(iter(value.values()), None)
        else:
            self._rows, self._scalar = [], value

    def mappings(self):
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar


class FakeSession:
    """Base de las sesiones falsas. También sirve como `async with AsyncSessionLocal() as s`."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def execute(self, statement, params=None):
        return FakeResult(self.handle(str(statement), params or {}))

    async def commit(self):
        pass

    async def rollback(self):
        pass

    def handle(self, sql: str, params: dict):
        """Por defecto ninguna consulta devuelve filas."""
        return []
