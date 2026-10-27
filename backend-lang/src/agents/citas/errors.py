"""Errores tipados del agente de citas. `message` es seguro de mostrar al modelo/cliente."""


class CitasError(Exception):
    """Base: la operación no se realizó. Nunca se confirma al cliente."""

    code = "error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidInput(CitasError):
    """Argumentos del modelo mal formados o fuera de rango."""

    code = "invalid_input"


class NotFoundOrNotAllowed(CitasError):
    """El id no existe en el workspace fijo, o la cita no es del cliente de la conversación."""

    code = "not_found"


class SlotConflict(CitasError):
    """El horario se solapa con una cita o bloqueo existente."""

    code = "slot_conflict"


class CalendarFailure(CitasError):
    """Google Calendar no respondió o rechazó la operación."""

    code = "calendar_failure"


class LLMNotConfigured(Exception):
    """No hay clave/modelo para el LLM: el agente falla cerrado."""
