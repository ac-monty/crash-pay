"""
Consolidated provider utilities.
Common utility methods used across all provider implementations.
"""

import json
import httpx
from typing import List, Dict, Any, Optional, AsyncGenerator
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from .base import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderModelNotFoundError
)


class ProviderUtilityMixin:
    """
    Mixin class containing common utility methods for all providers.
    Eliminates 90% of duplicate code across providers.
    """
    
    # =============================================================================
    # LANGCHAIN MESSAGE CONVERSION
    # =============================================================================
    
    def _convert_to_langchain_messages(self, messages: List[Dict[str, str]]) -> List:
        """Convert internal message format to LangChain message objects."""
        langchain_messages = []
        
        for msg in messages:
            role = msg.get('role')
            # Some messages (like tool results) may not include 'content'
            content = msg.get('content', "")
            
            # Skip tool-only messages in LangChain mode; tool execution is bound via tools
            if role not in ('system', 'user', 'assistant'):
                continue
            
            if role == 'system':
                langchain_messages.append(SystemMessage(content=content))
            elif role == 'user':
                langchain_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
        
        return langchain_messages
    
    # =============================================================================
    # FUNCTION CONVERSION - LANGCHAIN
    # =============================================================================
    
    def _convert_functions_to_langchain_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Convert function definitions to LangChain-compatible format.
        
        LangChain expects functions to have 'title' and 'description' at the top level,
        and the 'parameters' to be a proper JSON schema.
        """
        langchain_tools = []
        for func in functions:
            # LangChain expects this format for bind_tools
            langchain_tool = {
                "title": func['name'],
                "description": func['description'],
                "type": "object",
                "properties": func['parameters'].get('properties', {}),
                "required": func['parameters'].get('required', [])
            }
            langchain_tools.append(langchain_tool)
        return langchain_tools
    
    # =============================================================================
    # FUNCTION CALL PROCESSING
    # =============================================================================
    
    def _process_langchain_function_response(self, response) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        Process LangChain response to extract content and function calls.
        Handles the common pattern across all providers.
        """
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
    # UNIFIED ERROR HANDLING
    # =============================================================================
    
    def _handle_common_errors(self, error: Exception):
        """
        Common error handling pattern for all providers.
        Re-raises ProviderError instances, wraps others.
        """
        if isinstance(error, ProviderError):
            raise error
        else:
            raise ProviderError(str(error), self.provider_name, self.model)
    
    def _handle_api_error_by_status(self, response: httpx.Response, 
                                   provider_name: str = None,
                                   auth_indicators: List[str] = None,
                                   rate_limit_indicators: List[str] = None,
                                   model_not_found_indicators: List[str] = None):
        """
        Unified API error handling by status code and error message patterns.
        
        Args:
            response: HTTP response object
            provider_name: Name of the provider (for error messages)
            auth_indicators: List of strings that indicate authentication errors
            rate_limit_indicators: List of strings that indicate rate limit errors
            model_not_found_indicators: List of strings that indicate model not found errors
        """
        provider_name = provider_name or getattr(self, 'provider_name', 'unknown')
        model = getattr(self, 'model', 'unknown')
        
        # Extract error message from response
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            error_code = error_data.get('error', {}).get('code')
        except:
            error_message = f"HTTP {response.status_code}: {response.text}"
            error_code = None
        
        # Check for specific error patterns in message
        error_msg_lower = error_message.lower()
        
        # Authentication errors
        if (response.status_code == 401 or response.status_code == 403 or 
            any(indicator in error_msg_lower for indicator in (auth_indicators or []))):
            raise ProviderAuthenticationError(
                f"{provider_name} authentication failed: {error_message}",
                provider_name,
                model,
                error_code
            )
        
        # Rate limit errors
        if (response.status_code == 429 or 
            any(indicator in error_msg_lower for indicator in (rate_limit_indicators or []))):
            raise ProviderRateLimitError(
                f"{provider_name} rate limit exceeded: {error_message}",
                provider_name,
                model,
                error_code
            )
        
        # Model not found errors
        if (response.status_code == 404 or 
            any(indicator in error_msg_lower for indicator in (model_not_found_indicators or []))):
            raise ProviderModelNotFoundError(
                f"{provider_name} model not found: {error_message}",
                provider_name,
                model,
                error_code
            )
        
        # Generic provider error
        raise ProviderError(
            f"{provider_name} API error: {error_message}",
            provider_name,
            model,
            error_code
        )
    
    def _handle_exception_with_patterns(self, error: Exception,
                                       provider_name: str = None,
                                       auth_patterns: List[str] = None,
                                       rate_limit_patterns: List[str] = None,
                                       model_not_found_patterns: List[str] = None):
        """
        Handle exceptions by checking error message patterns.
        Used for LangChain or other non-HTTP errors.
        """
        provider_name = provider_name or getattr(self, 'provider_name', 'unknown')
        model = getattr(self, 'model', 'unknown')
        error_msg = str(error).lower()
        
        # Authentication errors
        if any(pattern in error_msg for pattern in (auth_patterns or [])):
            raise ProviderAuthenticationError(
                f"{provider_name} authentication failed: {str(error)}",
                provider_name,
                model
            )
        
        # Rate limit errors
        if any(pattern in error_msg for pattern in (rate_limit_patterns or [])):
            raise ProviderRateLimitError(
                f"{provider_name} rate limit exceeded: {str(error)}",
                provider_name,
                model
            )
        
        # Model not found errors
        if any(pattern in error_msg for pattern in (model_not_found_patterns or [])):
            raise ProviderModelNotFoundError(
                f"{provider_name} model not found: {str(error)}",
                provider_name,
                model
            )
        
        # Default to generic provider error
        raise ProviderError(
            f"{provider_name} provider error: {str(error)}",
            provider_name,
            model
        )
    
    # =============================================================================
    # UNIFIED TEST CONNECTION
    # =============================================================================
    
    async def _test_connection_base(self) -> Dict[str, Any]:
        """
        Base test connection implementation that can be used by all providers.
        """
        import asyncio
        
        try:
            test_messages = [{"role": "user", "content": "Hello"}]
            
            start_time = asyncio.get_event_loop().time()
            response = await self.chat(test_messages, max_tokens=5)
            end_time = asyncio.get_event_loop().time()
            
            return {
                "success": True,
                "response_time": end_time - start_time,
                "test_response": response[:50] + "..." if len(response) > 50 else response,
                "model": self.model,
                "provider": self.provider_name,
                "connection_mode": self.connection_mode.value
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "model": self.model,
                "provider": self.provider_name,
                "connection_mode": self.connection_mode.value
            }
    
    # =============================================================================
    # UNIFIED CONFIG VALIDATION
    # =============================================================================
    
    def _validate_config_base(self, api_key_prefix: str = None) -> bool:
        """
        Base configuration validation that can be extended by providers.
        
        Args:
            api_key_prefix: Expected prefix for API key (e.g., 'sk-', 'sk-ant-', 'AIza')
        """
        if not self.api_key:
            return False
        if not self.model:
            return False
        if api_key_prefix and not self.api_key.startswith(api_key_prefix):
            return False
        return True
    
    # =============================================================================
    # STREAMING UTILITIES
    # =============================================================================
    
    async def _simulate_streaming(self, response: str, chunk_size: int = 50) -> AsyncGenerator[str, None]:
        """
        Utility method to simulate streaming by yielding chunks.
        Used as fallback when true streaming is not available.
        """
        import asyncio
        
        for i in range(0, len(response), chunk_size):
            chunk = response[i:i + chunk_size]
            yield chunk
            await asyncio.sleep(0.01)  # Small delay to simulate streaming
    
    # =============================================================================
    # CONTENT EXTRACTION HELPERS
    # =============================================================================
    
    def _safe_extract_content(self, content: Any) -> str:
        """
        Safely extract string content from various response formats.
        Ensures content is always a string, never None.
        """
        if content is None:
            return ""
        elif isinstance(content, str):
            return content
        elif hasattr(content, 'get'):
            return content.get('content', '')
        else:
            return str(content)
    
    def _parse_json_arguments(self, arguments_str: str) -> Dict[str, Any]:
        """
        Safely parse JSON arguments from function calls.
        Returns empty dict if parsing fails.
        """
        try:
            return json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            return {}
    
    # =============================================================================
    # ERROR HANDLING HELPERS
    # =============================================================================
    
    def _determine_error_type(self, status_code: int, error_message: str) -> str:
        """
        Determine the appropriate error type based on status code and message.
        """
        if status_code == 401 or "authentication" in error_message.lower():
            return "authentication"
        elif status_code == 429 or "rate limit" in error_message.lower():
            return "rate_limit"
        elif status_code == 404 or "model" in error_message.lower():
            return "model_not_found"
        else:
            return "general"
    
    def _extract_error_message(self, response_data: Dict[str, Any]) -> str:
        """
        Extract error message from various API response formats.
        """
        # Try common error message paths
        error_paths = [
            ['error', 'message'],
            ['error', 'detail'],
            ['message'],
            ['detail']
        ]
        
        for path in error_paths:
            current = response_data
            for key in path:
                if isinstance(current, dict) and key in current:
                    current = current[key]
                else:
                    current = None
                    break
            
            if current and isinstance(current, str):
                return current
        
        return "Unknown error"


