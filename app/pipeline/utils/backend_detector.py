"""Auto-detect code language and create appropriate search backend"""

from pathlib import Path
from typing import Union
from ...context.search_py.search_backend import SearchBackend
from ...context.search_c.search_backend import CSearchBackend
from ...context.search_java.search_backend import JavaSearchBackend
from ...context.search_js.search_backend import JSSearchBackend


class BackendDetector:
    """Auto-detect code language and create appropriate search backend"""
    
    @staticmethod
    def detect_code_type(codebase_path: str) -> str:
        """
        Auto-detect code language based on file extensions
        
        Args:
            codebase_path: Path to the codebase
            
        Returns:
            "python", "c_cpp", "java", or "javascript"
        """
        path = Path(codebase_path)
        
        # Count file extensions
        python_files = 0
        c_cpp_files = 0
        java_files = 0
        js_ts_files = 0
        
        # Define extensions
        python_extensions = {'.py', '.pyx', '.pyi'}
        c_cpp_extensions = {'.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.C'}
        java_extensions = {'.java'}
        js_ts_extensions = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}
        
        # Walk through directory
        for file_path in path.rglob('*'):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in python_extensions:
                    python_files += 1
                elif ext in c_cpp_extensions:
                    c_cpp_files += 1
                elif ext in java_extensions:
                    java_files += 1
                elif ext in js_ts_extensions:
                    js_ts_files += 1
        
        # Decide based on majority
        counts = {
            "java": java_files,
            "c_cpp": c_cpp_files,
            "javascript": js_ts_files,
            "python": python_files
        }
        
        return max(counts, key=counts.get)
    
    @staticmethod
    def create_backend(
        backend_type: str,
        codebase_path: str,
        verbose: bool = False
    ) -> Union[SearchBackend, CSearchBackend, JavaSearchBackend, JSSearchBackend]:
        """
        Create appropriate search backend based on code type
        
        Args:
            backend_type: Type of backend ("python", "c_cpp", "java", "javascript")
            codebase_path: Path to codebase
            verbose: Whether to print verbose output
            
        Returns:
            Appropriate search backend instance
        """
        if backend_type == "c_cpp":
            backend = CSearchBackend(codebase_path)
            if verbose:
                print(f"🔧 Using C/C++ search backend for: {codebase_path}")
        elif backend_type == "java":
            backend = JavaSearchBackend(codebase_path)
            if verbose:
                print(f"☕ Using Java search backend for: {codebase_path}")
        elif backend_type == "javascript":
            backend = JSSearchBackend(codebase_path)
            if verbose:
                print(f"📜 Using JavaScript/TypeScript search backend for: {codebase_path}")
        else:
            backend = SearchBackend(codebase_path)
            if verbose:
                print(f"🐍 Using Python search backend for: {codebase_path}")
        
        return backend

