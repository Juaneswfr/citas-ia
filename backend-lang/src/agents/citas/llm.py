"""Fábrica del LLM desde Settings. Sin clave configurada falla cerrado (no hay respuesta de relleno)."""
from agents.citas.errors import LLMNotConfigured


def build_llm(settings):
    """Crea el chat model según AGENT_LLM_PROVIDER ('anthropic' | 'openai').

    Raises:
        LLMNotConfigured: si falta AGENT_LLM_API_KEY o el proveedor no es soportado.
    """
    if not settings.agent_llm_api_key:
        raise LLMNotConfigured("AGENT_LLM_API_KEY no configurada")
    provider = settings.agent_llm_provider.lower()
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=settings.agent_llm_model, api_key=settings.agent_llm_api_key,
                             timeout=settings.graph_timeout, max_retries=1)
    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=settings.agent_llm_model, api_key=settings.agent_llm_api_key,
                          timeout=settings.graph_timeout, max_retries=1)
    raise LLMNotConfigured(f"AGENT_LLM_PROVIDER no soportado: {provider}")
