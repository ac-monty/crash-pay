"""
System prompt loader and management service.
Loads system prompts from JSON configuration and provides them to the LLM service.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path
from app.utils.singleton import singleton_factory
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SystemPromptLoader:
    """Loads and manages system prompts from JSON configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the system prompt loader."""
        if config_path is None:
            # Default path relative to this file
            config_path = Path(__file__).parent / "system_prompts.json"
        
        self.config_path = Path(config_path)
        self._prompts_config = None
        logger.info(f"Initializing SystemPromptLoader with config path: {self.config_path}")
        self._load_prompts()
    
    def _load_prompts(self) -> None:
        """Load system prompts from JSON configuration file."""
        try:
            logger.info(f"Loading system prompts from {self.config_path}")
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._prompts_config = json.load(f)
            
            # Log summary of loaded prompts
            if self._prompts_config:
                system_prompts = self._prompts_config.get("system_prompts", {})
                total_prompts = sum(len(category_prompts) for category_prompts in system_prompts.values())
                categories = list(system_prompts.keys())
                logger.info(f"Successfully loaded {total_prompts} prompts across {len(categories)} categories: {categories}")
                
                # Log defaults
                defaults = self._prompts_config.get("default_prompts", {})
                if defaults:
                    logger.info(f"Default prompts configured: {defaults}")
            else:
                logger.warning("Loaded prompts configuration is empty")
                
        except FileNotFoundError:
            logger.error(f"System prompts configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"System prompts configuration file not found: {self.config_path}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in system prompts configuration: {e}")
            raise ValueError(f"Invalid JSON in system prompts configuration: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading system prompts: {e}")
            raise
    
    def reload_prompts(self) -> None:
        """Reload prompts from configuration file (useful for runtime updates)."""
        logger.info("Reloading system prompts from configuration file")
        old_config = self._prompts_config
        self._load_prompts()
        logger.info("System prompts reloaded successfully")
        
        # Log if configuration changed
        if old_config != self._prompts_config:
            logger.info("System prompt configuration has changed after reload")
        else:
            logger.info("System prompt configuration unchanged after reload")
    
    def get_prompt(self, category: str, prompt_id: str) -> Optional[str]:
        """
        Get a specific system prompt by category and ID.
        
        Args:
            category: The prompt category (e.g., 'function_calling', 'chat_only')
            prompt_id: The prompt identifier (e.g., 'banking_assistant')
            
        Returns:
            The system prompt string or None if not found
        """
        logger.debug(f"Requesting prompt: category='{category}', prompt_id='{prompt_id}'")
        
        if not self._prompts_config:
            logger.warning("No prompts configuration loaded")
            return None
        
        category_prompts = self._prompts_config.get("system_prompts", {}).get(category, {})
        if not category_prompts:
            logger.warning(f"Category '{category}' not found in system prompts")
            return None
        
        prompt_config = category_prompts.get(prompt_id, {})
        if not prompt_config:
            logger.warning(f"Prompt ID '{prompt_id}' not found in category '{category}'")
            return None
        
        prompt = prompt_config.get("prompt")
        if prompt:
            logger.debug(f"Retrieved prompt '{prompt_id}' from category '{category}' (length: {len(prompt)} chars)")
        else:
            logger.warning(f"Prompt '{prompt_id}' in category '{category}' has no content")
        
        return prompt
    
    def get_default_prompt(self, category: str) -> Optional[str]:
        """
        Get the default system prompt for a category.
        
        Args:
            category: The prompt category
            
        Returns:
            The default system prompt string or None if not found
        """
        logger.debug(f"Requesting default prompt for category: '{category}'")
        
        if not self._prompts_config:
            logger.warning("No prompts configuration loaded")
            return None
        
        defaults = self._prompts_config.get("default_prompts", {})
        
        # Map category to default key
        default_key = None
        if category == "function_calling":
            default_key = "function_calling_default"
        elif category == "chat_only":
            default_key = "chat_only_default"
        
        if default_key:
            default_prompt_id = defaults.get(default_key)
            if default_prompt_id:
                logger.debug(f"Using default prompt ID '{default_prompt_id}' for category '{category}'")
                return self.get_prompt(category, default_prompt_id)
            else:
                logger.warning(f"No default prompt ID configured for category '{category}'")
        else:
            logger.warning(f"No default mapping available for category '{category}'")
        
        return None
    
    def get_function_calling_prompt(self, prompt_id: Optional[str] = None) -> str:
        """
        Get a function calling system prompt.
        
        Args:
            prompt_id: Optional specific prompt ID, uses default if None
            
        Returns:
            The system prompt string
        """
        logger.debug(f"Requesting function calling prompt: prompt_id='{prompt_id}'")
        
        if prompt_id:
            prompt = self.get_prompt("function_calling", prompt_id)
            if prompt:
                logger.debug(f"Using specific function calling prompt: '{prompt_id}'")
                return prompt
            else:
                logger.warning(f"Specific function calling prompt '{prompt_id}' not found, falling back to default")
        
        # Fall back to default
        default_prompt = self.get_default_prompt("function_calling")
        if default_prompt:
            logger.debug("Using default function calling prompt")
            return default_prompt
        
        # Ultimate fallback
        logger.warning("No function calling prompts available, using ultimate fallback")
        return "You are a helpful assistant with access to functions. Use the available functions to fulfill user requests."
    
    def get_chat_prompt(self, prompt_id: Optional[str] = None) -> str:
        """
        Get a chat-only system prompt.
        
        Args:
            prompt_id: Optional specific prompt ID, uses default if None
            
        Returns:
            The system prompt string
        """
        logger.debug(f"Requesting chat prompt: prompt_id='{prompt_id}'")
        
        if prompt_id:
            prompt = self.get_prompt("chat_only", prompt_id)
            if prompt:
                logger.debug(f"Using specific chat prompt: '{prompt_id}'")
                return prompt
            else:
                logger.warning(f"Specific chat prompt '{prompt_id}' not found, falling back to default")
        
        # Fall back to default
        default_prompt = self.get_default_prompt("chat_only")
        if default_prompt:
            logger.debug("Using default chat prompt")
            return default_prompt
        
        # Ultimate fallback
        logger.warning("No chat prompts available, using ultimate fallback")
        return "You are a helpful assistant. Provide clear and accurate responses to user questions."
    
    def get_domain_specific_prompt(self, prompt_id: str) -> Optional[str]:
        """
        Get a domain-specific system prompt.
        
        Args:
            prompt_id: The domain-specific prompt ID
            
        Returns:
            The system prompt string or None if not found
        """
        logger.debug(f"Requesting domain-specific prompt: '{prompt_id}'")
        result = self.get_prompt("domain_specific", prompt_id)
        if result:
            logger.debug(f"Retrieved domain-specific prompt: '{prompt_id}'")
        else:
            logger.warning(f"Domain-specific prompt '{prompt_id}' not found")
        return result
    
    def list_available_prompts(self) -> Dict[str, Dict[str, str]]:
        """
        List all available system prompts.
        
        Returns:
            Dictionary mapping categories to prompt IDs and names
        """
        logger.debug("Listing all available system prompts")
        
        if not self._prompts_config:
            logger.warning("No prompts configuration loaded")
            return {}
        
        result = {}
        system_prompts = self._prompts_config.get("system_prompts", {})
        
        for category, prompts in system_prompts.items():
            result[category] = {}
            for prompt_id, prompt_config in prompts.items():
                result[category][prompt_id] = prompt_config.get("name", prompt_id)
        
        total_prompts = sum(len(category_prompts) for category_prompts in result.values())
        logger.debug(f"Listed {total_prompts} prompts across {len(result)} categories")
        
        return result
    
    def get_prompt_info(self, category: str, prompt_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific prompt.
        
        Args:
            category: The prompt category
            prompt_id: The prompt identifier
            
        Returns:
            Dictionary with prompt information or None if not found
        """
        logger.debug(f"Requesting prompt info: category='{category}', prompt_id='{prompt_id}'")
        
        if not self._prompts_config:
            logger.warning("No prompts configuration loaded")
            return None
        
        category_prompts = self._prompts_config.get("system_prompts", {}).get(category, {})
        prompt_info = category_prompts.get(prompt_id)
        
        if prompt_info:
            logger.debug(f"Retrieved prompt info for '{prompt_id}' in category '{category}'")
        else:
            logger.warning(f"Prompt info not found for '{prompt_id}' in category '{category}'")
            
        return prompt_info
    
    def interpolate_prompt(self, prompt: str, variables: Dict[str, str]) -> str:
        """
        Interpolate variables into a prompt template.
        
        Args:
            prompt: The prompt template with {variable} placeholders
            variables: Dictionary of variables to substitute
            
        Returns:
            The interpolated prompt string
        """
        logger.debug(f"Interpolating prompt template with {len(variables)} variables: {list(variables.keys())}")
        
        try:
            result = prompt.format(**variables)
            logger.debug(f"Prompt interpolation successful (original: {len(prompt)} chars, result: {len(result)} chars)")
            return result
        except KeyError as e:
            logger.error(f"Missing variable for prompt interpolation: {e}")
            raise ValueError(f"Missing variable for prompt interpolation: {e}")
        except Exception as e:
            logger.error(f"Error during prompt interpolation: {e}")
            raise


@singleton_factory
def get_system_prompt_loader() -> SystemPromptLoader:
    """Get the global system prompt loader instance (singleton pattern)."""
    return SystemPromptLoader()


def reload_system_prompts() -> None:
    """Reload system prompts from configuration file."""
    logger.info("Reloading system prompts via global function")
    loader = get_system_prompt_loader()
    loader.reload_prompts() 