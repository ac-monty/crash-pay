# shared/utils/apm.py
#
# Centralised APM (Application Performance Monitoring) utility for Python services
# Provides graceful degradation when observability stack is down
# Consistent error tracking across all Python services
# Safe initialization that never crashes the application
#

import os
import logging
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps

# Setup logging
logger = logging.getLogger(__name__)

class APMService:
    def __init__(self):
        self.apm = None
        self.is_initialized = False
        self.initialization_attempts = 0
        self.max_retries = 3
        self.service_name = os.getenv('ELASTIC_APM_SERVICE_NAME', 'unknown-service')
        
        self.initialize()
    
    def initialize(self):
        """Initialize APM with graceful error handling"""
        try:
            # Only initialize if APM server URL is configured
            if not os.getenv('ELASTIC_APM_SERVER_URL'):
                self.log_info('APM not configured (ELASTIC_APM_SERVER_URL not set), continuing without observability')
                return
            
            import elasticapm
            self.apm = elasticapm.get_client()
            
            if not self.apm:
                # Initialize APM client
                config = {
                    'SERVICE_NAME': self.service_name,
                    'SERVER_URL': os.getenv('ELASTIC_APM_SERVER_URL'),
                    'ENVIRONMENT': os.getenv('ELASTIC_APM_ENVIRONMENT', 'development'),
                    'VERIFY_SERVER_CERT': os.getenv('ELASTIC_APM_VERIFY_SERVER_CERT', 'false').lower() == 'true'
                }
                self.apm = elasticapm.Client(config)
            
            self.is_initialized = True
            self.log_info(f'✅ APM initialized successfully for service: {self.service_name}')
            
        except Exception as error:
            self.initialization_attempts += 1
            self.log_warning(f'⚠️ APM initialization failed (attempt {self.initialization_attempts}/{self.max_retries}): {str(error)}')
            
            if self.initialization_attempts < self.max_retries:
                # Don't retry immediately on startup failures
                pass
            else:
                self.log_warning('🔄 Max APM initialization attempts reached, continuing without observability')
    
    def log_info(self, message: str):
        """Safe logging that doesn't depend on APM"""
        logger.info(f'[APM:{self.service_name}] {message}')
    
    def log_warning(self, message: str):
        """Safe logging that doesn't depend on APM"""
        logger.warning(f'[APM:{self.service_name}] {message}')
    
    def log_error(self, message: str, error: Optional[Exception] = None):
        """Safe logging that doesn't depend on APM"""
        if error:
            logger.error(f'[APM:{self.service_name}] {message}', exc_info=error)
        else:
            logger.error(f'[APM:{self.service_name}] {message}')
    
    def is_available(self) -> bool:
        """Check if APM is available and working"""
        return self.is_initialized and self.apm is not None
    
    def capture_error(self, error: Exception, context: Optional[Dict[str, Any]] = None):
        """Safely capture an exception/error"""
        if not self.is_available():
            self.log_error('Error occurred (APM unavailable)', error)
            return
        
        try:
            apm_context = {
                'labels': {
                    'service': self.service_name,
                    'component': 'error-tracking',
                    **(context.get('labels', {}) if context else {})
                },
                'user': context.get('user', {}) if context else {},
                'custom': context.get('custom', {}) if context else {}
            }
            
            self.apm.capture_exception(exc_info=(type(error), error, error.__traceback__), **apm_context)
            self.log_info(f'Error captured in APM: {str(error)}')
            
        except Exception as apm_error:
            self.log_warning(f'APM error capture failed: {str(apm_error)}')
            self.log_error('Original error (APM capture failed)', error)
    
    def capture_message(self, message: str, level: str = 'info', context: Optional[Dict[str, Any]] = None):
        """Safely capture a custom message/warning"""
        if not self.is_available():
            self.log_info(f'Message (APM unavailable): {message}')
            return
        
        try:
            apm_context = {
                'labels': {
                    'service': self.service_name,
                    'component': 'message-tracking',
                    'level': level,
                    **(context.get('labels', {}) if context else {})
                },
                'user': context.get('user', {}) if context else {},
                'custom': context.get('custom', {}) if context else {}
            }
            
            self.apm.capture_message(message, level=level, **apm_context)
            self.log_info(f'Message captured in APM: {message}')
            
        except Exception as apm_error:
            self.log_warning(f'APM message capture failed: {str(apm_error)}')
            self.log_info(f'Message (APM capture failed): {message}')
    
    def start_transaction(self, name: str, transaction_type: str = 'custom') -> Optional[Any]:
        """Start a custom transaction"""
        if not self.is_available():
            self.log_info(f'Transaction started (APM unavailable): {name}')
            return None
        
        try:
            transaction = self.apm.begin_transaction(transaction_type)
            transaction.name = name
            self.log_info(f'Transaction started: {name}')
            return transaction
        except Exception as apm_error:
            self.log_warning(f'APM transaction start failed: {str(apm_error)}')
            return None
    
    def end_transaction(self, transaction: Optional[Any], result: str = 'success'):
        """End a transaction with result"""
        if not transaction or not self.is_available():
            return
        
        try:
            transaction.result = result
            self.apm.end_transaction(transaction.name, result)
            self.log_info(f'Transaction ended: {result}')
        except Exception as apm_error:
            self.log_warning(f'APM transaction end failed: {str(apm_error)}')
    
    def start_span(self, name: str, span_type: str = 'custom') -> Optional[Any]:
        """Create a custom span for performance monitoring"""
        if not self.is_available():
            return None
        
        try:
            span = self.apm.begin_span(name, span_type)
            return span
        except Exception as apm_error:
            self.log_warning(f'APM span start failed: {str(apm_error)}')
            return None
    
    def end_span(self, span: Optional[Any]):
        """End a span"""
        if not span or not self.is_available():
            return
        
        try:
            self.apm.end_span()
        except Exception as apm_error:
            self.log_warning(f'APM span end failed: {str(apm_error)}')
    
    def set_user(self, user: Dict[str, Any]):
        """Set user context for current transaction"""
        if not self.is_available():
            return
        
        try:
            self.apm.set_user_context(**user)
        except Exception as apm_error:
            self.log_warning(f'APM set user context failed: {str(apm_error)}')
    
    def add_labels(self, labels: Dict[str, Any]):
        """Add custom labels to current transaction"""
        if not self.is_available():
            return
        
        try:
            self.apm.label(**labels)
        except Exception as apm_error:
            self.log_warning(f'APM add labels failed: {str(apm_error)}')
    
    def get_health_status(self) -> Dict[str, Any]:
        """Health check for APM service"""
        return {
            'service': 'apm',
            'status': 'healthy' if self.is_available() else 'degraded',
            'initialized': self.is_initialized,
            'attempts': self.initialization_attempts,
            'message': 'APM operational' if self.is_available() else 'APM unavailable, using fallback logging'
        }

