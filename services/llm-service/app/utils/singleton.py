"""
Unified singleton pattern implementation for all services.
Eliminates duplicate singleton code across the application.
"""

from typing import TypeVar, Dict, Optional, Any, Type, Callable
from functools import wraps
import threading

T = TypeVar('T')


class SingletonMeta(type):
    """
    Thread-safe singleton metaclass that can be used by any service.
    """
    _instances: Dict[Type, Any] = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            with cls._lock:
                # Double-check pattern
                if cls not in cls._instances:
                    cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]

    def clear_instance(cls):
        """Clear the singleton instance for testing or reset purposes."""
        with cls._lock:
            cls._instances.pop(cls, None)


def singleton_service(cls: Type[T]) -> Type[T]:
    """
    Decorator that makes a class a singleton service.
    
    Usage:
        @singleton_service
        class MyService:
            pass
    """
    return SingletonMeta(cls.__name__, (cls,), dict(cls.__dict__))


def get_singleton_instance(cls: Type[T], *args, **kwargs) -> T:
    """
    Get or create a singleton instance of a class.
    
    Usage:
        instance = get_singleton_instance(MyService)
    """
    if not hasattr(cls, '_instance'):
        with threading.Lock():
            if not hasattr(cls, '_instance'):
                cls._instance = cls(*args, **kwargs)
    return cls._instance


def singleton_factory(factory_func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator that makes a factory function return singleton instances.
    
    Usage:
        @singleton_factory
        def get_my_service():
            return MyService()
    """
    _instance = None
    _lock = threading.Lock()
    
    @wraps(factory_func)
    def wrapper(*args, **kwargs):
        nonlocal _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = factory_func(*args, **kwargs)
        return _instance
    
    def clear_instance():
        nonlocal _instance
        with _lock:
            _instance = None
    
    wrapper.clear_instance = clear_instance
    return wrapper


# Global singleton registry for debugging and management
_singleton_registry: Dict[str, Any] = {}
_registry_lock = threading.Lock()


def register_singleton(name: str, instance: Any) -> None:
    """Register a singleton instance for debugging/management."""
    with _registry_lock:
        _singleton_registry[name] = instance


def get_registered_singletons() -> Dict[str, Any]:
    """Get all registered singleton instances."""
    with _registry_lock:
        return _singleton_registry.copy()


def clear_all_singletons() -> None:
    """Clear all registered singleton instances (for testing)."""
    with _registry_lock:
        _singleton_registry.clear() 