# =============================================================================
# PROVIDER-SPECIFIC UTILITIES
# =============================================================================

class OpenAIUtilities(ProviderUtilityMixin):
    """OpenAI-specific utilities."""
    
    def _convert_functions_to_openai_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert function definitions to OpenAI tools format."""
        tools = []
        for func in functions:
            tools.append({
                "type": "function",
                "function": {
                    "name": func['name'],
                    "description": func['description'],
                    "parameters": func['parameters']
                }
            })
        return tools
    
    def _extract_content_from_openai_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from OpenAI API response."""
        choices = response_data.get('choices', [])
        if choices and len(choices) > 0:
            message = choices[0].get('message', {})
            content = message.get('content', '')
            # Handle case where content is explicitly None (reasoning models with function calls)
            return content if content is not None else ''
        return ''
    
    def _extract_function_calls_from_openai_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from OpenAI API response."""
        choices = response_data.get('choices', [])
        if not choices:
            return None
            
        message = choices[0].get('message', {})
        tool_calls = message.get('tool_calls', [])
        
        if not tool_calls:
            return None
        
        function_calls = []
        for tool_call in tool_calls:
            if tool_call.get('type') == 'function':
                function_info = tool_call.get('function', {})
                arguments = self._parse_json_arguments(function_info.get('arguments', '{}'))
                
                function_calls.append({
                    'function': function_info.get('name'),
                    'arguments': arguments,
                    'id': tool_call.get('id'),
                    'result': 'pending'
                })
        
        return function_calls if function_calls else None


class AnthropicUtilities(ProviderUtilityMixin):
    """Anthropic-specific utilities."""
    
    def _extract_content_from_langchain_response(self, response) -> str:
        """
        Extract text content from Anthropic LangChain response.
        Anthropic returns response.content as a list, not a string.
        """
        content = response.content
        
        # Handle None content
        if content is None:
            return ""
        
        # If it's already a string (shouldn't happen with Anthropic, but be safe)
        if isinstance(content, str):
            return content
        
        # If it's a list of content blocks (typical Anthropic LangChain format)
        if isinstance(content, list):
            text_content = ""
            for block in content:
                if isinstance(block, dict) and block.get('type') == 'text':
                    text_value = block.get('text', '')
                    if text_value is not None:
                        text_content += text_value
            return text_content
        
        # Fallback - convert to string
        return str(content) if content else ""
    
    def _convert_functions_to_anthropic_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert function definitions to Anthropic tools format."""
        tools = []
        for func in functions:
            tools.append({
                'name': func['name'],
                'description': func['description'],
                'input_schema': func['parameters']
            })
        return tools
    
    def _convert_messages_for_anthropic_api(self, messages: List[Dict[str, str]]) -> Dict[str, Any]:
        """Convert internal message format to Anthropic API format.
        
        Key adaptations:
        - Assistant messages with tool_calls -> content blocks of type 'tool_use'
        - Tool result messages (role: 'tool' + tool_results) -> user message with 'tool_result' blocks
        - Plain messages keep role/content as-is (ensuring content is a string)
        """
        import json as _json
        anthropic_messages: List[Dict[str, Any]] = []
        system_content = None
        
        for msg in messages:
            role = msg.get('role')
            
            # Capture system prompt
            if role == 'system':
                system_content = msg.get('content', "")
                continue
            
            # Translate assistant with tool_calls into Anthropic tool_use blocks
            if role == 'assistant' and msg.get('tool_calls'):
                content_blocks: List[Dict[str, Any]] = []
                # Include any assistant text content first if present
                assistant_text = msg.get('content')
                if isinstance(assistant_text, str) and assistant_text:
                    content_blocks.append({'type': 'text', 'text': assistant_text})
                
                for call in msg.get('tool_calls', []) or []:
                    function_obj = call.get('function', {}) if isinstance(call, dict) else {}
                    args_raw = function_obj.get('arguments', "{}")
                    try:
                        args_parsed = _json.loads(args_raw) if isinstance(args_raw, str) else (args_raw or {})
                    except _json.JSONDecodeError:
                        args_parsed = {}
                    content_blocks.append({
                        'type': 'tool_use',
                        'id': call.get('id') or f"call_{len(content_blocks)}",
                        'name': function_obj.get('name'),
                        'input': args_parsed
                    })
                anthropic_messages.append({'role': 'assistant', 'content': content_blocks})
                continue
            
            # Translate tool results into Anthropic tool_result blocks (as a user message)
            if role == 'tool' and msg.get('tool_results'):
                result_blocks: List[Dict[str, Any]] = []
                for tr in msg.get('tool_results', []) or []:
                    tool_call_id = tr.get('tool_call_id')
                    content_value = tr.get('content', "")
                    # Anthropic allows 'content' as a string; leave JSON as-is
                    result_blocks.append({
                        'type': 'tool_result',
                        'tool_use_id': tool_call_id,
                        'content': content_value if isinstance(content_value, str) else _json.dumps(content_value)
                    })
                anthropic_messages.append({'role': 'user', 'content': result_blocks})
                continue
            
            # Default handling for plain messages (user/assistant without tools)
            # Ensure 'content' exists and is a string to prevent KeyError
            anthropic_messages.append({
                'role': role or 'user',
                'content': msg.get('content', "")
            })
        
        payload = {
            'model': self.model,
            'messages': anthropic_messages
        }
        
        if system_content:
            payload['system'] = system_content
        
        return payload
    
    def _extract_content_from_anthropic_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Anthropic API response."""
        content_blocks = response_data.get('content', [])
        text_content = ""
        
        for block in content_blocks:
            if block.get('type') == 'text':
                text_value = block.get('text', '')
                # Handle case where text is explicitly None
                if text_value is not None:
                    text_content += text_value
        
        return text_content
    
    def _extract_function_calls_from_anthropic_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Anthropic API response."""
        content_blocks = response_data.get('content', [])
        function_calls = []
        
        for block in content_blocks:
            if block.get('type') == 'tool_use':
                function_calls.append({
                    'function': block.get('name'),
                    'arguments': block.get('input', {}),
                    'id': block.get('id'),
                    'result': 'pending'
                })
        
        return function_calls if function_calls else None


