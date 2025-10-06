"""
Model registry and switching service.
Handles dynamic model registration, validation, and switching operations.
"""

import os
from typing import Dict, Any, Optional, List
from langchain_core.messages import HumanMessage

from app.config.settings import get_settings
from app.utils.logging import log_llm_event
from app.config.registry_loader import (
    load_model_registry,
    get_available_providers, 
    get_provider_models,
    get_api_model_name,
    is_reasoning_model
)
from app.utils.singleton import singleton_factory


class ModelRegistry:
    """Dynamic model registry for programmatic provider and model switching."""
    
    _registry_cache = None
    _config_file = 'model_registry.json'
    
    @classmethod
    def _load_registry(cls) -> Dict[str, Any]:
        """Load model registry using the new configuration loading."""
        if cls._registry_cache is None:
            try:
                config = load_model_registry()
                cls._registry_cache = config.get('model_registry', {})
                settings = get_settings()
                log_llm_event("info", f"Loaded model registry with {len(cls._registry_cache)} providers", 
                             settings.llm_provider, settings.llm_model)
            except Exception as e:
                settings = get_settings()
                log_llm_event("error", f"Failed to load model registry: {str(e)}", 
                             settings.llm_provider, settings.llm_model, error=e)
                # Fallback to empty registry
                cls._registry_cache = {}
        return cls._registry_cache
    
    @classmethod
    def reload_registry(cls):
        """Reload the model registry."""
        cls._registry_cache = None
        return cls._load_registry()
    
    @classmethod
    def get_all_providers(cls) -> List[str]:
        """Get list of all available providers."""
        registry = cls._load_registry()
        return list(registry.keys())
    
    @classmethod
    def get_models_by_provider(cls, provider: str) -> Dict[str, Dict[str, str]]:
        """Get all models for a specific provider grouped by type."""
        registry = cls._load_registry()
        return registry.get(provider, {})
    
    @classmethod
    def get_model_api_name(cls, provider: str, friendly_name: str) -> Optional[str]:
        """Get the actual API model name from friendly name."""
        try:
            return get_api_model_name(provider, friendly_name)
        except ValueError:
            return None
    
    @classmethod
    def get_model_type(cls, provider: str, friendly_name: str) -> Optional[str]:
        """Get the model type (reasoning or one_shot) for a model."""
        provider_models = cls.get_models_by_provider(provider)
        
        for category in ["reasoning", "one_shot"]:
            if category in provider_models:
                if friendly_name in provider_models[category]:
                    return category
        
        return None
    
    @classmethod
    def get_friendly_name(cls, provider: str, api_name: str) -> Optional[str]:
        """Get friendly name from API model name."""
        provider_models = cls.get_models_by_provider(provider)
        
        for category in ["reasoning", "one_shot"]:
            if category in provider_models:
                for friendly, api in provider_models[category].items():
                    if api == api_name:
                        return friendly
        
        return None
    
    @classmethod
    def validate_model_combo(cls, provider: str, model: str) -> bool:
        """Validate if provider and model combination exists."""
        return cls.get_model_api_name(provider, model) is not None
    
    @classmethod
    def get_model_capabilities(cls, provider: str, model: str) -> Dict[str, Any]:
        """Get model capabilities based on provider and type."""
        model_type = cls.get_model_type(provider, model)
        api_name = cls.get_model_api_name(provider, model)
        
        if not model_type or not api_name:
            return {}
        
        # Basic capabilities based on provider and type
        capabilities = {
            "provider": provider,
            "friendly_name": model,
            "api_name": api_name,
            "type": model_type,
            "supports_function_calling": False,
            "supports_streaming": True,
            "supports_system_prompts": True,
            "reasoning_model": model_type == "reasoning"
        }
        
        # Provider-specific capability adjustments
        if provider == "openai":
            capabilities.update({
                "supports_function_calling": True,
                "supports_structured_outputs": True,
                "supports_system_prompts": model_type != "reasoning",
                "max_context_length": 128000
            })
        elif provider == "anthropic":
            capabilities.update({
                "supports_function_calling": True,
                "supports_structured_outputs": False,
                "max_context_length": 200000
            })
        elif provider == "google":
            capabilities.update({
                "supports_function_calling": True,
                "supports_structured_outputs": False,
                "max_context_length": 2000000
            })
        elif provider == "cohere":
            capabilities.update({
                "supports_function_calling": True,
                "supports_structured_outputs": False,
                "max_context_length": 128000
            })
        elif provider == "mistral":
            capabilities.update({
                "supports_function_calling": True,
                "supports_structured_outputs": False,
                "max_context_length": 32768
            })
        elif provider == "fireworks":
            # Fireworks supports function calling for most models
            capabilities.update({
                "supports_function_calling": True,
                "supports_structured_outputs": False,
                "max_context_length": 32768
            })
        
        return capabilities

    @classmethod
    def get_default_params(cls, provider: str, friendly_name: str) -> Dict[str, Any]:
        """Return optional default parameters for a provider/model combo.

        The JSON structure allows an optional top-level key `model_parameters` with nested
        provider → friendly_name → params mapping. If not present or not found, returns {}.
        """
        try:
            config = load_model_registry()
            all_params = config.get("model_parameters", {})
            provider_params = (all_params or {}).get(provider, {})
            params = (provider_params or {}).get(friendly_name, {})
            if isinstance(params, dict):
                return params
        except Exception:
            pass
        return {}


