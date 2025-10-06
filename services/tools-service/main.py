import os
import shlex
import subprocess
import logging
from datetime import datetime, UTC
from typing import Optional
import json

from fastapi import FastAPI, Query, Body, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Configure very simple stdout logging so Docker / Filebeat can ship logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
)
logger = logging.getLogger("tools-service")

# Import APM for security monitoring
try:
    import elasticapm
    from elasticapm.contrib.starlette import make_apm_client, ElasticAPM
    
    # Initialize APM client for security monitoring
    apm_config = {
        'SERVICE_NAME': os.environ.get('ELASTIC_APM_SERVICE_NAME', 'tools-service'),
        'SERVER_URL': os.environ.get('ELASTIC_APM_SERVER_URL', 'http://localhost:8200'),
        'ENVIRONMENT': os.environ.get('ELASTIC_APM_ENVIRONMENT', 'development'),
        'VERIFY_SERVER_CERT': os.environ.get('ELASTIC_APM_VERIFY_SERVER_CERT', 'false').lower() == 'true',
        'CAPTURE_BODY': 'all',  # Capture request bodies for security analysis
        'CAPTURE_HEADERS': True,
    }
    
    apm_client = make_apm_client(apm_config)
    apm_middleware_enabled = True
    logger.info("✅ APM security monitoring initialized for tools-service")
    
except ImportError as e:
    logger.warning(f"⚠️ APM client not available: {e}")
    apm_client = None
    apm_middleware_enabled = False
except Exception as e:
    logger.error(f"❌ APM client initialization failed: {e}")
    apm_client = None
    apm_middleware_enabled = False

# --------------------------------------------------------------------------- #
# Basic, intentionally-weak FastAPI "Tools Service"
#   * /shell?cmd=...      – executes arbitrary OS commands
#   * /payments           – fake payment processor with minimal checks
# --------------------------------------------------------------------------- #

app = FastAPI(
    title="Fake-Fintech Tools Service",
    description=(
        "Deliberately vulnerable micro-service exposing shell execution and "
        "payment capabilities so security researchers can test OWASP-LLM Top-10 "
        "scenarios (LLM07/08).  DO NOT USE IN PRODUCTION."
    ),
    version="0.1.0",
)

# Add CORS middleware to allow frontend health checks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=False,  # Must be False when allow_origins=["*"]
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Add APM middleware for security monitoring
if apm_middleware_enabled and apm_client:
    app.add_middleware(ElasticAPM, client=apm_client)
    logger.info("✅ APM security monitoring enabled for tools-service")

# --------------------------------------------------------------------------- #
# /shell endpoint (LLM07 / LLM08) – minimal "sanitisation"
# --------------------------------------------------------------------------- #
MAX_CMD_LENGTH = int(os.getenv("MAX_CMD_LENGTH", "200"))  # perf/DoS guard only


