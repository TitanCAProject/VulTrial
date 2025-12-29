"""Base abstract class for LLM models"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseLLMModel(ABC):
    """Abstract base class for all LLM model providers"""
    
    def __init__(
        self,
        model_id: str,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Initialize the LLM model
        
        Args:
            model_id: The specific model identifier (e.g., "gpt-4", "claude-3-opus")
            api_key: API key for the model provider
            temperature: Sampling temperature (0-1)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters
        """
        self.model_id = model_id
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra_params = kwargs
        
    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        Generate a response from the model
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     Format: [{"role": "user", "content": "..."}, ...]
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional generation parameters
            
        Returns:
            Generated text response
        """
        pass
    
    @abstractmethod
    def generate_with_metadata(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response with metadata (tokens used, etc.)
        
        Args:
            messages: List of message dicts
            temperature: Override default temperature
            max_tokens: Override default max_tokens
            **kwargs: Additional generation parameters
            
        Returns:
            Dict with 'content', 'tokens_used', and other metadata
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model_id='{self.model_id}')"

