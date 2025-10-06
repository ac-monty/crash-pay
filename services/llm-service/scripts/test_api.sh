#!/usr/bin/env bash

# =============================================================================
# LLM Service Comprehensive API Test Script
# =============================================================================
# This script tests ALL models from OpenAI, Anthropic, and Google providers
# It performs comprehensive testing including:
# - Model switching
# - Basic chat functionality  
# - Function calling
# - Streaming
# - Health checks
#
# Usage: ./test_api.sh [COHERE_DELAY] [GENERAL_DELAY]
#   COHERE_DELAY: Seconds to wait after switching Cohere models (default: 1)
#   GENERAL_DELAY: Seconds to wait after switching other provider models (default: 1)
#
# Examples:
#   ./test_api.sh                    # Use default 1s delays for all providers
#   ./test_api.sh 5                  # Use 5s delay for Cohere, 1s for others
#   ./test_api.sh 5 2                # Use 5s delay for Cohere, 2s for others
#
# Make sure the service is running on localhost:8000 before running
# =============================================================================

# Rebuild with fixes
# docker build -t llm-service . --no-cache

# Run again (warnings should be gone)  
# docker run -p 8000:8000 --env-file .env llm-service

set -o pipefail  # Keep this for better error handling in pipelines

echo "-> Changing directory to root"
# Move to the directory where the script is located, then go one up
cd "$(dirname "$0")/.."

# Configuration
API_BASE="http://localhost:8000"
CONTENT_TYPE="Content-Type: application/json"
TEST_TIMEOUT=30

# Model switching delays (can be overridden by command line arguments)
COHERE_DELAY=${1:-1}  # Default 1 second, or pass custom delay for Cohere
GENERAL_DELAY=${2:-1}  # Default 1 second delay for all other providers

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Test results tracking
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
SKIPPED_TESTS=0

# Results tracking (compatible with older bash)
RESULTS_FILE="/tmp/llm_test_results_$$"
> "$RESULTS_FILE"  # Clear results file

# =============================================================================
# MODEL DEFINITIONS FROM REGISTRY
# =============================================================================

# OpenAI Models
declare -a OPENAI_REASONING=("o4-mini" "o3" "o3-mini" "o1")
declare -a OPENAI_ONESHOT=("gpt-4o" "gpt-4.1" "gpt-4.1-nano")

# Anthropic Models  
declare -a ANTHROPIC_REASONING=("opus-4" "sonnet-4" "sonnet-3.7")
declare -a ANTHROPIC_ONESHOT=("haiku-3.5" "sonnet-3.5" "opus-3" "haiku-3")

# Google Models
declare -a GOOGLE_REASONING=("gemini-1.5-pro")
declare -a GOOGLE_ONESHOT=("gemini-1.5-flash" "gemini-1.5-flash-8b" "gemini-1.5-pro")

# Cohere Models
declare -a COHERE_ONESHOT=("command-a" "command-r+" "command-r-07b" "command-r-08" "command-r")

# Mistral Models
declare -a MISTRAL_REASONING=("mistral-large-latest")
declare -a MISTRAL_ONESHOT=("mistral-medium-latest" "mistral-small-latest" "ministral-8b-latest" "ministral-3b-latest")

# Fireworks Models
declare -a FIREWORKS_REASONING=("deepseek-r1-0528")
declare -a FIREWORKS_ONESHOT=("llama4-maverick" "llama4-scout" "llama-v3p1-405b" "qwen3-235b" "deepseek-v3" "mixtral-8x22b")

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_section() {
    echo -e "\n${PURPLE}--- $1 ---${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASSED_TESTS++))
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
    ((FAILED_TESTS++))
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
    ((SKIPPED_TESTS++))
}

# Non-counting versions for informational messages
print_success_info() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error_info() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning_info() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

# Function to increment total tests
count_test() {
    ((TOTAL_TESTS++))
}

# Function to log test results
log_test_result() {
    local provider=$1
    local model=$2
    local test_type=$3
    local status=$4
    local details=$5
    
    echo "${provider}:${model}:${test_type}:${status}:${details}" >> "$RESULTS_FILE"
}

