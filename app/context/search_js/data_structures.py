"""Data structures for JavaScript/TypeScript search results"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class JSSearchResult:
    """Search result for JavaScript/TypeScript code"""
    
    file_path: str
    line_number: int
    end_line: int
    function_name: Optional[str]
    class_name: Optional[str]
    module_path: Optional[str]  # ES6 module path or CommonJS module
    code: str
    extraction_method: str = "ast"  # 'ast' (ts-morph), 'regex', 'manual'
    is_typescript: bool = False
    is_async: bool = False
    is_arrow: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dictionary for compatibility"""
        return {
            'file_path': self.file_path,
            'start': self.line_number,
            'end': self.end_line,
            'func_name': self.function_name,
            'class_name': self.class_name,
            'module_path': self.module_path,
            'code': self.code,
            'type': 'js_method' if self.function_name else 'js_class' if self.class_name else 'js_code',
            'extraction_method': self.extraction_method,
            'is_typescript': self.is_typescript,
            'is_async': self.is_async,
            'is_arrow': self.is_arrow
        }
    
    def __repr__(self) -> str:
        location = f"{self.file_path}:{self.line_number}-{self.end_line}"
        lang = "TS" if self.is_typescript else "JS"
        if self.function_name and self.class_name:
            return f"JSSearchResult({location}, {self.class_name}.{self.function_name}, {lang}, {self.extraction_method})"
        elif self.function_name:
            return f"JSSearchResult({location}, {self.function_name}, {lang}, {self.extraction_method})"
        elif self.class_name:
            return f"JSSearchResult({location}, {self.class_name}, {lang}, {self.extraction_method})"
        return f"JSSearchResult({location}, {lang}, {self.extraction_method})"


@dataclass
class JSCallChainResult:
    """Call chain result for JavaScript/TypeScript analysis"""
    
    chain: List[str]
    depth: int
    files: List[str]
    details: List[JSSearchResult]
    
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
        return f"JSCallChainResult(depth={self.depth}, chain={chain_str})"


@dataclass
class JSTaintPath:
    """Taint flow path for JavaScript/TypeScript analysis"""
    
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
        return f"JSTaintPath({self.source}~>{self.sink}, path={path_str}, confidence={self.confidence})"

