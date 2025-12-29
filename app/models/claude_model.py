"""Claude (Anthropic) model implementation"""

import os
from typing import List, Dict, Any, Optional

from .base import BaseLLMModel
from ..utils.retry_helper import retry_with_backoff


class ClaudeModel(BaseLLMModel):
    """Anthropic Claude API implementation"""
    
    def __init__(
        self,
        model_id: str = "claude-3-5-sonnet-20241022",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        **kwargs
    ):
        super().__init__(model_id, api_key, temperature, max_tokens, **kwargs)
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key not provided. Set ANTHROPIC_API_KEY environment variable or pass api_key parameter.")
        
        # Lazy import
        try:
            from anthropic import Anthropic
            # Set a very long timeout (1 hour) for large code analysis
            # This prevents the "10 minute streaming required" error
            self.client = Anthropic(
                api_key=self.api_key,
                timeout=3600.0  # 1 hour timeout
            )
        except ImportError:
            raise ImportError("anthropic package not installed. Install with: pip install anthropic")
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response from Claude API"""
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
        tokens = max_tokens if max_tokens is not None else (self.max_tokens or 4096)
        
        # Claude requires separating system message from user/assistant messages
        system_message = None
        conversation_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                conversation_messages.append(msg)
        
        # Prepare request parameters
        request_params = {
            "model": self.model_id,
            "messages": conversation_messages,
            "temperature": temp,
            "max_tokens": tokens,
        }
        
        if system_message:
            request_params["system"] = system_message
        
        # Add any extra parameters
        request_params.update(kwargs)
        
        # Make API call with retry logic
        @retry_with_backoff(max_attempts=3, initial_delay=1.0, max_delay=60.0)
        def _api_call():
            return self.client.messages.create(**request_params)
        
        response = _api_call()
        
        # Extract content
        content = response.content[0].text
        
        # Build metadata
        metadata = {
            "content": content,
            "model": response.model,
            "tokens_used": {
                "prompt": response.usage.input_tokens,
                "completion": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens,
            },
            "finish_reason": response.stop_reason,
        }
        
        return metadata