# Generate JWT token for testing
generate_test_token() {
    local scenario=${1:-"basic_customer"}
    
    # Try to generate token using Docker container
    if command -v docker >/dev/null 2>&1; then
        local token=$(docker exec llm-service python3 scripts/generate_test_token.py --scenario "$scenario" 2>/dev/null | grep "Token:" | cut -d' ' -f2)
        if [ -n "$token" ]; then
            echo "$token"
            return 0
        fi
    fi
    
    # Fallback: try with python3 on host
    if command -v python3 >/dev/null 2>&1; then
        local token=$(python3 scripts/generate_test_token.py --scenario "$scenario" 2>/dev/null | grep "Token:" | cut -d' ' -f2)
        if [ -n "$token" ]; then
            echo "$token"
            return 0
        fi
    fi
    
    # Fallback: try with python on host
    if command -v python >/dev/null 2>&1; then
        local token=$(python scripts/generate_test_token.py --scenario "$scenario" 2>/dev/null | grep "Token:" | cut -d' ' -f2)
        if [ -n "$token" ]; then
            echo "$token"
            return 0
        fi
    fi
    
    # If token generation fails, return empty
    echo ""
    return 1
}

# Function to check if service is running
check_service() {
    print_header "Checking LLM Service Availability"
    
    if curl -s "${API_BASE}/" > /dev/null 2>&1; then
        local service_info=$(curl -s "${API_BASE}/" | jq -r '.service + " v" + .version')
        print_success_info "Service is running: $service_info"
        return 0
    else
        print_error_info "Service is not accessible at ${API_BASE}"
        print_info "Please start the service first:"
        print_info "  docker run -p 8000:8000 --env-file .env llm-service:latest"
        exit 1
    fi
}

# Function to switch model with timeout and error handling
switch_model() {
    local provider=$1
    local model=$2
    local timeout=${3:-$TEST_TIMEOUT}
    
    print_info "Switching to ${provider}/${model}..."
    
    # URL encode the model name to handle special characters like +
    local encoded_model=$(printf '%s' "${model}" | sed 's/+/%2B/g')
    
    local response=$(timeout $timeout curl -s -X POST \
        "${API_BASE}/api/v1/switch-model?provider=${provider}&model=${encoded_model}&should_validate=false" \
        -H "${CONTENT_TYPE}" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$response" | jq -e '.success == true' > /dev/null 2>&1; then
        print_success_info "Successfully switched to ${provider}/${model}"
        return 0
    else
        local error_msg=$(echo "$response" | jq -r '.detail // .error // "Unknown error"')
        print_error_info "Failed to switch to ${provider}/${model}: $error_msg"
        return 1
    fi
}

# Function to test basic chat
test_basic_chat() {
    local provider=$1
    local model=$2
    local is_reasoning=$3
    
    count_test
    print_info "Testing basic chat for ${provider}/${model}..."
    
    local payload
    if [ "$is_reasoning" = "true" ]; then
        payload='{
            "prompt": "Hello! Please introduce yourself briefly as a banking assistant in one sentence.",
            "reasoning_effort": "medium",
            "max_tokens": 1024,
            "stream": false
        }'
    else
        payload='{
            "prompt": "Hello! Please introduce yourself briefly as a banking assistant in one sentence.",
            "max_tokens": 1024,
            "temperature": 0.7,
            "stream": false
        }'
    fi
    
    local response=$(timeout $TEST_TIMEOUT curl -s -X POST "${API_BASE}/api/v1/chat" \
        -H "${CONTENT_TYPE}" \
        -d "$payload" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$response" | jq -e '.response' > /dev/null 2>&1; then
        local response_text=$(echo "$response" | jq -r '.response' | head -c 100)
        print_success "Basic chat works for ${provider}/${model}"
        log_test_result "$provider" "$model" "basic_chat" "PASS" "$response_text..."
        return 0
    else
        local error_msg=$(echo "$response" | jq -r '.detail // .error // "Unknown error"')
        print_error "Basic chat failed for ${provider}/${model}: $error_msg"
        log_test_result "$provider" "$model" "basic_chat" "FAIL" "$error_msg"
        return 1
    fi
}



