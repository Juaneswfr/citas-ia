"""Reglas comunes de los tests.

`api.main` hace `load_dotenv()`: si algún test importa la app, las claves reales del `.env` quedan en el entorno.
Ningún test debe hablar con LangSmith (ni leerlo ni mandarle trazos), así que se quitan siempre. Los tests que
necesitan una clave la ponen ellos mismos con `monkeypatch.setenv`.
"""
import pytest

_LANGSMITH_VARS = ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY", "LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2",
                   "LANGSMITH_PROJECT", "LANGCHAIN_PROJECT")


@pytest.fixture(autouse=True)
def sin_langsmith(monkeypatch):
    for name in _LANGSMITH_VARS:
        monkeypatch.delenv(name, raising=False)
