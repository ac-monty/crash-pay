"""
Authenticated chat API routes with OAuth-based permission management.
Production-ready routes that implement proper authorization for function calling.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends

from app.auth.middleware import get_current_user, get_optional_user
from app.auth.models import UserPermissions
from app.auth.permissions import PermissionManager
from app.models.requests import AuthenticatedChatRequest, Function
from app.models.responses import ChatResponse
from app.services.llm_service import LLMService, get_llm_service
from app.config.settings import get_settings
from app.utils.logging import log_llm_event, get_logger


logger = get_logger(__name__)
router = APIRouter()


@router.post("/auth/chat",
             summary="Authenticated Chat with Function Permissions",
             description="Production chat endpoint with OAuth-based function calling permissions",
             response_model=ChatResponse)
async def authenticated_chat(
    request: AuthenticatedChatRequest,
    user: UserPermissions = Depends(get_current_user),
    llm_service: LLMService = Depends(get_llm_service)
):
    """
    Production-ready chat endpoint that:
    1. Validates JWT token and extracts user context
    2. Determines permitted functions based on OAuth scopes and ABAC rules
    3. Only provides AI with functions the user is authorized to use
    4. AI decides which function to call from permitted list
    """
    chat_start = time.time()
    settings = get_settings()
    request_id = f"auth_chat_{int(time.time() * 1000)}"
    
    try:
        # Validate input
        if not request.prompt:
            raise HTTPException(
                status_code=400,
                detail="Prompt is required"
            )
        
        # Permission Manager for function resolution
        permission_manager = PermissionManager()
        
        # Get available functions for this user
        available_functions = permission_manager.get_available_functions_for_user(user)
        
        # Log permission check
        log_llm_event(
            "info",
            f"User {user.user_id} has access to {len(available_functions)} functions",
            settings.llm_provider,
            settings.llm_model,
            extra_data={
                "request_id": request_id,
                "user_id": user.user_id,
                "permitted_functions": user.permitted_functions,
                "user_scopes": user.scopes
            }
        )
        
        # Convert user's natural language request to messages
        messages = [{"role": "user", "content": request.prompt}]
        
        # Create Function objects for the LLM (only permitted functions)
        functions = None
        if available_functions:
            functions = []
            for func_info in available_functions:
                # Create function definition for LLM
                # In production, these would come from a function registry
                function_def = _create_function_definition(func_info["name"])
                if function_def:
                    functions.append(Function(**function_def))
        
        # Prepare LLM request with user context
        from app.models.requests import ChatRequest, UserContext
        
        # Create user context from authenticated user
        user_context = UserContext(
            user_id=user.user_id,
            permissions=user.scopes,
            roles=user.attributes.get('roles', []) if user.attributes else [],
            attributes=user.attributes,
            permitted_functions=user.permitted_functions
        )
        
        llm_request = ChatRequest(
            messages=None,  # Using prompt instead
            prompt=request.prompt,
            use_rag=request.use_rag,
            use_functions=bool(functions),
            functions=functions,
            session_id=request.session_id,
            user_context=user_context,
            stream=request.stream,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # Call LLM service
        response_content, function_calls = await llm_service.chat(
            messages=messages,
            request=llm_request,
            request_id=request_id
        )
        
        # Validate function calls against user permissions
        if function_calls:
            validated_calls = []
            for call in function_calls:
                function_name = call.get("function")
                # Whitelist get_rag_context for internal KB lookups
                if function_name == "get_rag_context" or function_name in user.permitted_functions:
                    validated_calls.append(call)
                    logger.info(f"Function call approved: {function_name} for user {user.user_id}")
                else:
                    logger.warning(f"Function call blocked: {function_name} for user {user.user_id}")
            function_calls = validated_calls
        
        total_time = time.time() - chat_start
        
        # Log successful completion
        log_llm_event(
            "info",
            f"Authenticated chat completed for user {user.user_id}",
            settings.llm_provider,
            settings.llm_model,
            extra_data={
                "request_id": request_id,
                "user_id": user.user_id,
                "total_time": total_time,
                "function_calls": len(function_calls) if function_calls else 0
            }
        )
        
        return ChatResponse(
            response=response_content,
            provider=settings.llm_provider,
            model=settings.llm_model,
            function_calls=function_calls,
            request_id=request_id,
            total_time=total_time
        )
        
    except Exception as e:
        total_time = time.time() - chat_start
        
        # Log the error
        log_llm_event(
            "error",
            f"Authenticated chat failed for user {user.user_id}: {str(e)}",
            settings.llm_provider,
            settings.llm_model,
            error=e,
            extra_data={
                "request_id": request_id,
                "user_id": user.user_id,
                "total_time": total_time
            }
        )
        
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/auth/permissions",
            summary="Get User Permissions",
            description="Get the current user's function permissions and available actions")
async def get_user_permissions(
    user: UserPermissions = Depends(get_current_user)
):
    """Get detailed permission information for the authenticated user."""
    try:
        permission_manager = PermissionManager()
        available_functions = permission_manager.get_available_functions_for_user(user)
        
        return {
            "user_id": user.user_id,
            "scopes": user.scopes,
            "permitted_functions": user.permitted_functions,
            "available_functions": available_functions,
            "user_attributes": user.attributes,
            "expires_at": user.expires_at.isoformat() if user.expires_at else None
        }
        
    except Exception as e:
        logger.error(f"Failed to get permissions for user {user.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve permissions")


@router.get("/auth/functions",
            summary="Get Available Functions",
            description="Get list of functions the current user can access")
async def get_available_functions(
    user: UserPermissions = Depends(get_current_user)
):
    """Get list of functions available to the current user."""
    try:
        permission_manager = PermissionManager()
        available_functions = permission_manager.get_available_functions_for_user(user)
        
        return {
            "user_id": user.user_id,
            "total_functions": len(available_functions),
            "functions": available_functions
        }
        
    except Exception as e:
        logger.error(f"Failed to get functions for user {user.user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve functions")


def _create_function_definition(function_name: str) -> Optional[Dict[str, Any]]:
    """
    Create function definition for LLM based on function name.
    In production, this would be from a comprehensive function registry.
    """
    function_definitions = {
        "get_account_balance": {
            "name": "get_account_balance",
            "description": "Check the current balance of a user's account",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "enum": ["checking", "savings", "credit"],
                        "description": "The type of account to check"
                    }
                },
                "required": ["account_type"]
            }
        },
        "get_transaction_history": {
            "name": "get_transaction_history",
            "description": "Get recent transaction history for an account",
            "parameters": {
                "type": "object",
                "properties": {
                    "account_type": {
                        "type": "string",
                        "enum": ["checking", "savings", "credit"],
                        "description": "The type of account"
                    },
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 90,
                        "description": "Number of days of history to retrieve"
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "description": "Maximum number of transactions to return (default 5)"
                    }
                },
                "required": ["account_type"]
            }
        },
        "transfer_funds": {
            "name": "transfer_funds",
            "description": "Transfer funds between your accounts or to another user's account ID (obtain via list_recipients). Use the recipient's account_type if specified to select the correct destination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_account": {
                        "type": "string",
                        "enum": ["checking", "savings"],
                        "description": "Source account type (checking or savings)"
                    },
                    "to_account_id": {
                        "type": "string",
                        "description": "Destination ACCOUNT ID (UUID) – call list_recipients first to obtain it"
                    },
                    "amount": {
                        "type": "number",
                        "minimum": 0.01,
                        "description": "Amount to transfer"
                    }
                },
                "required": ["from_account", "to_account_id", "amount"]
            }
        },
        "list_recipients": {
            "name": "list_recipients",
            "description": "Search recipient users by name. If account_type is provided, returns recipients with an account ID of that type; otherwise returns the first account ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Partial or full name of the recipient (min 3 characters)"
                    },
                    "account_type": {
                        "type": "string",
                        "enum": ["checking", "savings"],
                        "description": "Optional desired recipient account type (e.g., savings). If omitted, the first account will be selected."
                    }
                },
                "required": ["name"]
            }
        },
        "get_portfolio_balance": {
            "name": "get_portfolio_balance",
            "description": "Get investment portfolio balance and allocation",
            "parameters": {
                "type": "object",
                "properties": {
                    "portfolio_type": {
                        "type": "string",
                        "enum": ["stocks", "bonds", "etfs", "all"],
                        "description": "Type of portfolio to check"
                    }
                },
                "required": ["portfolio_type"]
            }
        },
        "place_trade_order": {
            "name": "place_trade_order",
            "description": "Place buy/sell orders for securities",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock symbol (e.g., AAPL, GOOGL)"
                    },
                    "order_type": {
                        "type": "string",
                        "enum": ["buy", "sell"],
                        "description": "Order type"
                    },
                    "quantity": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Number of shares"
                    },
                    "order_method": {
                        "type": "string",
                        "enum": ["market", "limit"],
                        "description": "Market or limit order"
                    },
                    "limit_price": {
                        "type": "number",
                        "minimum": 0.01,
                        "description": "Limit price (required for limit orders)"
                    }
                },
                "required": ["symbol", "order_type", "quantity", "order_method"]
            }
        },
        "check_credit_score": {
            "name": "check_credit_score",
            "description": "Check current credit score and credit report summary",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        "apply_for_loan": {
            "name": "apply_for_loan",
            "description": "Submit loan application",
            "parameters": {
                "type": "object",
                "properties": {
                    "loan_type": {
                        "type": "string",
                        "enum": ["personal", "auto", "home", "business"],
                        "description": "Type of loan to apply for"
                    },
                    "amount": {
                        "type": "number",
                        "minimum": 1000,
                        "description": "Loan amount requested"
                    },
                    "term_months": {
                        "type": "integer",
                        "minimum": 12,
                        "maximum": 360,
                        "description": "Loan term in months"
                    }
                },
                "required": ["loan_type", "amount", "term_months"]
            }
        },
        "get_all_customer_accounts": {
            "name": "get_all_customer_accounts",
            "description": "Get customer account information (admin only)",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_id": {
                        "type": "string",
                        "description": "Customer ID to lookup"
                    },
                    "account_type": {
                        "type": "string",
                        "enum": ["all", "checking", "savings", "credit", "investment"],
                        "description": "Filter by account type"
                    }
                },
                "required": ["customer_id"]
            }
        },
        "trigger_end_session": {
            "name": "trigger_end_session",
            "description": "Signal that the user wants to end the banking session (shows end session option to user)",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Optional reason for ending the session",
                        "default": "User requested to end session"
                    }
                },
                "required": []
            }
        },
        "get_user_profile": {
            "name": "get_user_profile",
            "description": "Fetch basic profile information for the current authenticated user (admin only).  Returns name, email, tier, region, and list of accounts.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        # RAG as a tool – lets the model fetch KB context when needed
        "get_rag_context": {
            "name": "get_rag_context",
            "description": "Retrieve concise knowledge-base context for the user’s question.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The user’s latest question to retrieve KB context for"
                    }
                },
                "required": ["query"]
            }
        }
    }
    
    return function_definitions.get(function_name) 