"""Data structures for C/C++ search results"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class CSearchResult:
    """Search result for C/C++ code"""
    
    file_path: str
    line_number: int
    end_line: int
    function_name: Optional[str]
    class_name: Optional[str]
    code: str
    extraction_method: str = "cscope"  # 'cscope', 'tree-sitter', 'ctags', 'manual'
    
    def to_dict(self) -> dict:
        """Convert to dictionary for compatibility"""
        return {
            'file_path': self.file_path,
            'start': self.line_number,
            'end': self.end_line,
            'func_name': self.function_name,
            'class_name': self.class_name,
            'code': self.code,
            'type': 'c_function' if self.function_name else 'c_code',
            'extraction_method': self.extraction_method
        }
    
    def __repr__(self) -> str:
        location = f"{self.file_path}:{self.line_number}-{self.end_line}"
        if self.function_name:
            return f"CSearchResult({location}, {self.function_name}, {self.extraction_method})"
        return f"CSearchResult({location}, {self.extraction_method})"


@dataclass
class CCallChainResult:
    """Call chain result for C/C++ analysis"""

    chain: List[str]
    depth: int
    files: List[str]
    details: List[CSearchResult]
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'chain': self.chain,
            'depth': self.depth,
            'files': self.files,
            'details': [d.to_dict() for d in self.details]
        }

    def __repr__(self) -> str:
        chain_str = " -> ".join(self.chain)
        return f"CCallChainResult(depth={self.depth}, chain={chain_str})"


@dataclass
class CTaintPath:
    """Taint flow path for C/C++ analysis"""

    source: str
    sink: str
    path: List[str]
    variables: List[str]
    confidence: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'source': self.source,
            'sink': self.sink,
            'path': self.path,
            'variables': self.variables,
            'confidence': self.confidence
        }

    def __repr__(self) -> str:
        path_str = " -> ".join(self.path)
        return f"CTaintPath({self.source}~>{self.sink}, path={path_str}, confidence={self.confidence})"

