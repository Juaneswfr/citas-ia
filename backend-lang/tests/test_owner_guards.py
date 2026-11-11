"""Vigila que las rutas no usen roles inexistentes (p. ej. el antiguo ``owner``).

Un rol que no está en ROLE_HIERARCHY hace que el guard responda 403 a todos,
incluido super_admin; y ``member_role='owner'`` viola el CHECK de la migración 007.
"""
import re
from pathlib import Path

import pytest

from core.security import ROLE_HIERARCHY

ROUTES_DIR = Path(__file__).resolve().parents[1] / "src" / "api" / "routes"
ROUTE_FILES = sorted(ROUTES_DIR.glob("*.py"))

GUARD_RE = re.compile(r"""require_(?:role|workspace_access)\(\s*["']([^"']+)["']""")
LEGACY_OWNER_RE = re.compile(r"""["']owner["']""")


def test_hay_rutas_que_revisar():
    assert ROUTE_FILES, f"No se encontraron rutas en {ROUTES_DIR}"


@pytest.mark.parametrize("path", ROUTE_FILES, ids=lambda p: p.name)
def test_guards_usan_roles_existentes(path):
    source = path.read_text(encoding="utf-8")
    desconocidos = {rol for rol in GUARD_RE.findall(source) if rol not in ROLE_HIERARCHY}
    assert not desconocidos, f"{path.name}: roles inexistentes en guards: {desconocidos}"


@pytest.mark.parametrize("path", ROUTE_FILES, ids=lambda p: p.name)
def test_sin_rol_owner_literal(path):
    source = path.read_text(encoding="utf-8")
    lineas = [
        n for n, linea in enumerate(source.splitlines(), 1) if LEGACY_OWNER_RE.search(linea)
    ]
    assert not lineas, f"{path.name}: usa el rol 'owner' (debe ser 'workspace_owner') en líneas {lineas}"
