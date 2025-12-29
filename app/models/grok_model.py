"""Grok (xAI) model implementation"""

import os
from typing import List, Dict, Any, Optional

from .base import BaseLLMModel
from ..utils.retry_helper import retry_with_backoff


class GrokModel(BaseLLMModel):
    """xAI Grok API implementation (OpenAI-compatible)"""
    
    def __init__(
        self,
        model_id: str = "grok-beta",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        base_url: str = "https://api.x.ai/v1",
        **kwargs
    ):
        super().__init__(model_id, api_key, temperature, max_tokens, **kwargs)
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("xAI API key not provided. Set XAI_API_KEY environment variable or pass api_key parameter.")
        
        self.base_url = base_url
        
        # Lazy import - Grok uses OpenAI-compatible API
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=3600.0  # 1 hour timeout (same as Claude)
            )
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response from Grok API"""
        response_data = self.generate_with_metadata(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        return response_data['content']
    
    def generate_with_metadata(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate response with metadata"""
        # Use provided or default values
        temp = temperature if temperature is not None else self.temperature
        tokens = max_tokens if max_tokens is not None else self.max_tokens
        
        # Prepare request parameters
        request_params = {
            "model": self.model_id,
            "messages": messages,
            "temperature": temp,
        }
        
        if tokens is not None:
            request_params["max_tokens"] = tokens
        
        # Add any extra parameters
        request_params.update(kwargs)
        
        # Make API call with retry logic
        @retry_with_backoff(max_attempts=3, initial_delay=1.0, max_delay=60.0)
        def _api_call():
            return self.client.chat.completions.create(**request_params)
        
        response = _api_call()
        
        # Extract response
        content = response.choices[0].message.content
        
        # Build metadata
        metadata = {
            "content": content,
            "model": response.model,
            "tokens_used": {
                "prompt": response.usage.prompt_tokens if response.usage else 0,
                "completion": response.usage.completion_tokens if response.usage else 0,
                "total": response.usage.total_tokens if response.usage else 0,
            },
            "finish_reason": response.choices[0].finish_reason,
        }
        
        return metadata