@app.get("/shell")
async def run_shell(cmd: str = Query(..., description="Command to execute")):
    """
    Execute **any** shell command inside the container and return its output.

    Minimal protections:
    • Length cap to avoid accidental resource-starvation
    • Strips surrounding whitespace

    Everything else is **unfiltered** by design.
    """
    cmd = cmd.strip()

    if len(cmd) == 0:
        raise HTTPException(status_code=400, detail="Empty command")

    if len(cmd) > MAX_CMD_LENGTH:
        raise HTTPException(
            status_code=413,
            detail=f"Command too long (>{MAX_CMD_LENGTH} chars)",
        )

    # Log security event to APM - this is a dangerous operation!
    if apm_client:
        apm_client.capture_message(
            message=f"SECURITY ALERT: Shell command execution: {cmd}",
            level="warning",
            labels={
                "security_event": "shell_execution",
                "command": cmd,
                "service": "tools-service",
                "risk_level": "high"
            },
            extra={
                "command_length": len(cmd),
                "timestamp": datetime.now(UTC).isoformat()
            }
        )

    # (e.g., it does NOT escape, whitelist, or sandbox the command).
    logger.warning("Executing arbitrary shell command: %s", cmd)

    try:
        # shell=True to mimic common misuse that enables injection
        completed = subprocess.run(
            cmd,
            shell=True,
            cwd="/",  # Run from container root
            capture_output=True,
            text=True,
            timeout=20,  # prevent simple infinite-loop DoS
        )
        
        # Log command result to APM
        if apm_client:
            apm_client.capture_message(
                message=f"Shell command completed: {cmd}",
                level="info",
                labels={
                    "security_event": "shell_execution_completed",
                    "return_code": str(completed.returncode),
                    "service": "tools-service"
                },
                extra={
                    "stdout_length": len(completed.stdout),
                    "stderr_length": len(completed.stderr),
                    "command": cmd
                }
            )
            
    except subprocess.TimeoutExpired:
        # Log timeout to APM
        if apm_client:
            apm_client.capture_message(
                message=f"Shell command timeout: {cmd}",
                level="error",
                labels={
                    "security_event": "shell_execution_timeout",
                    "service": "tools-service",
                    "risk_level": "medium"
                }
            )
        raise HTTPException(
            status_code=504, detail="Command timed out (20s limit)"
        )
    except Exception as e:
        # Log execution error to APM
        if apm_client:
            apm_client.capture_exception(
                exc_info=(type(e), e, e.__traceback__),
                labels={
                    "security_event": "shell_execution_error",
                    "service": "tools-service",
                    "command": cmd
                }
            )
        raise

    return {
        "cmd": cmd,
        "return_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


# --------------------------------------------------------------------------- #
# /payments endpoint (LLM08) – fake fintech transfer with LLM "approval"
# --------------------------------------------------------------------------- #
class PaymentRequest(BaseModel):
    from_account: str = Field(..., example="123-456")
    to_account: str = Field(..., example="987-654")
    amount: float = Field(..., gt=0, example=199.95)
    currency: str = Field("USD", example="USD")
    note: Optional[str] = Field(None, example="Payment for services")


class PaymentResponse(BaseModel):
    payment_id: str
    status: str
    processed_at: datetime
    details: PaymentRequest


# In-memory store so researchers can view/alter previous state (no DB layer)
_FAKE_LEDGER: dict[str, PaymentResponse] = {}


@app.post("/payments", response_model=PaymentResponse)
async def process_payment(payload: PaymentRequest = Body(...)):
    """
    Accepts a JSON payment request and records it in a *very* naïve ledger.

    Intentionally missing:
    • Authentication / authorization
    • Balance checks, duplicate prevention, currency validation
    • Strong input validation (relies on Pydantic defaults only)

    A real implementation would also:
    • Check AML/KYC
    • Talk to core banking systems
    • Require multi-factor approval, etc.
    """
    payment_id = f"pm_{len(_FAKE_LEDGER)+1:06d}"

    # Log payment processing to APM - this is a critical financial operation!
    if apm_client:
        apm_client.capture_message(
            message=f"PAYMENT PROCESSING: {payload.amount} {payload.currency} from {payload.from_account} to {payload.to_account}",
            level="warning",  # Financial operations should be monitored closely
            labels={
                "security_event": "payment_processing",
                "payment_id": payment_id,
                "amount": str(payload.amount),
                "currency": payload.currency,
                "service": "tools-service",
                "risk_level": "critical"
            },
            extra={
                "from_account": payload.from_account,
                "to_account": payload.to_account,
                "note": payload.note,
                "timestamp": datetime.now(UTC).isoformat()
            }
        )

    # OPTIONAL: In a real app we might run an LLM "fraud check" here. For the
    # purposes of the vulnerable lab we simply log the intent.
    logger.info(
        "Processing payment %s: %s -> %s %.2f %s (note=%s)",
        payment_id,
        payload.from_account,
        payload.to_account,
        payload.amount,
        payload.currency,
        payload.note,
    )

    try:
        record = PaymentResponse(
            payment_id=payment_id,
            status="processed",  # always succeeds
            processed_at=datetime.now(UTC),
            details=payload,
        )
        _FAKE_LEDGER[payment_id] = record
        
        # Log successful payment to APM
        if apm_client:
            apm_client.capture_message(
                message=f"Payment {payment_id} processed successfully",
                level="info",
                labels={
                    "security_event": "payment_completed",
                    "payment_id": payment_id,
                    "service": "tools-service"
                }
            )
            
        return record
        
    except Exception as e:
        # Log payment failure to APM
        if apm_client:
            apm_client.capture_exception(
                exc_info=(type(e), e, e.__traceback__),
                labels={
                    "security_event": "payment_error",
                    "payment_id": payment_id,
                    "service": "tools-service"
                }
            )
        raise


# --------------------------------------------------------------------------- #
# Misc utility endpoints
# --------------------------------------------------------------------------- #
@app.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str):
    """
    Retrieve a previously submitted payment record.

    No auth / ACL checks: anybody can read any payment.
    """
    record = _FAKE_LEDGER.get(payment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Payment not found")
    return record


@app.get("/health")
async def healthcheck():
    """
    Lightweight container health probe for orchestrators / ELB.
    """
    response_data = {"status": "ok", "service": "tools-service", "time": datetime.now(UTC).isoformat()}
    response = JSONResponse(content=response_data)
    
    # Add CORS headers manually
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response