"""Data structures for Java search results"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class JavaSearchResult:
    """Search result for Java code"""
    
    file_path: str
    line_number: int
    end_line: int
    method_name: Optional[str]
    class_name: Optional[str]
    package_name: Optional[str]
    code: str
    extraction_method: str = "ast"  # 'ast', 'regex', 'manual'
    
    def to_dict(self) -> dict:
        """Convert to dictionary for compatibility"""
        return {
            'file_path': self.file_path,
            'start': self.line_number,
            'end': self.end_line,
            'func_name': self.method_name,
            'class_name': self.class_name,
            'package_name': self.package_name,
            'code': self.code,
            'type': 'java_method' if self.method_name else 'java_class' if self.class_name else 'java_code',
            'extraction_method': self.extraction_method
        }
    
    def __repr__(self) -> str:
        location = f"{self.file_path}:{self.line_number}-{self.end_line}"
        if self.method_name and self.class_name:
            return f"JavaSearchResult({location}, {self.class_name}.{self.method_name}, {self.extraction_method})"
        elif self.class_name:
            return f"JavaSearchResult({location}, {self.class_name}, {self.extraction_method})"
        return f"JavaSearchResult({location}, {self.extraction_method})"


@dataclass
class JavaCallChainResult:
    """Call chain result for Java analysis"""
    
    chain: List[str]
    depth: int
    files: List[str]
    details: List[JavaSearchResult]
    
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
        return f"JavaCallChainResult(depth={self.depth}, chain={chain_str})"


@dataclass
class JavaTaintPath:
    """Taint flow path for Java analysis"""
    
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
        return f"JavaTaintPath({self.source}~>{self.sink}, path={path_str}, confidence={self.confidence})"


