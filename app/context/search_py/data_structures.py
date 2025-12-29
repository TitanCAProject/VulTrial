"""Data structures for search results"""

from typing import Optional, List
from dataclasses import dataclass


@dataclass
class SearchResult:
    """Search result containing code location and content"""
    
    file_path: str
    start: int
    end: int
    class_name: Optional[str]
    func_name: Optional[str]
    code: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'file_path': self.file_path,
            'start': self.start,
            'end': self.end,
            'class_name': self.class_name,
            'func_name': self.func_name,
            'code': self.code
        }
    
    def __repr__(self) -> str:
        location = f"{self.file_path}:{self.start}-{self.end}"
        if self.class_name and self.func_name:
            return f"SearchResult({location}, {self.class_name}.{self.func_name})"
        elif self.func_name:
            return f"SearchResult({location}, {self.func_name})"
        elif self.class_name:
            return f"SearchResult({location}, {self.class_name})"
        return f"SearchResult({location})"


@dataclass
class CallChainResult:
    """Multi-level call chain from source to target"""
    chain: List[str]  # Function names in order
    depth: int
    files: List[str]  # Files involved
    details: List[SearchResult]  # Full details for each function
    
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
        return f"CallChainResult({chain_str}, depth={self.depth})"


@dataclass
class TaintPath:
    """Path showing how tainted data flows"""
    source: str  # e.g., "user_input"
    sink: str    # e.g., "eval"
    path: List[str]  # Function call chain
    variables: List[str]  # Variable names along path
    confidence: str  # "high", "medium", "low"
    
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
        return f"TaintPath({self.source} ~> {self.sink}, {path_str}, confidence={self.confidence})"

