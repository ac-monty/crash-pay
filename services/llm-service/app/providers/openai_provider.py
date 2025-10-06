"""
OpenAI provider implementation.
Example implementation of the BaseLLMProvider for OpenAI models.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from langchain_openai import ChatOpenAI

from .base import (
    BaseLLMProvider, 
    ProviderCapabilities, 
    ConnectionMode,
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderModelNotFoundError
)
from .utils import OpenAIUtilities
from app.utils.logging import debug_log_api_request, debug_log_api_response


class OpenAIProvider(BaseLLMProvider, OpenAIUtilities):
    """OpenAI provider implementation supporting both direct API and LangChain modes."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.org_id = kwargs.get('org_id')
        self.base_url = kwargs.get('base_url', 'https://api.openai.com/v1')
        self._langchain_client = None
        
    @property
    def provider_name(self) -> str:
        return "openai"
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        # OpenAI capabilities - ALL models support function calling and system prompts
        is_reasoning_model = self.model.startswith(('o1-', 'o3-', 'o4-'))
        
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,  # ALL OpenAI models support this
            supports_system_prompts=True,   # ALL OpenAI models support this
            supports_reasoning=is_reasoning_model,
            max_context_length=128000,  # Most GPT-4 models
            supports_images=self.model in ['gpt-4-vision-preview', 'gpt-4o', 'gpt-4o-mini'],
            supports_audio=False,
            tool_schema="openai"
        )
    
    def _get_langchain_client(self) -> ChatOpenAI:
        """Get or create LangChain client."""
        if self._langchain_client is None:
            self._langchain_client = ChatOpenAI(
                model=self.model,
                api_key=self.api_key,
                organization=self.org_id,
                base_url=self.base_url
            )
        return self._langchain_client
    
    def _is_reasoning_model(self) -> bool:
        """Check if the current model is a reasoning model."""
        return self.model.startswith(('o1-', 'o3-', 'o4-'))
    
    def _filter_parameters_for_model(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter parameters based on model capabilities."""
        filtered = {}
        
        # Handle max_tokens vs max_completion_tokens for different model types
        if 'max_tokens' in kwargs:
            if self._is_reasoning_model():
                # Reasoning models (o1, o3, o4 series) use max_completion_tokens
                filtered['max_completion_tokens'] = kwargs['max_tokens']
            else:
                # Regular models use max_tokens
                filtered['max_tokens'] = kwargs['max_tokens']
        
        # Temperature is not supported by reasoning models
        if 'temperature' in kwargs and not self._is_reasoning_model():
            filtered['temperature'] = kwargs['temperature']
        
        # Reasoning effort only for reasoning models
        if 'reasoning_effort' in kwargs and self._is_reasoning_model():
            filtered['reasoning_effort'] = kwargs['reasoning_effort']
            
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
        
        if self.org_id:
            headers["OpenAI-Organization"] = self.org_id
        
        # Build request payload
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }
        
        # Add filtered parameters based on model capabilities
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        # DEBUG: Log the complete request being sent to OpenAI
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
            
            # DEBUG: Log the response from OpenAI
            response_data = {
                'response': data['choices'][0]['message']['content'],
                'model': data.get('model', self.model),
                'usage': data.get('usage', {}),
                'finish_reason': data['choices'][0].get('finish_reason', 'unknown')
            }
            debug_log_api_response(self.provider_name, self.model, response_data, request_id)
            
            return self._extract_content_from_openai_response(data)
    
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
        
        if self.org_id:
            headers["OpenAI-Organization"] = self.org_id
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }
        
        # Add filtered parameters based on model capabilities
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
            
            # Apply parameter filtering for model capabilities
            filtered_params = self._filter_parameters_for_model(kwargs)
            
            # Update client parameters
            if 'temperature' in filtered_params:
                client.temperature = filtered_params['temperature']
            if 'max_tokens' in filtered_params:
                client.max_tokens = filtered_params['max_tokens']
            
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
        
        if self.org_id:
            headers["OpenAI-Organization"] = self.org_id
        
        # Build request payload with functions as tools
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": self._convert_functions_to_openai_tools(functions),
            "tool_choice": "auto"
        }
        
        # Add filtered parameters based on model capabilities
        filtered_params = self._filter_parameters_for_model(kwargs)
        payload.update(filtered_params)
        
        # DEBUG: Log the complete function calling request being sent to OpenAI
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
            content = self._extract_content_from_openai_response(data)
            function_calls = self._extract_function_calls_from_openai_response(data)
            
            # DEBUG: Log the function calling response from OpenAI
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
        
        # Apply parameter filtering for model capabilities
        filtered_params = self._filter_parameters_for_model(kwargs)
        
        # Update client parameters
        if 'temperature' in filtered_params:
            client.temperature = filtered_params['temperature']
        if 'max_tokens' in filtered_params:
            client.max_tokens = filtered_params['max_tokens']
        
        # Convert functions to LangChain-compatible format
        langchain_tools = self._convert_functions_to_langchain_tools(functions)
        llm_with_tools = client.bind_tools(langchain_tools)
        
        response = await llm_with_tools.ainvoke(langchain_messages)
        
        # Use consolidated utility to process response
        return self._process_langchain_function_response(response)

    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to OpenAI using unified implementation."""
        return await self._test_connection_base()
    
    def validate_config(self) -> bool:
        """Validate provider configuration using unified implementation."""
        return self._validate_config_base(api_key_prefix='sk-')
    
    async def _handle_api_error(self, response: httpx.Response):
        """Handle API error responses using unified error handling."""
        self._handle_api_error_by_status(
            response,
            auth_indicators=["authentication", "invalid_api_key"],
            rate_limit_indicators=["rate_limit_exceeded", "quota_exceeded"],
            model_not_found_indicators=["model_not_found", "invalid_request"]
        )
    
    async def _handle_error(self, error: Exception):
        """Handle and re-raise errors using unified error handling."""
        self._handle_common_errors(error) 