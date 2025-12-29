"""
Control flow graph construction and guard detection
"""

import ast
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass


@dataclass
class CFGNode:
    """Node in a control flow graph"""
    id: int
    type: str  # "statement", "if", "while", "for", "try", "return"
    line_no: int
    code: str
    successors: List[int]  # IDs of successor nodes


class ControlFlowGraph:
    """
    Basic control flow graph for a function
    """
    
    def __init__(self):
        """Initialize CFG"""
        self.nodes: Dict[int, CFGNode] = {}
        self.entry_node_id: Optional[int] = None
        self.exit_node_id: Optional[int] = None
        self.next_id = 0
    
    def build_from_function(self, function_ast: ast.FunctionDef) -> 'ControlFlowGraph':
        """
        Build CFG from a function AST
        
        Args:
            function_ast: AST node for a function
        
        Returns:
            Self for chaining
        """
        # Create entry node
        self.entry_node_id = self._create_node(
            "entry",
            function_ast.lineno,
            f"def {function_ast.name}(...)"
        )
        
        # Process function body
        last_node_ids = [self.entry_node_id]
        
        for stmt in function_ast.body:
            last_node_ids = self._process_statement(stmt, last_node_ids)
        
        # Create exit node
        self.exit_node_id = self._create_node(
            "exit",
            function_ast.end_lineno or function_ast.lineno,
            "return"
        )
        
        # Connect last statements to exit
        for node_id in last_node_ids:
            self.nodes[node_id].successors.append(self.exit_node_id)
        
        return self
    
    def _create_node(self, node_type: str, line_no: int, code: str) -> int:
        """Create a new CFG node"""
        node_id = self.next_id
        self.next_id += 1
        
        self.nodes[node_id] = CFGNode(
            id=node_id,
            type=node_type,
            line_no=line_no,
            code=code,
            successors=[]
        )
        
        return node_id
    
    def _process_statement(
        self,
        stmt: ast.AST,
        predecessor_ids: List[int]
    ) -> List[int]:
        """
        Process a statement and add to CFG
        
        Returns:
            List of node IDs that should connect to next statement
        """
        if isinstance(stmt, ast.If):
            return self._process_if(stmt, predecessor_ids)
        elif isinstance(stmt, ast.While):
            return self._process_while(stmt, predecessor_ids)
        elif isinstance(stmt, ast.For):
            return self._process_for(stmt, predecessor_ids)
        elif isinstance(stmt, ast.Try):
            return self._process_try(stmt, predecessor_ids)
        elif isinstance(stmt, ast.Return):
            return self._process_return(stmt, predecessor_ids)
        else:
            # Simple statement
            return self._process_simple_statement(stmt, predecessor_ids)
    
    def _process_simple_statement(
        self,
        stmt: ast.AST,
        predecessor_ids: List[int]
    ) -> List[int]:
        """Process a simple statement (assignment, call, etc.)"""
        try:
            code = ast.unparse(stmt) if hasattr(ast, 'unparse') else str(stmt)
        except:
            code = str(stmt)
        node_id = self._create_node("statement", stmt.lineno, code[:50])
        
        # Connect predecessors to this node
        for pred_id in predecessor_ids:
            self.nodes[pred_id].successors.append(node_id)
        
        return [node_id]
    
    def _process_if(
        self,
        stmt: ast.If,
        predecessor_ids: List[int]
    ) -> List[int]:
        """Process if statement"""
        # Create condition node
        cond_code = ast.unparse(stmt.test) if hasattr(ast, 'unparse') else "condition"
        cond_node_id = self._create_node("if", stmt.lineno, f"if {cond_code[:30]}")
        
        # Connect predecessors to condition
        for pred_id in predecessor_ids:
            self.nodes[pred_id].successors.append(cond_node_id)
        
        # Process then branch
        then_last_ids = [cond_node_id]
        for then_stmt in stmt.body:
            then_last_ids = self._process_statement(then_stmt, then_last_ids)
        
        # Process else branch
        else_last_ids = [cond_node_id]
        if stmt.orelse:
            for else_stmt in stmt.orelse:
                else_last_ids = self._process_statement(else_stmt, else_last_ids)
        
        # Return both branches' exit points
        return then_last_ids + else_last_ids
    
    def _process_while(
        self,
        stmt: ast.While,
        predecessor_ids: List[int]
    ) -> List[int]:
        """Process while loop"""
        cond_code = ast.unparse(stmt.test) if hasattr(ast, 'unparse') else "condition"
        cond_node_id = self._create_node("while", stmt.lineno, f"while {cond_code[:30]}")
        
        # Connect predecessors to condition
        for pred_id in predecessor_ids:
            self.nodes[pred_id].successors.append(cond_node_id)
        
        # Process loop body
        body_last_ids = [cond_node_id]
        for body_stmt in stmt.body:
            body_last_ids = self._process_statement(body_stmt, body_last_ids)
        
        # Connect loop body back to condition (back edge)
        for body_id in body_last_ids:
            self.nodes[body_id].successors.append(cond_node_id)
        
        # Loop exit connects to next statement
        return [cond_node_id]
    
    def _process_for(
        self,
        stmt: ast.For,
        predecessor_ids: List[int]
    ) -> List[int]:
        """Process for loop"""
        iter_code = ast.unparse(stmt.iter) if hasattr(ast, 'unparse') else "iterable"
        loop_node_id = self._create_node("for", stmt.lineno, f"for ... in {iter_code[:20]}")
        
        # Connect predecessors
        for pred_id in predecessor_ids:
            self.nodes[pred_id].successors.append(loop_node_id)
        
        # Process loop body
        body_last_ids = [loop_node_id]
        for body_stmt in stmt.body:
            body_last_ids = self._process_statement(body_stmt, body_last_ids)
        
        # Back edge
        for body_id in body_last_ids:
            self.nodes[body_id].successors.append(loop_node_id)
        
        return [loop_node_id]
    
    def _process_try(
        self,
        stmt: ast.Try,
        predecessor_ids: List[int]
    ) -> List[int]:
        """Process try-except statement"""
        try_node_id = self._create_node("try", stmt.lineno, "try")
        
        # Connect predecessors
        for pred_id in predecessor_ids:
            self.nodes[pred_id].successors.append(try_node_id)
        
        # Process try body
        try_last_ids = [try_node_id]
        for try_stmt in stmt.body:
            try_last_ids = self._process_statement(try_stmt, try_last_ids)
        
        # Process except handlers
        exit_ids = try_last_ids
        for handler in stmt.handlers:
            handler_last_ids = [try_node_id]  # Handlers can be entered from try node
            for handler_stmt in handler.body:
                handler_last_ids = self._process_statement(handler_stmt, handler_last_ids)
            exit_ids.extend(handler_last_ids)
        
        # Process finally
        if stmt.finalbody:
            finally_last_ids = exit_ids
            for finally_stmt in stmt.finalbody:
                finally_last_ids = self._process_statement(finally_stmt, finally_last_ids)
            return finally_last_ids
        
        return exit_ids
    
    def _process_return(
        self,
        stmt: ast.Return,
        predecessor_ids: List[int]
    ) -> List[int]:
        """Process return statement"""
        ret_code = ""
        if stmt.value:
            ret_code = ast.unparse(stmt.value) if hasattr(ast, 'unparse') else "value"
        
        ret_node_id = self._create_node("return", stmt.lineno, f"return {ret_code[:30]}")
        
        # Connect predecessors
        for pred_id in predecessor_ids:
            self.nodes[pred_id].successors.append(ret_node_id)
        
        # Return statements don't connect to subsequent statements
        return []
    
    def find_guards_before_line(self, line_no: int) -> List[Dict[str, Any]]:
        """
        Find conditional guards (if statements) that must be true before reaching a line
        
        Args:
            line_no: Line number to analyze
        
        Returns:
            List of guard information
        """
        guards = []
        
        # Find the node at or after the target line
        target_node = None
        for node in self.nodes.values():
            if node.line_no >= line_no:
                if target_node is None or node.line_no < target_node.line_no:
                    target_node = node
        
        if not target_node:
            return guards
        
        # Find all paths from entry to target
        paths = self._find_paths_to_node(self.entry_node_id, target_node.id)
        
        # Extract conditional guards from paths
        for path in paths:
            for node_id in path:
                node = self.nodes[node_id]
                if node.type == "if":
                    guards.append({
                        'type': 'if',
                        'line': node.line_no,
                        'condition': node.code,
                        'protects_line': line_no
                    })
        
        return guards
    
    def _find_paths_to_node(
        self,
        start_id: int,
        target_id: int,
        max_depth: int = 20
    ) -> List[List[int]]:
        """Find all paths from start to target node"""
        paths = []
        
        def dfs(current_id: int, path: List[int], depth: int):
            if depth > max_depth:
                return
            
            if current_id == target_id:
                paths.append(path[:])
                return
            
            if current_id in path:  # Cycle detection
                return
            
            path.append(current_id)
            
            for successor_id in self.nodes[current_id].successors:
                dfs(successor_id, path, depth + 1)
            
            path.pop()
        
        dfs(start_id, [], 0)
        return paths


