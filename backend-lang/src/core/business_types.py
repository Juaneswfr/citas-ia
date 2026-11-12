"""
Catálogo de tipos de negocio (industrias) que atiende la plataforma.

Es la única fuente de verdad en el backend para:
- validar `workspaces.business_type` (lista de permitidos),
- el vocabulario del agente de citas (cómo se llama quien atiende: barbero, estilista, doctor…),
- las advertencias propias de cada industria (p. ej. salud: no dar diagnósticos).

El frontend tiene su espejo en `front/src/lib/business-types.ts` (iconos y servicios sugeridos);
los `id` deben coincidir. `tests/test_business_types.py` lo vigila.
"""
from dataclasses import dataclass

DEFAULT_BUSINESS_TYPE = "otro"

_HEALTH_NOTE = (
    "No des diagnósticos, no recomiendes medicamentos ni tratamientos y no interpretes síntomas: "
    "ofrece agendar una cita para que lo revise el profesional. "
    "Si el cliente describe una urgencia, dile que acuda a un servicio de urgencias."
)


@dataclass(frozen=True)
class BusinessProfile:
    """Vocabulario y reglas de una industria."""

    id: str
    label: str
    staff_singular: str
    staff_plural: str
    agent_note: str = ""


_PROFILES: tuple[BusinessProfile, ...] = (
    BusinessProfile("barberia", "Barbería", "barbero", "barberos"),
    BusinessProfile("salon", "Salón de belleza", "estilista", "estilistas"),
    BusinessProfile("manicure", "Manicure y pedicure", "manicurista", "manicuristas"),
    BusinessProfile("spa", "Spa y bienestar", "terapeuta", "terapeutas"),
    BusinessProfile("estetica", "Centro de estética", "esteticista", "esteticistas"),
    BusinessProfile("tatuajes", "Estudio de tatuajes", "tatuador", "tatuadores"),
    BusinessProfile("consultorio", "Consultorio médico", "doctor", "doctores", _HEALTH_NOTE),
    BusinessProfile("odontologia", "Odontología", "odontólogo", "odontólogos", _HEALTH_NOTE),
    BusinessProfile("psicologia", "Psicología", "psicólogo", "psicólogos", _HEALTH_NOTE),
    BusinessProfile("fisioterapia", "Fisioterapia", "fisioterapeuta", "fisioterapeutas", _HEALTH_NOTE),
    BusinessProfile(
        "veterinaria", "Veterinaria", "veterinario", "veterinarios",
        "No des diagnósticos ni recomiendes medicamentos para la mascota: ofrece agendar una cita. "
        "Si describe una urgencia, dile que la lleve de inmediato a una clínica veterinaria.",
    ),
    BusinessProfile("fitness", "Entrenamiento y fitness", "entrenador", "entrenadores"),
    BusinessProfile(DEFAULT_BUSINESS_TYPE, "Otro negocio", "profesional", "profesionales"),
)

BUSINESS_PROFILES: dict[str, BusinessProfile] = {p.id: p for p in _PROFILES}
BUSINESS_TYPE_IDS: tuple[str, ...] = tuple(BUSINESS_PROFILES)


def get_profile(business_type: str | None) -> BusinessProfile:
    """Perfil de la industria; un valor vacío o desconocido cae en el perfil genérico («profesional»)."""
    return BUSINESS_PROFILES.get(business_type or "", BUSINESS_PROFILES[DEFAULT_BUSINESS_TYPE])


def validate_business_type(value: str | None) -> str | None:
    """
    Valida un `business_type` recibido del cliente (lista de permitidos).

    Raises:
        ValueError: si el valor no está en el catálogo.
    """
    if value is None:
        return None
    if value not in BUSINESS_PROFILES:
        raise ValueError(f"Tipo de negocio no válido. Permitidos: {', '.join(BUSINESS_TYPE_IDS)}")
    return value
