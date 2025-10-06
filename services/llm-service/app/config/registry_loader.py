"""
Model Registry Loader - Single source of truth for model configurations.
"""
import json
from pathlib import Path
from typing import Dict, Any


def load_model_registry() -> Dict[str, Any]:
    """
    Load model registry from config file.
    
    Returns:
        Dict containing the complete model registry configuration.
    """
    config_path = Path(__file__).parent / "model_registry.json"
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Model registry file not found: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in model registry: {e}")


def get_provider_models(provider_name: str) -> Dict[str, Dict[str, str]]:
    """
    Get all models for a specific provider.
    
    Args:
        provider_name: Name of the provider (e.g., 'openai', 'anthropic', 'google')
    
    Returns:
        Dict containing model categories and their mappings for the provider.
    """
    registry = load_model_registry()
    model_registry = registry.get("model_registry", {})
    
    if provider_name not in model_registry:
        raise ValueError(f"Provider '{provider_name}' not found in model registry")
    
    return model_registry[provider_name]


def get_model_mappings(provider_name: str) -> Dict[str, str]:
    """
    Get flattened model mappings for a provider.
    
    Args:
        provider_name: Name of the provider
    
    Returns:
        Dict mapping friendly names to API model names
    """
    provider_models = get_provider_models(provider_name)
    mappings = {}
    
    # Flatten all categories into a single mapping
    for category_models in provider_models.values():
        mappings.update(category_models)
    
    return mappings


def get_available_providers() -> list:
    """
    Get list of all available providers.
    
    Returns:
        List of provider names.
    """
    registry = load_model_registry()
    return list(registry.get("model_registry", {}).keys())


def is_reasoning_model(provider_name: str, model_name: str) -> bool:
    """
    Check if a model is classified as a reasoning model.
    
    Args:
        provider_name: Name of the provider
        model_name: Friendly name of the model
    
    Returns:
        True if the model is in the reasoning category
    """
    try:
        provider_models = get_provider_models(provider_name)
        reasoning_models = provider_models.get("reasoning", {})
        return model_name in reasoning_models
    except (ValueError, KeyError):
        return False


def get_api_model_name(provider_name: str, friendly_name: str) -> str:
    """
    Get the API model name for a friendly model name.
    
    Args:
        provider_name: Name of the provider
        friendly_name: Friendly name of the model
    
    Returns:
        API model name for the provider
        
    Raises:
        ValueError: If provider or model not found
    """
    mappings = get_model_mappings(provider_name)
    
    if friendly_name not in mappings:
        available_models = ", ".join(mappings.keys())
        raise ValueError(
            f"Model '{friendly_name}' not found for provider '{provider_name}'. "
            f"Available models: {available_models}"
        )
    
    return mappings[friendly_name] 