"""
Model and provider management routes.
Handles model discovery, switching, testing, and registry management.
"""

import time
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query

from app.config.settings import get_settings
from app.services.model_registry import ModelRegistry, get_model_switcher
from app.config.system_prompt_loader import get_system_prompt_loader, reload_system_prompts
from app.utils.logging import log_llm_event
from app.models.responses import (
    ModelSwitchResponse,
    ModelListResponse,
    HealthResponse
)
# Legacy import removed - now using provider capabilities

router = APIRouter()


def get_model_switcher_dependency():
    """Dependency to get the model switcher instance."""
    return get_model_switcher()


@router.post("/switch-model", 
             summary="Dynamically switch LLM model (runtime)",
             response_model=ModelSwitchResponse)
async def switch_model(
    provider: str, 
    model: str, 
    should_validate: bool = True,
    model_switcher = Depends(get_model_switcher_dependency)
):
    """Dynamically switch to a different LLM provider and model at runtime."""
    try:
        result = await model_switcher.switch_model(provider, model, should_validate)
        
        if result["success"]:
            return ModelSwitchResponse(
                success=True,
                message=f"Successfully switched to {provider}/{model}",
                previous_provider=result["previous_provider"],
                previous_model=result["previous_model"],
                new_provider=result["provider"],
                new_model=result["api_name"]
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Model switch failed: {result['error']}"
            )
            
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Model switch endpoint error: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during model switch: {str(e)}"
        )


@router.post("/rollback-model", 
             summary="Rollback to previous model",
             response_model=ModelSwitchResponse)
async def rollback_model(
    model_switcher = Depends(get_model_switcher_dependency)
):
    """Rollback to the previous model configuration."""
    try:
        result = model_switcher.rollback()
        
        if result["success"]:
            return ModelSwitchResponse(
                success=True,
                message=result["message"],
                current_provider=result["current_provider"],
                current_model=result["current_model"]
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result["error"]
            )
            
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Model rollback error: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Internal error during rollback: {str(e)}"
        )


@router.get("/available-models", 
            summary="Get all available models by provider",
            response_model=ModelListResponse)
async def get_available_models():
    """Get comprehensive list of all available models grouped by provider and type."""
    try:
        settings = get_settings()
        all_models = {}
        
        for provider in ModelRegistry.get_all_providers():
            provider_models = ModelRegistry.get_models_by_provider(provider)
            
            # Get friendly name for current model if it matches this provider
            current_friendly = None
            if provider == settings.llm_provider:
                current_friendly = ModelRegistry.get_friendly_name(provider, settings.llm_model)
            
            all_models[provider] = {
                "reasoning": provider_models.get("reasoning", {}),
                "one_shot": provider_models.get("one_shot", {}),
                "is_current_provider": provider == settings.llm_provider,
                "current_model": current_friendly if provider == settings.llm_provider else None
            }
        
        total_models = sum(len(p.get("reasoning", {})) + len(p.get("one_shot", {})) for p in all_models.values())
        
        return ModelListResponse(
            current_provider=settings.llm_provider,
            current_model=settings.llm_model,
            connection_mode=settings.llm_connection_mode,
            available_models=all_models
        )
        
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Error getting available models: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get available models: {str(e)}"
        )


@router.get("/models/{provider}", 
            summary="Get models for specific provider")
async def get_provider_models(provider: str):
    """Get all models for a specific provider."""
    try:
        if provider not in ModelRegistry.get_all_providers():
            raise HTTPException(
                status_code=404,
                detail=f"Provider '{provider}' not found. Available: {', '.join(ModelRegistry.get_all_providers())}"
            )
        
        settings = get_settings()
        provider_models = ModelRegistry.get_models_by_provider(provider)
        
        return {
            "provider": provider,
            "models": provider_models,
            "is_current_provider": provider == settings.llm_provider,
            "current_model": ModelRegistry.get_friendly_name(provider, settings.llm_model) if provider == settings.llm_provider else None,
            "total_models": len(provider_models.get("reasoning", {})) + len(provider_models.get("one_shot", {}))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Error getting models for provider {provider}: {str(e)}", 
                      provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get models for provider {provider}: {str(e)}"
        )


@router.get("/current-model", 
            summary="Get current model information")
async def get_current_model(
    model_switcher = Depends(get_model_switcher_dependency)
):
    """Get detailed information about the currently active model."""
    try:
        settings = get_settings()
        
        # Get friendly name and capabilities
        friendly_name = ModelRegistry.get_friendly_name(settings.llm_provider, settings.llm_model)
        capabilities = ModelRegistry.get_model_capabilities(settings.llm_provider, friendly_name or settings.llm_model)
        model_type = ModelRegistry.get_model_type(settings.llm_provider, friendly_name or settings.llm_model)
        
        # Test model connection
        test_result = await model_switcher._test_model_connection()
        
        return {
            "provider": settings.llm_provider,
            "api_model": settings.llm_model,
            "friendly_name": friendly_name,
            "type": model_type,
            "capabilities": capabilities,
            "connection_status": test_result,
            "is_reasoning_model": model_type == "reasoning",
            "supports_function_calling": capabilities.get("supports_function_calling", False),
            "supports_streaming": capabilities.get("supports_streaming", True),
            "max_context_length": capabilities.get("max_context_length", "unknown")
        }
        
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Error getting current model info: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get current model info: {str(e)}"
        )