class ModelSwitcher:
    """Handles dynamic model switching with validation and rollback."""
    
    def __init__(self):
        self.previous_provider = None
        self.previous_model = None
        
    async def switch_model(self, provider: str, model: str, validate: bool = True) -> Dict[str, Any]:
        """Switch to a new provider and model combination."""
        from app.providers.factory import provider_factory  # Import here to avoid circular dependency
        from app.providers.base import ConnectionMode
        
        settings = get_settings()
        
        # Store current state for rollback
        self.previous_provider = settings.llm_provider
        self.previous_model = settings.llm_model
        
        try:
            # Validate the combination
            if validate and not ModelRegistry.validate_model_combo(provider, model):
                raise ValueError(f"Invalid provider/model combination: {provider}/{model}")
            
            # Get API model name
            api_model_name = ModelRegistry.get_model_api_name(provider, model)
            if not api_model_name:
                raise ValueError(f"Could not find API name for {provider}/{model}")
            
            # Update settings
            settings.llm_provider = provider
            settings.llm_model = api_model_name
            
            # Test the new configuration
            if validate:
                test_result = await self._test_model_connection()
                if not test_result["success"]:
                    # Rollback on failure
                    self.rollback()
                    raise Exception(f"Model test failed: {test_result['error']}")
            
            # Get model capabilities
            capabilities = ModelRegistry.get_model_capabilities(provider, model)
            
            log_llm_event("info", f"Successfully switched to {provider}/{model}", 
                         provider, api_model_name, 
                         friendly_name=model, previous_provider=self.previous_provider, 
                         previous_model=self.previous_model)
            
            return {
                "success": True,
                "provider": provider,
                "friendly_name": model,
                "api_name": api_model_name,
                "previous_provider": self.previous_provider,
                "previous_model": self.previous_model,
                "capabilities": capabilities
            }
            
        except Exception as e:
            # Rollback on error
            if self.previous_provider and self.previous_model:
                self.rollback()
            
            log_llm_event("error", f"Failed to switch to {provider}/{model}: {str(e)}", 
                         provider, model, error=e)
            
            return {
                "success": False,
                "error": str(e),
                "provider": settings.llm_provider,
                "model": settings.llm_model
            }
    
    def rollback(self) -> Dict[str, Any]:
        """Rollback to the previous model configuration."""
        settings = get_settings()
        
        if self.previous_provider and self.previous_model:
            old_provider = settings.llm_provider
            old_model = settings.llm_model
            
            settings.llm_provider = self.previous_provider
            settings.llm_model = self.previous_model
            
            log_llm_event("info", f"Rolled back from {old_provider}/{old_model} to {self.previous_provider}/{self.previous_model}", 
                         self.previous_provider, self.previous_model)
            
            return {
                "success": True,
                "message": f"Rolled back to {self.previous_provider}/{self.previous_model}",
                "current_provider": settings.llm_provider,
                "current_model": settings.llm_model
            }
        else:
            return {
                "success": False,
                "error": "No previous configuration to rollback to"
            }
    
    async def _test_model_connection(self) -> Dict[str, Any]:
        """Test the current model configuration."""
        try:
            from app.providers.factory import provider_factory  # Import here to avoid circular dependency
            from app.providers.base import ConnectionMode
            import asyncio
            
            settings = get_settings()
            
            # Simple connection test
            connection_mode = ConnectionMode(settings.llm_connection_mode)
            llm = provider_factory.create_provider(
                provider_name=settings.llm_provider,
                model=settings.llm_model,
                connection_mode=connection_mode
            )
            
            # Test with the provider's test_connection method
            test_result = await llm.test_connection()
            
            if test_result.get("success"):
                return {"success": True, "message": "Model connection successful", "response": test_result.get("test_response", "")}
            else:
                return {"success": False, "error": test_result.get("error", "Connection test failed")}
                    
        except Exception as e:
            return {"success": False, "error": str(e)}


@singleton_factory
def get_model_switcher() -> ModelSwitcher:
    """Get the global model switcher instance."""
    return ModelSwitcher() 