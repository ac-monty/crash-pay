"""
Base provider interface for LLM providers.
Defines the contract that all LLM providers must implement.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from enum import Enum
from app.config.registry_loader import get_model_mappings, get_api_model_name, is_reasoning_model


class ConnectionMode(Enum):
    """Supported connection modes."""
    DIRECT = "direct"
    LANGCHAIN = "langchain"


class ProviderCapabilities:
    """Provider capabilities metadata."""
    
    def __init__(
        self,
        supports_streaming: bool = True,
        supports_function_calling: bool = False,
        supports_system_prompts: bool = True,
        supports_reasoning: bool = False,
        max_context_length: int = 4096,
        supports_images: bool = False,
        supports_audio: bool = False,
        # Tool schema used for function calling follow-up messages.
        #   "openai"      -> OpenAI-style assistant+tool messages
        #   "anthropic"   -> Claude-style tool_results array
        #   "text"        -> No strict schema, results embedded in plain text
        tool_schema: str = "text"
    ):
        self.supports_streaming = supports_streaming
        self.supports_function_calling = supports_function_calling
        self.supports_system_prompts = supports_system_prompts
        self.supports_reasoning = supports_reasoning
        self.max_context_length = max_context_length
        self.supports_images = supports_images
        self.supports_audio = supports_audio
        self.tool_schema = tool_schema


class BaseLLMProvider(ABC):
    """Abstract base class for all LLM providers."""
    
    def __init__(self, model: str, api_key: str, **kwargs):
        self.model = model
        self.api_key = api_key
        self.connection_mode = kwargs.get('connection_mode', ConnectionMode.LANGCHAIN)
        self.extra_config = kwargs
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic')."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return the capabilities of this provider."""
        pass
    
    @abstractmethod
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> str:
        """
        Send a chat request and return the response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Returns:
            The response content as a string
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Send a chat request and return a streaming response.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
            
        Yields:
            Response chunks as strings
        """
        pass
    
    @abstractmethod
    async def chat_with_functions(
        self,
        messages: List[Dict[str, str]],
        functions: List[Dict[str, Any]],
        **kwargs
    ) -> tuple[str, Optional[List[Dict[str, Any]]]]:
        """
        Send a chat request with function calling capability.
        
        Args:
            messages: List of message dictionaries
            functions: List of function definitions
            **kwargs: Additional parameters
            
        Returns:
            Tuple of (response_content, function_calls)
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Dict[str, Any]:
        """
        Test the connection to the provider.
        
        Returns:
            Dictionary with test results and connection status
        """
        pass
    
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        return bool(self.api_key and self.model)
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": self.provider_name,
            "model": self.model,
            "connection_mode": self.connection_mode.value,
            "capabilities": {
                "streaming": self.capabilities.supports_streaming,
                "function_calling": self.capabilities.supports_function_calling,
                "system_prompts": self.capabilities.supports_system_prompts,
                "reasoning": self.capabilities.supports_reasoning,
                "max_context": self.capabilities.max_context_length,
                "images": self.capabilities.supports_images,
                "audio": self.capabilities.supports_audio
            }
        }
    
    def is_reasoning_model(self, model_name: str = None) -> bool:
        """Check if the model is a reasoning model."""
        model_to_check = model_name or self.model
        return is_reasoning_model(self.provider_name, model_to_check)


class ProviderError(Exception):
    """Base exception for provider-related errors."""
    
    def __init__(self, message: str, provider: str, model: str, error_code: str = None):
        self.provider = provider
        self.model = model
        self.error_code = error_code
        super().__init__(f"[{provider}/{model}] {message}")


class ProviderAuthenticationError(ProviderError):
    """Raised when authentication fails."""
    pass


class ProviderRateLimitError(ProviderError):
    """Raised when rate limits are exceeded."""
    pass


class ProviderModelNotFoundError(ProviderError):
    """Raised when the specified model is not found."""
    pass


class ProviderConnectionError(ProviderError):
    """Raised when connection to provider fails."""
    pass 