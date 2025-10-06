"""
Anthropic provider implementation.
Template implementation showing proper dual-mode support with function calling.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
import httpx
from langchain_anthropic import ChatAnthropic
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
from .utils import AnthropicUtilities
from app.utils.logging import debug_log_api_request, debug_log_api_response


class AnthropicProvider(BaseLLMProvider, AnthropicUtilities):
    """Anthropic provider implementation supporting both direct API and LangChain modes."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        super().__init__(model, api_key, **kwargs)
        self.base_url = kwargs.get('base_url', 'https://api.anthropic.com')
        self.api_version = kwargs.get('api_version', '2023-06-01')
        self._langchain_client = None
        
    @property
    def provider_name(self) -> str:
        return "anthropic"
    
    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_streaming=True,
            supports_function_calling=True,  # Claude supports function calling
            supports_system_prompts=True,   # Claude supports system prompts
            supports_reasoning=False,       # Claude doesn't have reasoning mode
            max_context_length=200000,      # Claude 3 context length
            supports_images=True,           # Claude 3 supports images
            supports_audio=False,          # Claude doesn't support audio yet
            tool_schema="anthropic"
        )
    
    def _get_langchain_client(self) -> ChatAnthropic:
        """Get or create LangChain client."""
        if self._langchain_client is None:
            self._langchain_client = ChatAnthropic(
                model=self.model,
                api_key=self.api_key,
                base_url=self.base_url
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
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": self.api_version
        }
        
        # Convert messages to Anthropic format
        anthropic_payload = self._convert_messages_for_anthropic_api(messages)
        
        # Add optional parameters
        if 'temperature' in kwargs:
            anthropic_payload['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            anthropic_payload['max_tokens'] = kwargs['max_tokens']
        else:
            anthropic_payload['max_tokens'] = 1024  # Required by Anthropic
        
        # DEBUG: Log the complete request being sent to Anthropic
        debug_log_api_request(self.provider_name, self.model, anthropic_payload, request_id)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=anthropic_payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            content = self._extract_content_from_response(data)
            
            # DEBUG: Log the response from Anthropic
            response_data = {
                'response': content,
                'model': data.get('model', self.model),
                'usage': data.get('usage', {}),
                'stop_reason': data.get('stop_reason', 'unknown')
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
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": self.api_version
        }
        
        # Convert messages to Anthropic format
        anthropic_payload = self._convert_messages_for_anthropic_api(messages)
        
        # Add functions as tools (SAME function definitions, different API format)
        anthropic_payload['tools'] = self._convert_functions_to_anthropic_tools(functions)
        
        # Add optional parameters
        if 'temperature' in kwargs:
            anthropic_payload['temperature'] = kwargs['temperature']
        if 'max_tokens' in kwargs:
            anthropic_payload['max_tokens'] = kwargs['max_tokens']
        else:
            anthropic_payload['max_tokens'] = 1024
        
        # DEBUG: Log the complete function calling request being sent to Anthropic
        debug_log_api_request(self.provider_name, self.model, anthropic_payload, request_id)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/v1/messages",
                headers=headers,
                json=anthropic_payload,
                timeout=60.0
            )
            
            if response.status_code != 200:
                await self._handle_api_error(response)
            
            data = response.json()
            content = self._extract_content_from_response(data)
            function_calls = self._extract_function_calls_from_response(data)
            
            # DEBUG: Log the function calling response from Anthropic
            response_data = {
                'response': content,
                'model': data.get('model', self.model),
                'usage': data.get('usage', {}),
                'stop_reason': data.get('stop_reason', 'unknown'),
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
        
        client = self._get_langchain_client()
        
        # Update client parameters if provided
        if 'temperature' in kwargs:
            client.temperature = kwargs['temperature']
        if 'max_tokens' in kwargs:
            client.max_tokens = kwargs['max_tokens']
        
        response = await client.ainvoke(langchain_messages)
        # Use Anthropic-specific content extraction for LangChain responses
        return self._extract_content_from_langchain_response(response)
    
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
        
        # Extract content and function calls from LangChain response
        content = self._extract_content_from_langchain_response(response)
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
        # Implementation would use Anthropic's streaming API
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
        client = self._get_langchain_client()
        
        async for chunk in client.astream(langchain_messages):
            if hasattr(chunk, 'content'):
                # Extract text content from streaming chunk (might also be a list)
                content = self._extract_content_from_langchain_response(chunk)
                if content:
                    yield content
    
    # =============================================================================
    # UTILITY METHODS - SHARED BETWEEN MODES
    # =============================================================================
    
    def _convert_messages_for_anthropic_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Convert internal message format to Anthropic API format."""
        anthropic_messages = []
        system_content = None
        
        for msg in messages:
            if msg['role'] == 'system':
                system_content = msg.get('content', system_content)
            elif msg['role'] == 'assistant' and 'tool_calls' in msg and msg['tool_calls']:
                # Assistant message with tool calls (and optional assistant text)
                content_blocks = []
                assistant_text = msg.get('content')
                if isinstance(assistant_text, str) and assistant_text.strip():
                    content_blocks.append({'type': 'text', 'text': assistant_text})

                for tool_call in msg['tool_calls']:
                    # Support both OpenAI-style and generic structures
                    tool_id = tool_call.get('id') or tool_call.get('tool_call_id') or "tool_call"
                    function_obj = tool_call.get('function', {}) or {}
                    tool_name = function_obj.get('name') or tool_call.get('name') or "unknown_tool"
                    tool_args = function_obj.get('arguments', {})

                    # Anthropic requires input as an object; parse if it's a JSON string
                    if isinstance(tool_args, str):
                        try:
                            tool_args = json.loads(tool_args)
                        except Exception:
                            # Fallback to wrapping as a string field to keep object shape
                            tool_args = {"__args": tool_args}

                    content_blocks.append({
                        'type': 'tool_use',
                        'id': tool_id,
                        'name': tool_name,
                        'input': tool_args if isinstance(tool_args, dict) else {}
                    })

                anthropic_messages.append({
                    'role': 'assistant',
                    'content': content_blocks
                })
            elif msg['role'] == 'tool':
                # Convert internal tool messages to Anthropic-compatible user/tool_result messages
                if 'tool_results' in msg and isinstance(msg['tool_results'], list):
                    for tool_result in msg['tool_results']:
                        result_content = tool_result.get('content', '')
                        if not isinstance(result_content, str):
                            try:
                                result_content = json.dumps(result_content)
                            except Exception:
                                result_content = str(result_content)
                        anthropic_messages.append({
                            'role': 'user',
                            'content': [
                                {
                                    'type': 'tool_result',
                                    'tool_use_id': tool_result.get('tool_call_id') or tool_result.get('id') or "tool_call",
                                    'content': result_content
                                }
                            ]
                        })
                elif 'tool_call_id' in msg:
                    # OpenAI-style single tool message: { role: 'tool', tool_call_id, content }
                    result_content = msg.get('content', '')
                    if not isinstance(result_content, str):
                        try:
                            result_content = json.dumps(result_content)
                        except Exception:
                            result_content = str(result_content)
                    anthropic_messages.append({
                        'role': 'user',
                        'content': [
                            {
                                'type': 'tool_result',
                                'tool_use_id': msg['tool_call_id'],
                                'content': result_content
                            }
                        ]
                    })
                # else: silently ignore unknown tool message shapes to avoid invalid roles
            else:
                # Standard message with content
                content = msg.get('content', '')
                if msg['role'] in ['user', 'assistant']:
                    # Allow empty assistant content only if it's genuinely an assistant turn without tools
                    if isinstance(content, list):
                        # Already content blocks; forward as-is
                        anthropic_messages.append({
                            'role': msg['role'],
                            'content': content
                        })
                    else:
                        anthropic_messages.append({
                            'role': msg['role'],
                            'content': content if isinstance(content, str) else str(content)
                        })
        
        payload = {
            'model': self.model,
            'messages': anthropic_messages
        }
        
        if system_content:
            payload['system'] = system_content
        
        return payload
    

    

    
    def _extract_content_from_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Anthropic API response."""
        return self._extract_content_from_anthropic_response(response_data)
    
    def _extract_function_calls_from_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Anthropic API response."""
        return self._extract_function_calls_from_anthropic_response(response_data)



    # =============================================================================
    # ERROR HANDLING
    # =============================================================================
    
    async def _handle_error(self, error: Exception):
        """Handle provider-specific errors using unified error handling."""
        self._handle_exception_with_patterns(
            error,
            auth_patterns=["401", "authentication"],
            rate_limit_patterns=["429", "rate limit"],
            model_not_found_patterns=["404", "model"]
        )
    
    async def _handle_api_error(self, response: httpx.Response):
        """Handle API error responses using unified error handling."""
        self._handle_api_error_by_status(
            response,
            auth_indicators=["authentication"],
            rate_limit_indicators=["rate limit"],
            model_not_found_indicators=["model"]
        )
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test the connection to Anthropic using unified implementation."""
        return await self._test_connection_base()

    def validate_config(self) -> bool:
        """Validate provider configuration using unified implementation."""
        return self._validate_config_base(api_key_prefix='sk-ant-') 