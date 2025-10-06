"""
Mistral provider implementation.
Example implementation of the BaseLLMProvider for Mistral models.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from langchain_mistralai import ChatMistralAI

from .base import (
    BaseLLMProvider, 
    ProviderCapabilities, 
    ConnectionMode,
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderModelNotFoundError
)
from .utils import MistralUtilities
from app.utils.logging import debug_log_api_request, debug_log_api_response


class MistralProvider(BaseLLMProvider, MistralUtilities):
    """Mistral provider implementation supporting both direct API and LangChain modes."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.base_url = kwargs.get('base_url', 'https://api.mistral.ai/v1')
        self._langchain_client = None
        
    @property
    def provider_name(self) -> str:
        return "mistral"
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        # Check if it's a reasoning model
        is_reasoning_model = self.model.startswith('mistral-large-latest')
        
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,  # All Mistral models support function calling
            supports_system_prompts=True,   # All Mistral models support system prompts
            supports_reasoning=is_reasoning_model,
            max_context_length=128000,      # All Mistral models have 128k context
            supports_images=False,          # Mistral doesn't support images yet
            supports_audio=False,
            tool_schema="openai"
        )
    
    def _filter_parameters_for_model(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter parameters based on Mistral model capabilities."""
        filtered = {}
        
        # All models support max_tokens
        if 'max_tokens' in kwargs:
            filtered['max_tokens'] = kwargs['max_tokens']
        
        # Temperature handling - optimize for function calling
        if 'temperature' in kwargs:
            temperature = kwargs['temperature']
            # For function calling, use very low temperature for Mistral
            if kwargs.get('is_function_calling', False):
                filtered['temperature'] = min(0.1, temperature)  # Cap at 0.1 for function calling
            else:
                filtered['temperature'] = temperature
        
        # Reasoning effort for reasoning models
        if 'reasoning_effort' in kwargs and self.model.startswith('mistral-large-latest'):
            filtered['reasoning_effort'] = kwargs['reasoning_effort']
            
        return filtered
    
    def _get_langchain_client(self) -> ChatMistralAI:
        """Get or create LangChain client."""
        if self._langchain_client is None:
            self._langchain_client = ChatMistralAI(
                model=self.model,
                api_key=self.api_key,
                endpoint=self.base_url
            )
        return self._langchain_client
    
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
            "messages": messages,
            "stream": False
        }
        
        # Add filtered parameters
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        # DEBUG: Log the complete request being sent to Mistral
        debug_log_api_request(self.provider_name, self.model, payload, request_id)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            
            # DEBUG: Log the response from Mistral
            response_data = {
                'response': data['choices'][0]['message']['content'],
                'model': data.get('model', self.model),
                'usage': data.get('usage', {}),
                'finish_reason': data['choices'][0].get('finish_reason', 'unknown')
            }
            debug_log_api_response(self.provider_name, self.model, response_data, request_id)
            
            return self._extract_content_from_mistral_response(data)
    
    async def _chat_langchain(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """LangChain implementation."""
        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        client = self._get_langchain_client()
        
        # Update client parameters if provided
        if 'temperature' in kwargs:
            client.temperature = kwargs['temperature']
        if 'max_tokens' in kwargs:
            client.max_tokens = kwargs['max_tokens']
        
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
            "messages": messages,
            "stream": True
        }
        
        # Add filtered parameters
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            ) as response:
                
                if response.status_code != 200:
                    await self._handle_api_error(response)
                
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        
                        if data_str.strip() == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(data_str)
                            if 'choices' in data and len(data['choices']) > 0:
                                delta = data['choices'][0].get('delta', {})
                                if 'content' in delta and delta['content']:
                                    yield delta['content']
                        except json.JSONDecodeError:
                            continue
    
    async def _chat_stream_langchain(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """LangChain streaming implementation."""
        try:
            client = self._get_langchain_client()
            langchain_messages = self._convert_to_langchain_messages(messages)
            
            # Update client parameters
            if 'temperature' in kwargs:
                client.temperature = kwargs['temperature']
            if 'max_tokens' in kwargs:
                client.max_tokens = kwargs['max_tokens']
            
            # LangChain streaming
            async for chunk in client.astream(langchain_messages):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
                    
        except Exception as e:
            # Fallback to simulated streaming if LangChain streaming fails
            response = await self._chat_langchain(messages, **kwargs)
            
            # Use consolidated streaming utility
            async for chunk in self._simulate_streaming(response):
                yield chunk
    
    async def chat_with_functions(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        Chat with function calling support.
        Returns (response_content, function_calls).
        """
        if not self.capabilities.supports_function_calling:
            raise ProviderError(
                "Function calling not supported by this model",
                self.provider_name,
                self.model
            )
        
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
        request_id = kwargs.get('request_id', 'unknown')
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Build request payload with functions as tools
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": self._convert_functions_to_mistral_tools(functions),
            "tool_choice": "auto"
        }
        
        # Add filtered parameters with function calling flag
        kwargs_with_function_flag = {**kwargs, 'is_function_calling': True}
        filtered_params = self._filter_parameters_for_model(kwargs_with_function_flag)
        payload.update(filtered_params)
        
        # DEBUG: Log the complete function calling request being sent to Mistral
        debug_log_api_request(self.provider_name, self.model, payload, request_id)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            content = self._extract_content_from_mistral_response(data)
            function_calls = self._extract_function_calls_from_mistral_response(data)
            
            # DEBUG: Log the function calling response from Mistral
            response_data = {
                'response': content,
                'model': data.get('model', self.model),
                'usage': data.get('usage', {}),
                'finish_reason': data['choices'][0].get('finish_reason', 'unknown'),
                'function_calls': function_calls,
                'has_function_calls': bool(function_calls)
            }
            debug_log_api_response(self.provider_name, self.model, response_data, request_id)
            
            return content, function_calls
    
    async def _chat_with_functions_langchain(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """LangChain function calling implementation."""
        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        client = self._get_langchain_client()
        
        # Update client parameters
        if 'temperature' in kwargs:
            client.temperature = kwargs['temperature']
        if 'max_tokens' in kwargs:
            client.max_tokens = kwargs['max_tokens']
        
        # Convert functions to LangChain-compatible format
        langchain_tools = self._convert_functions_to_langchain_tools(functions)
        llm_with_tools = client.bind_tools(langchain_tools)
        
        response = await llm_with_tools.ainvoke(langchain_messages)
        
        # Use consolidated utility to process response
        return self._process_langchain_function_response(response)

    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Mistral using unified implementation."""
        return await self._test_connection_base()
    
    def validate_config(self) -> bool:
        """Validate provider configuration using unified implementation."""
        # Mistral API keys don't have a specific prefix, just check basic validity
        return self._validate_config_base(api_key_prefix=None)
    
    async def _handle_api_error(self, response: httpx.Response):
        """Handle API error responses using unified error handling."""
        self._handle_api_error_by_status(
            response,
            auth_indicators=["authentication", "unauthorized", "invalid_api_key"],
            rate_limit_indicators=["rate_limit_exceeded", "quota_exceeded"],
            model_not_found_indicators=["model_not_found", "invalid_request"]
        )
    
    async def _handle_error(self, error: Exception):
        """Handle and re-raise errors using unified error handling."""
        self._handle_common_errors(error) 