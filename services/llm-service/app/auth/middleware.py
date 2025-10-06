"""
JWT Authentication middleware and dependency injection.
"""

import jwt
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone

from .models import JWTPayload, UserPermissions, AuthenticationResult
from .permissions import PermissionManager
from app.config.settings import get_settings
from app.utils.logging import get_service_logger, log_security_event, performance_monitor, get_logger


logger = get_logger(__name__)
security = HTTPBearer()
service_logger = get_service_logger('auth_middleware')


class JWTAuthMiddleware:
    """JWT authentication middleware for validating and parsing tokens."""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.permission_manager = PermissionManager()
        
        service_logger.info("JWT Auth Middleware initialized",
                          algorithm=algorithm)
    
    @performance_monitor("auth.validate_token")
    async def validate_token(self, token: str) -> AuthenticationResult:
        """
        Validate JWT token and return authentication result with comprehensive security logging.
        """
        # Truncate token for logging (security)
        token_preview = token[:10] + "..." if len(token) > 10 else token
        
        service_logger.debug("Token validation started",
                           token_preview=token_preview,
                           token_length=len(token))
        
        try:
            # Get settings for audience validation
            settings = get_settings()
            
            with service_logger.performance_context("jwt_decode"):
                # Decode JWT token with audience validation
                payload = jwt.decode(
                    token, 
                    self.secret_key, 
                    algorithms=[self.algorithm],
                    audience=settings.oauth_audience,
                    options={"verify_exp": True}
                )
            
            # Parse into Pydantic model
            with service_logger.performance_context("payload_parsing"):
                jwt_payload = JWTPayload(**payload)
            
            service_logger.debug("JWT decoded successfully",
                               user_id=jwt_payload.sub,
                               scopes=jwt_payload.scope,
                               roles=jwt_payload.roles,
                               expires_at=jwt_payload.exp,
                               verified=jwt_payload.verified,
                               membership_tier=jwt_payload.membership_tier)
            
            # Check expiration
            current_time = datetime.now(timezone.utc).timestamp()
            if jwt_payload.exp < current_time:
                log_security_event("warning", "Expired token used",
                                 user_id=jwt_payload.sub,
                                 expired_at=jwt_payload.exp,
                                 current_time=current_time,
                                 token_preview=token_preview)
                
                service_logger.warning("Token expired",
                                     user_id=jwt_payload.sub,
                                     expired_at=jwt_payload.exp)
                
                return AuthenticationResult(
                    success=False,
                    error_message="Token expired",
                    status_code=401
                )
            
            # Resolve or accept pre-computed permitted functions
            if jwt_payload.permitted_functions:
                # Use functions embedded in token (issuer already computed)
                user_permissions = UserPermissions(
                    user_id=jwt_payload.sub,
                    scopes=jwt_payload.scope.split() if jwt_payload.scope else [],
                    permitted_functions=jwt_payload.permitted_functions,
                    attributes=jwt_payload.attributes or {},
                    expires_at=datetime.fromtimestamp(jwt_payload.exp, timezone.utc)
                )
                service_logger.info(
                    "Permissions sourced from JWT claim", user_id=jwt_payload.sub,
                    function_count=len(jwt_payload.permitted_functions)
                )
            else:
                # Fallback to dynamic resolution
                with service_logger.performance_context("permission_resolution", user_id=jwt_payload.sub):
                    user_permissions = await self.permission_manager.resolve_permissions(jwt_payload)
            
            # Security logging for successful authentication
            log_security_event("info", "User authenticated successfully",
                             user_id=jwt_payload.sub,
                             scopes=jwt_payload.scope,
                             roles=jwt_payload.roles,
                             permitted_functions=user_permissions.permitted_functions,
                             verified=jwt_payload.verified,
                             membership_tier=jwt_payload.membership_tier)
            
            service_logger.info("Authentication successful",
                              user_id=jwt_payload.sub,
                              function_count=len(user_permissions.permitted_functions),
                              expires_at=jwt_payload.exp,
                              verified=jwt_payload.verified)
            
            return AuthenticationResult(
                success=True,
                user_permissions=user_permissions
            )
            
        except jwt.ExpiredSignatureError:
            log_security_event("warning", "Expired JWT signature",
                             token_preview=token_preview,
                             error_type="ExpiredSignatureError")
            
            service_logger.warning("Token signature expired", 
                                 token_preview=token_preview)
            
            return AuthenticationResult(
                success=False,
                error_message="Token expired",
                status_code=401
            )
        except jwt.InvalidTokenError as e:
            log_security_event("warning", "Invalid JWT token",
                             token_preview=token_preview,
                             error_type="InvalidTokenError",
                             error_details=str(e))
            
            service_logger.warning("Invalid token",
                                 token_preview=token_preview,
                                 error=str(e))
            
            return AuthenticationResult(
                success=False,
                error_message=f"Invalid token: {str(e)}",
                status_code=401
            )
        except Exception as e:
            log_security_event("error", "Authentication system error",
                             token_preview=token_preview,
                             error_type=type(e).__name__,
                             error_details=str(e))
            
            service_logger.error("Authentication system error",
                                error=e,
                                token_preview=token_preview)
            
            return AuthenticationResult(
                success=False,
                error_message="Authentication failed",
                status_code=500
            )


# Global middleware instance
_auth_middleware: Optional[JWTAuthMiddleware] = None


def get_auth_middleware() -> JWTAuthMiddleware:
    """Get or create the global authentication middleware."""
    global _auth_middleware
    if _auth_middleware is None:
        settings = get_settings()
        # In production, get this from environment variables
        secret_key = settings.jwt_secret
        _auth_middleware = JWTAuthMiddleware(secret_key)
    return _auth_middleware


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserPermissions:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage in routes:
    @router.post("/protected-endpoint")
    async def protected_route(user: UserPermissions = Depends(get_current_user)):
        # user.permitted_functions contains what the user can access
        pass
    """
    auth_middleware = get_auth_middleware()
    
    result = await auth_middleware.validate_token(credentials.credentials)
    
    if not result.success:
        raise HTTPException(
            status_code=result.status_code,
            detail=result.error_message
        )
    
    return result.user_permissions


async def get_optional_user(
    request: Request
) -> Optional[UserPermissions]:
    """
    Optional authentication - returns None if no token provided.
    Used for endpoints that work with or without authentication.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    auth_middleware = get_auth_middleware()
    
    result = await auth_middleware.validate_token(token)
    
    if result.success:
        return result.user_permissions
    
    # Log warning but don't fail
    logger.warning(f"Optional auth failed: {result.error_message}")
    return None 