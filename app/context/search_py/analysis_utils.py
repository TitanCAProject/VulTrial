"""
Utility functions for AST analysis and code flow tracking
"""

import ast
from typing import List, Set, Dict, Any, Optional, Tuple


# Dangerous sinks that should not receive untrusted input
DANGEROUS_SINKS = {
    # Code execution
    'exec', 'eval', 'compile', '__import__',
    
    # Command execution
    'system', 'popen', 'spawn', 'execl', 'execlp', 'execle',
    'execv', 'execvp', 'execve', 'execvpe',
    
    # Subprocess
    'call', 'run', 'Popen', 'check_call', 'check_output',
    
    # SQL operations (common patterns)
    'execute', 'executemany', 'raw', 'query',
    
    # File operations (path traversal risks)
    'open', 'read', 'write', 'remove', 'unlink', 'rmdir',
    
    # Deserialization
    'loads', 'load', 'Unpickler', 'unmarshal',
    
    # Template rendering (SSTI)
    'render', 'render_template', 'render_string',
    
    # URL operations (SSRF)
    'urlopen', 'request', 'get', 'post',
}

# Taint sources - where untrusted data comes from
TAINT_SOURCES = {
    # User input
    'input', 'raw_input',
    
    # Web request data
    'request', 'args', 'form', 'cookies', 'headers', 'files',
    'get_data', 'get_json',
    
    # Command line
    'argv', 'environ', 'getenv',
    
    # Network
    'recv', 'recvfrom', 'read', 'readline', 'readlines',
    
    # File input
    'read', 'readline', 'readlines',
}


class VariableExtractor(ast.NodeVisitor):
    """Extract variable assignments and uses from AST"""
    
    def __init__(self):
        self.assignments: Dict[str, List[int]] = {}  # var_name -> [line_numbers]
        self.uses: Dict[str, List[int]] = {}  # var_name -> [line_numbers]
        
    def visit_Assign(self, node: ast.Assign) -> None:
        """Track variable assignments"""
        for target in node.targets:
            var_names = self._extract_names(target)
            for name in var_names:
                if name not in self.assignments:
                    self.assignments[name] = []
                self.assignments[name].append(node.lineno)
        
        # Visit the value being assigned to track uses
        self.visit(node.value)
        self.generic_visit(node)
    
    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Track augmented assignments (+=, -=, etc.)"""
        var_names = self._extract_names(node.target)
        for name in var_names:
            if name not in self.assignments:
                self.assignments[name] = []
            self.assignments[name].append(node.lineno)
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:
        """Track variable uses"""
        if isinstance(node.ctx, ast.Load):
            if node.id not in self.uses:
                self.uses[node.id] = []
            self.uses[node.id].append(node.lineno)
        self.generic_visit(node)
    
    def _extract_names(self, node: ast.AST) -> List[str]:
        """Extract variable names from assignment targets"""
        names = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Tuple) or isinstance(node, ast.List):
            for elt in node.elts:
                names.extend(self._extract_names(elt))
        elif isinstance(node, ast.Attribute):
            # For obj.attr, just track the base object
            if isinstance(node.value, ast.Name):
                names.append(node.value.id)
        elif isinstance(node, ast.Subscript):
            # For arr[idx], track the array
            if isinstance(node.value, ast.Name):
                names.append(node.value.id)
        return names


class FunctionCallExtractor(ast.NodeVisitor):
    """Extract function calls with arguments"""
    
    def __init__(self):
        self.calls: List[Dict[str, Any]] = []
        
    def visit_Call(self, node: ast.Call) -> None:
        """Extract function call information"""
        func_name = self._get_func_name(node.func)
        
        # Extract argument names
        args = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                args.append(arg.id)
            elif isinstance(arg, ast.Constant):
                args.append(f"<constant:{arg.value}>")
            else:
                args.append("<expr>")
        
        # Extract keyword argument names
        kwargs = {}
        for keyword in node.keywords:
            if keyword.arg:
                if isinstance(keyword.value, ast.Name):
                    kwargs[keyword.arg] = keyword.value.id
                else:
                    kwargs[keyword.arg] = "<expr>"
        
        self.calls.append({
            'function': func_name,
            'line': node.lineno,
            'args': args,
            'kwargs': kwargs
        })
        
        self.generic_visit(node)
    
    def _get_func_name(self, node: ast.AST) -> str:
        """Get function name from call node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            # obj.method() -> return "method"
            return node.attr
        elif isinstance(node, ast.Call):
            # Chained calls
            return self._get_func_name(node.func)
        return "<unknown>"


