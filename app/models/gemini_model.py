"""Google Gemini model implementation"""

import os
from typing import List, Dict, Any, Optional

from .base import BaseLLMModel
from ..utils.retry_helper import retry_with_backoff


class GeminiModel(BaseLLMModel):
    """Google Gemini API implementation"""
    
    def __init__(
        self,
        model_id: str = "gemini-1.5-pro",
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        super().__init__(model_id, api_key, temperature, max_tokens, **kwargs)
        
        # Get API key from parameter or environment
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("Google API key not provided. Set GOOGLE_API_KEY environment variable or pass api_key parameter.")
        
        # Lazy import
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.genai = genai
            self.model = genai.GenerativeModel(self.model_id)
        except ImportError:
            raise ImportError("google-generativeai package not installed. Install with: pip install google-generativeai")
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> tuple:
        """Convert OpenAI-style messages to Gemini format"""
        system_instruction = None
        conversation = []
        
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            if role == 'system':
                system_instruction = content
            elif role == 'user':
                conversation.append({"role": "user", "parts": [content]})
            elif role == 'assistant':
                conversation.append({"role": "model", "parts": [content]})
        
        return system_instruction, conversation
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response from Gemini API"""
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
        
        # Convert messages to Gemini format
        system_instruction, conversation = self._convert_messages_to_gemini_format(messages)
        
        # Create model with system instruction if provided
        if system_instruction:
            model = self.genai.GenerativeModel(
                self.model_id,
                system_instruction=system_instruction
            )
        else:
            model = self.model
        
        # Configure generation
        generation_config = {
            "temperature": temp,
        }
        if tokens is not None:
            generation_config["max_output_tokens"] = tokens
        
        generation_config.update(kwargs)
        
        # Generate response with retry logic
        @retry_with_backoff(max_attempts=3, initial_delay=1.0, max_delay=60.0)
        def _api_call():
            if len(conversation) == 1:
                # Single turn
                return model.generate_content(
                    conversation[0]['parts'][0],
                    generation_config=generation_config
                )
            else:
                # Multi-turn conversation
                chat = model.start_chat(history=conversation[:-1])
                return chat.send_message(
                    conversation[-1]['parts'][0],
                    generation_config=generation_config
                )
        
        response = _api_call()
        
        content = response.text
        
        # Build metadata
        metadata = {
            "content": content,
            "model": self.model_id,
            "tokens_used": {
                "prompt": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0,
                "completion": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0,
                "total": response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0,
            },
            "finish_reason": response.candidates[0].finish_reason.name if response.candidates else "UNKNOWN",
        }
        
        return metadata

