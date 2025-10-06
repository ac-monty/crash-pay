"""
Main FastAPI application for the LLM service.
Replaces the monolithic main.py with a clean, modular structure.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.api.routes import chat, models, health, auth_chat
from app.api.routes import permissions as permissions_routes
from app.api.routes import threads as threads_routes
from app.utils.logging import log_llm_event, setup_logging, get_logger


# Configure logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    settings = get_settings()
    
    logger.info("Starting LLM Service application lifespan")
    
    log_llm_event(
        "info", 
        f"LLM Service starting up (mode: {settings.llm_connection_mode})",
        settings.llm_provider,
        settings.llm_model,
        extra_data={
            "connection_mode": settings.llm_connection_mode,
            "streaming_enabled": settings.llm_streaming
        }
    )
    
    # Load authentication system
    if settings.enable_function_permissions:
        logger.info("Function permissions enabled - initializing auth system")
        log_llm_event("info", "Function permissions enabled - loading auth system")
        try:
            from app.auth.middleware import get_auth_middleware
            auth_middleware = get_auth_middleware()
            logger.info("Authentication middleware initialized successfully")
            log_llm_event("info", f"Authentication middleware initialized")
        except Exception as e:
            logger.error(f"Failed to initialize auth middleware: {str(e)}", exc_info=e)
            log_llm_event("error", f"Failed to initialize auth middleware: {str(e)}", error=e)
    else:
        logger.info("Function permissions disabled - skipping auth system")
    
    logger.info("LLM Service startup completed successfully")
    
    yield
    
    # Shutdown
    logger.info("Starting LLM Service shutdown")
    log_llm_event(
        "info",
        "LLM Service shutting down",
        settings.llm_provider,
        settings.llm_model
    )
    logger.info("LLM Service shutdown completed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    logger.info("Creating FastAPI application instance")
    
    app = FastAPI(
        title="LLM Service",
        description="Unified LLM service supporting multiple providers and connection modes",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc"
    )
    
    logger.info("FastAPI application instance created")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    logger.info("CORS middleware added to application")
    
    # Add APM middleware if available
    try:
        import elasticapm
        from elasticapm.contrib.starlette import ElasticAPM
        
        apm_config = {
            'SERVICE_NAME': settings.elastic_apm_service_name,
            'SERVER_URL': settings.elastic_apm_server_url,
            'ENVIRONMENT': settings.elastic_apm_environment,
            'VERIFY_SERVER_CERT': settings.elastic_apm_verify_server_cert,
        }
        
        app.add_middleware(ElasticAPM, client=elasticapm.Client(apm_config))
        logger.info("APM middleware added successfully")
        log_llm_event("info", "APM middleware added successfully")
        
    except ImportError:
        logger.warning("ElasticAPM not available, skipping APM middleware")
        log_llm_event("warning", "ElasticAPM not available, skipping APM middleware")
    except Exception as e:
        logger.error(f"Failed to initialize APM middleware: {str(e)}", exc_info=e)
        log_llm_event("warning", f"Failed to initialize APM middleware: {str(e)}")
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Global exception handler with logging."""
        logger.error(f"Unhandled exception in {request.method} {request.url.path}: {str(exc)}", exc_info=exc)
        
        log_llm_event(
            "error",
            f"Unhandled exception: {str(exc)}",
            settings.llm_provider,
            settings.llm_model,
            error=exc,
            extra_data={"path": str(request.url.path), "method": request.method}
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "error_type": "internal_error",
                "provider": settings.llm_provider,
                "model": settings.llm_model,
            }
        )
    
    logger.info("Global exception handler registered")
    
    # Include routers
    app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
    logger.info("Chat router included at /api/v1")
    
    app.include_router(models.router, prefix="/api/v1", tags=["Models"])
    logger.info("Models router included at /api/v1")
    
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])

    # Permissions resolution endpoint for issuers
    app.include_router(permissions_routes.router, prefix="/api/v1", tags=["Permissions"])
    app.include_router(threads_routes.router, prefix="/api/v1", tags=["Threads"])
    logger.info("Health router included at /api/v1")
    
    # NEW: Include authentication routes
    if settings.enable_function_permissions:
        app.include_router(auth_chat.router, prefix="/api/v1", tags=["Authenticated Chat"])
        logger.info("Authentication chat router included at /api/v1")
        log_llm_event("info", "Authentication routes enabled")
    else:
        logger.info("Authentication routes disabled - skipping auth chat router")
    
    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint providing service information."""
        return {
            "service": "LLM Service",
            "version": "2.0.0",
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "connection_mode": settings.llm_connection_mode,
            "streaming": settings.llm_streaming,
            "authentication_enabled": settings.enable_function_permissions,
            "docs": "/docs",
            "health": "/api/v1/healthz"
        }
    
    logger.info("Root endpoint registered")

    # Bare /health endpoint for orchestrator probes (no prefix)
    @app.get("/health", include_in_schema=False)
    async def bare_health():
        return {"status": "ok"}

    logger.info("Bare /health endpoint registered")
    logger.info("FastAPI application configuration completed successfully")
    
    return app


# Create the app instance
logger.info("Initializing LLM Service application")
app = create_app()
logger.info("LLM Service application initialized")


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    logger.info("Starting LLM Service in standalone mode")
    logger.info(f"Server configuration - Host: 0.0.0.0, Port: 8000, Reload: {os.getenv('ENVIRONMENT', 'development') == 'development'}")
    
    # Run the application
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if os.getenv("ENVIRONMENT", "development") == "development" else False,
        log_level="info"
    ) 