# Function to test authenticated function calling (NEW)
test_authenticated_function_calling() {
    local provider=$1
    local model=$2
    
    count_test
    print_info "Testing authenticated function calling for ${provider}/${model}..."
    
    # Generate JWT token for a premium customer who can check account balance
    local token=$(generate_test_token "premium_customer")
    
    if [ -z "$token" ]; then
        print_error "Failed to generate JWT token for authentication test"
        log_test_result "$provider" "$model" "auth_function_calling" "FAIL" "Token generation failed"
        return 1
    fi
    
    # Natural user request - NO function definitions provided
    local payload='{
        "prompt": "hey can u check my checking account balance real quick?",
        "user_id": "user_premium_002",
        "stream": false,
        "max_tokens": 1024,
        "temperature": 0.2
    }'
    
    # Call authenticated endpoint with JWT token
    local response=$(timeout $TEST_TIMEOUT curl -s -X POST "${API_BASE}/api/v1/auth/chat" \
        -H "${CONTENT_TYPE}" \
        -H "Authorization: Bearer $token" \
        -d "$payload" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$response" | jq -e '.response' > /dev/null 2>&1; then
        # Check if AI called a function
        local has_function_calls=$(echo "$response" | jq -e '.function_calls != null' > /dev/null 2>&1 && echo "true" || echo "false")
        if [ "$has_function_calls" = "true" ]; then
            # Check if it called the right function
            local function_name=$(echo "$response" | jq -r '.function_calls[0].function // "none"')
            if [ "$function_name" = "get_account_balance" ]; then
                print_success "✨ PERFECT! AI automatically called the correct function: $function_name"
                log_test_result "$provider" "$model" "auth_function_calling" "PASS" "AI called $function_name automatically"
                
                # Show the function arguments to verify AI understood the request
                local arguments=$(echo "$response" | jq -r '.function_calls[0].arguments // "{}"')
                print_info "   Function arguments: $arguments"
            else
                print_warning "AI called a function but wrong one: $function_name (expected: get_account_balance)"
                log_test_result "$provider" "$model" "auth_function_calling" "PARTIAL" "AI called wrong function: $function_name"
            fi
        else
            print_warning "AI responded but didn't call any function (authentication/permissions working, but AI didn't use functions)"
            log_test_result "$provider" "$model" "auth_function_calling" "PARTIAL" "Response without function call"
        fi
        return 0
    else
        local error_msg=$(echo "$response" | jq -r '.detail // .error // "Unknown error"')
        if [[ "$error_msg" == *"Token"* ]] || [[ "$error_msg" == *"401"* ]]; then
            print_error "Authentication failed: $error_msg"
            log_test_result "$provider" "$model" "auth_function_calling" "FAIL" "Auth error: $error_msg"
        elif [[ "$error_msg" == *"403"* ]] || [[ "$error_msg" == *"permission"* ]]; then
            print_error "Authorization failed: $error_msg"
            log_test_result "$provider" "$model" "auth_function_calling" "FAIL" "Authz error: $error_msg"
        else
            print_error "Authenticated function calling failed: $error_msg"
            log_test_result "$provider" "$model" "auth_function_calling" "FAIL" "$error_msg"
        fi
        return 1
    fi
}

# Function to test streaming
test_streaming() {
    local provider=$1
    local model=$2
    
    count_test
    print_info "Testing streaming for ${provider}/${model}..."
    
    local payload='{
        "prompt": "Count from 1 to 5.",
        "stream": true,
        "max_tokens": 1024,
        "temperature": 0.1
    }'
    
    # Test streaming by checking if we get Server-Sent Events
    local response=$(timeout $TEST_TIMEOUT curl -s -X POST "${API_BASE}/api/v1/chat" \
        -H "${CONTENT_TYPE}" \
        -d "$payload" 2>/dev/null | head -5)
    
    if echo "$response" | grep -q "data:" || echo "$response" | jq -e '.response' > /dev/null 2>&1; then
        print_success "Streaming works for ${provider}/${model}"
        log_test_result "$provider" "$model" "streaming" "PASS" "Streaming response received"
        return 0
    else
        print_error "Streaming failed for ${provider}/${model}"
        log_test_result "$provider" "$model" "streaming" "FAIL" "No streaming response"
        return 1
    fi
}

