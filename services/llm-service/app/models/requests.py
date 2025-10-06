"""
Request models for the LLM service API.
Pydantic models for validating incoming requests.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Individual message in a conversation."""
    role: str = Field(pattern="^(user|system|assistant|tool)$")
    content: str


class Function(BaseModel):
    """Function definition for function calling."""
    name: str
    description: str
    parameters: dict


class UserContext(BaseModel):
    """User context extracted from JWT token."""
    user_id: str
    permissions: List[str] = Field(default=[], description="OAuth scopes/permissions")
    roles: List[str] = Field(default=[], description="User roles")
    attributes: Dict[str, Any] = Field(default={}, description="User attributes (region, tier, etc)")
    permitted_functions: List[str] = Field(default=[], description="Functions user can access")


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""
    messages: Optional[List[Message]] = Field(
        None, description="Full message history. If omitted, `prompt` must be provided."
    )
    prompt: Optional[str] = Field(
        None, description="Single-shot prompt if `messages` not supplied."
    )
    use_rag: bool = Field(
        default=False, description="If true, augment with vector retrieval context."
    )
    use_functions: bool = Field(
        default=False, description="If true, enable function calling for intent detection."
    )
    functions: Optional[List[Function]] = Field(
        default=None, description="Available functions for the LLM to call."
    )
    stream: Optional[bool] = Field(
        default=None, description="If true, return streaming response. If None, use default setting."
    )
    temperature: Optional[float] = Field(
        default=None, ge=0.0, le=2.0, description="Sampling temperature (0-2)."
    )
    max_tokens: Optional[int] = Field(
        default=None, ge=1, le=4096, description="Maximum tokens in response."
    )
    reasoning_effort: Optional[str] = Field(
        default=None, description="Reasoning effort level for reasoning models (e.g., 'low', 'medium', 'high')."
    )

    session_id: Optional[str] = Field(
        default=None,
        description="Conversation thread identifier for memory management"
    )

    # NEW: User context (populated by middleware)
    user_context: Optional[UserContext] = Field(
        default=None, description="User context from authentication"
    )


class AuthenticatedChatRequest(BaseModel):
    """Production chat request with OAuth-based authentication."""
    prompt: Optional[str] = Field(
        None, description="Natural language user request"
    )
    user_id: str = Field(description="User identifier from JWT")
    permitted_functions: List[str] = Field(
        default=[], description="Functions this user can access"
    )
    user_attributes: Dict[str, Any] = Field(
        default={}, description="User attributes for ABAC (region, tier, verified, etc)"
    )
    session_id: Optional[str] = Field(
        default=None, description="Conversation thread identifier for memory management"
    )
    use_rag: bool = Field(
        default=True, description="If true, augment with vector retrieval context from knowledge base"
    )
    stream: bool = Field(default=False)
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, ge=1, le=4096)


class SystemPromptRequest(BaseModel):
    """Request model for updating system prompt."""
    system_prompt: str
    enabled: bool = True
    content_filter_enabled: bool = True


class ModelSwitchRequest(BaseModel):
    """Request model for switching models."""
    provider: str
    model: str
    should_validate: bool = True


class AssistantThreadRequest(BaseModel):
    """Request model for creating assistant threads."""
    user_id: str = "default"


class AssistantMessageRequest(BaseModel):
    """Request model for sending assistant messages."""
    thread_id: str
    message: str
    user_id: str = "default" 