@router.post("/test-model", 
             summary="Test current model connection")
async def test_model(
    model_switcher = Depends(get_model_switcher_dependency)
):
    """Test the current model configuration and connection."""
    try:
        settings = get_settings()
        test_result = await model_switcher._test_model_connection()
        
        return {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "test_result": test_result,
            "timestamp": time.time()
        }
        
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Model test error: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Model test failed: {str(e)}"
        )


@router.post("/reload-registry", 
             summary="Reload model registry from JSON")
async def reload_model_registry():
    """Reload the model registry from the JSON config file for hot updates."""
    try:
        old_count = len(ModelRegistry.get_all_providers())
        registry = ModelRegistry.reload_registry()
        new_count = len(registry)
        
        settings = get_settings()
        log_llm_event("info", f"Model registry reloaded: {old_count} → {new_count} providers", 
                      settings.llm_provider, settings.llm_model)
        
        return {
            "status": "success",
            "message": f"Model registry reloaded successfully",
            "providers_before": old_count,
            "providers_after": new_count,
            "total_models": sum(len(p.get("reasoning", {})) + len(p.get("one_shot", {})) for p in registry.values()),
            "timestamp": time.time()
        }
        
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Failed to reload model registry: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload registry: {str(e)}"
        )


@router.get("/model-config/{provider}/{model}", 
            summary="Get model configuration")
async def get_model_config(provider: str, model: str):
    """Get configuration for a specific provider and model."""
    try:
        # Validate provider/model combination
        if not ModelRegistry.validate_model_combo(provider, model):
            raise HTTPException(
                status_code=404,
                detail=f"Model '{model}' not found for provider '{provider}'"
            )
        
        # Get API model name
        api_model_name = ModelRegistry.get_model_api_name(provider, model)
        if not api_model_name:
            raise HTTPException(
                status_code=404,
                detail=f"Could not find API name for {provider}/{model}"
            )
        
        # Get model parameters and capabilities
        try:
            from app.providers.factory import provider_factory
            from app.providers.base import ConnectionMode
            provider_instance = provider_factory.create_provider(
                provider_name=provider,
                model=api_model_name,
                connection_mode=ConnectionMode.LANGCHAIN
            )
            model_info = provider_instance.get_model_info()
            capabilities = ModelRegistry.get_model_capabilities(provider, model)
            
            return {
                "provider": provider,
                "friendly_name": model,
                "api_name": api_model_name,
                "parameters": model_info.get("capabilities", {}),
                "capabilities": capabilities
            }
        except Exception as e:
            # Return basic info if parameter loading fails
            return {
                "provider": provider,
                "friendly_name": model,
                "api_name": api_model_name,
                "parameters": {},
                "capabilities": ModelRegistry.get_model_capabilities(provider, model),
                "error": f"Failed to load model parameters: {str(e)}"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        log_llm_event("error", f"Error getting model config for {provider}/{model}: {str(e)}", 
                      provider, model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model config: {str(e)}"
        )


@router.post("/reload-system-prompts", 
             summary="Reload system prompts from JSON")
async def reload_system_prompts_endpoint():
    """Reload the system prompts from the JSON config file for hot updates."""
    try:
        prompt_loader = get_system_prompt_loader()
        available_before = prompt_loader.list_available_prompts()
        
        reload_system_prompts()  # This calls the global reload function
        
        available_after = prompt_loader.list_available_prompts()
        
        settings = get_settings()
        log_llm_event("info", f"System prompts reloaded successfully", 
                      settings.llm_provider, settings.llm_model)
        
        return {
            "status": "success",
            "message": f"System prompts reloaded successfully",
            "categories": list(available_after.keys()),
            "total_prompts": sum(len(prompts) for prompts in available_after.values()),
            "timestamp": time.time()
        }
        
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Failed to reload system prompts: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reload system prompts: {str(e)}"
        )


@router.get("/system-prompts", 
            summary="Get all available system prompts")
async def get_system_prompts():
    """Get all available system prompts organized by category."""
    try:
        prompt_loader = get_system_prompt_loader()
        available_prompts = prompt_loader.list_available_prompts()
        
        return {
            "status": "success",
            "prompts": available_prompts,
            "categories": list(available_prompts.keys()),
            "total_prompts": sum(len(prompts) for prompts in available_prompts.values())
        }
        
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Error getting system prompts: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system prompts: {str(e)}"
        )


@router.get("/system-prompt/{category}/{prompt_id}", 
            summary="Get specific system prompt by category and ID")
async def get_system_prompt(category: str, prompt_id: str):
    """Get detailed information about a specific system prompt."""
    try:
        prompt_loader = get_system_prompt_loader()
        prompt_info = prompt_loader.get_prompt_info(category, prompt_id)
        
        if prompt_info:
            return {
                "status": "success",
                "category": category,
                "prompt_id": prompt_id,
                "prompt_info": prompt_info
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Prompt '{prompt_id}' not found in category '{category}'"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        settings = get_settings()
        log_llm_event("error", f"Error getting system prompt: {str(e)}", 
                      settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get system prompt: {str(e)}"
        ) 