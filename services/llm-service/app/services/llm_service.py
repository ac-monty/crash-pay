"""
Core LLM service that handles both direct API calls and LangChain integration.
Provides a unified interface for chat operations across different connection modes.
"""

import asyncio
import json
import logging
import time
from typing import List, Dict, Any, Optional, AsyncGenerator, Tuple

from app.config.settings import get_settings
from app.models.requests import ChatRequest
from app.utils.logging import (
    log_llm_event, debug_log_system_prompt, debug_log_function_context,
    get_service_logger, performance_monitor, log_security_event, get_logger
)
from app.utils.singleton import singleton_factory
from app.providers.factory import provider_factory
from app.providers.base import ConnectionMode
from app.config.system_prompt_loader import get_system_prompt_loader


logger = get_logger(__name__)
service_logger = get_service_logger('llm_service')


class LLMService:
    """Main LLM service that provides unified chat interface."""
    
    def __init__(self):
        self._current_provider = None
        self._provider_cache = {}
        service_logger.info("LLM Service initialized", 
                          cache_size=len(self._provider_cache))
        
    def _get_provider(self):
        """Get or create the current LLM provider."""
        settings = get_settings()
        provider_key = f"{settings.llm_provider}_{settings.llm_model}_{settings.llm_connection_mode}"
        
        if provider_key not in self._provider_cache:
            with service_logger.performance_context("provider_creation", 
                                                   provider=settings.llm_provider, 
                                                   model=settings.llm_model):
                connection_mode = ConnectionMode(settings.llm_connection_mode)
                self._provider_cache[provider_key] = provider_factory.create_provider(
                    provider_name=settings.llm_provider,
                    model=settings.llm_model,
                    connection_mode=connection_mode
                )
                
                service_logger.info("Provider created and cached", 
                                  provider=settings.llm_provider,
                                  model=settings.llm_model,
                                  connection_mode=settings.llm_connection_mode,
                                  cache_size=len(self._provider_cache))
        
        return self._provider_cache[provider_key]
    
    def clear_cache(self):
        """Clear the provider cache (useful after model switching)."""
        old_size = len(self._provider_cache)
        self._provider_cache.clear()
        service_logger.info("Provider cache cleared", 
                          previous_size=old_size)
    
    def _log_request_details(self, messages: List[Dict[str, str]], request: ChatRequest, request_id: str):
        """Log detailed request information for debugging."""
        settings = get_settings()
        if not settings.debug_mode:
            return
            
        # Log message structure and content (truncated for safety)
        logger.debug(f"REQUEST DETAILS - {request_id}")
        logger.debug(f"Provider: {settings.llm_provider}, Model: {settings.llm_model}")
        logger.debug(f"Message count: {len(messages)}")
        
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            content_preview = content[:200] + ('...' if len(content) > 200 else '')
            logger.debug(f"Message {i+1} - Role: {role}, Content length: {len(content)}")
            logger.debug(f"Message {i+1} - Content preview: {content_preview}")
        
        # Log request parameters
        logger.debug(f"Request parameters - Temperature: {request.temperature}, Max tokens: {request.max_tokens}")
        logger.debug(f"Request flags - Use functions: {request.use_functions}, Use RAG: {request.use_rag}")
        
        if request.functions:
            logger.debug(f"Available functions: {[f.name for f in request.functions]}")
            for func in request.functions:
                logger.debug(f"Function {func.name} - Description: {func.description}")
                logger.debug(f"Function {func.name} - Parameters: {func.parameters}")
    
    def _log_response_details(self, response_content: str, function_calls: Optional[List[Dict[str, Any]]], 
                            processing_time: float, request_id: str):
        """Log detailed response information for debugging."""
        settings = get_settings()
        if not settings.debug_mode:
            return
            
        logger.debug(f"RESPONSE DETAILS - {request_id}")
        logger.debug(f"Processing time: {processing_time:.3f}s")
        logger.debug(f"Response length: {len(response_content) if response_content else 0}")
        
        if response_content:
            # Log response content (truncated for safety)
            content_preview = response_content[:500] + ('...' if len(response_content) > 500 else '')
            logger.debug(f"Response content preview: {content_preview}")
        
        if function_calls:
            logger.debug(f"Function calls executed: {len(function_calls)}")
            for i, fc in enumerate(function_calls):
                logger.debug(f"Function call {i+1} - Name: {fc.get('function', 'unknown')}")
                logger.debug(f"Function call {i+1} - Arguments: {fc.get('arguments', {})}")
                logger.debug(f"Function call {i+1} - Result: {fc.get('result', 'no result')}")
    
    def _log_error_details(self, error: Exception, messages: List[Dict[str, str]], 
                          request: ChatRequest, request_id: str):
        """Log comprehensive error details for debugging."""
        settings = get_settings()
        
        logger.error(f"ERROR DETAILS - {request_id}")
        logger.error(f"Provider: {settings.llm_provider}, Model: {settings.llm_model}")
        logger.error(f"Error type: {type(error).__name__}")
        logger.error(f"Error message: {str(error)}")
        
        # Log request context during error
        logger.error(f"Request context - Message count: {len(messages)}")
        logger.error(f"Request context - Use functions: {request.use_functions}")
        logger.error(f"Request context - Function count: {len(request.functions) if request.functions else 0}")
        
        if request.functions:
            logger.error(f"Functions available during error: {[f.name for f in request.functions]}")
        
        # Log full exception with stack trace
        logger.error(f"Full exception details:", exc_info=error)
    
    @performance_monitor("llm_service.chat")
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        request: ChatRequest,
        request_id: str
    ) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        Main chat method supporting both direct API and LangChain modes.
        Returns (response_content, function_calls).
        """
        settings = get_settings()
        start_time = time.time()

        # Load previous history
        from app.services.memory import get_memory_manager
        memory = get_memory_manager()
        if request.session_id:
            history_messages = await memory.load_history(request.session_id)
            messages = history_messages + messages  # prepend history
        
        # Log request start
        service_logger.debug("Starting chat request",
                           request_id=request_id,
                           provider=settings.llm_provider,
                           model=settings.llm_model,
                           use_functions=request.use_functions,
                           use_rag=request.use_rag,
                           message_count=len(messages))
        
        # Log detailed request information
        self._log_request_details(messages, request, request_id)
        
        try:
            # Auto-populate function definitions from user context if missing
            if (not request.functions or len(request.functions) == 0) \
                and request.user_context and request.user_context.permitted_functions:

                from app.api.routes.auth_chat import _create_function_definition
                funcs = []
                for fname in request.user_context.permitted_functions:
                    fdef = _create_function_definition(fname)
                    if fdef:
                        from app.models.requests import Function
                        funcs.append(Function(**fdef))
                if funcs:
                    request.functions = funcs
                    request.use_functions = True
            # Get the provider
            provider = self._get_provider()
            
            # Provider-agnostic sanitization: drop orphan tool messages (no preceding assistant tool_calls)
            def _sanitize_messages_for_provider(input_messages: List[Dict[str, Any]], tool_schema: str) -> List[Dict[str, Any]]:
                sanitized: List[Dict[str, Any]] = []
                prev_assistant_tool_ids: List[str] = []
                for msg in input_messages:
                    role = msg.get("role")
                    if role == "assistant":
                        # capture tool_call ids when present
                        prev_assistant_tool_ids = []
                        for tc in msg.get("tool_calls", []) or []:
                            call_id = tc.get("id")
                            if call_id:
                                prev_assistant_tool_ids.append(call_id)
                        sanitized.append(msg)
                    elif role == "tool":
                        if tool_schema == "openai":
                            # Valid only if immediately following assistant tool_calls and has a tool_call_id
                            tool_call_id = msg.get("tool_call_id")
                            if prev_assistant_tool_ids and tool_call_id in prev_assistant_tool_ids:
                                sanitized.append(msg)
                            else:
                                # drop orphan tool message
                                continue
                        elif tool_schema == "anthropic":
                            # Anthropic expects a user-role tool_result block, but we sometimes stage as role=tool
                            # Keep only if preceded by assistant tool_calls as well
                            if prev_assistant_tool_ids:
                                sanitized.append(msg)
                            else:
                                continue
                        else:
                            # Unknown schema – drop tool messages to be safe
                            continue
                    else:
                        sanitized.append(msg)
                return sanitized

            # Persist new user message to memory
            if request.session_id and messages:
                await memory.append_messages(
                    request.session_id,
                    request.user_context.user_id if request.user_context else "anonymous",
                    [messages[-1]],
                )

            # ALWAYS APPLY BANKING SYSTEM PROMPT FIRST
            banking_system_prompt = get_system_prompt_loader().get_chat_prompt()
            # Ensure banking prompt is the first system message
            messages = [{"role": "system", "content": banking_system_prompt}] + [m for m in messages if m.get("role") != "system"]
            debug_log_system_prompt(settings.llm_provider, settings.llm_model, banking_system_prompt, request_id)
            service_logger.debug("Applied banking system prompt", request_id=request_id, prompt_length=len(banking_system_prompt))

            # RAG-as-a-tool: do not inject RAG context up-front
            # (unconditional _enhance_with_rag removed)
            
            # Prepare parameters
            invoke_params = {}
            if request.temperature is not None:
                invoke_params["temperature"] = request.temperature
            if request.max_tokens is not None:
                invoke_params["max_tokens"] = request.max_tokens
            else:
                # Apply per-model default max_tokens if available
                try:
                    from app.services.model_registry import ModelRegistry
                    # We want friendly name, not API name, so map back if possible
                    friendly = ModelRegistry.get_friendly_name(settings.llm_provider, settings.llm_model) or settings.llm_model
                    defaults = ModelRegistry.get_default_params(settings.llm_provider, friendly)
                    if isinstance(defaults, dict) and defaults.get("max_tokens"):
                        invoke_params["max_tokens"] = int(defaults["max_tokens"])
                except Exception:
                    pass
            
            # Handle reasoning effort for reasoning models only
            if request.reasoning_effort:
                if self._is_reasoning_model(settings.llm_model):
                    invoke_params["reasoning_effort"] = request.reasoning_effort
                    service_logger.debug("Reasoning effort applied", 
                                       effort=request.reasoning_effort,
                                       model=settings.llm_model)
            
            # Handle function calling if supported and requested
            function_calls = None
            service_logger.debug("Function calling check", 
                               functions_provided=bool(request.functions),
                               use_functions=request.use_functions,
                               supports_function_calling=provider.capabilities.supports_function_calling,
                               request_id=request_id)
            
            if request.functions:
                service_logger.info(f"Functions available: {len(request.functions)}", 
                                  function_names=[f.name for f in request.functions],
                                  request_id=request_id)
            
            if request.functions and request.use_functions and provider.capabilities.supports_function_calling:
                user_permissions = getattr(request, 'user_permissions', [])
                function_names = [f.name for f in request.functions]

                log_security_event("info", "Function calling initiated",
                                  request_id=request_id,
                                  provider=settings.llm_provider,
                                  model=settings.llm_model,
                                  functions=function_names,
                                  user_permissions=user_permissions)

                debug_log_function_context(settings.llm_provider, settings.llm_model, request.functions, user_permissions, request_id)

                # Optionally inject RAG tool definition so the model can fetch KB when needed
                if request.use_rag:
                    try:
                        from app.api.routes.auth_chat import _create_function_definition
                        rag_def = _create_function_definition("get_rag_context")
                        if rag_def:
                            from app.models.requests import Function
                            # Avoid duplicates
                            existing = {f.name for f in request.functions}
                            if "get_rag_context" not in existing:
                                request.functions.append(Function(**rag_def))
                    except Exception as e:
                        logger.warning(f"Failed to inject RAG tool definition: {e}")

                functions_dict = [
                    {
                        "name": func.name,
                        "description": func.description,
                        "parameters": func.parameters
                    }
                    for func in request.functions
                ]

                logger.debug(f"Executing function calling - {request_id}")
                for func_dict in functions_dict:
                    logger.debug(f"Function available: {func_dict['name']} - {func_dict['description']}")

                # Iterative tool-calling loop to allow sequential functions (e.g., list_recipients -> transfer_funds)
                max_tool_iterations = 4
                executed_calls: List[Dict[str, Any]] = []
                conversation_messages = list(messages)

                # sanitize before first tool turn
                schema = getattr(provider.capabilities, "tool_schema", "text")
                conversation_messages = _sanitize_messages_for_provider(conversation_messages, schema)

                schema = getattr(provider.capabilities, "tool_schema", "text")

                def _append_tool_messages(base_messages: List[Dict[str, str]],
                                          assistant_content: str,
                                          calls: List[Dict[str, Any]]) -> List[Dict[str, str]]:
                    updated = list(base_messages)
                    if schema == "openai":
                        assistant_message = {
                            "role": "assistant",
                            "content": assistant_content or "",
                            "tool_calls": []
                        }
                        tool_messages = []
                        for i, fc in enumerate(calls):
                            call_id = fc.get("id", f"call_{i}")
                            assistant_message["tool_calls"].append({
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": fc.get("function"),
                                    "arguments": json.dumps(fc.get("arguments", {}))
                                }
                            })
                            tool_messages.append({
                                "role": "tool",
                                "tool_call_id": call_id,
                                "content": json.dumps({
                                    "result": fc.get("result"),
                                    "error": fc.get("error")
                                })
                            })
                        updated += [assistant_message] + tool_messages
                    elif schema == "anthropic":
                        assistant_message = {
                            "role": "assistant",
                            "content": assistant_content or "",
                            "tool_calls": []
                        }
                        tool_results_payload = []
                        for i, fc in enumerate(calls):
                            call_id = fc.get("id", f"call_{i}")
                            assistant_message["tool_calls"].append({
                                "id": call_id,
                                "type": "function",
                                "function": {
                                    "name": fc.get("function"),
                                    "arguments": json.dumps(fc.get("arguments", {}))
                                }
                            })
                            tool_results_payload.append({
                                "tool_call_id": call_id,
                                "content": json.dumps({
                                    "result": fc.get("result"),
                                    "error": fc.get("error")
                                })
                            })
                        updated += [assistant_message, {"role": "tool", "tool_results": tool_results_payload}]
                    else:
                        result_blob = {
                            fc.get("function"): {"result": fc.get("result"), "error": fc.get("error")} for fc in calls
                        }
                        updated.append({"role": "assistant", "content": f"Function results: {json.dumps(result_blob)}"})
                    return updated

                for iteration in range(max_tool_iterations):
                    with service_logger.performance_context("function_calling", function_count=len(functions_dict), request_id=request_id):
                        function_invoke_params = {**invoke_params, "is_function_calling": True}
                        response_content, function_calls = await provider.chat_with_functions(
                            conversation_messages, functions_dict, **function_invoke_params
                        )

                    if not function_calls:
                        break

                    service_logger.info("Functions returned by provider",
                                      function_calls_count=len(function_calls),
                                      executed_functions=[fc.get('function', 'unknown') for fc in function_calls],
                                      request_id=request_id)

                    from app.services.function_executor import get_function_executor
                    executor = get_function_executor()

                    for fc in function_calls:
                        func_name = fc.get("function")
                        args = fc.get("arguments", {})
                        try:
                            # Enrich user_context with latest user message for RAG tool convenience
                            if func_name == "get_rag_context" and request and messages:
                                last_user = None
                                for m in reversed(messages):
                                    if m.get("role") == "user":
                                        last_user = m.get("content")
                                        break
                                if request.user_context is not None:
                                    # Attach ephemeral field for executor to use
                                    try:
                                        setattr(request.user_context, "last_user_message", last_user)
                                    except Exception:
                                        pass
                            result = await executor.execute(func_name, args, request.user_context)
                            fc["result"] = result
                            fc["error"] = None
                            service_logger.info("Function executed successfully", function=func_name, request_id=request_id)
                        except Exception as exc:
                            logger.exception(f"Function {func_name} execution failed - {request_id}")
                            fc["result"] = None
                            fc["error"] = str(exc)
                            service_logger.error("Function execution failed", function=func_name, error=str(exc), request_id=request_id)

                    executed_calls.extend(function_calls)

                    conversation_messages = _append_tool_messages(conversation_messages, response_content, function_calls)

                # After tool loop, perform a final assistant turn without tools to generate the natural language response
                with service_logger.performance_context("followup_chat", request_id=request_id):
                    # sanitize again before final chat without tools
                    conversation_messages = _sanitize_messages_for_provider(conversation_messages, schema)
                    response_content = await provider.chat(conversation_messages, **invoke_params)

                # Replace function_calls with the executed_calls for downstream consumers
                function_calls = executed_calls
            else:
                # Regular chat without functions
                with service_logger.performance_context("regular_chat", request_id=request_id):
                    schema = getattr(provider.capabilities, "tool_schema", "text")
                    safe_messages = _sanitize_messages_for_provider(messages, schema)
                    response_content = await provider.chat(safe_messages, **invoke_params)
            
            processing_time = time.time() - start_time
            
            # Log detailed response information
            self._log_response_details(response_content, function_calls, processing_time, request_id)

            # Persist assistant response and a concise function result summary only (provider-agnostic)
            if request.session_id and response_content is not None:
                persisted_messages = []

                # Save assistant message
                persisted_messages.append({
                    "role": "assistant",
                    "content": response_content
                })

                # Persist concise function results as assistant text, not as tool-role
                if function_calls:
                    for fc in function_calls:
                        func_name = fc.get("function", "unknown")
                        result_summary = fc.get("result")
                        try:
                            summary_text = json.dumps(result_summary) if result_summary is not None else "null"
                        except Exception:
                            summary_text = str(result_summary)
                        persisted_messages.append({
                            "role": "assistant",
                            "content": f"[function_result] {func_name}: {summary_text}"
                        })

                # Persist to MongoDB-based memory
                try:
                    await memory.append_messages(
                        request.session_id,
                        request.user_context.user_id if request.user_context else "assistant",
                        persisted_messages,
                    )
                except Exception as mem_exc:
                    logger.warning(
                        f"Failed to persist assistant messages to memory – {mem_exc}",
                        exc_info=mem_exc,
                    )
            
            service_logger.info("Chat completed successfully", 
                              processing_time=processing_time,
                              response_length=len(response_content) if response_content else 0,
                              has_function_calls=bool(function_calls),
                              request_id=request_id)
            
            log_llm_event(
                "info",
                f"Chat completed successfully in {processing_time:.2f}s",
                settings.llm_provider,
                settings.llm_model,
                extra_data={
                    "request_id": request_id,
                    "processing_time": processing_time,
                    "response_length": len(response_content) if response_content else 0,
                    "connection_mode": settings.llm_connection_mode,
                    "has_functions": bool(request.functions and request.use_functions)
                }
            )
            
            return response_content, function_calls
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Log comprehensive error details
            self._log_error_details(e, messages, request, request_id)
            
            service_logger.error("Chat request failed", 
                               error=e,
                               processing_time=processing_time,
                               request_id=request_id,
                               provider=settings.llm_provider,
                               model=settings.llm_model)
            
            log_llm_event(
                "error",
                f"Chat failed after {processing_time:.2f}s: {str(e)}",
                settings.llm_provider,
                settings.llm_model,
                error=e,
                extra_data={"request_id": request_id, "processing_time": processing_time}
            )
            raise
    
    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        request: ChatRequest, 
        request_id: str
    ) -> AsyncGenerator[str, None]:
        """
        Streaming chat method with support for true streaming.
        """
        settings = get_settings()
        
        logger.debug(f"Starting streaming chat - {request_id}")
        
        try:
            # Get the provider
            provider = self._get_provider()
            
            # Streaming path: do not inject RAG up-front
            
            # ALWAYS APPLY BANKING SYSTEM PROMPT (STREAMING)
            banking_system_prompt = get_system_prompt_loader().get_chat_prompt()
            
            # Add banking system prompt if no system message exists
            if not any(msg.get("role") == "system" for msg in messages):
                messages = [{"role": "system", "content": banking_system_prompt}] + messages
                debug_log_system_prompt(settings.llm_provider, settings.llm_model, banking_system_prompt, request_id)
                logger.debug(f"Applied banking system prompt for streaming - {request_id}")
            
            # Prepare parameters
            invoke_params = {}
            if request.temperature is not None:
                invoke_params["temperature"] = request.temperature
            if request.max_tokens is not None:
                invoke_params["max_tokens"] = request.max_tokens
            else:
                try:
                    from app.services.model_registry import ModelRegistry
                    friendly = ModelRegistry.get_friendly_name(settings.llm_provider, settings.llm_model) or settings.llm_model
                    defaults = ModelRegistry.get_default_params(settings.llm_provider, friendly)
                    if isinstance(defaults, dict) and defaults.get("max_tokens"):
                        invoke_params["max_tokens"] = int(defaults["max_tokens"])
                except Exception:
                    pass
            
            # Handle reasoning effort for reasoning models only
            if request.reasoning_effort:
                if self._is_reasoning_model(settings.llm_model):
                    invoke_params["reasoning_effort"] = request.reasoning_effort
            
            # Use true streaming if enabled and supported
            if settings.llm_enable_true_streaming and provider.capabilities.supports_streaming:
                logger.debug(f"Using true streaming mode - {request_id}")
                log_llm_event("info", f"Starting true streaming chat", settings.llm_provider, settings.llm_model, 
                             extra_data={"request_id": request_id, "streaming_mode": "true"})
                
                # Handle function calls for streaming
                if request.functions and request.use_functions and provider.capabilities.supports_function_calling:
                    # Debug logging
                    user_permissions = getattr(request, 'user_permissions', [])
                    debug_log_function_context(settings.llm_provider, settings.llm_model, request.functions, user_permissions, request_id)
                    
                    # Convert Function Pydantic objects to dictionaries
                    functions_dict = [
                        {
                            "name": func.name,
                            "description": func.description,
                            "parameters": func.parameters
                        }
                        for func in request.functions
                    ]
                    # Add is_function_calling flag for providers that need it (like Mistral)
                    function_invoke_params = {**invoke_params, "is_function_calling": True}
                    _, function_calls = await provider.chat_with_functions(
                        messages, functions_dict, **function_invoke_params
                    )
                    if function_calls:
                        logger.debug(f"Streaming function calls executed - {request_id}")
                        yield f"data: {json.dumps({'function_calls': function_calls, 'type': 'function_calls'})}\n\n"
                else:
                    # Regular streaming without functions
                    chunk_count = 0
                    async for chunk in provider.chat_stream(messages, **invoke_params):
                        chunk_count += 1
                        if chunk_count % 10 == 0:  # Log every 10th chunk
                            logger.debug(f"Streaming chunk {chunk_count} - {request_id}")
                        yield f"data: {json.dumps({'content': chunk, 'type': 'content'})}\n\n"
            
            else:
                # Fallback to simulated streaming
                logger.debug(f"Using simulated streaming mode - {request_id}")
                log_llm_event("info", f"Using simulated streaming", settings.llm_provider, settings.llm_model,
                             extra_data={"request_id": request_id, "streaming_mode": "simulated"})
                
                response_content, function_calls = await self.chat(messages, request, request_id)
                
                # Simulate streaming by yielding chunks
                chunk_size = 50
                for i in range(0, len(response_content), chunk_size):
                    chunk = response_content[i:i + chunk_size]
                    yield f"data: {json.dumps({'content': chunk, 'type': 'content'})}\n\n"
                    await asyncio.sleep(0.01)  # Small delay to simulate streaming
                
                # Send function calls if any
                if function_calls:
                    logger.debug(f"Simulated streaming function calls sent - {request_id}")
                    yield f"data: {json.dumps({'function_calls': function_calls, 'type': 'function_calls'})}\n\n"
            
            # Send completion signal
            logger.debug(f"Streaming completed - {request_id}")
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming chat failed - {request_id}: {str(e)}", exc_info=e)
            log_llm_event("error", f"Streaming chat failed: {str(e)}", settings.llm_provider, settings.llm_model,
                         error=e, extra_data={"request_id": request_id})
            yield f"data: {json.dumps({'error': str(e), 'type': 'error'})}\n\n"
    

    
    async def _enhance_with_rag(self, messages: List[Dict[str, str]], request_id: str) -> List[Dict[str, str]]:
        """Enhance messages with RAG context."""
        try:
            # Get the last user message for RAG query
            user_query = None
            for msg in reversed(messages):
                if msg["role"] == "user":
                    user_query = msg["content"]
                    break
            
            if not user_query:
                logger.debug(f"No user query found for RAG enhancement - {request_id}")
                return messages
            
            logger.debug(f"Attempting RAG enhancement - {request_id}")
            
            # Call RAG service
            settings = get_settings()
            import httpx
            
            async with httpx.AsyncClient() as client:
                rag_response = await client.post(
                    f"{settings.rag_service_url}/query",
                    json={"query": user_query},
                    timeout=10.0
                )
                
                if rag_response.status_code == 200:
                    rag_data = rag_response.json()
                    context = rag_data.get("context", "")
                    
                    if context:
                        # Truncate context per settings
                        max_chars = settings.rag_max_context_chars
                        if isinstance(max_chars, int) and max_chars > 0 and len(context) > max_chars:
                            context = context[:max_chars]
                        # Determine role for RAG context injection
                        ctx_role = settings.rag_context_role if settings.rag_context_role in ("system", "user") else "user"
                        enhanced_messages = [
                            {"role": ctx_role, "content": f"Context from knowledge base: {context}"}
                        ] + messages
                        
                        logger.debug(f"RAG context added - {request_id}, Context length: {len(context)}")
                        
                        log_llm_event(
                            "info", 
                            f"Enhanced with RAG context",
                            settings.llm_provider,
                            settings.llm_model,
                            extra_data={"request_id": request_id, "context_length": len(context)}
                        )
                        
                        return enhanced_messages
                    else:
                        logger.debug(f"RAG returned empty context - {request_id}")
                else:
                    logger.warning(f"RAG service returned status {rag_response.status_code} - {request_id}")
            
        except Exception as e:
            logger.error(f"RAG enhancement failed - {request_id}: {str(e)}", exc_info=e)
            log_llm_event(
                "warning",
                f"RAG enhancement failed: {str(e)}",
                settings.llm_provider,
                settings.llm_model,
                extra_data={"request_id": request_id}
            )
        
        return messages
    


    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check if a model is a reasoning model (o1, o3, o4 series)."""
        reasoning_models = [
            'o1', 'o1-preview', 'o1-mini',
            'o3', 'o3-mini', 'o3-2025-04-16',
            'o4', 'o4-mini', 'o4-mini-2025-04-16'
        ]
        model_lower = model_name.lower()
        return any(reasoning_model in model_lower for reasoning_model in reasoning_models)


@singleton_factory
def get_llm_service() -> LLMService:
    """Get the global LLM service instance (singleton pattern)."""
    return LLMService()


 