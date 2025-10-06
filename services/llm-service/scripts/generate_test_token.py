#!/usr/bin/env python3
"""
Utility script to generate test JWT tokens for different user scenarios.
Use this to test the authentication and authorization system.
"""

import jwt
import json
import argparse
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List


def parse_expires_in(expires_in: str) -> timedelta:
    """
    Parse duration string like '30d', '24h', '60m', '3600s' into timedelta.
    """
    if not expires_in:
        return timedelta(days=30)  # default
    
    # Match pattern like '30d', '24h', '60m', '3600s'
    pattern = r'^(\d+)([dhms])$'
    match = re.match(pattern, expires_in.lower())
    
    if not match:
        # If no unit specified, assume days
        try:
            days = int(expires_in)
            return timedelta(days=days)
        except ValueError:
            return timedelta(days=30)  # fallback
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'd':
        return timedelta(days=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 's':
        return timedelta(seconds=value)
    else:
        return timedelta(days=30)  # fallback


def generate_test_token(
    user_id: str,
    scopes: List[str],
    roles: List[str],
    membership_tier: str = "basic",
    region: str = "domestic",
    verified: bool = True,
    expires_in: str = "30d",
    secret_key: str = "super-secret-not-safe"
) -> str:
    """Generate a JWT token for testing purposes."""
    
    now = datetime.now(timezone.utc)
    expiry_delta = parse_expires_in(expires_in)
    exp = now + expiry_delta
    
    payload = {
        "sub": user_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "scope": " ".join(scopes),
        "aud": "llm-service",
        "iss": "test-issuer",
        "roles": roles,
        "permissions": scopes,
        "membership_tier": membership_tier,
        "region": region,
        "verified": verified,
        "attributes": {
            "test_user": True,
            "generated_at": now.isoformat()
        }
    }
    
    token = jwt.encode(payload, secret_key, algorithm="HS256")
    return token


def get_user_scenarios() -> Dict[str, Dict[str, Any]]:
    """Define different user scenarios for testing."""
    return {
        "basic_customer": {
            "user_id": "user_basic_001",
            "scopes": ["banking:read"],
            "roles": ["customer"],
            "membership_tier": "basic",
            "region": "domestic",
            "verified": True,
            "description": "Basic verified customer - can read account balance and transactions"
        },
        "premium_customer": {
            "user_id": "user_premium_002", 
            "scopes": ["banking:read", "banking:write", "investments:read", "transfers:create"],
            "roles": ["customer"],
            "membership_tier": "premium",
            "region": "domestic",
            "verified": True,
            "description": "Premium customer - can transfer funds and view investments"
        },
        "director_customer": {
            "user_id": "user_director_003",
            "scopes": ["banking:read", "banking:write", "investments:read", "investments:write", 
                      "trading:execute", "transfers:create", "credit:read", "credit:apply"],
            "roles": ["customer"],
            "membership_tier": "director",
            "region": "domestic", 
            "verified": True,
            "description": "Director-level customer - full access including trading"
        },
        "international_customer": {
            "user_id": "user_intl_004",
            "scopes": ["banking:read", "investments:read"],
            "roles": ["customer"],
            "membership_tier": "premium",
            "region": "international",
            "verified": True,
            "description": "International customer - limited to read operations"
        },
        "unverified_customer": {
            "user_id": "user_unverified_005",
            "scopes": ["banking:read"],
            "roles": ["customer"],
            "membership_tier": "basic",
            "region": "domestic",
            "verified": False,
            "description": "Unverified customer - should have no function access"
        },
        "bank_advisor": {
            "user_id": "advisor_001",
            "scopes": ["banking:read", "banking:write", "investments:read", "investments:write",
                      "credit:read", "customers:view"],
            "roles": ["advisor"],
            "membership_tier": "director",
            "region": "domestic",
            "verified": True,
            "description": "Bank advisor - can help customers with most operations"
        },
        "bank_admin": {
            "user_id": "admin_001",
            "scopes": ["banking:read", "banking:write", "investments:read", "investments:write",
                      "credit:read", "admin:read", "customers:view"],
            "roles": ["admin"],
            "membership_tier": "director", 
            "region": "domestic",
            "verified": True,
            "description": "Bank administrator - full access to all functions"
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Generate test JWT tokens for LLM service authentication")
    parser.add_argument("--scenario", type=str, help="User scenario to generate token for")
    parser.add_argument("--list-scenarios", action="store_true", help="List available user scenarios")
    parser.add_argument("--custom", action="store_true", help="Generate custom token")
    parser.add_argument("--user-id", type=str, help="Custom user ID")
    parser.add_argument("--scopes", type=str, help="Custom scopes (comma-separated)")
    parser.add_argument("--roles", type=str, help="Custom roles (comma-separated)")
    parser.add_argument("--tier", type=str, default="basic", help="Membership tier")
    parser.add_argument("--region", type=str, default="domestic", help="User region")
    parser.add_argument("--verified", action="store_true", default=True, help="User verification status")
    parser.add_argument("--secret", type=str, default="super-secret-not-safe", help="JWT secret key")
    parser.add_argument("--expires-in", type=str, default="30d", help="Token expiry (e.g., '30d', '24h', '60m')")
    
    args = parser.parse_args()
    
    scenarios = get_user_scenarios()
    
    if args.list_scenarios:
        print("\nAvailable user scenarios:")
        print("=" * 50)
        for name, scenario in scenarios.items():
            print(f"\n{name.upper()}:")
            print(f"  Description: {scenario['description']}")
            print(f"  User ID: {scenario['user_id']}")
            print(f"  Scopes: {', '.join(scenario['scopes'])}")
            print(f"  Roles: {', '.join(scenario['roles'])}")
            print(f"  Tier: {scenario['membership_tier']}")
            print(f"  Region: {scenario['region']}")
            print(f"  Verified: {scenario['verified']}")
        return
    
    if args.custom:
        if not all([args.user_id, args.scopes, args.roles]):
            print("Custom token requires --user-id, --scopes, and --roles")
            return
        
        token = generate_test_token(
            user_id=args.user_id,
            scopes=args.scopes.split(","),
            roles=args.roles.split(","),
            membership_tier=args.tier,
            region=args.region,
            verified=args.verified,
            expires_in=args.expires_in,
            secret_key=args.secret
        )
        
        print(f"\nGenerated custom token for {args.user_id}:")
        print(f"Expires in: {args.expires_in}")
        print(f"Token: {token}")
        return
    
    if args.scenario:
        if args.scenario not in scenarios:
            print(f"Unknown scenario: {args.scenario}")
            print(f"Available scenarios: {', '.join(scenarios.keys())}")
            return
        
        scenario = scenarios[args.scenario]
        token = generate_test_token(
            user_id=scenario["user_id"],
            scopes=scenario["scopes"],
            roles=scenario["roles"],
            membership_tier=scenario["membership_tier"],
            region=scenario["region"],
            verified=scenario["verified"],
            expires_in=args.expires_in,
            secret_key=args.secret
        )
        
        print(f"\nGenerated token for scenario: {args.scenario}")
        print(f"Description: {scenario['description']}")
        print(f"User ID: {scenario['user_id']}")
        print(f"Expires in: {args.expires_in}")
        print(f"Token: {token}")
        
        # Example curl command
        print(f"\nExample usage:")
        print(f'curl -X POST "http://localhost:8000/api/v1/auth/chat" \\')
        print(f'  -H "Authorization: Bearer {token}" \\')
        print(f'  -H "Content-Type: application/json" \\')
        print(f'  -d \'{{"prompt": "check my account balance", "user_id": "{scenario["user_id"]}"}}\'')
        
        return
    
    # Generate tokens for all scenarios
    print("\nGenerating tokens for all scenarios:")
    print("=" * 60)
    
    for name, scenario in scenarios.items():
        token = generate_test_token(
            user_id=scenario["user_id"],
            scopes=scenario["scopes"],
            roles=scenario["roles"],
            membership_tier=scenario["membership_tier"],
            region=scenario["region"],
            verified=scenario["verified"],
            expires_in=args.expires_in,
            secret_key=args.secret
        )
        
        print(f"\n{name.upper()}:")
        print(f"  Description: {scenario['description']}")
        print(f"  Expires in: {args.expires_in}")
        print(f"  Token: {token}")


if __name__ == "__main__":
    main() 