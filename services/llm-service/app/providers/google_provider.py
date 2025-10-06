"""
Google provider implementation.
Template implementation showing proper dual-mode support with function calling for Google Gemini models.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from .base import (
    BaseLLMProvider, 
    ProviderCapabilities, 
    ConnectionMode,
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderModelNotFoundError
)
from .utils import ProviderUtilityMixin
from app.utils.logging import debug_log_api_request, debug_log_api_response


class GoogleProvider(BaseLLMProvider, ProviderUtilityMixin):
    """Google provider implementation supporting both direct API and LangChain modes."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.base_url = kwargs.get('base_url', 'https://generativelanguage.googleapis.com')
        self.api_version = kwargs.get('api_version', 'v1beta')
        self._langchain_client = None
        
    @property
    def provider_name(self) -> str:
        return "google"
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,  # Gemini supports function calling
            supports_system_prompts=True,   # Gemini supports system prompts
            supports_reasoning=False,       # Gemini doesn't have reasoning mode
            max_context_length=1048576,     # Gemini 1.5 has 1M+ context length
            supports_images=True,           # Gemini supports images
            supports_audio=True,
            tool_schema="openai"
        )
    
    def _get_langchain_client(self, **kwargs) -> ChatGoogleGenerativeAI:
        """Get or create LangChain client with dynamic parameters."""
        # For Google, we need to create a new client instance with parameters
        # since ChatGoogleGenerativeAI doesn't support dynamic parameter updates
        client_params = {
            'model': self.model,
            'google_api_key': self.api_key
        }
        
        # Add temperature if provided
        if 'temperature' in kwargs:
            client_params['temperature'] = kwargs['temperature']
        
        # Add max_tokens if provided
        if 'max_tokens' in kwargs:
            client_params['max_output_tokens'] = kwargs['max_tokens']
        
        return ChatGoogleGenerativeAI(**client_params)
    
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send a chat request using either direct API or LangChain."""
        try:
            if self.connection_mode == ConnectionMode.DIRECT:
                return await self._chat_direct(messages, **kwargs)
            else:
                return await self._chat_langchain(messages, **kwargs)
        except Exception as e:
            await self._handle_error(e)
    
    async def chat_with_functions(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        Chat with function calling support.
        Returns (response_content, function_calls).
        
        NOTE: Function DEFINITIONS are the same for both modes!
        Only the CALLING MECHANISM differs.
        """
        try:
            if self.connection_mode == ConnectionMode.DIRECT:
                return await self._chat_with_functions_direct(messages, functions, **kwargs)
            else:
                return await self._chat_with_functions_langchain(messages, functions, **kwargs)
        except Exception as e:
            await self._handle_error(e)
    
    # =============================================================================
    # DIRECT API IMPLEMENTATION
    # =============================================================================
    
    async def _chat_direct(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Direct API implementation using HTTP calls."""
        request_id = kwargs.get('request_id', 'unknown')
        
        # Convert messages to Google format
        google_payload = self._convert_messages_for_google_api(messages)
        
        # Add optional parameters
        generation_config = {}
        if 'temperature' in kwargs:
            generation_config['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            generation_config['maxOutputTokens'] = kwargs['max_tokens']
        
        if generation_config:
            google_payload['generationConfig'] = generation_config
        
        # DEBUG: Log the complete request being sent to Google
        debug_log_api_request(self.provider_name, self.model, google_payload, request_id)
        
        # Build URL with API key
        url = f"{self.base_url}/{self.api_version}/models/{self.model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=google_payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            content = self._extract_content_from_response(data)
            
            # DEBUG: Log the response from Google
            response_data = {
                'response': content,
                'model': self.model,
                'usage': data.get('usageMetadata', {}),
                'finish_reason': 'completed'  # Google doesn't provide explicit finish reasons
            }
            debug_log_api_response(self.provider_name, self.model, response_data, request_id)
            
            return content
    
    async def _chat_with_functions_direct(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """Direct API function calling implementation."""
        request_id = kwargs.get('request_id', 'unknown')
        
        # Convert messages to Google format
        google_payload = self._convert_messages_for_google_api(messages)
        
        # Add functions as tools (SAME function definitions, different API format)
        google_payload['tools'] = self._convert_functions_to_google_tools(functions)
        
        # Add optional parameters
        generation_config = {}
        if 'temperature' in kwargs:
            generation_config['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            generation_config['maxOutputTokens'] = kwargs['max_tokens']
        
        if generation_config:
            google_payload['generationConfig'] = generation_config
        
        # DEBUG: Log the complete function calling request being sent to Google
        debug_log_api_request(self.provider_name, self.model, google_payload, request_id)
        
        # Build URL with API key
        url = f"{self.base_url}/{self.api_version}/models/{self.model}:generateContent?key={self.api_key}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Content-Type": "application/json"},
                json=google_payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            content = self._extract_content_from_response(data)
            function_calls = self._extract_function_calls_from_response(data)
            
            # DEBUG: Log the function calling response from Google
            response_data = {
                'response': content,
                'model': self.model,
                'usage': data.get('usageMetadata', {}),
                'finish_reason': 'completed',
                'function_calls': function_calls,
                'has_function_calls': bool(function_calls)
            }
            debug_log_api_response(self.provider_name, self.model, response_data, request_id)
            
            return content, function_calls
    
    # =============================================================================
    # LANGCHAIN IMPLEMENTATION  
    # =============================================================================
    
    async def _chat_langchain(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """LangChain implementation."""
        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        # Get client with dynamic parameters for Google
        client = self._get_langchain_client(**kwargs)
        
        response = await client.ainvoke(langchain_messages)
        return response.content
    
    async def _chat_with_functions_langchain(
        self, 
        messages: List[Dict[str, str]], 
        functions: List[Dict[str, Any]], 
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """LangChain function calling implementation."""
        # Convert to LangChain message format
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        # Get client with dynamic parameters for Google
        client = self._get_langchain_client(**kwargs)
        
        # Convert functions to LangChain-compatible format
        langchain_tools = self._convert_functions_to_langchain_tools(functions)
        llm_with_tools = client.bind_tools(langchain_tools)
        
        response = await llm_with_tools.ainvoke(langchain_messages)
        
        # Extract content and function calls from LangChain response
        content = response.content or ""  # Ensure content is never None
        function_calls = None
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            function_calls = [
                {
                    "function": call.get('name'),
                    "arguments": call.get('args', {}),
                    "id": call.get('id'),
                    "result": "pending"  # Would be filled by function execution
                }
                for call in response.tool_calls
            ]
        
        return content, function_calls
    
    # =============================================================================
    # STREAMING SUPPORT
    # =============================================================================
    
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
        # Implementation would use Google's streaming API
        # For now, simulate streaming
        full_response = await self._chat_direct(messages, **kwargs)
        
        # Simulate streaming by yielding chunks
        chunk_size = 50
        for i in range(0, len(full_response), chunk_size):
            chunk = full_response[i:i + chunk_size]
            yield chunk
            await asyncio.sleep(0.01)
    
    async def _chat_stream_langchain(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        """LangChain streaming implementation."""
        langchain_messages = self._convert_to_langchain_messages(messages)
        client = self._get_langchain_client(**kwargs)
        
        async for chunk in client.astream(langchain_messages):
            if hasattr(chunk, 'content'):
                yield chunk.content
    
    # =============================================================================
    # UTILITY METHODS - SHARED BETWEEN MODES
    # =============================================================================
    
    def _convert_messages_for_google_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Convert internal message format to Google API format."""
        contents = []
        system_instruction = None
        
        for msg in messages:
            if msg['role'] == 'system':
                system_instruction = msg['content']
            elif msg['role'] == 'user':
                contents.append({
                    'role': 'user',
                    'parts': [{'text': msg['content']}]
                })
            elif msg['role'] == 'assistant':
                contents.append({
                    'role': 'model',  # Google uses 'model' instead of 'assistant'
                    'parts': [{'text': msg['content']}]
                })
        
        payload = {'contents': contents}
        
        if system_instruction:
            payload['systemInstruction'] = {
                'parts': [{'text': system_instruction}]
            }
        
        return payload
    
    def _convert_functions_to_google_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert function definitions to Google tools format.
        
        NOTE: This takes the SAME function definitions and converts them 
        to Google's specific tool format.
        """
        tools = []
        function_declarations = []
        
        for func in functions:
            function_declarations.append({
                'name': func['name'],
                'description': func['description'],
                'parameters': func['parameters']
            })
        
        if function_declarations:
            tools.append({
                'functionDeclarations': function_declarations
            })
        
        return tools
    

    
    def _extract_content_from_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Google API response."""
        candidates = response_data.get('candidates', [])
        if not candidates:
            return ""
        
        content_obj = candidates[0].get('content', {})
        parts = content_obj.get('parts', [])
        
        text_content = ""
        for part in parts:
            if 'text' in part:
                text_content += part.get('text', '')
        
        return text_content
    
    def _extract_function_calls_from_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Google API response."""
        candidates = response_data.get('candidates', [])
        if not candidates:
            return None
        
        content_obj = candidates[0].get('content', {})
        parts = content_obj.get('parts', [])
        
        function_calls = []
        for part in parts:
            if 'functionCall' in part:
                func_call = part.get('functionCall', {})
                function_calls.append({
                    'function': func_call.get('name'),
                    'arguments': func_call.get('args', {}),
                    'id': str(hash(str(func_call))),  # Google doesn't provide IDs
                    'result': 'pending'
                })
        
        return function_calls if function_calls else None



    # =============================================================================
    # ERROR HANDLING
    # =============================================================================
    
    async def _handle_error(self, error: Exception):
        """Handle provider-specific errors using unified error handling."""
        self._handle_exception_with_patterns(
            error,
            auth_patterns=["403", "api_key_invalid"],
            rate_limit_patterns=["429", "rate_limit_exceeded"],
            model_not_found_patterns=["404", "model_not_found"]
        )
    
    async def _handle_api_error(self, response: httpx.Response):
        """Handle API error responses using unified error handling."""
        self._handle_api_error_by_status(
            response,
            auth_indicators=["api_key_invalid"],
            rate_limit_indicators=["rate_limit_exceeded"],
            model_not_found_indicators=["model_not_found"]
        )
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Google using unified implementation."""
        return await self._test_connection_base()
    
    def validate_config(self) -> bool:
        """Validate provider configuration using unified implementation."""
        return self._validate_config_base(api_key_prefix='AIza') 