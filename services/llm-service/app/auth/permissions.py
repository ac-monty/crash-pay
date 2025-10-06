"""
Permission management and function registry for banking operations.
Implements ABAC (Attribute-Based Access Control) for function calling.
"""

import logging
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timezone

from .models import JWTPayload, UserPermissions, FunctionPermission
from app.utils.logging import get_logger


logger = get_logger(__name__)


class FunctionRegistry:
    """Registry of available functions and their permission requirements."""
    
    def __init__(self):
        self._functions: Dict[str, FunctionPermission] = {}
        self._load_default_functions()
    
    def _load_default_functions(self):
        """Load default banking functions with their permission requirements."""
        
        # Account operations
        self.register_function(FunctionPermission(
            function_name="get_account_balance",
            required_scopes=["banking:read"],
            required_roles=["customer", "advisor", "admin"],
            conditions={
                "verified": True,  # Must be verified
                "region": ["domestic", "international"]  # Any region
            },
            description="Get account balance for checking/savings accounts"
        ))
        
        self.register_function(FunctionPermission(
            function_name="get_transaction_history",
            required_scopes=["banking:read"],
            required_roles=["customer", "advisor", "admin"],
            conditions={
                "verified": True,
                "membership_tier": ["basic", "premium", "director"]
            },
            description="Get recent transaction history"
        ))
        
        # Transfer and payment operations
        self.register_function(FunctionPermission(
            function_name="transfer_funds",
            required_scopes=["banking:write", "transfers:create"],
            required_roles=["customer", "advisor"],
            conditions={
                "verified": True,
                "membership_tier": ["premium", "director"],  # Premium and above only
                "region": ["domestic"]  # Domestic transfers only for now
            },
            description="Transfer funds between accounts"
        ))
        
        # Investment operations
        self.register_function(FunctionPermission(
            function_name="get_portfolio_balance",
            required_scopes=["investments:read"],
            required_roles=["customer", "advisor", "admin"],
            conditions={
                "verified": True,
                "membership_tier": ["premium", "director"]  # Premium features
            },
            description="Get investment portfolio balance and allocation"
        ))
        
        self.register_function(FunctionPermission(
            function_name="place_trade_order",
            required_scopes=["investments:write", "trading:execute"],
            required_roles=["customer", "advisor"],
            conditions={
                "verified": True,
                "membership_tier": ["director"],  # Directors only
                "region": ["domestic"]  # Domestic trading only
            },
            description="Place buy/sell orders for securities"
        ))
        
        # Credit and lending
        self.register_function(FunctionPermission(
            function_name="check_credit_score",
            required_scopes=["credit:read"],
            required_roles=["customer", "advisor", "admin"],
            conditions={
                "verified": True
            },
            description="Check current credit score and history"
        ))
        
        self.register_function(FunctionPermission(
            function_name="apply_for_loan",
            required_scopes=["credit:apply"],
            required_roles=["customer"],
            conditions={
                "verified": True,
                "region": ["domestic"]  # Domestic loans only
            },
            description="Submit loan application"
        ))
        
        # Administrative functions
        self.register_function(FunctionPermission(
            function_name="get_all_customer_accounts",
            required_scopes=["admin:read", "customers:view"],
            required_roles=["advisor", "admin"],
            conditions={
                "verified": True,
                "membership_tier": ["director"]  # Admin access only
            },
            description="Get customer account information (admin only)"
        ))
        
        # Session management functions
        self.register_function(FunctionPermission(
            function_name="trigger_end_session",
            required_scopes=[],  # No specific scopes required
            required_roles=["customer", "advisor", "admin"],  # Available to all authenticated users
            conditions={},  # No additional conditions
            description="Signal that the user wants to end the banking session"
        ))

        # User profile (admin only)
        self.register_function(FunctionPermission(
            function_name="get_user_profile",
            required_scopes=["banking:read"],
            required_roles=["customer", "advisor", "admin"],
            conditions={
                "verified": True,
                "membership_tier": ["premium", "director"]
            },
            description="Fetch basic profile information for the current user (premium/director tiers)"
        ))

        self.register_function(FunctionPermission(
            function_name="list_recipients",
            required_scopes=["banking:read"],
            required_roles=["customer", "advisor", "admin"],
            conditions={"verified": True},
            description="Look up recipient users by name to get their account IDs for transfers"
        ))
    
    def register_function(self, function_permission: FunctionPermission):
        """Register a new function with its permission requirements."""
        self._functions[function_permission.function_name] = function_permission
        logger.info(f"Registered function: {function_permission.function_name}")
    
    def get_function(self, function_name: str) -> Optional[FunctionPermission]:
        """Get function permission definition."""
        return self._functions.get(function_name)
    
    def get_all_functions(self) -> Dict[str, FunctionPermission]:
        """Get all registered functions."""
        return self._functions.copy()
    
    def list_function_names(self) -> List[str]:
        """Get list of all registered function names."""
        return list(self._functions.keys())


