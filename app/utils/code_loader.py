"""
Code Loader - Handles file loading and basic preprocessing

Responsible for reading code files and basic preprocessing operations.
"""

from pathlib import Path
from typing import Optional


class CodeLoader:
    """Loads and preprocesses code files"""
    
    @staticmethod
    def load_code_file(file_path: str) -> str:
        """
        Load code from a text file
        
        Args:
            file_path: Path to the code file
            
        Returns:
            Code content as string
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file can't be read
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Code file not found: {file_path}")
        
        if not path.is_file():
            raise IOError(f"Path is not a file: {file_path}")
        
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            return content
        except Exception as e:
            raise IOError(f"Error reading file {file_path}: {str(e)}")
    
    @staticmethod
    def preprocess_code(code: str, max_length: Optional[int] = None) -> str:
        """
        Preprocess code (trim whitespace, limit length, etc.)
        
        Args:
            code: Raw code string
            max_length: Optional maximum length to truncate to
            
        Returns:
            Preprocessed code string
        """
        # Remove leading/trailing whitespace
        code = code.strip()
        
        # Truncate if needed
        if max_length and len(code) > max_length:
            code = code[:max_length] + "\n... [truncated]"
        
        return code
    
    @staticmethod
    def load_and_preprocess(
        file_path: str,
        max_length: Optional[int] = None
    ) -> str:
        """
        Load and preprocess code file in one step
        
        Args:
            file_path: Path to the code file
            max_length: Optional maximum length
            
        Returns:
            Preprocessed code string
        """
        code = CodeLoader.load_code_file(file_path)
        return CodeLoader.preprocess_code(code, max_length)
    
    @staticmethod
    def normalize_code_for_matching(code: str) -> str:
        """
        Normalize code for fuzzy matching by handling whitespace variations
        
        Args:
            code: Code string to normalize
            
        Returns:
            Normalized code string
        """
        # Replace tabs with spaces
        code = code.replace('\t', '    ')
        
        # Normalize line endings
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove leading/trailing whitespace from each line
        lines = code.split('\n')
        normalized_lines = [line.rstrip() for line in lines]
        
        return '\n'.join(normalized_lines)
    
    @staticmethod
    def detect_language(file_path: str) -> str:
        """
        Detect programming language from file extension
        
        Args:
            file_path: Path to the code file
            
        Returns:
            Language identifier: 'python', 'c', 'cpp', 'java', 'javascript', 'go', 'rust', 'unknown'
        """
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.pyx': 'python',
            '.c': 'c',
            '.h': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.hpp': 'cpp',
            '.java': 'java',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.php': 'php',
            '.rb': 'ruby',
            '.swift': 'swift',
            '.kt': 'kotlin',
        }
        
        return language_map.get(ext, 'unknown')
    
    @staticmethod
    def get_file_stats(file_path: str) -> dict:
        """
        Get statistics about a code file
        
        Args:
            file_path: Path to the code file
            
        Returns:
            Dict with file stats: size, lines, language, etc.
        """
        path = Path(file_path)
        
        if not path.exists():
            return {'exists': False}
        
        try:
            content = CodeLoader.load_code_file(file_path)
            lines = content.split('\n')
            
            return {
                'exists': True,
                'size_bytes': path.stat().st_size,
                'size_chars': len(content),
                'total_lines': len(lines),
                'non_empty_lines': sum(1 for line in lines if line.strip()),
                'language': CodeLoader.detect_language(file_path),
                'file_name': path.name,
                'file_extension': path.suffix,
            }
        except Exception as e:
            return {
                'exists': True,
                'error': str(e)
            }