# Create singleton instance
apm_service = APMService()

# Convenience functions for direct use
def capture_error(error: Exception, context: Optional[Dict[str, Any]] = None):
    apm_service.capture_error(error, context)

def capture_message(message: str, level: str = 'info', context: Optional[Dict[str, Any]] = None):
    apm_service.capture_message(message, level, context)

def start_transaction(name: str, transaction_type: str = 'custom') -> Optional[Any]:
    return apm_service.start_transaction(name, transaction_type)

def end_transaction(transaction: Optional[Any], result: str = 'success'):
    apm_service.end_transaction(transaction, result)

def start_span(name: str, span_type: str = 'custom') -> Optional[Any]:
    return apm_service.start_span(name, span_type)

def end_span(span: Optional[Any]):
    apm_service.end_span(span)

def set_user(user: Dict[str, Any]):
    apm_service.set_user(user)

def add_labels(labels: Dict[str, Any]):
    apm_service.add_labels(labels)

def is_available() -> bool:
    return apm_service.is_available()

def get_health_status() -> Dict[str, Any]:
    return apm_service.get_health_status()

# Decorator for automatic error capture
def apm_capture_errors(func: Callable) -> Callable:
    """Decorator to automatically capture errors in APM"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            capture_error(e, {
                'labels': {
                    'function': func.__name__,
                    'module': func.__module__
                }
            })
            raise
    return wrapper

# Decorator for automatic transaction tracking
def apm_transaction(name: Optional[str] = None, transaction_type: str = 'custom'):
    """Decorator to automatically track function as APM transaction"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            transaction_name = name or f'{func.__module__}.{func.__name__}'
            transaction = start_transaction(transaction_name, transaction_type)
            
            try:
                result = func(*args, **kwargs)
                end_transaction(transaction, 'success')
                return result
            except Exception as e:
                end_transaction(transaction, 'error')
                capture_error(e, {
                    'labels': {
                        'function': func.__name__,
                        'module': func.__module__
                    }
                })
                raise
        return wrapper
    return decorator 