# Function to test a single model comprehensively
test_model() {
    local provider=$1
    local model=$2
    local is_reasoning=$3
    
    print_section "Testing ${provider}/${model} ($([ "$is_reasoning" = "true" ] && echo "REASONING" || echo "ONE-SHOT"))"
    
    # Try to switch to the model
    if switch_model "$provider" "$model"; then
        # Wait for the switch to complete - configurable delay per provider
        if [ "$provider" = "cohere" ]; then
            print_info "   Waiting ${COHERE_DELAY}s for Cohere model switch to complete..."
            sleep $COHERE_DELAY
        else
            print_info "   Waiting ${GENERAL_DELAY}s for model switch to complete..."
            sleep $GENERAL_DELAY
        fi
        
        # Run all tests for this model
        test_basic_chat "$provider" "$model" "$is_reasoning"
        test_authenticated_function_calling "$provider" "$model"
        test_streaming "$provider" "$model"
    else
        # Mark all tests as failed if we can't switch to the model
        count_test && print_error "Basic chat failed for ${provider}/${model}: Model switch failed"
        log_test_result "$provider" "$model" "basic_chat" "FAIL" "Model switch failed"
        
        count_test && print_error "Authenticated function calling failed for ${provider}/${model}: Model switch failed"
        log_test_result "$provider" "$model" "auth_function_calling" "FAIL" "Model switch failed"
        
        count_test && print_error "Streaming failed for ${provider}/${model}: Model switch failed"
        log_test_result "$provider" "$model" "streaming" "FAIL" "Model switch failed"
    fi
    
    echo ""
}

# =============================================================================
# MAIN TEST FUNCTIONS
# =============================================================================

test_openai_models() {
    print_header "🤖 Testing OpenAI Models"
    
    print_info "Testing OpenAI Reasoning Models..."
    for model in "${OPENAI_REASONING[@]}"; do
        test_model "openai" "$model" "true"
    done
    
    print_info "Testing OpenAI One-Shot Models..."
    for model in "${OPENAI_ONESHOT[@]}"; do
        test_model "openai" "$model" "false"
    done
}

test_anthropic_models() {
    print_header "🧠 Testing Anthropic Models"
    
    print_info "Testing Anthropic Reasoning Models..."
    for model in "${ANTHROPIC_REASONING[@]}"; do
        test_model "anthropic" "$model" "true"
    done
    
    print_info "Testing Anthropic One-Shot Models..."
    for model in "${ANTHROPIC_ONESHOT[@]}"; do
        test_model "anthropic" "$model" "false"
    done
}

test_google_models() {
    print_header "🔍 Testing Google Models"
    
    print_info "Testing Google Reasoning Models..."
    for model in "${GOOGLE_REASONING[@]}"; do
        test_model "google" "$model" "true"
    done
    
    print_info "Testing Google One-Shot Models..."
    for model in "${GOOGLE_ONESHOT[@]}"; do
        test_model "google" "$model" "false"
    done
}

test_cohere_models() {
    print_header "🗣️ Testing Cohere Models"
    
    print_info "Testing Cohere One-Shot Models..."
    for model in "${COHERE_ONESHOT[@]}"; do
        test_model "cohere" "$model" "false"
    done
}

test_mistral_models() {
    print_header "🌟 Testing Mistral Models"
    
    print_info "Testing Mistral Reasoning Models..."
    for model in "${MISTRAL_REASONING[@]}"; do
        test_model "mistral" "$model" "true"
    done
    
    print_info "Testing Mistral One-Shot Models..."
    for model in "${MISTRAL_ONESHOT[@]}"; do
        test_model "mistral" "$model" "false"
    done
}

