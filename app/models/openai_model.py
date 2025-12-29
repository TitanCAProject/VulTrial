"""OpenAI model implementation"""

import os
from typing import List, Dict, Any, Optional

from .base import BaseLLMModel
from ..utils.retry_helper import retry_with_backoff


class OpenAIModel(BaseLLMModel):
    """OpenAI API implementation"""
    
    def __init__(
        self,
        model_id: str = "gpt-4",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        super().__init__(model_id, api_key, temperature, max_tokens, **kwargs)
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        # Lazy import to avoid requiring openai if not used
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package not installed. Install with: pip install openai")
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response from OpenAI API"""
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
        
        # Check if model has temperature restrictions
        model_lower = self.model_id.lower()
        has_temp_restriction = (
            'o1' in model_lower or           # o1 models only support temperature=1
            'o3' in model_lower or           # o3 models only support temperature=1
            'gpt-5' in model_lower           # GPT-5 models only support temperature=1
        )
        
        # Prepare request parameters
        request_params = {
            "model": self.model_id,
            "messages": messages,
        }
        
        # Only add temperature if model supports it
        if not has_temp_restriction:
            request_params["temperature"] = temp
        
        if tokens is not None:
            # OpenAI API parameter varies by model:
            # - Legacy (GPT-3.x, GPT-4, GPT-4-turbo): max_tokens
            # - New (GPT-4o, GPT-5+, o1, o3): max_completion_tokens
            model_lower = self.model_id.lower()
            
            # Check for new models that use max_completion_tokens
            uses_completion_tokens = (
                '4o' in model_lower or      # GPT-4o, GPT-4o-mini
                'gpt-5' in model_lower or    # GPT-5, GPT-5-mini, etc.
                'gpt-6' in model_lower or    # Future models
                'o1' in model_lower or       # o1-preview, o1-mini, o1
                'o3' in model_lower          # o3-mini, o3
            )
            
            if uses_completion_tokens:
                request_params["max_completion_tokens"] = tokens
            else:
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
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            },
            "finish_reason": response.choices[0].finish_reason,
        }
        
        return metadata