class GoogleUtilities(ProviderUtilityMixin):
    """Google-specific utilities."""
    
    def _convert_functions_to_google_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert function definitions to Google tools format."""
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
    
    def _extract_content_from_google_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Google API response."""
        candidates = response_data.get('candidates', [])
        if not candidates:
            return ""
        
        content_obj = candidates[0].get('content', {})
        parts = content_obj.get('parts', [])
        
        text_content = ""
        for part in parts:
            if 'text' in part:
                text_value = part.get('text', '')
                # Handle case where text is explicitly None
                if text_value is not None:
                    text_content += text_value
        
        return text_content
    
    def _extract_function_calls_from_google_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
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


class CohereUtilities(ProviderUtilityMixin):
    """Cohere-specific utilities."""
    
    def _convert_functions_to_cohere_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert function definitions to Cohere tools format."""
        tools = []
        for func in functions:
            tools.append({
                'type': 'function',
                'function': {
                    'name': func['name'],
                    'description': func['description'],
                    'parameters': func['parameters']
                }
            })
        return tools
    
    def _convert_messages_for_cohere_api(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Convert internal message format to Cohere API format."""
        cohere_messages = []
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            # Cohere API expects role and content structure
            cohere_messages.append({
                'role': role,
                'content': content
            })
        
        return cohere_messages
    
    def _extract_content_from_cohere_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Cohere API response."""
        message = response_data.get('message', {})
        content_blocks = message.get('content', [])
        
        text_content = ""
        for block in content_blocks:
            if block.get('type') == 'text':
                text_value = block.get('text', '')
                if text_value is not None:
                    text_content += text_value
        
        return text_content
    
    def _extract_function_calls_from_cohere_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Cohere API response."""
        # Cohere (v2024-05) returns tool calls at the top-level of the response.
        # Older beta versions nested them inside message.tool_calls. We must
        # support both to remain backward-compatible.

        # 1. New schema – top-level list
        tool_calls_root = response_data.get('tool_calls', [])

        # 2. Legacy schema – inside the assistant message
        message = response_data.get('message', {})
        tool_calls_msg = message.get('tool_calls', [])

        # Prefer new top-level if present, else fallback
        tool_calls = tool_calls_root or tool_calls_msg

        if not tool_calls:
            return None
        
        function_calls = []
        for tool_call in tool_calls:
            if tool_call.get('type') == 'function':
                function_info = tool_call.get('function', {})
                arguments = function_info.get('arguments', {})
                
                # Parse arguments if they're a string
                if isinstance(arguments, str):
                    arguments = self._parse_json_arguments(arguments)
                
                function_calls.append({
                    'function': function_info.get('name'),
                    'arguments': arguments,
                    'id': tool_call.get('id'),
                    'result': 'pending'
                })
        
        return function_calls if function_calls else None 