class DefUseChainBuilder(ast.NodeVisitor):
    """Build definition-use chains for variables within a function"""
    
    def __init__(self):
        self.def_use_chains: Dict[str, List[Tuple[int, int]]] = {}  # var -> [(def_line, use_line)]
        self.current_defs: Dict[str, int] = {}  # var -> last_def_line
        
    def visit_Assign(self, node: ast.Assign) -> None:
        """Track definitions"""
        for target in node.targets:
            var_names = self._extract_names(target)
            for name in var_names:
                self.current_defs[name] = node.lineno
        
        # Visit value to track uses
        self.visit(node.value)
        self.generic_visit(node)
    
    def visit_Name(self, node: ast.Name) -> None:
        """Track uses and link to definitions"""
        if isinstance(node.ctx, ast.Load):
            var_name = node.id
            if var_name in self.current_defs:
                if var_name not in self.def_use_chains:
                    self.def_use_chains[var_name] = []
                self.def_use_chains[var_name].append(
                    (self.current_defs[var_name], node.lineno)
                )
        self.generic_visit(node)
    
    def _extract_names(self, node: ast.AST) -> List[str]:
        """Extract variable names from assignment targets"""
        names = []
        if isinstance(node, ast.Name):
            names.append(node.id)
        elif isinstance(node, ast.Tuple) or isinstance(node, ast.List):
            for elt in node.elts:
                names.extend(self._extract_names(elt))
        return names


def extract_variables(function_ast: ast.FunctionDef) -> Tuple[Dict[str, List[int]], Dict[str, List[int]]]:
    """
    Extract variable assignments and uses from a function
    
    Args:
        function_ast: AST node for a function
        
    Returns:
        (assignments, uses) where each is {var_name: [line_numbers]}
    """
    extractor = VariableExtractor()
    extractor.visit(function_ast)
    return extractor.assignments, extractor.uses


def extract_function_calls(function_ast: ast.FunctionDef) -> List[Dict[str, Any]]:
    """
    Extract all function calls from a function
    
    Args:
        function_ast: AST node for a function
        
    Returns:
        List of call information dicts
    """
    extractor = FunctionCallExtractor()
    extractor.visit(function_ast)
    return extractor.calls


def build_def_use_chains(function_ast: ast.FunctionDef) -> Dict[str, List[Tuple[int, int]]]:
    """
    Build definition-use chains for variables in a function
    
    Args:
        function_ast: AST node for a function
        
    Returns:
        {var_name: [(def_line, use_line), ...]}
    """
    builder = DefUseChainBuilder()
    builder.visit(function_ast)
    return builder.def_use_chains


def is_dangerous_sink(func_name: str) -> bool:
    """Check if a function is a dangerous sink"""
    return func_name in DANGEROUS_SINKS


def is_taint_source(name: str) -> bool:
    """Check if a name represents a taint source"""
    # Check exact match
    if name in TAINT_SOURCES:
        return True
    
    # Check if it's an attribute of a taint source (e.g., request.args)
    for source in TAINT_SOURCES:
        if name.startswith(source + '.') or name.endswith('.' + source):
            return True
    
    return False


def get_function_parameters(function_ast: ast.FunctionDef) -> List[str]:
    """Extract parameter names from a function definition"""
    params = []
    
    # Regular arguments
    for arg in function_ast.args.args:
        params.append(arg.arg)
    
    # *args
    if function_ast.args.vararg:
        params.append(function_ast.args.vararg.arg)
    
    # **kwargs
    if function_ast.args.kwarg:
        params.append(function_ast.args.kwarg.arg)
    
    return params


def find_return_statements(function_ast: ast.FunctionDef) -> List[Tuple[int, Optional[str]]]:
    """
    Find all return statements in a function
    
    Returns:
        List of (line_number, returned_var_name or None)
    """
    returns = []
    
    for node in ast.walk(function_ast):
        if isinstance(node, ast.Return):
            var_name = None
            if node.value and isinstance(node.value, ast.Name):
                var_name = node.value.id
            returns.append((node.lineno, var_name))
    
    return returns