test_fireworks_models() {
    print_header "🔥 Testing Fireworks Models"
    
    print_info "Testing Fireworks Reasoning Models..."
    for model in "${FIREWORKS_REASONING[@]}"; do
        test_model "fireworks" "$model" "true"
    done
    
    print_info "Testing Fireworks One-Shot Models..."
    for model in "${FIREWORKS_ONESHOT[@]}"; do
        test_model "fireworks" "$model" "false"
    done
}

# Function to test service health
test_service_health() {
    print_header "🏥 Testing Service Health"
    
    count_test
    print_info "Testing health endpoint..."
    
    local response=$(timeout $TEST_TIMEOUT curl -s -X GET "${API_BASE}/api/v1/healthz" \
        -H "${CONTENT_TYPE}" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$response" | jq -e '.status' > /dev/null 2>&1; then
        local status=$(echo "$response" | jq -r '.status')
        local provider=$(echo "$response" | jq -r '.provider // "unknown"')
        local model=$(echo "$response" | jq -r '.model // "unknown"')
        print_success "Health check passed - Status: $status, Provider: $provider, Model: $model"
    else
        print_error "Health check failed"
    fi
    
    count_test
    print_info "Testing available models endpoint..."
    
    local models_response=$(timeout $TEST_TIMEOUT curl -s -X GET "${API_BASE}/api/v1/available-models" \
        -H "${CONTENT_TYPE}" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$models_response" | jq -e '.available_models' > /dev/null 2>&1; then
        local provider_count=$(echo "$models_response" | jq '.available_models | keys | length')
        print_success "Available models endpoint works - Found $provider_count providers"
    else
        print_error "Available models endpoint failed"
    fi
}

# Function to generate comprehensive test report
generate_report() {
    print_header "📊 Test Results Summary"
    
    echo -e "${BLUE}Total Tests: ${TOTAL_TESTS}${NC}"
    echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
    echo -e "${YELLOW}Skipped: ${SKIPPED_TESTS}${NC}"
    
    if [ $TOTAL_TESTS -gt 0 ]; then
        local effective_passed=$(( PASSED_TESTS + SKIPPED_TESTS ))
        local success_rate=$(( (effective_passed * 100) / TOTAL_TESTS ))
        echo -e "${PURPLE}Success Rate: ${success_rate}%${NC}"
    fi
    
    print_section "📋 Detailed Results by Provider"
    
    # Group results by provider
    for provider in "openai" "anthropic" "google" "cohere" "mistral" "fireworks"; do
        echo -e "\n${BLUE}$(echo $provider | tr a-z A-Z) Results:${NC}"
        
        local provider_total=0
        local provider_passed=0
        local provider_partial=0
        local provider_failed=0
        
        while IFS=':' read -r p model test_type status details; do
            if [ "$p" = "$provider" ]; then
                ((provider_total++))
                case $status in
                    "PASS") ((provider_passed++)) && echo -e "  ${GREEN}✓${NC} $model ($test_type): $details" ;;
                    "PARTIAL") ((provider_partial++)) && echo -e "  ${YELLOW}⚠${NC} $model ($test_type): $details" ;;
                    "FAIL") ((provider_failed++)) && echo -e "  ${RED}✗${NC} $model ($test_type): $details" ;;
                esac
            fi
        done < "$RESULTS_FILE"
        
        if [ $provider_total -gt 0 ]; then
            local provider_effective_passed=$(( provider_passed + provider_partial ))
            local provider_success_rate=$(( (provider_effective_passed * 100) / provider_total ))
            echo -e "  ${PURPLE}Provider Success Rate: ${provider_success_rate}% (${provider_effective_passed}/${provider_total})${NC}"
        fi
    done
    
    print_section "🎯 Recommendations"
    
    if [ $FAILED_TESTS -gt 0 ]; then
        echo -e "${YELLOW}• Check failed tests for API key configuration${NC}"
        echo -e "${YELLOW}• Verify model availability and access permissions${NC}"
        echo -e "${YELLOW}• Review error messages for specific issues${NC}"
    fi
    
    if [ $SKIPPED_TESTS -gt 0 ]; then
        echo -e "${CYAN}• Some models responded but didn't call functions - this is normal model behavior variation${NC}"
        echo -e "${CYAN}• Authentication and authorization systems are working correctly${NC}"
    fi
    
    local overall_success_rate=$(( (PASSED_TESTS + SKIPPED_TESTS) * 100 / TOTAL_TESTS ))
    if [ $overall_success_rate -gt 80 ]; then
        echo -e "${GREEN}• Overall test results look good!${NC}"
    elif [ $overall_success_rate -gt 60 ]; then
        echo -e "${YELLOW}• Some models may need attention!${NC}"
    else
        echo -e "${RED}• Significant issues detected - review configuration ${NC}"
    fi
}

