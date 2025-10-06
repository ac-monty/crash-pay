#!/usr/bin/env python3
"""
Simple test script to verify the authentication system works.
"""

import asyncio
import sys
sys.path.append('.')

from ..app.auth.permissions import PermissionManager, FunctionRegistry
from ..app.auth.models import JWTPayload


async def test_permission_system():
    """Test the permission system with different user scenarios."""
    print("Testing Authentication & Authorization System")
    print("=" * 50)
    
    # Initialize permission manager
    permission_manager = PermissionManager()
    
    # Test scenarios
    scenarios = [
        {
            "name": "Basic Customer",
            "payload": JWTPayload(
                sub="user_basic_001",
                exp=1000000000,
                iat=999999999,
                scope="banking:read",
                roles=["customer"],
                membership_tier="basic",
                region="domestic",
                verified=True
            )
        },
        {
            "name": "Premium Customer", 
            "payload": JWTPayload(
                sub="user_premium_002",
                exp=1000000000,
                iat=999999999,
                scope="banking:read banking:write transfers:create",
                roles=["customer"],
                membership_tier="premium",
                region="domestic",
                verified=True
            )
        },
        {
            "name": "Unverified Customer",
            "payload": JWTPayload(
                sub="user_unverified_003",
                exp=1000000000,
                iat=999999999,
                scope="banking:read",
                roles=["customer"],
                membership_tier="basic",
                region="domestic",
                verified=False
            )
        },
        {
            "name": "International Customer",
            "payload": JWTPayload(
                sub="user_intl_004",
                exp=1000000000,
                iat=999999999,
                scope="banking:read banking:write transfers:create",
                roles=["customer"],
                membership_tier="premium",
                region="international",
                verified=True
            )
        }
    ]
    
    for scenario in scenarios:
        print(f"\n{scenario['name']}:")
        print("-" * 30)
        
        # Resolve permissions
        user_permissions = await permission_manager.resolve_permissions(scenario["payload"])
        
        print(f"User ID: {user_permissions.user_id}")
        print(f"Scopes: {user_permissions.scopes}")
        print(f"Permitted Functions: {user_permissions.permitted_functions}")
        
        # Test specific function checks
        can_transfer = await permission_manager.check_function_permission(
            user_permissions, "transfer_funds"
        )
        can_trade = await permission_manager.check_function_permission(
            user_permissions, "place_trade_order"
        )
        can_check_balance = await permission_manager.check_function_permission(
            user_permissions, "get_account_balance"
        )
        
        print(f"Can transfer funds: {can_transfer}")
        print(f"Can trade: {can_trade}")
        print(f"Can check balance: {can_check_balance}")
    
    # Test function registry
    print(f"\nFunction Registry Test:")
    print("-" * 30)
    function_registry = FunctionRegistry()
    all_functions = function_registry.list_function_names()
    print(f"Registered functions: {all_functions}")
    
    # Test function details
    transfer_function = function_registry.get_function("transfer_funds")
    if transfer_function:
        print(f"\nTransfer function details:")
        print(f"  Required scopes: {transfer_function.required_scopes}")
        print(f"  Required roles: {transfer_function.required_roles}")
        print(f"  Conditions: {transfer_function.conditions}")
        print(f"  Description: {transfer_function.description}")
    
    print("\n✅ Authentication system test completed!")


if __name__ == "__main__":
    asyncio.run(test_permission_system()) 