"""
Cohere provider implementation.
Example implementation of the BaseLLMProvider for Cohere models.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from langchain_cohere import ChatCohere

from .base import (
    BaseLLMProvider, 
    ProviderCapabilities, 
    ConnectionMode,
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderModelNotFoundError
)
from .utils import CohereUtilities
from app.utils.logging import debug_log_api_request, debug_log_api_response


class CohereProvider(BaseLLMProvider, CohereUtilities):
    """Cohere provider implementation supporting both direct API and LangChain modes."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.base_url = kwargs.get('base_url', 'https://api.cohere.com/v2')
        self._langchain_client = None
        
    @property
    def provider_name(self) -> str:
        return "cohere"
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        # Cohere capabilities - Command models support function calling and system prompts
        supports_function_calling = True  # All Command models support tool use
        max_context = 128000  # Command R and R+ have 128k context
        
        # Check for specific model capabilities
        if self.model.startswith('command-light'):
            max_context = 4096
            supports_function_calling = False
        
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=supports_function_calling,
            supports_system_prompts=True,
            supports_reasoning=False,  # Cohere doesn't have reasoning models like o1
            max_context_length=max_context,
            supports_images=False,  # Command models don't support images
            supports_audio=False
        )
    
    def _get_langchain_client(self) -> ChatCohere:
        """Get or create LangChain client."""
        if self._langchain_client is None:
            self._langchain_client = ChatCohere(
                model=self.model,
                cohere_api_key=self.api_key
            )
        return self._langchain_client
    
    def _filter_parameters_for_model(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter parameters based on model capabilities."""
        filtered = {}
        
        # Temperature
        if 'temperature' in kwargs:
            filtered['temperature'] = kwargs['temperature']
        
        # Max tokens
        if 'max_tokens' in kwargs:
            filtered['max_tokens'] = kwargs['max_tokens']
        
        # Seed for deterministic output
        if 'seed' in kwargs:
            filtered['seed'] = kwargs['seed']
        
        # Stop sequences
        if 'stop_sequences' in kwargs:
            filtered['stop_sequences'] = kwargs['stop_sequences']
        
        # P (nucleus sampling)
        if 'p' in kwargs:
            filtered['p'] = kwargs['p']
        
        # K (top-k sampling)
        if 'k' in kwargs:
            filtered['k'] = kwargs['k']
            
        return filtered
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send a chat request using either direct API or LangChain."""
        try:
            if self.connection_mode == ConnectionMode.DIRECT:
                return await self._chat_direct(messages, **kwargs)
            else:
                return await self._chat_langchain(messages, **kwargs)
        except Exception as e:
            await self._handle_error(e)
    
    async def _chat_direct(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Direct API implementation."""
        request_id = kwargs.get('request_id', 'unknown')
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Build request payload
        payload = {
            "model": self.model,
            "messages": self._convert_messages_for_cohere_api(messages),
            "stream": False
        }
        
        # Add filtered parameters based on model capabilities
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        # DEBUG: Log the complete request being sent to Cohere
        debug_log_api_request(self.provider_name, self.model, payload, request_id)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            
            # DEBUG: Log the response from Cohere
            response_data = {
                'response': self._extract_content_from_cohere_response(data),
                'model': data.get('model', self.model),
                'usage': data.get('usage', {}),
                'finish_reason': data.get('finish_reason', 'unknown')
            }
            debug_log_api_response(self.provider_name, self.model, response_data, request_id)
            
            return self._extract_content_from_cohere_response(data)
    
    async def _chat_langchain(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """LangChain implementation."""
        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        client = self._get_langchain_client()
        
        # Apply parameter filtering for model capabilities
        filtered_params = self._filter_parameters_for_model(kwargs)
        
        # Update client parameters if provided
        if 'temperature' in filtered_params:
            client.temperature = filtered_params['temperature']
        if 'max_tokens' in filtered_params:
            client.max_tokens = filtered_params['max_tokens']
        
        response = await client.ainvoke(langchain_messages)
        return response.content or ""
    
    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """Stream chat response."""
        if self.connection_mode == ConnectionMode.DIRECT:
            async for chunk in self._chat_stream_direct(messages, **kwargs):
                yield chunk
        else:
            async for chunk in self._chat_stream_langchain(messages, **kwargs):
                yield chunk
    
    async def _chat_stream_direct(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """Direct API streaming implementation."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": self._convert_messages_for_cohere_api(messages),
            "stream": True
        }
        
        # Add filtered parameters based on model capabilities
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat",
                headers=headers,
                json=payload,
                timeout=120.0
            ) as response:
                if response.status_code != 200:
                    await self._handle_api_error(response)
                
                async for line in response.aiter_lines():
                    if line.strip():
                        if line.startswith("data: "):
                            chunk_data = line[6:].strip()
                            if chunk_data == "[DONE]":
                                break
                            
                            try:
                                chunk_json = json.loads(chunk_data)
                                
                                # Handle different event types from Cohere streaming
                                if chunk_json.get("type") == "content-delta":
                                    delta = chunk_json.get("delta", {})
                                    if "message" in delta and "content" in delta["message"]:
                                        content = delta["message"]["content"].get("text", "")
                                        if content:
                                            yield content
                                            
                            except json.JSONDecodeError:
                                continue
    
    async def _chat_stream_langchain(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """LangChain streaming implementation."""
        langchain_messages = self._convert_to_langchain_messages(messages)
        client = self._get_langchain_client()
        
        # Apply parameter filtering
        filtered_params = self._filter_parameters_for_model(kwargs)
        if 'temperature' in filtered_params:
            client.temperature = filtered_params['temperature']
        if 'max_tokens' in filtered_params:
            client.max_tokens = filtered_params['max_tokens']
        
        async for chunk in client.astream(langchain_messages):
            if chunk.content:
                yield chunk.content
    
    async def chat_with_functions(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Chat with function calling capability."""
        try:
            if self.connection_mode == ConnectionMode.DIRECT:
                return await self._chat_with_functions_direct(messages, functions, **kwargs)
            else:
                return await self._chat_with_functions_langchain(messages, functions, **kwargs)
        except Exception as e:
            await self._handle_error(e)
    
    async def _chat_with_functions_direct(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Direct API function calling implementation."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Convert functions to Cohere tools format
        tools = self._convert_functions_to_cohere_tools(functions)
        
        payload = {
            "model": self.model,
            "messages": self._convert_messages_for_cohere_api(messages),
            "tools": tools,
            "stream": False,
            "tool_choice": "auto"
        }
        
        # Add filtered parameters
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            # DEBUG: Log raw Cohere response when tools are enabled (truncated)
            try:
                from app.utils.logging import logger as service_logger
                raw_json = json.dumps(data)[:2000]
                service_logger.info("Cohere raw response", raw_response=raw_json)
            except Exception:
                pass
            content = self._extract_content_from_cohere_response(data)
            function_calls = self._extract_function_calls_from_cohere_response(data)
            
            return content, function_calls
    
    async def _chat_with_functions_langchain(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """LangChain function calling implementation."""
        langchain_messages = self._convert_to_langchain_messages(messages)
        client = self._get_langchain_client()
        
        # Convert functions to LangChain tools format
        tools = self._convert_functions_to_langchain_tools(functions)
        
        # Bind tools to the client
        client_with_tools = client.bind_tools(tools)
        
        # Apply parameter filtering
        filtered_params = self._filter_parameters_for_model(kwargs)
        if 'temperature' in filtered_params:
            client_with_tools.temperature = filtered_params['temperature']
        if 'max_tokens' in filtered_params:
            client_with_tools.max_tokens = filtered_params['max_tokens']
        
        response = await client_with_tools.ainvoke(langchain_messages)
        return self._process_langchain_function_response(response)
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Cohere API."""
        return await self._test_connection_base()
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        # Cohere API keys don't have a specific prefix, just check basic validity
        return self._validate_config_base(api_key_prefix=None)
    
    async def _handle_api_error(self, response: httpx.Response):
        """Handle Cohere API errors."""
        auth_indicators = ["unauthorized", "invalid api key", "authentication failed"]
        rate_limit_indicators = ["rate limit", "too many requests", "quota exceeded"]
        model_not_found_indicators = ["model not found", "invalid model", "model does not exist"]
        
        self._handle_api_error_by_status(
            response,
            provider_name="cohere",
            auth_indicators=auth_indicators,
            rate_limit_indicators=rate_limit_indicators,
            model_not_found_indicators=model_not_found_indicators
        )
    
    async def _handle_error(self, error: Exception):
        """Handle general errors."""
        auth_patterns = ["unauthorized", "authentication", "api key"]
        rate_limit_patterns = ["rate limit", "too many requests"]
        model_not_found_patterns = ["model not found", "invalid model"]
        
        self._handle_exception_with_patterns(
            error,
            provider_name="cohere",
            auth_patterns=auth_patterns,
            rate_limit_patterns=rate_limit_patterns,
            model_not_found_patterns=model_not_found_patterns
        ) 