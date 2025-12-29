"""
Input Handler - Main interface for code input processing

This is a facade that combines functionality from:
- CodeLoader: File loading and preprocessing
- FunctionExtractor: Function extraction
- SnippetMatcher: Code snippet matching

Provides a unified InputHandler class for backward compatibility.
"""

from typing import Optional, Dict, Any, Tuple, List

from .code_loader import CodeLoader
from .function_extractor import FunctionExtractor
from .snippet_matcher import SnippetMatcher


class InputHandler:
    """
    Unified interface for handling code input
    
    This class combines functionality from CodeLoader, FunctionExtractor, and SnippetMatcher
    to provide a clean API for code file processing.
    """
    
    # ==================== File Loading ====================
    
    @staticmethod
    def load_code_file(file_path: str) -> str:
        """Load code from a text file"""
        return CodeLoader.load_code_file(file_path)
    
    @staticmethod
    def preprocess_code(code: str, max_length: Optional[int] = None) -> str:
        """Preprocess code (trim whitespace, limit length)"""
        return CodeLoader.preprocess_code(code, max_length)
    
    @staticmethod
    def load_and_preprocess(file_path: str, max_length: Optional[int] = None) -> str:
        """Load and preprocess code file in one step"""
        return CodeLoader.load_and_preprocess(file_path, max_length)
    
    @staticmethod
    def normalize_code_for_matching(code: str) -> str:
        """Normalize code for fuzzy matching"""
        return CodeLoader.normalize_code_for_matching(code)
    
    @staticmethod
    def detect_language(file_path: str) -> str:
        """Detect programming language from file extension"""
        return CodeLoader.detect_language(file_path)
    
    @staticmethod
    def get_file_stats(file_path: str) -> dict:
        """Get statistics about a code file"""
        return CodeLoader.get_file_stats(file_path)
    
    # ==================== Function Extraction ====================
    
    @staticmethod
    def extract_function_from_file(
        file_path: str,
        function_name: str
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Extract a specific function from a file"""
        return FunctionExtractor.extract_function_from_file(file_path, function_name)
    
    @staticmethod
    def extract_function_name_from_snippet(code_snippet: str) -> Optional[str]:
        """Try to extract function name from a code snippet"""
        return FunctionExtractor.extract_function_name_from_snippet(code_snippet)
    
    @staticmethod
    def list_all_functions_in_file(file_path: str) -> List[Dict[str, Any]]:
        """List all functions in a file with their locations"""
        return FunctionExtractor.list_all_functions_in_file(file_path)
    
    # ==================== Snippet Matching ====================
    
    @staticmethod
    def match_code_snippet_in_file(
        file_path: str,
        code_snippet: str
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Match a code snippet in a file (smart two-strategy approach)
        
        Strategy 1: Function extraction (if looks like a function)
        Strategy 2: Fuzzy snippet matching (6 levels)
        """
        return SnippetMatcher.match_code_snippet_in_file(file_path, code_snippet)
    
    # ==================== Metadata ====================
    
    @staticmethod
    def prepare_input_metadata(
        file_path: Optional[str] = None,
        function_name: Optional[str] = None,
        codebase_path: Optional[str] = None,
        code_snippet: Optional[str] = None,
        snippet_start_line: Optional[int] = None,
        snippet_end_line: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Prepare metadata about the input for analysis
        
        Args:
            file_path: Path to specific file
            function_name: Name of specific function to analyze
            codebase_path: Path to entire codebase
            code_snippet: Code snippet that was matched
            snippet_start_line: Starting line number of the snippet
            snippet_end_line: Ending line number of the snippet
            
        Returns:
            Dictionary with input metadata
        """
        metadata = {
            'input_type': None,
            'file_path': file_path,
            'function_name': function_name,
            'codebase_path': codebase_path,
            'code_snippet': code_snippet,
            'snippet_start_line': snippet_start_line,
            'snippet_end_line': snippet_end_line,
            'analysis_scope': None
        }
        
        if code_snippet and file_path:
            metadata['input_type'] = 'snippet'
            if snippet_start_line and snippet_end_line:
                metadata['analysis_scope'] = f"Code snippet (lines {snippet_start_line}-{snippet_end_line}) in '{file_path}'"
            else:
                metadata['analysis_scope'] = f"Code snippet in '{file_path}'"
        elif function_name and file_path:
            metadata['input_type'] = 'function'
            metadata['analysis_scope'] = f"Function '{function_name}' in '{file_path}'"
        elif file_path:
            metadata['input_type'] = 'file'
            metadata['analysis_scope'] = f"File '{file_path}'"
        elif codebase_path:
            metadata['input_type'] = 'codebase'
            metadata['analysis_scope'] = f"Codebase '{codebase_path}'"
        
        return metadata