class MistralUtilities(ProviderUtilityMixin):
    """Mistral-specific utilities."""
    
    def _convert_functions_to_mistral_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert function definitions to Mistral tools format."""
        tools = []
        for func in functions:
            tools.append({
                'type': 'function',
                'function': {
                    'name': func['name'],
                    'description': func['description'],
                    'parameters': func['parameters']
                }
            })
        return tools
    
    def _convert_messages_for_mistral_api(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Convert internal message format to Mistral API format."""
        mistral_messages = []
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            # Mistral API expects role and content structure
            mistral_messages.append({
                'role': role,
                'content': content
            })
        
        return mistral_messages
    
    def _extract_content_from_mistral_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Mistral API response."""
        choices = response_data.get('choices', [])
        if not choices:
            return ""
        
        message = choices[0].get('message', {})
        content = message.get('content', '')
        
        # Handle case where content is explicitly None
        return content if content is not None else ""
    
    def _extract_function_calls_from_mistral_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Mistral API response."""
        choices = response_data.get('choices', [])
        if not choices:
            return None
        
        message = choices[0].get('message', {})
        tool_calls = message.get('tool_calls', [])
        
        if not tool_calls:
            return None
        
        function_calls = []
        for tool_call in tool_calls:
            # Mistral doesn't include 'type' field in tool_calls, they're all functions
            # Check if it has a 'function' object instead
            function_info = tool_call.get('function', {})
            if function_info:  # If we have function info, it's a function call
                arguments = function_info.get('arguments', {})
                
                # Parse arguments if they're a string (like Fireworks does)
                if isinstance(arguments, str):
                    try:
                        import json
                        arguments = json.loads(arguments)
                    except (json.JSONDecodeError, TypeError):
                        arguments = {}
                
                function_calls.append({
                    'function': function_info.get('name'),
                    'arguments': arguments,
                    'id': tool_call.get('id'),
                    'result': 'pending'
                })
        
        return function_calls if function_calls else None


