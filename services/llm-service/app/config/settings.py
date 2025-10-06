"""
Configuration settings for the LLM service.
Centralized settings management with environment variable support.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings
from app.utils.singleton import singleton_factory


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Basic LLM Configuration
    llm_provider: str = Field(default="openai", env="LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4.1-nano-2025-04-14", env="LLM_MODEL")
    llm_streaming: bool = Field(default=False, env="LLM_STREAMING")
    llm_connection_mode: str = Field(default="langchain", env="LLM_CONNECTION_MODE")
    llm_enable_true_streaming: bool = Field(default=True, env="LLM_ENABLE_TRUE_STREAMING")
    
    # System Prompt and Safety Configuration
    system_prompt_enabled: bool = Field(default=True, env="SYSTEM_PROMPT_ENABLED")
    content_filter_enabled: bool = Field(default=True, env="CONTENT_FILTER_ENABLED")
    max_response_tokens: int = Field(default=4096, env="MAX_RESPONSE_TOKENS")
    # RAG controls
    rag_max_context_chars: int = Field(default=2000, env="RAG_MAX_CONTEXT_CHARS")
    rag_context_role: str = Field(default="user", env="RAG_CONTEXT_ROLE")  # user or system
    
    # Debug and Logging Configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug_mode: bool = Field(default=True, env="DEBUG_MODE")  # For red teaming, default to True
    log_api_requests: bool = Field(default=True, env="LOG_API_REQUESTS")
    log_api_responses: bool = Field(default=True, env="LOG_API_RESPONSES")
    log_system_prompts: bool = Field(default=True, env="LOG_SYSTEM_PROMPTS")
    
    # Enhanced Logging Controls
    log_performance: bool = Field(default=True, env="LOG_PERFORMANCE")
    log_security_events: bool = Field(default=True, env="LOG_SECURITY_EVENTS")
    log_function_calls: bool = Field(default=True, env="LOG_FUNCTION_CALLS")
    log_service_debug: bool = Field(default=True, env="LOG_SERVICE_DEBUG")
    log_error_context: bool = Field(default=True, env="LOG_ERROR_CONTEXT")
    
    # Log Management
    max_log_file_lines: int = Field(default=10000, env="MAX_LOG_FILE_LINES")
    log_cleanup_enabled: bool = Field(default=True, env="LOG_CLEANUP_ENABLED")
    verbose_error_logging: bool = Field(default=True, env="VERBOSE_ERROR_LOGGING")
    log_request_ids: bool = Field(default=True, env="LOG_REQUEST_IDS")
    
    # Performance Monitoring
    performance_monitoring_enabled: bool = Field(default=True, env="PERFORMANCE_MONITORING_ENABLED")
    slow_request_threshold: float = Field(default=5.0, env="SLOW_REQUEST_THRESHOLD")  # seconds
    log_performance_counters: bool = Field(default=True, env="LOG_PERFORMANCE_COUNTERS")
    
    # Authentication and Authorization (NEW)
    jwt_secret: str = Field(default="super-secret-not-safe", env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expires_in: str = Field(default="30d", env="JWT_EXPIRES_IN")
    
    # MongoDB for chat memory
    mongo_uri: str = Field(default="mongodb://mongo:27017/fakefintech", env="MONGO_URI")
    
    # OAuth/OIDC Configuration
    oauth_issuer: Optional[str] = Field(default=None, env="OAUTH_ISSUER")
    oauth_audience: Optional[str] = Field(default=None, env="OAUTH_AUDIENCE")
    jwks_url: Optional[str] = Field(default=None, env="JWKS_URL")
    
    # Authorization settings
    enable_function_permissions: bool = Field(default=True, env="ENABLE_FUNCTION_PERMISSIONS")
    default_user_role: str = Field(default="customer", env="DEFAULT_USER_ROLE")
    require_verified_users: bool = Field(default=True, env="REQUIRE_VERIFIED_USERS")
    
    @field_validator('llm_streaming', 'llm_enable_true_streaming', 'system_prompt_enabled', 'content_filter_enabled', 
                     'enable_function_permissions', 'require_verified_users', 'log_performance', 'log_security_events',
                     'log_function_calls', 'log_service_debug', 'log_error_context', 'log_cleanup_enabled',
                     'verbose_error_logging', 'log_request_ids', 'performance_monitoring_enabled', 
                     'log_performance_counters', mode='before')
    @classmethod
    def parse_bool_with_comments(cls, v):
        """Parse boolean values that might have comments in .env files"""
        if isinstance(v, str):
            # Remove comments and whitespace
            v = v.split('#')[0].strip().lower()
            if v in ('true', '1', 'yes', 'on'):
                return True
            elif v in ('false', '0', 'no', 'off'):
                return False
            else:
                raise ValueError(f"Cannot parse boolean value: {v}")
        return v

    @field_validator('max_response_tokens', 'max_log_file_lines', mode='before')
    @classmethod
    def parse_int_with_comments(cls, v):
        """Parse integer values that might have comments in .env files"""
        if isinstance(v, str):
            # Remove comments and whitespace
            v = v.split('#')[0].strip()
            try:
                return int(v)
            except ValueError:
                raise ValueError(f"Cannot parse integer value: {v}")
        return v

    @field_validator('slow_request_threshold', mode='before')
    @classmethod
    def parse_float_with_comments(cls, v):
        """Parse float values that might have comments in .env files"""
        if isinstance(v, str):
            # Remove comments and whitespace
            v = v.split('#')[0].strip()
            try:
                return float(v)
            except ValueError:
                raise ValueError(f"Cannot parse float value: {v}")
        return v

    @field_validator('openai_api_key', 'anthropic_api_key', 'google_api_key', 'cohere_api_key', 
                     'mistral_api_key', 'azure_openai_api_key', 'together_api_key', 
                     'replicate_api_token', 'huggingface_api_token', 'perplexity_api_key', 
                     'fireworks_api_key', mode='before')
    @classmethod
    def strip_comments_from_api_keys(cls, v):
        """Strip comments from API keys that might have comments in .env files"""
        if isinstance(v, str):
            # Remove comments and whitespace
            return v.split('#')[0].strip()
        return v
    
    # Provider API Keys
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_org_id: Optional[str] = Field(default=None, env="OPENAI_ORG_ID")
    anthropic_api_key: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    google_api_key: Optional[str] = Field(default=None, env="GOOGLE_API_KEY")
    cohere_api_key: Optional[str] = Field(default=None, env="COHERE_API_KEY")
    mistral_api_key: Optional[str] = Field(default=None, env="MISTRAL_API_KEY")
    azure_openai_api_key: Optional[str] = Field(default=None, env="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, env="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(default="2024-02-15-preview", env="AZURE_OPENAI_API_VERSION")
    azure_openai_deployment_name: Optional[str] = Field(default=None, env="AZURE_OPENAI_DEPLOYMENT_NAME")
    together_api_key: Optional[str] = Field(default=None, env="TOGETHER_API_KEY")
    replicate_api_token: Optional[str] = Field(default=None, env="REPLICATE_API_TOKEN")
    huggingface_api_token: Optional[str] = Field(default=None, env="HUGGINGFACE_API_TOKEN")
    perplexity_api_key: Optional[str] = Field(default=None, env="PERPLEXITY_API_KEY")
    fireworks_api_key: Optional[str] = Field(default=None, env="FIREWORKS_API_KEY")
    
    # Special parameters for reasoning models
    llm_reasoning_effort: str = Field(default="medium", env="LLM_REASONING_EFFORT")
    
    # Service URLs
    tools_service_url: str = Field(default="http://tools-service:8000", env="TOOLS_SERVICE_URL")
    rag_service_url: str = Field(default="http://rag-service:8001", env="RAG_SERVICE_URL")
    # Finance service (internal) base URL for FunctionExecutor
    finance_service_url: str = Field(default="http://finance-service:4002", env="FINANCE_SERVICE_URL")
    
    # APM Configuration
    elastic_apm_service_name: str = Field(default="llm-service", env="ELASTIC_APM_SERVICE_NAME")
    elastic_apm_server_url: str = Field(default="http://localhost:8200", env="ELASTIC_APM_SERVER_URL")
    elastic_apm_environment: str = Field(default="development", env="ELASTIC_APM_ENVIRONMENT")
    elastic_apm_verify_server_cert: bool = Field(default=False, env="ELASTIC_APM_VERIFY_SERVER_CERT")
    
    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra environment variables


@singleton_factory
def get_settings() -> Settings:
    """Get the global settings instance (singleton pattern)."""
    return Settings()


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = Settings()
    return _settings


# For backward compatibility
settings = get_settings() 