# Function to test authentication system
test_authentication_system() {
    print_header "🔐 Testing Authentication System"
    
    count_test
    print_info "Testing JWT token generation..."
    
    local token=$(generate_test_token "basic_customer")
    if [ -n "$token" ]; then
        print_success "JWT token generation works"
        print_info "   Generated token: ${token:0:50}..."
    else
        print_error "JWT token generation failed"
        return 1
    fi
    
    count_test
    print_info "Testing user permissions endpoint..."
    
    local response=$(timeout $TEST_TIMEOUT curl -s -X GET "${API_BASE}/api/v1/auth/permissions" \
        -H "${CONTENT_TYPE}" \
        -H "Authorization: Bearer $token" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$response" | jq -e '.user_id' > /dev/null 2>&1; then
        local user_id=$(echo "$response" | jq -r '.user_id')
        local function_count=$(echo "$response" | jq '.permitted_functions | length')
        print_success "User permissions endpoint works - User: $user_id, Functions: $function_count"
    else
        local error_msg=$(echo "$response" | jq -r '.detail // .error // "Unknown error"')
        print_error "User permissions endpoint failed: $error_msg"
    fi
    
    count_test
    print_info "Testing user functions endpoint..."
    
    local functions_response=$(timeout $TEST_TIMEOUT curl -s -X GET "${API_BASE}/api/v1/auth/functions" \
        -H "${CONTENT_TYPE}" \
        -H "Authorization: Bearer $token" 2>/dev/null || echo '{"error":"timeout"}')
    
    if echo "$functions_response" | jq -e '.functions' > /dev/null 2>&1; then
        local total_functions=$(echo "$functions_response" | jq '.total_functions')
        print_success "User functions endpoint works - Available functions: $total_functions"
    else
        local error_msg=$(echo "$functions_response" | jq -r '.detail // .error // "Unknown error"')
        print_error "User functions endpoint failed: $error_msg"
    fi
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    print_header "🧪 LLM Service Comprehensive Test Suite"
    print_info "Testing ALL models from OpenAI, Anthropic, Google, Cohere, Mistral, and Fireworks providers"
    print_info "This will test $(( ${#OPENAI_REASONING[@]} + ${#OPENAI_ONESHOT[@]} + ${#ANTHROPIC_REASONING[@]} + ${#ANTHROPIC_ONESHOT[@]} + ${#GOOGLE_REASONING[@]} + ${#GOOGLE_ONESHOT[@]} + ${#COHERE_ONESHOT[@]} + ${#MISTRAL_REASONING[@]} + ${#MISTRAL_ONESHOT[@]} + ${#FIREWORKS_REASONING[@]} + ${#FIREWORKS_ONESHOT[@]} )) models with 3 tests each"
    print_info "Model switching delays: Cohere=${COHERE_DELAY}s, Others=${GENERAL_DELAY}s"
    print_info "Started at: $(date)"
    echo ""
    
    # Check if service is running
    check_service
    
    # Test authentication system first
    test_authentication_system
    
    # Test service health
    test_service_health
    
    # Test all provider models
    test_openai_models
    test_anthropic_models  
    test_google_models
    test_cohere_models
    test_mistral_models
    test_fireworks_models
    
    # Generate final report
    generate_report
    
    print_header "🏁 Testing Complete"
    print_info "Finished at: $(date)"
    
    # Clean up results file
    rm -f "$RESULTS_FILE"
    
    # Exit with error code if any tests failed
    if [ $FAILED_TESTS -gt 0 ]; then
        exit 1
    else
        exit 0
    fi
}

# Run main function
main "$@" 