class PermissionManager:
    """Manages user permissions and function access using ABAC."""
    
    def __init__(self):
        self.function_registry = FunctionRegistry()
    
    async def resolve_permissions(self, jwt_payload: JWTPayload) -> UserPermissions:
        """
        Resolve user permissions based on JWT payload.
        Determines which functions the user can access.
        """
        # Parse OAuth scopes
        scopes = jwt_payload.scope.split() if jwt_payload.scope else []
        
        # Get user attributes for ABAC
        user_attributes = {
            "membership_tier": jwt_payload.membership_tier,
            "region": jwt_payload.region,
            "verified": jwt_payload.verified,
            "roles": jwt_payload.roles,
            **jwt_payload.attributes
        }
        
        # Determine permitted functions
        permitted_functions = await self._evaluate_function_permissions(
            scopes=scopes,
            roles=jwt_payload.roles,
            attributes=user_attributes
        )
        
        return UserPermissions(
            user_id=jwt_payload.sub,
            scopes=scopes,
            permitted_functions=permitted_functions,
            attributes=user_attributes,
            expires_at=datetime.fromtimestamp(jwt_payload.exp, timezone.utc)
        )
    
    async def _evaluate_function_permissions(
        self, 
        scopes: List[str], 
        roles: List[str], 
        attributes: Dict[str, Any]
    ) -> List[str]:
        """
        Evaluate which functions the user can access based on ABAC rules.
        """
        permitted_functions = []
        scopes_set = set(scopes)
        roles_set = set(roles)
        
        for function_name, function_perm in self.function_registry.get_all_functions().items():
            if self._check_function_access(function_perm, scopes_set, roles_set, attributes):
                permitted_functions.append(function_name)
        
        logger.info(f"User with scopes {scopes} and roles {roles} permitted functions: {permitted_functions}")
        return permitted_functions
    
    def _check_function_access(
        self, 
        function_perm: FunctionPermission,
        user_scopes: Set[str],
        user_roles: Set[str],
        user_attributes: Dict[str, Any]
    ) -> bool:
        """
        Check if user has access to a specific function using ABAC.
        """
        # Check required OAuth scopes
        required_scopes = set(function_perm.required_scopes)
        if required_scopes and not required_scopes.intersection(user_scopes):
            return False
        
        # Check required roles
        required_roles = set(function_perm.required_roles)
        if required_roles and not required_roles.intersection(user_roles):
            return False
        
        # Check ABAC conditions
        for condition_key, condition_value in function_perm.conditions.items():
            user_value = user_attributes.get(condition_key)
            
            if condition_key == "verified":
                # Boolean condition
                if condition_value and not user_value:
                    return False
            elif condition_key in ["membership_tier", "region"]:
                # Array/choice conditions
                if isinstance(condition_value, list):
                    if user_value not in condition_value:
                        return False
                else:
                    if user_value != condition_value:
                        return False
        
        return True
    
    async def check_function_permission(
        self, 
        user_permissions: UserPermissions, 
        function_name: str
    ) -> bool:
        """
        Check if user has permission to call a specific function.
        """
        return function_name in user_permissions.permitted_functions
    
    def get_available_functions_for_user(
        self, 
        user_permissions: UserPermissions
    ) -> List[Dict[str, Any]]:
        """
        Get list of available functions with descriptions for a user.
        """
        available_functions = []
        
        for function_name in user_permissions.permitted_functions:
            function_perm = self.function_registry.get_function(function_name)
            if function_perm:
                available_functions.append({
                    "name": function_name,
                    "description": function_perm.description,
                    "required_scopes": function_perm.required_scopes,
                    "conditions": function_perm.conditions
                })
        
        return available_functions 