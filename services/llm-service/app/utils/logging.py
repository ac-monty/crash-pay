"""
Enhanced logging utilities for the LLM service.
Provides standardized logging with consistent formatting and enhanced debugging capabilities.
"""

import logging
import logging.config
import json
import os
import time
import functools
import threading
from typing import Dict, Any, Optional, Callable, List
from contextlib import contextmanager
from pathlib import Path
from app.config.settings import get_settings


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a standardized logger instance.
    
    Args:
        name: Logger name. If None, uses the caller's __name__
        
    Returns:
        Configured logger with standardized formatting
    """
    if name is None:
        import inspect
        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')
    
    # Get or create logger
    logger = logging.getLogger(name)
    
    # Ensure logger is configured if not already
    if not logger.handlers:
        # Set up console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        
        # Standard format: Date Time - LEVEL - __name__ - message
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        console_handler.setFormatter(formatter)
        
        # Set up file handler
        file_handler = logging.FileHandler('/tmp/llm-service.log', mode='a')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        
        # Add handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.setLevel(logging.DEBUG)
        
        # Prevent propagation to avoid duplicate logs
        logger.propagate = False
    
    return logger


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter that adds colors to log levels and key information for console output.
    """
    
    # Color codes
    COLORS = {
        'DEBUG': '\033[96m',    # Light blue
        'INFO': '\033[97m',     # White
        'WARNING': '\033[93m',  # Yellow
        'ERROR': '\033[91m',    # Red
        'CRITICAL': '\033[91m'  # Red
    }
    
    # Additional colors for specific content
    CONTENT_COLORS = {
        'PROVIDER': '\033[94m',     # Navy blue
        'MODEL': '\033[34m',        # Blue
        'REQUEST_ID': '\033[95m',   # Magenta
        'FUNCTION': '\033[32m',     # Green
    }
    
    RESET = '\033[0m'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def format(self, record):
        # Get the original formatted message
        original_format = super().format(record)
        
        # Add colors for log level
        level_color = self.COLORS.get(record.levelname, '')
        if level_color:
            # Color the level name
            colored_level = f"{level_color}{record.levelname}{self.RESET}"
            # Replace the level name in the formatted message
            formatted_msg = original_format.replace(record.levelname, colored_level)
        else:
            formatted_msg = original_format
        
        # Add colors for specific content patterns
        formatted_msg = self._add_content_colors(formatted_msg)
        
        return formatted_msg
    
    def _add_content_colors(self, message: str) -> str:
        """Add colors to specific content patterns in the message."""
        import re
        
        # Color Provider names (Provider: openai, Provider openai, etc.)
        provider_pattern = r'(Provider:?\s*)([a-zA-Z_][a-zA-Z0-9_]*)'
        message = re.sub(provider_pattern, 
                        lambda m: f"{m.group(1)}{self.CONTENT_COLORS['PROVIDER']}{m.group(2)}{self.RESET}", 
                        message)
        
        # Color Model names (Model: gpt-4, Model gpt-4, etc.)
        model_pattern = r'(Model:?\s*)([a-zA-Z0-9._-]+)'
        message = re.sub(model_pattern, 
                        lambda m: f"{m.group(1)}{self.CONTENT_COLORS['MODEL']}{m.group(2)}{self.RESET}", 
                        message)
        
        # Color Request IDs (req_123, request_id: req_123, etc.)
        request_id_pattern = r'(request_id:?\s*)?(req_[a-zA-Z0-9_]+)'
        message = re.sub(request_id_pattern, 
                        lambda m: f"{m.group(1) or ''}{self.CONTENT_COLORS['REQUEST_ID']}{m.group(2)}{self.RESET}", 
                        message)
        
        # Color Function names (Function: transfer_funds, Function transfer_funds, etc.)
        function_pattern = r'(Function:?\s*)([a-zA-Z_][a-zA-Z0-9_]*)'
        message = re.sub(function_pattern, 
                        lambda m: f"{m.group(1)}{self.CONTENT_COLORS['FUNCTION']}{m.group(2)}{self.RESET}", 
                        message)
        
        # Color provider/model in combined format (openai/gpt-4)
        combined_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)/([a-zA-Z0-9._-]+)'
        message = re.sub(combined_pattern, 
                        lambda m: f"{self.CONTENT_COLORS['PROVIDER']}{m.group(1)}{self.RESET}/{self.CONTENT_COLORS['MODEL']}{m.group(2)}{self.RESET}", 
                        message)
        
        return message


