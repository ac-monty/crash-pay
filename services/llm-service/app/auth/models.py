"""
Authentication models for JWT handling and permission management.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class JWTPayload(BaseModel):
    """JWT token payload structure."""
    sub: str = Field(description="Subject (user ID)")
    exp: int = Field(description="Expiration timestamp")
    iat: int = Field(description="Issued at timestamp")
    scope: str = Field(default="", description="OAuth scopes separated by spaces")
    aud: Optional[str] = Field(default=None, description="Audience")
    iss: Optional[str] = Field(default=None, description="Issuer")
    
    # Custom claims for banking context
    roles: List[str] = Field(default=[], description="User roles")
    permissions: List[str] = Field(default=[], description="Explicit permissions")
    attributes: Dict[str, Any] = Field(default={}, description="User attributes")
    
    # Banking-specific attributes
    membership_tier: Optional[str] = Field(default=None, description="Customer tier (basic, premium, director)")
    region: Optional[str] = Field(default=None, description="User region (domestic, international)")
    verified: bool = Field(default=False, description="User verification status")

    # New claim: list of function names permitted for the user. Short alias 'fxn' to keep token small.
    permitted_functions: List[str] = Field(
        default_factory=list,
        alias="fxn",
        description="Function names the user is allowed to invoke (embedded by issuer)"
    )


class UserPermissions(BaseModel):
    """Resolved user permissions for function calling."""
    user_id: str
    scopes: List[str] = Field(default=[], description="OAuth scopes")
    permitted_functions: List[str] = Field(default=[], description="Functions user can call")
    denied_functions: List[str] = Field(default=[], description="Explicitly denied functions")
    attributes: Dict[str, Any] = Field(default={}, description="User attributes for ABAC")
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    expires_at: Optional[datetime] = Field(default=None, description="Permission expiration")


class FunctionPermission(BaseModel):
    """Function permission definition."""
    function_name: str
    required_scopes: List[str] = Field(default=[], description="Required OAuth scopes")
    required_roles: List[str] = Field(default=[], description="Required user roles")
    conditions: Dict[str, Any] = Field(default={}, description="ABAC conditions")
    description: str = Field(default="", description="Human-readable description")


class AuthenticationResult(BaseModel):
    """Result of authentication validation."""
    success: bool
    user_permissions: Optional[UserPermissions] = None
    error_message: Optional[str] = None
    status_code: int = 200 