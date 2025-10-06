"""
Provider module for LLM integrations.
Provides a unified interface for different LLM providers with support for both
direct API calls and LangChain integration.
"""

from .base import (
    BaseLLMProvider,
    ProviderCapabilities,
    ConnectionMode,
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderModelNotFoundError,
    ProviderConnectionError
)

from .factory import (
    ProviderFactory,
    provider_factory,
    get_provider_factory
)

from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
# from .cohere_provider import CohereProvider  # Temporarily disabled due to langchain-cohere import issues
from .mistral_provider import MistralProvider
from .fireworks_provider import FireworksProvider

# Easy access to commonly used items
__all__ = [
    # Base classes and interfaces
    "BaseLLMProvider",
    "ProviderCapabilities", 
    "ConnectionMode",
    
    # Exceptions
    "ProviderError",
    "ProviderAuthenticationError",
    "ProviderRateLimitError", 
    "ProviderModelNotFoundError",
    "ProviderConnectionError",
    
    # Factory
    "ProviderFactory",
    "provider_factory",
    "get_provider_factory",
    
    # Concrete providers
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleProvider",
    # "CohereProvider",  # Temporarily disabled due to langchain-cohere import issues
    "MistralProvider",
    "FireworksProvider",
]


def create_provider(provider_name: str, model: str, **kwargs):
    """Convenience function to create a provider instance."""
    return provider_factory.create_provider(provider_name, model, **kwargs)


def get_available_providers():
    """Convenience function to get available providers."""
    return provider_factory.get_available_providers()


def is_provider_available(provider_name: str):
    """Convenience function to check if a provider is available."""
    return provider_factory.is_provider_available(provider_name)
