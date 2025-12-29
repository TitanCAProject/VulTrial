"""
Taint analysis for tracking untrusted data flow from sources to sinks
"""

import ast
from typing import List, Dict, Set, Optional, Tuple, Any
from .analysis_utils import (
    is_dangerous_sink,
    is_taint_source,
    get_function_parameters,
    extract_function_calls,
    extract_variables
)


class TaintTracker:
    """
    Track taint propagation through a function
    """
    
    def __init__(self):
        """Initialize taint tracker"""
        self.tainted_vars: Dict[str, Set[int]] = {}  # var_name -> {line_numbers where tainted}
        self.taint_flows: List[Dict[str, Any]] = []  # List of taint flow records
        
    def analyze_function(
        self,
        function_ast: ast.FunctionDef,
        function_name: str
    ) -> Dict[str, Any]:
        """
        Analyze a function for taint flows
        
        Args:
            function_ast: AST node for the function
            function_name: Name of the function
        
        Returns:
            Dict with taint analysis results
        """
        # Mark parameters as potentially tainted
        params = get_function_parameters(function_ast)
        for param in params:
            self._mark_tainted(param, function_ast.lineno)
        
        # Analyze function body
        self._analyze_node(function_ast)
        
        # Find dangerous sinks by walking the AST directly
        dangerous_flows = []
        for node in ast.walk(function_ast):
            if isinstance(node, ast.Call):
                func_name = self._get_func_name(node.func)
                
                if is_dangerous_sink(func_name):
                    # Check if any arguments are tainted using AST nodes
                    tainted_args = []
                    
                    for arg in node.args:
                        if self._is_value_tainted(arg, node.lineno):
                            # Get a string representation of the arg
                            if isinstance(arg, ast.Name):
                                tainted_args.append(arg.id)
                            elif isinstance(arg, ast.Subscript) and isinstance(arg.value, ast.Name):
                                tainted_args.append(f"{arg.value.id}[...]")
                            else:
                                tainted_args.append("<tainted_expr>")
                    
                    if tainted_args:
                        dangerous_flows.append({
                            'sink': func_name,
                            'line': node.lineno,
                            'tainted_args': tainted_args,
                            'confidence': 'high' if len(tainted_args) == len(node.args) else 'medium'
                        })
        
        return {
            'function': function_name,
            'tainted_variables': dict(self.tainted_vars),
            'dangerous_flows': dangerous_flows,
            'has_vulnerabilities': len(dangerous_flows) > 0
        }
    
    def _analyze_node(self, node: ast.AST):
        """Recursively analyze AST node for taint propagation"""
        if isinstance(node, ast.Assign):
            self._handle_assignment(node)
        elif isinstance(node, ast.AugAssign):
            self._handle_aug_assignment(node)
        elif isinstance(node, ast.Call):
            self._handle_call(node)
        
        # Recursively visit children
        for child in ast.iter_child_nodes(node):
            self._analyze_node(child)
    
    def _handle_assignment(self, node: ast.Assign):
        """Handle variable assignment and taint propagation"""
        # Check if the value is tainted
        value_tainted = self._is_value_tainted(node.value, node.lineno)
        
        if value_tainted:
            # Mark all targets as tainted
            for target in node.targets:
                var_names = self._extract_target_names(target)
                for var_name in var_names:
                    self._mark_tainted(var_name, node.lineno)
    
    def _handle_aug_assignment(self, node: ast.AugAssign):
        """Handle augmented assignment (+=, etc.)"""
        value_tainted = self._is_value_tainted(node.value, node.lineno)
        target_tainted = self._is_value_tainted(node.target, node.lineno)
        
        if value_tainted or target_tainted:
            var_names = self._extract_target_names(node.target)
            for var_name in var_names:
                self._mark_tainted(var_name, node.lineno)
    
    def _handle_call(self, node: ast.Call):
        """Handle function calls"""
        # Check if this is a taint source
        func_name = self._get_func_name(node.func)
        
        # For now, we don't mark return values as tainted from taint source calls
        # This would require more sophisticated inter-procedural analysis
        pass
    
    def _is_value_tainted(self, node: ast.AST, line_no: int) -> bool:
        """Check if a value expression is tainted"""
        if isinstance(node, ast.Name):
            return self._is_tainted_at_line(node.id, line_no)
        
        elif isinstance(node, ast.Call):
            func_name = self._get_func_name(node.func)
            
            # Check if it's a taint source
            if is_taint_source(func_name):
                return True
            
            # Check if calling method on tainted object (e.g., request.get())
            if isinstance(node.func, ast.Attribute):
                obj_name = self._get_full_attribute_name(node.func)
                # If the object itself is a taint source, the return is tainted
                if is_taint_source(obj_name):
                    return True
                # If the base object is tainted, the return is tainted
                if self._is_value_tainted(node.func.value, line_no):
                    return True
            
            # Check if any arguments are tainted (taint propagation through call)
            for arg in node.args:
                if self._is_value_tainted(arg, line_no):
                    return True
        
        elif isinstance(node, ast.BinOp):
            # Binary operations propagate taint
            return (self._is_value_tainted(node.left, line_no) or 
                   self._is_value_tainted(node.right, line_no))
        
        elif isinstance(node, ast.UnaryOp):
            return self._is_value_tainted(node.operand, line_no)
        
        elif isinstance(node, ast.Subscript):
            # arr[idx] or dict['key'] - check if container is tainted
            # If the container (dict/list) is tainted, the extracted value is tainted
            return self._is_value_tainted(node.value, line_no)
        
        elif isinstance(node, ast.Attribute):
            # obj.attr - check if object is tainted
            attr_name = self._get_full_attribute_name(node)
            if is_taint_source(attr_name):
                return True
            return self._is_value_tainted(node.value, line_no)
        
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            # Collection literals - tainted if any element is tainted
            for elt in node.elts:
                if self._is_value_tainted(elt, line_no):
                    return True
        
        elif isinstance(node, ast.Dict):
            # Dict literals
            for key, value in zip(node.keys, node.values):
                if key and self._is_value_tainted(key, line_no):
                    return True
                if self._is_value_tainted(value, line_no):
                    return True
        
        elif isinstance(node, ast.JoinedStr):
            # f-strings propagate taint
            for value in node.values:
                if isinstance(value, ast.FormattedValue):
                    if self._is_value_tainted(value.value, line_no):
                        return True
        
        return False
    
    def _mark_tainted(self, var_name: str, line_no: int):
        """Mark a variable as tainted at a specific line"""
        if var_name not in self.tainted_vars:
            self.tainted_vars[var_name] = set()
        self.tainted_vars[var_name].add(line_no)
    
    def _is_tainted_at_line(self, var_name: str, line_no: int) -> bool:
        """Check if a variable is tainted at or before a specific line"""
        if var_name not in self.tainted_vars:
            return False
        
        # Check if tainted at any line before or at the current line
        return any(taint_line <= line_no for taint_line in self.tainted_vars[var_name])
    
    def _extract_target_names(self, node: ast.AST) -> List[str]:
        """Extract variable names from assignment target"""
        names = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                names.extend(self._extract_target_names(elt))
        elif isinstance(node, ast.Attribute):
            # For obj.attr, track the base object
            if isinstance(node.value, ast.Name):
                names.append(node.value.id)
        elif isinstance(node, ast.Subscript):
            # For arr[idx], track the array
            if isinstance(node.value, ast.Name):
                names.append(node.value.id)
        return names
    
    def _get_func_name(self, node: ast.AST) -> str:
        """Get function name from call node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return "<unknown>"
    
    def _get_full_attribute_name(self, node: ast.Attribute) -> str:
        """Get full attribute name (e.g., request.args)"""
        parts = [node.attr]
        current = node.value
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return '.'.join(reversed(parts))


class InterProceduralTaintTracker:
    """
    Track taint across multiple functions using call graph
    """
    
    def __init__(self, call_graph):
        """
        Initialize inter-procedural taint tracker
        
        Args:
            call_graph: CallGraph instance
        """
        self.call_graph = call_graph
        self.function_taints: Dict[str, Dict[str, Any]] = {}  # func_name -> taint results
    
    def find_taint_paths(
        self,
        source_pattern: str,
        sink_function: str,
        max_depth: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find paths where tainted data from source reaches a dangerous sink
        
        Args:
            source_pattern: Pattern to identify taint source (e.g., "request.args")
            sink_function: Dangerous function name
            max_depth: Maximum call chain depth
        
        Returns:
            List of taint path dictionaries
        """
        paths = []
        
        # Find functions that contain the source pattern
        source_functions = self._find_functions_with_pattern(source_pattern)
        
        # Find functions that call the sink
        sink_callers = self._find_functions_calling_sink(sink_function)
        
        # For each source function, find paths to sink callers
        for source_func in source_functions:
            for sink_caller in sink_callers:
                # Find call chains from source to sink
                call_chains = self.call_graph.find_paths_between(
                    source_func,
                    sink_caller,
                    max_length=max_depth
                )
                
                for chain in call_chains:
                    paths.append({
                        'source': source_pattern,
                        'sink': sink_function,
                        'path': chain,
                        'depth': len(chain) - 1,
                        'confidence': self._calculate_confidence(chain, source_pattern, sink_function)
                    })
        
        return paths
    
    def _find_functions_with_pattern(self, pattern: str) -> List[str]:
        """Find functions that contain a specific pattern"""
        # This is a simplified version - in practice, would need AST analysis
        functions = []
        # Would iterate through all functions and check if they use the pattern
        # For now, return empty list as this requires integration with SearchBackend
        return functions
    
    def _find_functions_calling_sink(self, sink: str) -> List[str]:
        """Find functions that call a dangerous sink"""
        return self.call_graph.get_callers(sink)
    
    def _calculate_confidence(self, chain: List[str], source: str, sink: str) -> str:
        """Calculate confidence level for a taint path"""
        # Simplified confidence calculation
        if len(chain) <= 2:
            return "high"
        elif len(chain) <= 3:
            return "medium"
        else:
            return "low"

