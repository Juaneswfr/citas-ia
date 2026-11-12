"""Catálogo de tipos de negocio: validación, vocabulario del agente y espejo con el frontend."""
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from core.business_types import (
    BUSINESS_PROFILES, BUSINESS_TYPE_IDS, DEFAULT_BUSINESS_TYPE, get_profile, validate_business_type,
)
from schemas.workspace import WorkspaceUpdate
from services import appointment_agent

FRONT_CATALOG = Path(__file__).resolve().parents[2] / "front" / "src" / "lib" / "business-types.ts"


def _ctx(business_type):
    return {"workspace": {"name": "Negocio X", "timezone": "UTC", "business_type": business_type}}


def test_perfil_desconocido_o_vacio_cae_en_generico():
    for value in (None, "", "no-existe"):
        assert get_profile(value).id == DEFAULT_BUSINESS_TYPE
    assert get_profile(None).staff_singular == "profesional"


def test_cada_perfil_tiene_vocabulario_completo():
    for profile in BUSINESS_PROFILES.values():
        assert profile.label and profile.staff_singular and profile.staff_plural, profile.id


def test_validacion_es_lista_de_permitidos():
    assert validate_business_type(None) is None
    assert validate_business_type("barberia") == "barberia"
    with pytest.raises(ValueError):
        validate_business_type("barberia'; DROP TABLE workspaces;--")


def test_workspace_update_rechaza_tipo_desconocido():
    assert WorkspaceUpdate(business_type="consultorio").business_type == "consultorio"
    with pytest.raises(ValidationError):
        WorkspaceUpdate(business_type="carniceria")


def test_un_negocio_no_puede_reactivarse_a_si_mismo():
    # Suspender/reactivar es del panel de plataforma: `is_active` no es editable por el negocio.
    assert "is_active" not in WorkspaceUpdate.model_fields


@pytest.mark.parametrize("business_type,singular,heading", [
    ("barberia", "barbero", "BARBEROS DISPONIBLES"),
    ("consultorio", "doctor", "DOCTORES DISPONIBLES"),
    ("veterinaria", "veterinario", "VETERINARIOS DISPONIBLES"),
    (None, "profesional", "PROFESIONALES DISPONIBLES"),
])
def test_prompt_usa_el_vocabulario_de_la_industria(business_type, singular, heading):
    prompt = appointment_agent.build_system_prompt(_ctx(business_type), "servicios", "equipo")
    assert heading in prompt
    assert f"es un {singular}" in prompt
    if business_type != "barberia":
        assert "barbero" not in prompt.lower()


def test_prompt_de_salud_prohibe_diagnosticos_y_el_de_barberia_no():
    assert "diagnósticos" in appointment_agent.build_system_prompt(_ctx("odontologia"), "s", "e")
    assert "diagnósticos" not in appointment_agent.build_system_prompt(_ctx("barberia"), "s", "e")


def test_herramientas_tienen_nombres_neutros():
    tools = appointment_agent.build_tools(
        {"workspace_id": "ws-1", "workspace": {"timezone": "UTC", "business_type": "spa"}}, {})
    names = {t.name for t in tools}
    assert "listar_profesionales" in names
    assert not any("barber" in name for name in names)
    by_name = {t.name: t for t in tools}
    assert "terapeutas" in by_name["listar_profesionales"].description


def test_catalogo_del_front_tiene_los_mismos_ids():
    source = FRONT_CATALOG.read_text(encoding="utf-8")
    front_ids = set(re.findall(r"\{\s*id:\s*'([a-z_]+)'", source))
    assert front_ids == set(BUSINESS_TYPE_IDS), front_ids ^ set(BUSINESS_TYPE_IDS)
