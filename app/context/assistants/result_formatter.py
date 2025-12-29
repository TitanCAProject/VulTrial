"""Result formatter - formats analysis results for display"""


class ResultFormatter:
    """Formats advanced analysis results for display"""
    
    @staticmethod
    def format_call_chain(chain_result) -> dict:
        """Format CallChainResult for evidence"""
        chain_str = " → ".join(chain_result.chain)
        detail_blocks = []
        for func in chain_result.details[:3]:
            func_name = getattr(func, 'func_name', None) or getattr(func, 'function_name', None)
            class_name = getattr(func, 'class_name', None)
            header = func_name or class_name or 'snippet'
            code_snippet = getattr(func, 'code', '')[:500]
            detail_blocks.append(f"[{header}]\n{code_snippet}")

        details_code = "\n\n".join(detail_blocks)
        
        return {
            'type': 'call_chain',
            'file_path': 'multi-file',
            'code': f"Call Chain (depth {chain_result.depth}):\n{chain_str}\n\nDetails:\n{details_code}",
            'context': f"Multi-level call chain: {chain_str}"
        }
    
    @staticmethod
    def format_taint_path(taint_path) -> dict:
        """Format TaintPath for evidence"""
        path_str = " → ".join(taint_path.path)
        vars_str = ", ".join(taint_path.variables) if taint_path.variables else "N/A"
        
        return {
            'type': 'taint_path',
            'file_path': 'analysis',
            'code': f"Taint Flow Analysis:\nSource: {taint_path.source}\nSink: {taint_path.sink}\nPath: {path_str}\nVariables: {vars_str}\nConfidence: {taint_path.confidence}",
            'context': f"Tainted data from {taint_path.source} reaches {taint_path.sink}"
        }
    
    @staticmethod
    def format_variable_flow(var_flow) -> dict:
        """Format variable flow tracking for evidence"""
        assignments_str = ", ".join(map(str, var_flow.get('assignments', [])))
        uses_str = ", ".join(map(str, var_flow.get('uses', [])))
        
        return {
            'type': 'variable_flow',
            'file_path': var_flow.get('file', 'unknown'),
            'code': f"Variable Flow Analysis: {var_flow['variable']}\nFunction: {var_flow['function']}\nAssignments at lines: {assignments_str}\nUses at lines: {uses_str}\nReturned: {var_flow.get('returned', False)}",
            'context': f"Tracking variable {var_flow['variable']} in {var_flow['function']}"
        }
    
    @staticmethod
    def get_code_language(backend_type: str) -> str:
        """Get syntax highlighting language for code blocks"""
        if "C++" in backend_type or "C/C++" in backend_type:
            return "cpp"
        elif "Java" in backend_type:
            return "java"
        elif "JavaScript" in backend_type or "TypeScript" in backend_type:
            return "javascript"
        else:
            return "python"

