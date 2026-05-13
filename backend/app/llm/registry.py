from app.llm.base import LLMProvider, ProviderDisabledError
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.google import GoogleProvider
from app.llm.providers.openai import OpenAIProvider
from app.llm.providers.openrouter import OpenRouterProvider
from app.models import LLMProviderEnum
from app.settings import get_settings

_PROVIDER_CLASSES: dict[LLMProviderEnum, type[LLMProvider]] = {
    LLMProviderEnum.anthropic: AnthropicProvider,
    LLMProviderEnum.openai: OpenAIProvider,
    LLMProviderEnum.google: GoogleProvider,
    LLMProviderEnum.openrouter: OpenRouterProvider,
}


def _api_key_for(provider: LLMProviderEnum) -> str | None:
    s = get_settings()
    match provider:
        case LLMProviderEnum.anthropic:
            return s.anthropic_api_key
        case LLMProviderEnum.openai:
            return s.openai_api_key
        case LLMProviderEnum.google:
            return s.google_api_key
        case LLMProviderEnum.openrouter:
            return s.openrouter_api_key


def get_provider(provider: LLMProviderEnum) -> LLMProvider:
    cls = _PROVIDER_CLASSES[provider]
    return cls(api_key=_api_key_for(provider))


def provider_status() -> dict[str, bool]:
    return {p.value: get_provider(p).enabled for p in LLMProviderEnum}


__all__ = [
    "get_provider",
    "provider_status",
    "ProviderDisabledError",
]