class FireworksUtilities(ProviderUtilityMixin):
    """Fireworks-specific utilities."""
    
    def _convert_functions_to_fireworks_tools(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert function definitions to Fireworks tools format."""
        tools = []
        for func in functions:
            tools.append({
                'type': 'function',
                'function': {
                    'name': func['name'],
                    'description': func['description'],
                    'parameters': func['parameters']
                }
            })
        return tools
    
    def _convert_messages_for_fireworks_api(self, messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Convert internal message format to Fireworks API format."""
        # Fireworks uses standard OpenAI format, so no conversion needed
        return messages
    
    def _extract_content_from_fireworks_response(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from Fireworks API response."""
        if 'choices' in response_data and len(response_data['choices']) > 0:
            message = response_data['choices'][0].get('message', {})
            return message.get('content', '')
        return ""
    
    def _extract_function_calls_from_fireworks_response(self, response_data: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Fireworks API response."""
        if 'choices' in response_data and len(response_data['choices']) > 0:
            message = response_data['choices'][0].get('message', {})
            tool_calls = message.get('tool_calls', [])
            
            if tool_calls:
                function_calls = []
                for tool_call in tool_calls:
                    if tool_call.get('type') == 'function':
                        function_info = tool_call.get('function', {})
                        arguments = function_info.get('arguments', '{}')
                        
                        # Safe JSON parsing with error handling
                        try:
                            if isinstance(arguments, str):
                                parsed_args = json.loads(arguments)
                            else:
                                parsed_args = arguments
                        except (json.JSONDecodeError, TypeError):
                            # If JSON parsing fails, use empty dict
                            parsed_args = {}
                        
                        function_calls.append({
                            'function': function_info.get('name'),
                            'arguments': parsed_args,
                            'id': tool_call.get('id', ''),
                            'result': 'pending'
                        })
                return function_calls
        return None 