def find_guards_for_call(
    function_ast: ast.FunctionDef,
    dangerous_call: str
) -> List[Dict[str, Any]]:
    """
    Find conditional guards protecting a dangerous function call
    
    Args:
        function_ast: AST of the function
        dangerous_call: Name of dangerous function to find guards for
    
    Returns:
        List of guard information
    """
    guards = []
    
    # Find the line number where the dangerous call occurs
    call_line = None
    for node in ast.walk(function_ast):
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            
            if func_name == dangerous_call:
                call_line = node.lineno
                break
    
    if not call_line:
        return guards
    
    # Build CFG
    cfg = ControlFlowGraph().build_from_function(function_ast)
    
    # Find guards before this line
    guards = cfg.find_guards_before_line(call_line)
    
    return guards


def has_validation_before(
    function_ast: ast.FunctionDef,
    variable_name: str,
    before_line: int
) -> bool:
    """
    Check if a variable is validated before a specific line
    
    Args:
        function_ast: AST of the function
        variable_name: Name of variable to check
        before_line: Line number to check before
    
    Returns:
        True if validation found
    """
    # Look for if statements that check the variable
    for node in ast.walk(function_ast):
        if isinstance(node, ast.If):
            if node.lineno < before_line:
                # Check if the condition involves the variable
                condition_str = ast.unparse(node.test) if hasattr(ast, 'unparse') else ""
                if variable_name in condition_str:
                    # Found a conditional check
                    return True
    
    return False

