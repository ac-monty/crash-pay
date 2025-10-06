"""
Health check API routes.
Provides health status and service diagnostics.
"""

import time
from datetime import datetime
from fastapi import APIRouter

from app.config.settings import get_settings
from app.utils.logging import log_llm_event
from app.models.responses import HealthResponse
from app.providers import create_provider

router = APIRouter()


@router.get("/healthz", 
            include_in_schema=False,
            response_model=HealthResponse)
async def healthcheck():
    """Health check endpoint with LLM testing and error logging."""
    health_start = time.time()
    
    try:
        settings = get_settings()
        
        log_llm_event("info", "Health check started", settings.llm_provider, settings.llm_model)
        
        # Test the new provider system
        try:
            provider = create_provider(settings.llm_provider, settings.llm_model)
            
            # Test basic functionality
            test_result = await provider.test_connection()
            
            health_time = time.time() - health_start
            
            if test_result["success"]:
                log_llm_event("info", f"Health check passed in {health_time:.2f}s", 
                              settings.llm_provider, settings.llm_model, 
                              health_time=health_time)
                
                return HealthResponse(
                    status="ok",
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                    connection_mode=settings.llm_connection_mode,
                    timestamp=datetime.now().isoformat(),
                    response_time_ms=health_time * 1000,
                    test_response=test_result.get("test_response"),
                    capabilities=provider.get_model_info()
                )
            else:
                log_llm_event("warning", f"Health check degraded: {test_result.get('error')}", 
                              settings.llm_provider, settings.llm_model, 
                              health_time=health_time)
                
                return HealthResponse(
                    status="degraded",
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                    connection_mode=settings.llm_connection_mode,
                    timestamp=datetime.now().isoformat(),
                    response_time_ms=health_time * 1000,
                    capabilities=provider.get_model_info()
                )
            
        except Exception as provider_error:
            health_time = time.time() - health_start
            log_llm_event("error", f"Provider test failed in health check: {str(provider_error)}", 
                          settings.llm_provider, settings.llm_model, 
                          error=provider_error, health_time=health_time)
            
            return HealthResponse(
                status="degraded",
                provider=settings.llm_provider,
                model=settings.llm_model,
                connection_mode=settings.llm_connection_mode,
                timestamp=datetime.now().isoformat(),
                response_time_ms=health_time * 1000
            )
    
    except Exception as e:
        health_time = time.time() - health_start
        log_llm_event("error", f"Health check failed: {str(e)}", 
                      settings.llm_provider, settings.llm_model, 
                      error=e, health_time=health_time)
        
        return HealthResponse(
            status="error",
            provider=settings.llm_provider,
            model=settings.llm_model,
            connection_mode=settings.llm_connection_mode,
            timestamp=datetime.now().isoformat(),
            response_time_ms=health_time * 1000
        )


@router.get("/health", 
            include_in_schema=False,
            response_model=HealthResponse)
async def health_alias():
    """Alternative health endpoint for compatibility with different monitoring systems."""
    return await healthcheck() 