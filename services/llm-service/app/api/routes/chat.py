"""
Chat API routes.
Handles chat interactions with support for both direct API calls and LangChain modes.
"""

import time
import json
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse

from app.auth.middleware import get_optional_user
from app.auth.models import UserPermissions
from app.models.requests import UserContext
from app.config.settings import get_settings
from app.models.requests import ChatRequest
from app.models.responses import ChatResponse
from app.services.llm_service import LLMService, get_llm_service
from app.utils.logging import log_llm_event

router = APIRouter()


def get_llm_service_dependency() -> LLMService:
    """Dependency to get the LLM service instance."""
    return get_llm_service()


@router.post("/chat", 
             summary="Chat with LLM",
             description="Main chat endpoint supporting both single prompts and multi-turn conversations",
             response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: UserPermissions = Depends(get_optional_user),
    llm_service: LLMService = Depends(get_llm_service_dependency)
):
    """
    Chat endpoint that supports:
    - Single prompts or multi-turn conversations
    - Function calling
    - RAG integration
    - Both direct API and LangChain modes
    - Streaming responses
    """
    chat_start = time.time()
    settings = get_settings()
    request_id = f"chat_{int(time.time() * 1000)}"
    
    try:
        # Input validation
        if not request.messages and not request.prompt:
            raise HTTPException(
                status_code=400, 
                detail="Either 'messages' or 'prompt' must be provided"
            )
        
        if request.messages and request.prompt:
            raise HTTPException(
                status_code=400, 
                detail="Provide either 'messages' or 'prompt', not both"
            )
        
        # Attach user context if available
        if user:
            request.user_context = UserContext(
                user_id=user.user_id,
                permissions=user.scopes,
                roles=user.attributes.get('roles', []) if user.attributes else [],
                attributes=user.attributes,
                permitted_functions=user.permitted_functions
            )

        # Generate session_id if not provided
        if not request.session_id:
            import uuid
            request.session_id = str(uuid.uuid4())

        # Build messages from prompt if provided
        if request.prompt:
            messages = [{"role": "user", "content": request.prompt}]
        else:
            messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]
        
        # Log the request
        log_llm_event(
            "info", 
            f"Processing chat request (mode: {settings.llm_connection_mode})",
            settings.llm_provider,
            settings.llm_model,
            extra_data={
                "request_id": request_id,
                "message_count": len(messages),
                "use_rag": request.use_rag,
                "functions": len(request.functions) if request.functions else 0,
                "streaming": request.stream or settings.llm_streaming
            }
        )
        
        # Handle streaming vs non-streaming
        stream_response = request.stream if request.stream is not None else settings.llm_streaming
        
        if stream_response:
            # Return streaming response
            return StreamingResponse(
                llm_service.chat_stream(
                    messages=messages,
                    request=request,
                    request_id=request_id
                ),
                media_type="text/plain"
            )
        else:
            # Non-streaming response
            response_content, function_calls = await llm_service.chat(
                messages=messages,
                request=request,
                request_id=request_id
            )
            
            total_time = time.time() - chat_start
            
            # Log successful completion
            log_llm_event(
                "info",
                f"Chat request completed successfully",
                settings.llm_provider,
                settings.llm_model,
                extra_data={
                    "request_id": request_id,
                    "total_time": total_time,
                    "response_length": len(response_content) if response_content else 0,
                    "function_calls": len(function_calls) if function_calls else 0
                }
            )
            
            return ChatResponse(
                response=response_content,
                provider=settings.llm_provider,
                model=settings.llm_model,
                function_calls=function_calls,
                request_id=request_id,
                total_time=total_time
            )
            
    except Exception as e:
        total_time = time.time() - chat_start
        
        # Log the error
        log_llm_event(
            "error",
            f"Chat request failed: {str(e)}",
            settings.llm_provider,
            settings.llm_model,
            error=e,
            extra_data={
                "request_id": request_id,
                "total_time": total_time
            }
        )
        
        # Return appropriate error response
        if "rate limit" in str(e).lower():
            raise HTTPException(status_code=429, detail=f"Rate limit exceeded: {str(e)}")
        elif "authentication" in str(e).lower() or "api key" in str(e).lower():
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")
        elif "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Model or endpoint not found: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/chat/models",
            summary="Get available models for chat",
            description="Returns available models and their capabilities")
async def get_chat_models():
    """Get available models and their chat capabilities."""
    try:
        from app.services.model_registry import ModelRegistry
        
        settings = get_settings()
        providers = ModelRegistry.get_all_providers()
        
        models_info = {}
        for provider in providers:
            models = ModelRegistry.get_models_by_provider(provider)
            models_info[provider] = {}
            
            for category, model_dict in models.items():
                for friendly_name, api_name in model_dict.items():
                    capabilities = ModelRegistry.get_model_capabilities(provider, friendly_name)
                    models_info[provider][friendly_name] = {
                        "api_name": api_name,
                        "category": category,
                        "capabilities": capabilities
                    }
        
        return {
            "current_provider": settings.llm_provider,
            "current_model": settings.llm_model,
            "connection_mode": settings.llm_connection_mode,
            "available_models": models_info
        }
        
    except Exception as e:
        log_llm_event("error", f"Failed to get chat models: {str(e)}", 
                     settings.llm_provider, settings.llm_model, error=e)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve models: {str(e)}") 