def load_logging_config():
    """Load logging configuration from JSON file."""
    config_path = Path(__file__).parent.parent / 'config' / 'logging_config.json'
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"Error loading logging config: {e}")
    
    # Fallback to default config
    return {
        "version": 1,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "standard"
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"]
        }
    }


def setup_colored_logging():
    """Setup logging with colors and proper configuration."""
    # Load configuration
    config = load_logging_config()
    
    # Create a custom handler for colored console output
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # Use our colored formatter
    formatter = ColoredFormatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    # Create file handler
    file_handler = logging.FileHandler('/tmp/llm-service.log', mode='a')
    file_handler.setLevel(logging.INFO)
    
    # Use standard formatter for file (no colors)
    file_formatter = logging.Formatter(
        fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Add our handlers
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger


# Global APM client variables
apm_client = None
apm_middleware_enabled = False
_loggers_cache = {}
_cache_lock = threading.Lock()


class LoggerFactory:
    """
    Flexible logger factory that creates specialized loggers on demand.
    Supports easy expansion of logging categories and custom formatting.
    """
    
    _default_categories = {
        'llm_api': {
            'file': '/tmp/llm-api.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - Provider:%(provider)s - Model:%(model)s - %(message)s',
            'level': 'INFO'
        },
        'api_debug': {
            'file': '/tmp/api-debug.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [API] %(message)s',
            'level': 'DEBUG'
        },
        'system_prompts': {
            'file': '/tmp/system-prompts.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [PROMPT] %(message)s',
            'level': 'DEBUG'
        },
        'performance': {
            'file': '/tmp/performance.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [PERF] %(message)s',
            'level': 'INFO'
        },
        'security': {
            'file': '/tmp/security.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [SECURITY] %(message)s',
            'level': 'WARNING'
        },
        'service_debug': {
            'file': '/tmp/service-debug.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [SERVICE] %(service)s - %(message)s',
            'level': 'DEBUG'
        },
        'function_calls': {
            'file': '/tmp/function-calls.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [FUNCTIONS] %(message)s',
            'level': 'DEBUG'
        },
        'error_context': {
            'file': '/tmp/error-context.log',
            'format': '%(asctime)s - %(levelname)s - %(name)s - [ERROR] %(message)s',
            'level': 'ERROR'
        }
    }
    
    @classmethod
    def get_logger(cls, category: str, **custom_config) -> logging.Logger:
        """
        Get or create a logger for a specific category.
        
        Args:
            category: Logger category (e.g., 'api_debug', 'performance')
            **custom_config: Override default configuration
        
        Returns:
            Configured logger instance
        """
        global _loggers_cache
        
        with _cache_lock:
            if category in _loggers_cache:
                return _loggers_cache[category]
            
            # Get configuration
            config = cls._default_categories.get(category, {})
            config.update(custom_config)
            
            # Set defaults if not provided
            log_file = config.get('file', f'/tmp/{category}.log')
            log_format = config.get('format', '%(asctime)s - %(levelname)s - %(name)s - %(message)s')
            log_level = config.get('level', 'INFO')
            
            # Create logger
            logger = logging.getLogger(category)
            logger.setLevel(getattr(logging, log_level.upper()))
            
            # Avoid duplicate handlers
            if not logger.handlers:
                # File handler
                file_handler = logging.FileHandler(log_file)
                file_formatter = logging.Formatter(
                    fmt=log_format,
                    datefmt="%Y-%m-%d %H:%M:%S"
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)
                
                # Add console handler with colors for debug mode
                settings = get_settings()
                if settings.debug_mode and category in ['error_context', 'security', 'performance']:
                    console_handler = logging.StreamHandler()
                    console_formatter = ColoredFormatter(
                        fmt=f'[{category.upper()}] %(levelname)s - %(message)s',
                        datefmt="%Y-%m-%d %H:%M:%S"
                    )
                    console_handler.setFormatter(console_formatter)
                    logger.addHandler(console_handler)
            
            _loggers_cache[category] = logger
            return logger
    
    @classmethod
    def add_custom_category(cls, category: str, config: Dict[str, Any]) -> None:
        """
        Add a new custom logging category.
        
        Args:
            category: New category name
            config: Logger configuration dict
        """
        cls._default_categories[category] = config
        
        # Clear cache to force recreation
        with _cache_lock:
            if category in _loggers_cache:
                del _loggers_cache[category]
    
    @classmethod
    def list_categories(cls) -> List[str]:
        """List all available logging categories."""
        return list(cls._default_categories.keys())


class PerformanceLogger:
    """
    Enhanced performance monitoring with detailed timing and resource tracking.
    """
    
    def __init__(self):
        self.logger = LoggerFactory.get_logger('performance')
        self._timers = {}
        self._counters = {}
        
    def start_timer(self, operation: str, **context) -> str:
        """Start a performance timer for an operation."""
        timer_id = f"{operation}_{int(time.time() * 1000000)}"  # Microsecond precision
        self._timers[timer_id] = {
            'operation': operation,
            'start_time': time.perf_counter(),
            'context': context
        }
        
        if get_settings().debug_mode:
            self.logger.debug(f"Started timer for {operation} (ID: {timer_id})", extra=context)
        
        return timer_id
    
    def end_timer(self, timer_id: str, **additional_context) -> float:
        """End a performance timer and log the result."""
        if timer_id not in self._timers:
            self.logger.warning(f"Timer {timer_id} not found")
            return 0.0
        
        timer_info = self._timers.pop(timer_id)
        duration = time.perf_counter() - timer_info['start_time']
        
        context = {**timer_info['context'], **additional_context}
        context['duration_seconds'] = duration
        context['duration_ms'] = duration * 1000
        
        # Log with different levels based on duration
        if duration > 5.0:  # > 5 seconds
            level = 'warning'
            prefix = "SLOW"
        elif duration > 1.0:  # > 1 second
            level = 'info'
            prefix = "NORMAL"
        else:
            level = 'debug'
            prefix = "FAST"
        
        message = f"{prefix} {timer_info['operation']} completed in {duration:.3f}s"
        getattr(self.logger, level)(message, extra=context)
        
        return duration
    
    def increment_counter(self, counter_name: str, value: int = 1, **context) -> None:
        """Increment a performance counter."""
        if counter_name not in self._counters:
            self._counters[counter_name] = 0
        
        self._counters[counter_name] += value
        
        if get_settings().debug_mode:
            self.logger.debug(f"Counter {counter_name} incremented to {self._counters[counter_name]}", extra=context)
    
    def get_counters(self) -> Dict[str, int]:
        """Get all performance counters."""
        return self._counters.copy()
    
    def reset_counters(self) -> None:
        """Reset all performance counters."""
        self._counters.clear()


class ServiceLogger:
    """
    Service-specific logger with enhanced context and debugging.
    """
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.logger = LoggerFactory.get_logger('service_debug')
        self.performance = PerformanceLogger()
    
    def debug(self, message: str, **context) -> None:
        """Log debug message with service context."""
        context['service'] = self.service_name
        self.logger.debug(message, extra=context)
    
    def info(self, message: str, **context) -> None:
        """Log info message with service context."""
        context['service'] = self.service_name
        self.logger.info(message, extra=context)
    
    def warning(self, message: str, **context) -> None:
        """Log warning message with service context."""
        context['service'] = self.service_name
        self.logger.warning(message, extra=context)
    
    def error(self, message: str, error: Optional[Exception] = None, **context) -> None:
        """Log error message with enhanced context."""
        context['service'] = self.service_name
        
        if error:
            context['error_type'] = type(error).__name__
            context['error_details'] = str(error)
            
            # Log to error context logger for detailed analysis
            error_logger = LoggerFactory.get_logger('error_context')
            error_logger.error(f"[{self.service_name}] {message}", extra=context, exc_info=error)
        
        self.logger.error(message, extra=context)
    
    @contextmanager
    def performance_context(self, operation: str, **context):
        """Context manager for performance monitoring."""
        timer_id = self.performance.start_timer(f"{self.service_name}.{operation}", **context)
        try:
            yield
        finally:
            self.performance.end_timer(timer_id)


def performance_monitor(operation_name: Optional[str] = None):
    """
    Decorator for automatic performance monitoring of functions.
    
    Args:
        operation_name: Custom operation name, defaults to function name
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            perf_logger = PerformanceLogger()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            timer_id = perf_logger.start_timer(op_name, function=func.__name__)
            try:
                result = await func(*args, **kwargs)
                perf_logger.end_timer(timer_id, status='success')
                return result
            except Exception as e:
                perf_logger.end_timer(timer_id, status='error', error=str(e))
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            perf_logger = PerformanceLogger()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            timer_id = perf_logger.start_timer(op_name, function=func.__name__)
            try:
                result = func(*args, **kwargs)
                perf_logger.end_timer(timer_id, status='success')
                return result
            except Exception as e:
                perf_logger.end_timer(timer_id, status='error', error=str(e))
                raise
        
        # Return the appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Global performance logger instance
_global_performance_logger = None

def get_performance_logger() -> PerformanceLogger:
    """Get the global performance logger instance."""
    global _global_performance_logger
    if _global_performance_logger is None:
        _global_performance_logger = PerformanceLogger()
    return _global_performance_logger


def get_service_logger(service_name: str) -> ServiceLogger:
    """Get a service-specific logger."""
    return ServiceLogger(service_name)


# Enhanced logging functions with better error context
def log_security_event(level: str, message: str, **context):
    """Log security-related events with enhanced context."""
    security_logger = LoggerFactory.get_logger('security')
    
    # Add security-specific context
    context['timestamp'] = time.time()
    context['alert_type'] = 'security'
    
    # Add source information if available
    import inspect
    frame = inspect.currentframe().f_back
    if frame:
        context['source_file'] = frame.f_code.co_filename
        context['source_line'] = frame.f_lineno
        context['source_function'] = frame.f_code.co_name
    
    getattr(security_logger, level.lower())(message, extra=context)
    
    # Also log to main logger for visibility
    main_logger = get_logger(__name__)
    main_logger.log(getattr(logging, level.upper()), f"SECURITY: {message}")


def log_function_call(function_name: str, arguments: Dict[str, Any], result: Any = None, error: Exception = None, **context):
    """Log function calls with detailed context."""
    func_logger = LoggerFactory.get_logger('function_calls')
    
    log_data = {
        'function_name': function_name,
        'arguments': arguments,
        'timestamp': time.time(),
        **context
    }
    
    if result is not None:
        log_data['result'] = str(result)[:1000]  # Truncate long results
        log_data['result_type'] = type(result).__name__
        func_logger.info(f"Function {function_name} executed successfully", extra=log_data)
    elif error:
        log_data['error'] = str(error)
        log_data['error_type'] = type(error).__name__
        func_logger.error(f"Function {function_name} failed", extra=log_data)
    else:
        func_logger.debug(f"Function {function_name} called", extra=log_data)


# Keep existing functions for backward compatibility but enhance them


def initialize_apm() -> None:
    """Initialize Elastic APM client."""
    global apm_client, apm_middleware_enabled
    
    try:
        import elasticapm
        from elasticapm.contrib.starlette import make_apm_client
        
        settings = get_settings()
        
        # Initialize APM client
        apm_config = {
            'SERVICE_NAME': settings.elastic_apm_service_name,
            'SERVER_URL': settings.elastic_apm_server_url,
            'ENVIRONMENT': settings.elastic_apm_environment,
            'VERIFY_SERVER_CERT': settings.elastic_apm_verify_server_cert,
            'CAPTURE_BODY': 'transactions',
            'CAPTURE_HEADERS': True,
        }
        
        apm_client = make_apm_client(apm_config)
        apm_middleware_enabled = True
        
        logger = logging.getLogger(__name__)
        logger.info("✅ APM client initialized successfully")
        
    except ImportError as e:
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️ APM client not available: {e}")
        apm_client = None
        apm_middleware_enabled = False
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"APM client initialization failed: {e}")
        apm_client = None
        apm_middleware_enabled = False


def setup_logging() -> None:
    """Configure application logging with enhanced debug support and colors."""
    try:
        settings = get_settings()
        
        # Load and apply JSON logging configuration
        config = load_logging_config()
        
        # Apply the configuration using dictConfig
        logging.config.dictConfig(config)
        
        # Now replace the console handler with our colored formatter
        # Get the console handler and replace its formatter
        for handler_name, handler_config in config.get('handlers', {}).items():
            if handler_name == 'console' and handler_config.get('formatter') == 'colored':
                # Find the actual handler in the root logger or specific loggers
                root_logger = logging.getLogger()
                for handler in root_logger.handlers:
                    if isinstance(handler, logging.StreamHandler) and handler.stream.name == '<stdout>':
                        # Replace with colored formatter
                        colored_formatter = ColoredFormatter(
                            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S"
                        )
                        handler.setFormatter(colored_formatter)
                        break
                
                # Also update handlers for specific loggers
                for logger_name in ['llm_service', 'app']:
                    logger = logging.getLogger(logger_name)
                    for handler in logger.handlers:
                        if isinstance(handler, logging.StreamHandler) and handler.stream.name == '<stdout>':
                            colored_formatter = ColoredFormatter(
                                fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                                datefmt="%Y-%m-%d %H:%M:%S"
                            )
                            handler.setFormatter(colored_formatter)
        
        # Now explicitly set the external library loggers to WARNING to suppress noise
        # This ensures they don't inherit DEBUG from root or other loggers
        external_loggers = [
            'elasticapm', 'elasticapm.transport', 'elasticapm.transport.http', 
            'elasticapm.metrics', 'elasticapm.conf',
            'pymongo', 'pymongo.connection', 'pymongo.topology',
            'urllib3', 'urllib3.connectionpool', 'urllib3.util.retry',
            'httpx', 'httpcore', 'httpcore.connection', 'httpcore.http11'
        ]
        
        for logger_name in external_loggers:
            external_logger = logging.getLogger(logger_name)
            external_logger.setLevel(logging.WARNING)
            external_logger.propagate = False
        
        log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
        
        # Initialize all logger categories using the factory
        if settings.debug_mode:
            print(f"Debug mode enabled - Log level: {settings.log_level}")
            print(f"Enhanced logging categories: {LoggerFactory.list_categories()}")
            print(f"External loggers suppressed: {external_loggers}")
            print("Colored logging enabled for console output")
            
            # Force initialization of all debug loggers
            for category in LoggerFactory.list_categories():
                LoggerFactory.get_logger(category)
        
    except Exception as e:
        # Fallback to basic logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
        )
        logger = get_logger(__name__)
        logger.error(f"Failed to setup enhanced logging: {e}")


def get_apm_client():
    """Get the global APM client instance."""
    return apm_client


def is_apm_enabled() -> bool:
    """Check if APM middleware is enabled."""
    return apm_middleware_enabled


def log_llm_event(level: str, message: str, provider: str = "unknown", model: str = "unknown", **kwargs):
    """Enhanced LLM event logging with performance monitoring and security alerts."""
    global apm_client
    
    # Use enhanced logger
    llm_logger = LoggerFactory.get_logger('llm_api')
    
    extra = {"provider": provider, "model": model, **kwargs}
    
    # Enhanced logging with more context
    if "request_id" in kwargs:
        extra["request_id"] = kwargs["request_id"]
    if "user_input" in kwargs:
        # Log first 100 chars of input for security analysis
        extra["input_preview"] = kwargs["user_input"][:100] + ("..." if len(kwargs["user_input"]) > 100 else "")
        extra["input_length"] = len(kwargs["user_input"])
    if "response_tokens" in kwargs:
        extra["response_tokens"] = kwargs["response_tokens"]
    if "total_time" in kwargs:
        extra["duration_seconds"] = kwargs["total_time"]
    if "error" in kwargs:
        extra["error_type"] = type(kwargs["error"]).__name__
        extra["error_details"] = str(kwargs["error"])
    
    # Enhanced security-relevant flags
    security_alerts = []
    if "dangerous_tools_used" in kwargs:
        security_alerts.append("DANGEROUS_TOOLS_INVOKED")
        extra["security_alert"] = "DANGEROUS_TOOLS_INVOKED"
        extra["tools_used"] = kwargs["dangerous_tools_used"]
    if "shell_command" in kwargs:
        security_alerts.append("SHELL_EXECUTION")
        extra["security_alert"] = "SHELL_EXECUTION"
        extra["shell_command"] = kwargs["shell_command"]
    if "payment_call" in kwargs:
        security_alerts.append("PAYMENT_API_CALL")
        extra["security_alert"] = "PAYMENT_API_CALL"
        extra["payment_payload"] = kwargs["payment_call"]
    
    # Log security events to dedicated logger
    if security_alerts:
        log_security_event(level, f"Security alert in LLM operation: {', '.join(security_alerts)}", **extra)
    
    # Log to LLM-specific logger
    getattr(llm_logger, level.lower())(message, extra=extra)
    
    # Performance monitoring
    if "total_time" in kwargs:
        perf_logger = get_performance_logger()
        perf_logger.increment_counter(f"llm_requests_{provider}_{model}")
        if kwargs["total_time"] > 5.0:
            perf_logger.increment_counter("slow_llm_requests")
    
    # Send critical errors and security events to APM
    if apm_client and level.lower() in ["error", "warning"]:
        try:
            # Create APM labels for better filtering
            apm_labels = {
                "llm_provider": provider,
                "llm_model": model,
                "service_component": "llm_operations"
            }
            
            if "request_id" in extra:
                apm_labels["request_id"] = extra["request_id"]
            if "security_alert" in extra:
                apm_labels["security_alert"] = extra["security_alert"]
                
            # Capture error in APM if there's an actual exception
            if "error" in kwargs and isinstance(kwargs["error"], Exception):
                apm_client.capture_exception(
                    exc_info=(type(kwargs["error"]), kwargs["error"], kwargs["error"].__traceback__),
                    labels=apm_labels,
                    extra={"llm_context": extra}
                )
            else:
                # Capture as custom event for security alerts and warnings
                apm_client.capture_message(
                    message=f"[{level.upper()}] {provider}/{model}: {message}",
                    level=level.lower(),
                    labels=apm_labels,
                    extra={"llm_context": extra}
                )
        except Exception as apm_error:
            # Don't let APM errors break the main flow
            logger = get_logger(__name__)
            logger.warning(f"APM capture failed: {apm_error}")
    
    # Also log to console for development
    if level.lower() in ["error", "warning"]:
        console_msg = f"[{level}] {provider}/{model}: {message}"
        if "request_id" in extra:
            console_msg += f" (ID: {extra['request_id']})"
        if "error_details" in extra:
            console_msg += f" - {extra['error_details']}"
        
        logger = get_logger(__name__)
        logger.log(getattr(logging, level.upper()), console_msg)


def get_recent_logs(limit: int = 50, category: str = 'llm_api') -> list:
    """Get recent log entries from a specific log category."""
    try:
        config = LoggerFactory._default_categories.get(category, {})
        log_file = config.get('file', '/tmp/llm-api.log')
        
        with open(log_file, 'r') as f:
            lines = f.readlines()
            return lines[-limit:] if len(lines) > limit else lines
    except FileNotFoundError:
        return []
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Failed to read log file {category}: {e}")
        return []


def debug_log_api_request(provider: str, model: str, request_data: dict, request_id: str = None):
    """Enhanced API request logging with performance tracking."""
    try:
        settings = get_settings()
        if not settings.debug_mode or not settings.log_api_requests:
            return
        
        api_logger = LoggerFactory.get_logger('api_debug')
        
        # Track request size and timing
        perf_logger = get_performance_logger()
        perf_logger.increment_counter("api_requests")
        
        # Sanitize sensitive data
        safe_data = request_data.copy()
        if 'messages' in safe_data:
            # Log message structure but truncate long content
            safe_messages = []
            total_chars = 0
            for msg in safe_data['messages']:
                safe_msg = msg.copy()
                if 'content' in safe_msg:
                    content_length = len(safe_msg['content'])
                    total_chars += content_length
                    if content_length > 500:
                        safe_msg['content'] = safe_msg['content'][:500] + f"... [TRUNCATED - {content_length} chars total]"
                safe_messages.append(safe_msg)
            safe_data['messages'] = safe_messages
            safe_data['total_input_chars'] = total_chars
        
        # Remove API keys
        safe_data.pop('api_key', None)
        
        log_msg = f"REQUEST to {provider}/{model}"
        if request_id:
            log_msg += f" (ID: {request_id})"
        log_msg += f" - Request Data: {safe_data}"
        
        api_logger.debug(log_msg)
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to log API request: {e}")


def debug_log_api_response(provider: str, model: str, response_data: dict, request_id: str = None):
    """Enhanced API response logging with performance tracking."""
    try:
        settings = get_settings()
        if not settings.debug_mode or not settings.log_api_responses:
            return
        
        api_logger = LoggerFactory.get_logger('api_debug')
        
        # Track response size
        perf_logger = get_performance_logger()
        perf_logger.increment_counter("api_responses")
        
        # Sanitize sensitive data
        safe_data = response_data.copy()
        if 'response' in safe_data:
            response_length = len(safe_data['response'])
            safe_data['response_length'] = response_length
            if response_length > 1000:
                safe_data['response'] = safe_data['response'][:1000] + f"... [TRUNCATED - {response_length} chars total]"
        
        log_msg = f"RESPONSE from {provider}/{model}"
        if request_id:
            log_msg += f" (ID: {request_id})"
        log_msg += f" - Response Data: {safe_data}"
        
        api_logger.debug(log_msg)
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to log API response: {e}")


def debug_log_system_prompt(provider: str, model: str, system_prompt: str, request_id: str = None):
    """Enhanced system prompt logging."""
    try:
        settings = get_settings()
        if not settings.debug_mode or not settings.log_system_prompts:
            return
        
        prompt_logger = LoggerFactory.get_logger('system_prompts')
        
        log_msg = f"SYSTEM PROMPT for {provider}/{model}"
        if request_id:
            log_msg += f" (ID: {request_id})"
        log_msg += f" - System Prompt: {system_prompt}"
        log_msg += f" - Length: {len(system_prompt)} characters"
        
        prompt_logger.debug(log_msg)
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to log system prompt: {e}")


def debug_log_function_context(provider: str, model: str, functions: list, user_permissions: list, request_id: str = None):
    """Enhanced function calling context logging."""
    try:
        settings = get_settings()
        if not settings.debug_mode:
            return
        
        func_logger = LoggerFactory.get_logger('function_calls')
        
        function_names = [f.get('name', 'unnamed') for f in functions]
        
        log_msg = f"FUNCTION CONTEXT for {provider}/{model}"
        if request_id:
            log_msg += f" (ID: {request_id})"
        log_msg += f" - Functions Available ({len(functions)}): {function_names}"
        log_msg += f" - User Permissions: {user_permissions}"
        
        func_logger.debug(log_msg)
        
        # Also log each function for detailed analysis
        for func in functions:
            log_function_call(
                func.get('name', 'unnamed'),
                {'description': func.get('description', ''), 'parameters': func.get('parameters', {})},
                request_id=request_id,
                provider=provider,
                model=model,
                context='function_definition'
            )
        
    except Exception as e:
        logger = get_logger(__name__)
        logger.warning(f"Failed to log function context: {e}")


# New utility functions for enhanced logging
def get_log_stats() -> Dict[str, Any]:
    """Get comprehensive logging statistics."""
    perf_logger = get_performance_logger()
    counters = perf_logger.get_counters()
    
    stats = {
        'performance_counters': counters,
        'available_categories': LoggerFactory.list_categories(),
        'debug_mode': get_settings().debug_mode,
        'log_level': get_settings().log_level
    }
    
    return stats


def cleanup_logs(max_lines: int = 10000) -> Dict[str, int]:
    """Clean up log files that have grown too large."""
    cleanup_stats = {}
    
    for category in LoggerFactory.list_categories():
        config = LoggerFactory._default_categories[category]
        log_file = config.get('file', f'/tmp/{category}.log')
        
        try:
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    lines = f.readlines()
                
                if len(lines) > max_lines:
                    # Keep only the last max_lines
                    with open(log_file, 'w') as f:
                        f.writelines(lines[-max_lines:])
                    
                    cleanup_stats[category] = len(lines) - max_lines
                else:
                    cleanup_stats[category] = 0
        except Exception as e:
            logger = get_logger(__name__)
            logger.warning(f"Failed to cleanup log file {log_file}: {e}")
            cleanup_stats[category] = -1
    
    return cleanup_stats 


def test_colored_logging():
    """Test function to verify colored logging is working correctly."""
    # Setup logging
    setup_colored_logging()
    
    # Get a test logger
    test_logger = get_logger('test_logger')
    
    print("\n--- Testing colored logging system ---")
    print("=" * 50)
    
    # Test different log levels with colors
    test_logger.debug("This is a DEBUG message (should be light blue)")
    test_logger.info("This is an INFO message (should be white)")
    test_logger.warning("This is a WARNING message (should be yellow)")
    test_logger.error("This is an ERROR message (should be red)")
    test_logger.critical("This is a CRITICAL message (should be red)")
    
    print("=" * 50)
    print("Color logging test completed!")
    print("Check the logs above for different colors.")
    print("Also check /tmp/llm-service.log for file output (no colors).")
    
    # Test with LoggerFactory
    print("\n--- Testing LoggerFactory with colors ---")
    print("=" * 50)
    
    categories = ['api_debug', 'performance', 'security']
    for category in categories:
        logger = LoggerFactory.get_logger(category)
        logger.info(f"Testing {category} logger")
        logger.warning(f"Warning from {category}")
        logger.error(f"Error from {category}")
    
    print("=" * 50)
    print("LoggerFactory color test completed!")


if __name__ == "__main__":
    test_colored_logging() 