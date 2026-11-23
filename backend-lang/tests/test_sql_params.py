"""Guarda contra un error que solo se ve con Postgres real: `fecha - :parametro`.

Postgres infiere el tipo del parámetro por el operador: en `fecha - $1` lo toma como FECHA (fecha - fecha = entero) y
la consulta falla con «operator does not exist: date > integer». Los tests con BD falsa no ejecutan el SQL y no lo ven.
Un parámetro numérico que se resta o suma a una fecha debe llevar `CAST(:x AS INTEGER)` (o ir dentro de `make_interval`).
"""
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
FILES = ["services/billing_costs.py", "services/billing_cartera.py", "services/billing_metrics.py",
         "services/subscription_service.py", "services/billing_service.py", "services/billing_documents.py",
         "services/billing_plans.py", "workers/billing_worker.py"]
# un parámetro con nombre restado o sumado a algo, que no esté ya envuelto en CAST(...) ni en make_interval(...)
RISKY = re.compile(r"[-+]\s*:[a-z_]+\b")


@pytest.mark.parametrize("path", FILES)
def test_ningun_parametro_se_resta_o_suma_a_una_fecha_sin_cast(path):
    bad = []
    for n, line in enumerate((SRC / path).read_text(encoding="utf-8").splitlines(), 1):
        if RISKY.search(line) and "CAST(" not in line.upper() and "make_interval" not in line:
            bad.append(f"{path}:{n}: {line.strip()}")
    assert not bad, "Parámetro sin tipo en una operación con fechas:\n" + "\n".join(bad)
