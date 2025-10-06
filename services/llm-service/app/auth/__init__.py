"""
Authentication and authorization module for the LLM service.
Handles JWT validation, OAuth scopes, and function permissions.
"""

from .middleware import JWTAuthMiddleware, get_current_user
from .permissions import PermissionManager, FunctionRegistry
from .models import JWTPayload, UserPermissions

__all__ = [
    "JWTAuthMiddleware",
    "get_current_user", 
    "PermissionManager",
    "FunctionRegistry",
    "JWTPayload",
    "UserPermissions"
] 