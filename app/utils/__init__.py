"""Utility modules for VulTrial"""

# Main interface (combines functionality from modular components)
from .input_handler import InputHandler

# Modular components (can be used directly if needed)
from .code_loader import CodeLoader
from .function_extractor import FunctionExtractor
from .snippet_matcher import SnippetMatcher

# Other utilities
from .logger import VulTrialLogger
from .config_manager import ConfigManager
from .context_compressor import ContextCompressor
from .retry_helper import retry_with_backoff, RetryError
from .persistent_cache import PersistentCache
from .results_saver import ResultsSaver
from .snippet_normalizer import unescape_snippet, normalize_snippet_from_file, is_likely_escaped

__all__ = [
    # Main interface
    'InputHandler',
    
    # Modular components
    'CodeLoader',
    'FunctionExtractor', 
    'SnippetMatcher',
    
    # Other utilities
    'VulTrialLogger', 
    'ConfigManager', 
    'ContextCompressor', 
    'retry_with_backoff', 
    'RetryError',
    'PersistentCache',
    'ResultsSaver',
    'unescape_snippet',
    'normalize_snippet_from_file',
    'is_likely_escaped'
]

