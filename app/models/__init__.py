"""LLM Model providers for VulTrial framework"""

from .base import BaseLLMModel
from .huggingface_model import HuggingFaceModel

__all__ = [
    'BaseLLMModel',
    'HuggingFaceModel',
]
