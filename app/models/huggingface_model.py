"""Hugging Face model implementation for open-source LLMs"""

import os
from typing import List, Dict, Any, Optional

from .base import BaseLLMModel


class HuggingFaceModel(BaseLLMModel):
    """Hugging Face Transformers implementation for open-source models"""
    
    def __init__(
        self,
        model_id: str,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = 2048,
        device: Optional[str] = None,
        load_in_8bit: bool = False,
        load_in_4bit: bool = False,
        **kwargs
    ):
        """
        Initialize Hugging Face model
        
        Args:
            model_id: Model identifier from Hugging Face Hub (e.g., "meta-llama/Llama-2-13b-chat-hf")
            api_key: Hugging Face token (optional, for gated models)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            device: Device to run on ('cuda', 'cpu', or None for auto)
            load_in_8bit: Load model in 8-bit precision (saves memory)
            load_in_4bit: Load model in 4-bit precision (saves more memory)
            **kwargs: Additional model parameters
        """
        super().__init__(model_id, api_key, temperature, max_tokens, **kwargs)
        
        # Get Hugging Face token from parameter or environment
        self.hf_token = api_key or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        
        # Lazy import torch
        try:
            import torch
            self.torch = torch
        except ImportError:
            raise ImportError(
                "torch package not installed. Install with: "
                "pip install torch transformers accelerate bitsandbytes"
            )
        
        # Determine device
        if device is None:
            self.device = "cuda" if self.torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        
        self.load_in_8bit = load_in_8bit
        self.load_in_4bit = load_in_4bit
        
        print(f"Loading model: {model_id}")
        print(f"Device: {self.device}")
        if load_in_8bit:
            print("Using 8-bit quantization")
        elif load_in_4bit:
            print("Using 4-bit quantization")
        
        # Lazy import
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import transformers
            self.transformers = transformers
        except ImportError:
            raise ImportError(
                "transformers package not installed. Install with: "
                "pip install transformers torch accelerate bitsandbytes"
            )
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_id,
            token=self.hf_token,
            trust_remote_code=True
        )
        
        # Set padding token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Load model with quantization if requested
        model_kwargs = {
            "token": self.hf_token,
            "trust_remote_code": True,
        }
        
        if load_in_8bit:
            model_kwargs["load_in_8bit"] = True
            model_kwargs["device_map"] = "auto"
        elif load_in_4bit:
            model_kwargs["load_in_4bit"] = True
            model_kwargs["device_map"] = "auto"
        else:
            # No quantization
            pass
        
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            **model_kwargs
        )
        
        # Move to device if not using device_map
        if not (load_in_8bit or load_in_4bit):
            self.model = self.model.to(self.device)
        
        self.model.eval()
        
        print(f"Model loaded successfully!")
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """
        Format messages into a prompt string
        
        Different models have different chat templates. Try to use the model's
        built-in chat template if available, otherwise use a generic format.
        """
        # Try to use model's chat template
        if hasattr(self.tokenizer, "apply_chat_template") and self.tokenizer.chat_template is not None:
            try:
                return self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
            except Exception:
                pass
        
        # Fallback: Generic format
        prompt_parts = []
        for msg in messages:
            role = msg['role']
            content = msg['content']
            
            if role == 'system':
                prompt_parts.append(f"System: {content}\n")
            elif role == 'user':
                prompt_parts.append(f"User: {content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}\n")
        
        # Add assistant prefix to trigger generation
        prompt_parts.append("Assistant:")
        
        return "\n".join(prompt_parts)
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """Generate response from Hugging Face model"""
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
        tokens = max_tokens if max_tokens is not None else (self.max_tokens or 2048)
        
        # Format messages into prompt
        prompt = self._format_messages(messages)
        
        # Tokenize
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(self.device)
        
        input_length = inputs['input_ids'].shape[1]
        
        # Generate
        with self.torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=tokens,
                temperature=temp,
                do_sample=temp > 0,
                top_p=0.9,
                pad_token_id=self.tokenizer.pad_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
                **kwargs
            )
        
        # Decode only the generated tokens (skip the input prompt)
        generated_tokens = outputs[0][input_length:]
        content = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)
        
        # Build metadata
        output_length = len(generated_tokens)
        metadata = {
            "content": content.strip(),
            "model": self.model_id,
            "tokens_used": {
                "prompt": input_length,
                "completion": output_length,
                "total": input_length + output_length,
            },
            "finish_reason": "stop",
        }
        
        return metadata
    
    def __repr__(self) -> str:
        device_info = f", device={self.device}"
        quant_info = ""
        if self.load_in_8bit:
            quant_info = ", 8-bit"
        elif self.load_in_4bit:
            quant_info = ", 4-bit"
        return f"{self.__class__.__name__}(model_id='{self.model_id}'{device_info}{quant_info})"

