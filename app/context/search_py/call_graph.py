"""
Call graph construction and multi-level call chain analysis
"""

import networkx as nx
from typing import List, Dict, Set, Optional, Tuple, Any
from pathlib import Path


class CallGraph:
    """
    Call graph builder using NetworkX for multi-level call chain analysis
    """
    
    def __init__(self):
        """Initialize call graph"""
        self.graph = nx.DiGraph()
        self._path_cache: Dict[Tuple[str, int, str], List[List[str]]] = {}
        
    def add_call(self, caller: str, callee: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a call relationship to the graph
        
        Args:
            caller: Name of calling function
            callee: Name of called function
            metadata: Optional metadata (file_path, line_no, etc.)
        """
        if not self.graph.has_node(caller):
            self.graph.add_node(caller)
        if not self.graph.has_node(callee):
            self.graph.add_node(callee)
        
        # Add edge with metadata
        self.graph.add_edge(caller, callee, **(metadata or {}))
    
    def build_from_indexes(
        self,
        function_index: Dict,
        class_func_index: Dict,
        get_code_fn
    ):
        """
        Build call graph from existing search backend indexes
        
        Args:
            function_index: {func_name -> [(file, line_range)]}
            class_func_index: {class -> {func -> [(file, line_range)]}}
            get_code_fn: Function to retrieve code given (file, start, end)
        """
        import re
        
        # Pattern to match function calls
        call_pattern = r'\b([a-z_][a-z0-9_]*)\s*\('
        
        # Process top-level functions
        for func_name, locations in function_index.items():
            for file_path, line_range in locations:
                # Get function code
                code = get_code_fn(file_path, line_range.start, line_range.end)
                
                # Extract function calls
                calls = re.findall(call_pattern, code, re.IGNORECASE)
                
                # Add to graph
                for called_func in set(calls):
                    # Skip self-calls and common builtins
                    if called_func == func_name or self._is_builtin(called_func):
                        continue
                    
                    # Verify the callee exists in our index
                    if self._function_exists(called_func, function_index, class_func_index):
                        self.add_call(
                            func_name,
                            called_func,
                            {'file': file_path, 'line': line_range.start}
                        )
        
        # Process class methods
        for class_name, methods in class_func_index.items():
            for method_name, locations in methods.items():
                # Use qualified name for methods
                qualified_name = f"{class_name}.{method_name}"
                
                for file_path, line_range in locations:
                    code = get_code_fn(file_path, line_range.start, line_range.end)
                    calls = re.findall(call_pattern, code, re.IGNORECASE)
                    
                    for called_func in set(calls):
                        if called_func == method_name or self._is_builtin(called_func):
                            continue
                        
                        if self._function_exists(called_func, function_index, class_func_index):
                            self.add_call(
                                qualified_name,
                                called_func,
                                {'file': file_path, 'line': line_range.start}
                            )
    
    def find_call_chain(
        self,
        start_function: str,
        depth: int = 3,
        direction: str = "forward"
    ) -> List[List[str]]:
        """
        Find all call chains from a function up to a certain depth
        
        Args:
            start_function: Starting function name
            depth: Maximum depth to traverse
            direction: "forward" (callees) or "backward" (callers)
        
        Returns:
            List of call chains (each chain is a list of function names)
        """
        # Check cache
        cache_key = (start_function, depth, direction)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        
        if start_function not in self.graph:
            return []
        
        chains = []
        visited = set()
        
        def dfs(current: str, path: List[str], current_depth: int):
            """DFS traversal with depth limit"""
            if current_depth >= depth:
                if len(path) > 1:  # Only add if we have a chain
                    chains.append(path[:])
                return
            
            # Mark as visited for this path (cycle detection)
            if current in visited:
                return
            visited.add(current)
            
            # Get neighbors based on direction
            if direction == "forward":
                neighbors = list(self.graph.successors(current))
            else:  # backward
                neighbors = list(self.graph.predecessors(current))
            
            if not neighbors:
                # Leaf node - add current path if it's not empty
                if len(path) > 1:
                    chains.append(path[:])
            else:
                # Continue exploring
                for neighbor in neighbors:
                    path.append(neighbor)
                    dfs(neighbor, path, current_depth + 1)
                    path.pop()
            
            visited.remove(current)
        
        # Start DFS
        dfs(start_function, [start_function], 0)
        
        # Cache results
        self._path_cache[cache_key] = chains
        
        return chains
    
    def find_paths_between(
        self,
        source: str,
        target: str,
        max_length: int = 5
    ) -> List[List[str]]:
        """
        Find all paths from source to target function
        
        Args:
            source: Source function name
            target: Target function name
            max_length: Maximum path length
        
        Returns:
            List of paths (each path is a list of function names)
        """
        if source not in self.graph or target not in self.graph:
            return []
        
        try:
            # Use NetworkX to find all simple paths
            paths = list(nx.all_simple_paths(
                self.graph,
                source,
                target,
                cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []
    
    def get_callers(self, function: str) -> List[str]:
        """Get direct callers of a function"""
        if function not in self.graph:
            return []
        return list(self.graph.predecessors(function))
    
    def get_callees(self, function: str) -> List[str]:
        """Get direct callees of a function"""
        if function not in self.graph:
            return []
        return list(self.graph.successors(function))
    
    def get_transitive_callers(self, function: str, max_depth: int = 3) -> Set[str]:
        """Get all transitive callers up to max_depth"""
        if function not in self.graph:
            return set()
        
        callers = set()
        queue = [(function, 0)]
        visited = {function}
        
        while queue:
            current, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for caller in self.graph.predecessors(current):
                if caller not in visited:
                    visited.add(caller)
                    callers.add(caller)
                    queue.append((caller, depth + 1))
        
        return callers
    
    def get_transitive_callees(self, function: str, max_depth: int = 3) -> Set[str]:
        """Get all transitive callees up to max_depth"""
        if function not in self.graph:
            return set()
        
        callees = set()
        queue = [(function, 0)]
        visited = {function}
        
        while queue:
            current, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            for callee in self.graph.successors(current):
                if callee not in visited:
                    visited.add(callee)
                    callees.add(callee)
                    queue.append((callee, depth + 1))
        
        return callees
    
    def _is_builtin(self, func_name: str) -> bool:
        """Check if function name is a Python builtin"""
        builtins = {
            'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple',
            'open', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
            'isinstance', 'hasattr', 'getattr', 'setattr', 'super', 'type',
            'if', 'for', 'while', 'return', 'yield', 'raise', 'assert',
            'append', 'extend', 'split', 'join', 'strip', 'format', 'replace',
            'startswith', 'endswith', 'lower', 'upper', 'read', 'write', 'close',
            'get', 'items', 'keys', 'values'
        }
        return func_name in builtins
    
    def _function_exists(self, func_name: str, function_index: Dict, class_func_index: Dict) -> bool:
        """Check if a function exists in the indexes"""
        # Check top-level functions
        if func_name in function_index:
            return True
        
        # Check class methods
        for class_methods in class_func_index.values():
            if func_name in class_methods:
                return True
        
        return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the call graph"""
        return {
            'num_functions': self.graph.number_of_nodes(),
            'num_calls': self.graph.number_of_edges(),
            'avg_out_degree': sum(dict(self.graph.out_degree()).values()) / max(1, self.graph.number_of_nodes()),
            'max_out_degree': max(dict(self.graph.out_degree()).values()) if self.graph.number_of_nodes() > 0 else 0
        }

