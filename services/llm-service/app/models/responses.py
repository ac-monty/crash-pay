"""
Response models for the LLM service API.
Pydantic models for API responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ProviderInfo(BaseModel):
    """Information about the current LLM provider."""
    current_provider: str
    current_model: str
    available_providers: List[str]
    temperature: float
    max_tokens: int
    streaming: bool


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    response: str
    provider: str
    model: str
    function_calls: Optional[List[Dict[str, Any]]] = None
    request_id: Optional[str] = None
    total_time: Optional[float] = None


class ModelSwitchResponse(BaseModel):
    """Response from model switching operations."""
    success: bool
    message: str
    previous_provider: Optional[str] = None
    previous_model: Optional[str] = None
    new_provider: str
    new_model: str


class ModelListResponse(BaseModel):
    """Response containing available models."""
    current_provider: str
    current_model: str
    connection_mode: str
    available_models: Dict[str, Dict[str, Any]]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    provider: str
    model: str
    connection_mode: str
    timestamp: str
    response_time_ms: float
    test_response: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    error_type: str
    provider: Optional[str] = None
    model: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: str


class AssistantResponse(BaseModel):
    """Response from assistant operations."""
    id: str
    object: str
    created_at: int
    name: str
    description: Optional[str] = None
    model: str
    instructions: str
    tools: List[dict] = []
    file_ids: List[str] = []


class ThreadResponse(BaseModel):
    """Response from thread operations."""
    id: str
    object: str
    created_at: int
    metadata: Dict[str, Any] = {}


class RunResponse(BaseModel):
    """Response from run operations."""
    id: str
    object: str
    created_at: int
    assistant_id: str
    thread_id: str
    status: str
    required_action: Optional[Dict[str, Any]] = None
    last_error: Optional[Dict[str, Any]] = None
    expires_at: Optional[int] = None
    started_at: Optional[int] = None
    cancelled_at: Optional[int] = None
    failed_at: Optional[int] = None
    completed_at: Optional[int] = None


class SystemPromptResponse(BaseModel):
    """System prompt configuration response."""
    system_prompt_enabled: bool
    content_filter_enabled: bool
    max_response_tokens: int
    current_prompt: Optional[str] = None


class AssistantThreadResponse(BaseModel):
    """Response for assistant thread operations."""
    thread_id: str
    user_id: str
    created_at: Optional[str] = None


class AssistantMessageResponse(BaseModel):
    """Response for assistant message operations."""
    response: str
    thread_id: str
    run_id: str
    function_calls: Optional[List[Dict[str, Any]]] = None


class LogsResponse(BaseModel):
    """Response for recent logs."""
    logs: List[str]
    count: int


class StatsResponse(BaseModel):
    """Service statistics response."""
    provider: str
    model: str
    uptime_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time: float
    error_rate: float


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None 