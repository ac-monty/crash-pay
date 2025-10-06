"""
Provider factory for creating LLM providers.
Centralized provider creation with dynamic configuration loading.
"""

from typing import Dict, Type, Any, Optional, List
from app.config.settings import get_settings
from app.utils.logging import get_service_logger, performance_monitor, log_security_event
from .base import BaseLLMProvider, ConnectionMode, ProviderError
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .google_provider import GoogleProvider
from .cohere_provider import CohereProvider
from .mistral_provider import MistralProvider
from .fireworks_provider import FireworksProvider


# Initialize service logger
service_logger = get_service_logger(__name__)


class ProviderFactory:
    """Factory for creating LLM provider instances."""
    
    # Registry of available providers
    _providers: Dict[str, Type[BaseLLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,  # ✅ IMPLEMENTED
        "google": GoogleProvider,        # ✅ IMPLEMENTED
        "cohere": CohereProvider,
        "mistral": MistralProvider,      # ✅ IMPLEMENTED
        "fireworks": FireworksProvider,  # ✅ IMPLEMENTED
        # TODO: Add other providers as they're implemented
        # "azure_openai": AzureOpenAIProvider,
        # "together": TogetherProvider,
        # "replicate": ReplicateProvider,
        # "huggingface": HuggingFaceProvider,
        # "perplexity": PerplexityProvider,
    }
    
    @classmethod
    def get_available_providers(cls) -> List[str]:
        """Get list of available provider names."""
        return list(cls._providers.keys())
    
    @classmethod
    def is_provider_available(cls, provider_name: str) -> bool:
        """Check if a provider is available."""
        return provider_name in cls._providers
    
    @classmethod
    @performance_monitor("provider_factory.create_provider")
    def create_provider(
        cls, 
        provider_name: str, 
        model: str, 
        api_key: Optional[str] = None,
        connection_mode: Optional[ConnectionMode] = None,
        **kwargs
    ) -> BaseLLMProvider:
        """
        Create a provider instance with enhanced logging.
        
        Args:
            provider_name: Name of the provider (e.g., 'openai', 'anthropic')
            model: Model name/ID
            api_key: API key (if None, will get from settings)
            connection_mode: Connection mode (if None, will get from settings)
            **kwargs: Additional provider-specific configuration
            
        Returns:
            Configured provider instance
            
        Raises:
            ProviderError: If provider is not available or configuration is invalid
        """
        service_logger.debug("Creating provider instance",
                           provider=provider_name,
                           model=model,
                           has_api_key=bool(api_key),
                           connection_mode=connection_mode.value if connection_mode else None,
                           additional_params=list(kwargs.keys()))
        
        if not cls.is_provider_available(provider_name):
            available = ", ".join(cls.get_available_providers())
            service_logger.error("Unsupported provider requested",
                               requested_provider=provider_name,
                               available_providers=available)
            raise ProviderError(
                f"Provider '{provider_name}' not available. Available providers: {available}",
                provider_name,
                model
            )
        
        settings = get_settings()
        
        # Get API key from settings if not provided
        if api_key is None:
            with service_logger.performance_context("api_key_retrieval", provider=provider_name):
                api_key = cls._get_api_key_for_provider(provider_name)
        
        if not api_key:
            service_logger.error("API key not found",
                               provider=provider_name)
            raise ProviderError(
                f"No API key found for provider '{provider_name}'. "
                f"Set the appropriate environment variable.",
                provider_name,
                model
            )
        
        # Set connection mode
        if connection_mode is None:
            connection_mode = ConnectionMode(settings.llm_connection_mode)
            service_logger.debug("Using default connection mode",
                               connection_mode=connection_mode.value)
        
        # Security logging for provider creation
        log_security_event("info", "Provider instance creation initiated",
                         provider=provider_name,
                         model=model,
                         connection_mode=connection_mode.value,
                         has_api_key=bool(api_key))
        
        # Add connection mode to kwargs
        kwargs['connection_mode'] = connection_mode
        
        # Get provider class and create instance
        provider_class = cls._providers[provider_name]
        
        try:
            # Add provider-specific configuration
            with service_logger.performance_context("provider_config", provider=provider_name):
                provider_config = cls._get_provider_config(provider_name, **kwargs)
                
            with service_logger.performance_context("provider_instantiation", 
                                                   provider=provider_name,
                                                   model=model):
                provider_instance = provider_class(model, api_key, **provider_config)
                
                service_logger.debug("Provider instance created",
                                   provider=provider_name,
                                   model=model,
                                   config_keys=list(provider_config.keys()))
            
            # Validate configuration
            with service_logger.performance_context("provider_validation", provider=provider_name):
                if not provider_instance.validate_config():
                    service_logger.error("Provider configuration validation failed",
                                       provider=provider_name,
                                       model=model)
                    raise ProviderError(
                        f"Invalid configuration for provider '{provider_name}'",
                        provider_name,
                        model
                    )
            
            service_logger.info("Provider created successfully",
                              provider=provider_name,
                              model=model,
                              connection_mode=connection_mode.value,
                              capabilities=str(provider_instance.capabilities))
            
            return provider_instance
            
        except Exception as e:
            service_logger.error("Provider creation failed",
                               provider=provider_name,
                               model=model,
                               error=e)
            if isinstance(e, ProviderError):
                raise e
            else:
                raise ProviderError(
                    f"Failed to create provider '{provider_name}': {str(e)}",
                    provider_name,
                    model
                )
    
    @classmethod
    def create_from_settings(cls) -> BaseLLMProvider:
        """Create a provider instance using current settings."""
        settings = get_settings()
        return cls.create_provider(
            provider_name=settings.llm_provider,
            model=settings.llm_model
        )
    
    @classmethod
    def _get_api_key_for_provider(cls, provider_name: str) -> Optional[str]:
        """Get the API key for a specific provider from settings."""
        settings = get_settings()
        
        api_key_mapping = {
            "openai": settings.openai_api_key,
            "anthropic": settings.anthropic_api_key,
            "google": settings.google_api_key,
            "cohere": settings.cohere_api_key,
            "mistral": settings.mistral_api_key,
            "azure_openai": settings.azure_openai_api_key,
            "together": settings.together_api_key,
            "replicate": settings.replicate_api_token,
            "huggingface": settings.huggingface_api_token,
            "perplexity": settings.perplexity_api_key,
            "fireworks": settings.fireworks_api_key,
        }
        
        return api_key_mapping.get(provider_name)
    
    @classmethod
    def _get_provider_config(cls, provider_name: str, **kwargs) -> Dict:
        """Get provider-specific configuration."""
        settings = get_settings()
        config = kwargs.copy()
        
        # Provider-specific configuration
        if provider_name == "openai":
            config.update({
                "org_id": settings.openai_org_id,
                "base_url": kwargs.get("base_url", "https://api.openai.com/v1")
            })
        elif provider_name == "azure_openai":
            config.update({
                "endpoint": settings.azure_openai_endpoint,
                "api_version": settings.azure_openai_api_version,
                "deployment_name": settings.azure_openai_deployment_name
            })
        # Add other provider-specific configurations as needed
        
        return config
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseLLMProvider]):
        """Register a new provider class."""
        cls._providers[name] = provider_class
    
    @classmethod
    def get_provider_capabilities(cls, provider_name: str, model: str) -> Dict:
        """Get capabilities for a provider/model combination without creating instance."""
        if not cls.is_provider_available(provider_name):
            return {}
        
        try:
            # Create a temporary instance to get capabilities
            # Using a dummy API key since we're only getting capabilities
            provider_class = cls._providers[provider_name]
            temp_instance = provider_class(model, "dummy_key")
            return temp_instance.get_model_info()
        except Exception:
            return {}


# Global factory instance
provider_factory = ProviderFactory()


def get_provider_factory() -> ProviderFactory:
    """Get the global provider factory instance."""
    return provider_factory 