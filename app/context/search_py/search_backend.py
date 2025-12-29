"""
Search backend adapted from reference implementation
Provides production-quality search APIs for vulnerability analysis
"""

from collections import defaultdict, namedtuple
from collections.abc import MutableMapping
from functools import cache
from pathlib import Path
from typing import Optional

from . import search_utils
from .data_structures import SearchResult

LineRange = namedtuple("LineRange", ["start", "end"])

ClassIndexType = MutableMapping[str, list[tuple[str, LineRange]]]
ClassFuncIndexType = MutableMapping[
    str, MutableMapping[str, list[tuple[str, LineRange]]]
]
FuncIndexType = MutableMapping[str, list[tuple[str, LineRange]]]
ClassRelationIndexType = MutableMapping[str, list[str]]

RESULT_SHOW_LIMIT = 3


class SearchBackend:
    """Production-quality search backend adapted from reference code"""
    
    def __init__(self, project_path: str):
        self.project_path = project_path
        # list of all files ending with .py, which are likely not test files
        # These are all ABSOLUTE paths.
        self.parsed_files: list[str] = []

        # for file name in the indexes, assume they are absolute path
        # class name -> [(file_name, line_range)]
        self.class_index: ClassIndexType = {}

        # {class_name -> {func_name -> [(file_name, line_range)]}}
        self.class_func_index: ClassFuncIndexType = {}

        # {class_name -> [parent_class_names]}
        self.class_relation_index: ClassRelationIndexType = defaultdict(list)

        # function name -> [(file_name, line_range)]
        self.function_index: FuncIndexType = {}
        
        # Advanced analysis structures (built on-demand)
        self.ast_cache: dict = {}  # file_path -> parsed AST
        self._call_graph: Optional = None  # CallGraph instance (on-demand)
        
        self._build_index()

    def _build_index(self):
        """Build indexes for fast lookup"""
        self._update_indices(*self._build_python_index(self.project_path))

    def _update_indices(
        self,
        class_index: ClassIndexType,
        class_func_index: ClassFuncIndexType,
        function_index: FuncIndexType,
        class_relation_index: ClassRelationIndexType,
        parsed_files: list[str],
    ) -> None:
        self.class_index.update(class_index)
        self.class_func_index.update(class_func_index)
        self.function_index.update(function_index)
        self.class_relation_index.update(class_relation_index)
        self.parsed_files.extend(parsed_files)

    @classmethod
    @cache
    def _build_python_index(cls, project_path: str) -> tuple[
        ClassIndexType,
        ClassFuncIndexType,
        FuncIndexType,
        ClassRelationIndexType,
        list[str],
    ]:
        """Build indexes from Python files"""
        class_index: ClassIndexType = defaultdict(list)
        class_func_index: ClassFuncIndexType = defaultdict(lambda: defaultdict(list))
        function_index: FuncIndexType = defaultdict(list)
        class_relation_index: ClassRelationIndexType = defaultdict(list)

        py_files = search_utils.find_python_files(project_path)
        parsed_py_files = []
        
        for py_file in py_files:
            file_info = search_utils.parse_python_file(py_file)
            if file_info is None:
                continue
            parsed_py_files.append(py_file)
            
            classes, class_to_funcs, top_level_funcs, class_relation_map = file_info

            # (1) build class index
            for c, start, end in classes:
                class_index[c].append((py_file, LineRange(start, end)))

            # (2) build class-function index
            for c, class_funcs in class_to_funcs.items():
                for f, start, end in class_funcs:
                    class_func_index[c][f].append((py_file, LineRange(start, end)))

            # (3) build (top-level) function index
            for f, start, end in top_level_funcs:
                function_index[f].append((py_file, LineRange(start, end)))

            # (4) build class-superclass index
            for (c, start, end), super_classes in class_relation_map.items():
                class_relation_index[c] = super_classes

        return (
            class_index,
            class_func_index,
            function_index,
            class_relation_index,
            parsed_py_files,
        )

    def _get_candidate_matched_py_files(self, target_file_name: str):
        """Search for files matching target_file_name"""
        parsed_files_lower = [f.lower() for f in self.parsed_files]
        parsed_files = zip(self.parsed_files, parsed_files_lower)
        target_lower = target_file_name.lower()

        candidates = []
        for orig_file, lower_file in parsed_files:
            if lower_file.endswith(target_lower):
                candidates.append(orig_file)
        return candidates

    def search_class(self, class_name: str) -> tuple[str, list[SearchResult], bool]:
        """
        Search for a class in the codebase.
        Returns signature only (class def + method signatures, no method bodies).
        
        Args:
            class_name: Name of the class to search for
            
        Returns:
            (result_message, search_results, success_bool)
        """
        search_res: list[SearchResult] = []
        tool_result = f"Could not find class {class_name} in the codebase."

        if class_name not in self.class_index:
            return tool_result, search_res, False

        for fname, (start, end) in self.class_index[class_name]:
            # Get class signature (not full code)
            code = search_utils.get_class_signature(fname, class_name)
            res = SearchResult(fname, start, end, class_name, None, code)
            search_res.append(res)

        if not search_res:
            return tool_result, search_res, False

        # Format result
        tool_result = f"Found {len(search_res)} classes with name {class_name} in the codebase:\n\n"
        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_result += "They appeared in the following files:\n"
            for res in search_res:
                tool_result += f"- {Path(res.file_path).name}\n"
        else:
            for idx, res in enumerate(search_res):
                tool_result += f"- Search result {idx + 1}:\n```\n{res.code}\n```\n"
        
        return tool_result, search_res[:RESULT_SHOW_LIMIT], True

    def search_method_in_class(
        self, method_name: str, class_name: str
    ) -> tuple[str, list[SearchResult], bool]:
        """
        Search for a method in a given class.
        Returns the actual code of the method.
        
        Args:
            method_name: Name of the method to search for
            class_name: Consider only methods in this class
            
        Returns:
            (result_message, search_results, success_bool)
        """
        if class_name not in self.class_index:
            tool_output = f"Could not find class {class_name} in the codebase."
            return tool_output, [], False

        # Search for method in class
        search_res: list[SearchResult] = []
        if class_name in self.class_func_index and method_name in self.class_func_index[class_name]:
            for fname, (start, end) in self.class_func_index[class_name][method_name]:
                func_code = search_utils.get_code_snippets(fname, start, end)
                res = SearchResult(fname, start, end, class_name, method_name, func_code)
                search_res.append(res)

        if not search_res:
            tool_output = f"Could not find method {method_name} in class {class_name}."
            return tool_output, [], False

        # Format result
        tool_output = f"Found {len(search_res)} methods with name {method_name} in class {class_name}:\n\n"

        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_output += f"Too many results, showing first {RESULT_SHOW_LIMIT}:\n"
        
        for idx, res in enumerate(search_res[:RESULT_SHOW_LIMIT]):
            tool_output += f"- Search result {idx + 1}:\n```\n{res.code}\n```\n"

        return tool_output, search_res[:RESULT_SHOW_LIMIT], True

    def search_method(self, method_name: str) -> tuple[str, list[SearchResult], bool]:
        """
        Search for a method in the entire codebase.
        Returns the actual code of the method.
        
        Args:
            method_name: Name of the method to search for
            
        Returns:
            (result_message, search_results, success_bool)
        """
        # Search in top-level functions
        search_res: list[SearchResult] = []
        if method_name in self.function_index:
            for fname, (start, end) in self.function_index[method_name]:
                func_code = search_utils.get_code_snippets(fname, start, end)
                res = SearchResult(fname, start, end, None, method_name, func_code)
                search_res.append(res)

        # Search in all classes
        for class_name in self.class_func_index:
            if method_name in self.class_func_index[class_name]:
                for fname, (start, end) in self.class_func_index[class_name][method_name]:
                    func_code = search_utils.get_code_snippets(fname, start, end)
                    res = SearchResult(fname, start, end, class_name, method_name, func_code)
                    search_res.append(res)

        if not search_res:
            tool_output = f"Could not find method {method_name} in the codebase."
            return tool_output, [], False

        tool_output = f"Found {len(search_res)} methods with name {method_name} in the codebase:\n\n"

        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_output += "They appeared in the following files:\n"
            for res in search_res:
                tool_output += f"- {Path(res.file_path).name}\n"
        else:
            for idx, res in enumerate(search_res):
                tool_output += f"- Search result {idx + 1}:\n```\n{res.code}\n```\n"

        return tool_output, search_res[:RESULT_SHOW_LIMIT], True

    def search_code(self, code_str: str) -> tuple[str, list[SearchResult], bool]:
        """
        Search for a code snippet in the entire codebase.
        Returns the method that contains the code snippet.
        
        Args:
            code_str: The code snippet to search for
            
        Returns:
            (result_message, search_results, success_bool)
        """
        search_res: list[SearchResult] = []
        
        for file_path in self.parsed_files:
            searched_line_and_code = search_utils.get_code_region_containing_code(
                file_path, code_str
            )
            if not searched_line_and_code:
                continue
                
            for line_no, code_region in searched_line_and_code:
                # Find which function/class this line is in
                class_name, func_name = self._file_line_to_class_and_func(file_path, line_no)
                res = SearchResult(
                    file_path, line_no, line_no, class_name, func_name, code_region
                )
                search_res.append(res)

        if not search_res:
            tool_output = f"Could not find code `{code_str}` in the codebase."
            return tool_output, [], False

        tool_output = f"Found {len(search_res)} snippets containing `{code_str}` in the codebase:\n\n"

        if len(search_res) > RESULT_SHOW_LIMIT:
            tool_output += "They appeared in the following files:\n"
            files = list(set(res.file_path for res in search_res))
            for f in files[:RESULT_SHOW_LIMIT]:
                tool_output += f"- {Path(f).name}\n"
        else:
            for idx, res in enumerate(search_res):
                tool_output += f"- Search result {idx + 1}:\n```\n{res.code}\n```\n"

        return tool_output, search_res[:RESULT_SHOW_LIMIT], True

    def get_code_around_line(
        self, file_name: str, line_no: int, window_size: int = 10
    ) -> tuple[str, list[SearchResult], bool]:
        """
        Get the region of code around a line number in a file.
        
        Args:
            file_name: The file name
            line_no: The line number (1-based)
            window_size: Number of lines before and after
            
        Returns:
            (result_message, search_results, success_bool)
        """
        candidate_py_abs_paths = self._get_candidate_matched_py_files(file_name)
        if not candidate_py_abs_paths:
            tool_output = f"Could not find file {file_name} in the codebase."
            return tool_output, [], False

        region_search_results: list[SearchResult] = []

        for file_path in candidate_py_abs_paths:
            snippet = search_utils.get_code_region_around_line(
                file_path, line_no, window_size
            )
            if snippet is None:
                continue
            
            class_name, func_name = self._file_line_to_class_and_func(file_path, line_no)
            
            start_lineno = line_no - window_size
            end_lineno = line_no + window_size
            res = SearchResult(
                file_path, start_lineno, end_lineno, class_name, func_name, snippet
            )
            region_search_results.append(res)

        if not region_search_results:
            tool_output = f"{line_no} is invalid in file {file_name}."
            return tool_output, [], False

        tool_output = f"Found code around line {line_no}:\n\n"
        for idx, res in enumerate(region_search_results):
            tool_output += f"- Search result {idx + 1}:\n```\n{res.code}\n```\n"

        return tool_output, region_search_results, True

    def _file_line_to_class_and_func(
        self, file_path: str, line_no: int
    ) -> tuple[str | None, str | None]:
        """
        Given a file path and line number, return the class and function name.
        """
        # Check if line is inside a class method
        for class_name in self.class_func_index:
            func_dict = self.class_func_index[class_name]
            for func_name, func_info in func_dict.items():
                for file_name, (start, end) in func_info:
                    if file_name == file_path and start <= line_no <= end:
                        return class_name, func_name

        # Check if line is inside a top-level function
        for func_name in self.function_index:
            for file_name, (start, end) in self.function_index[func_name]:
                if file_name == file_path and start <= line_no <= end:
                    return None, func_name

        return None, None

    # Additional helper methods
    
    def search_function(self, function_name: str) -> list[SearchResult]:
        """
        Search for function (top-level or in classes)
        
        Returns:
            List of SearchResult objects
        """
        results = []
        
        # Top-level functions
        if function_name in self.function_index:
            for fname, (start, end) in self.function_index[function_name]:
                func_code = search_utils.get_code_snippets(fname, start, end)
                res = SearchResult(fname, start, end, None, function_name, func_code)
                results.append(res)
        
        # Methods in classes
        for class_name in self.class_func_index:
            if function_name in self.class_func_index[class_name]:
                for fname, (start, end) in self.class_func_index[class_name][function_name]:
                    func_code = search_utils.get_code_snippets(fname, start, end)
                    res = SearchResult(fname, start, end, class_name, function_name, func_code)
                    results.append(res)
        
        return results

    def find_callers(self, function_name: str) -> list[SearchResult]:
        """
        Find functions that call the specified function
        
        Args:
            function_name: Name of the function
            
        Returns:
            List of SearchResult objects for caller functions
        """
        results = []
        pattern = f"{function_name}("
        
        # Search in all functions
        for func in self.function_index:
            # Skip the function itself
            if func == function_name:
                continue
                
            for fname, (start, end) in self.function_index[func]:
                func_code = search_utils.get_code_snippets(fname, start, end)
                if pattern in func_code:
                    # Make sure it's actually a call, not just the definition
                    # Check if the pattern appears in a context that looks like a call
                    lines = func_code.split('\n')
                    is_actual_call = False
                    for line in lines:
                        if pattern in line:
                            line_stripped = line.strip()
                            # Skip if it's a def line (function definition)
                            if line_stripped.startswith('def ' + function_name):
                                continue
                            # This looks like a real call
                            is_actual_call = True
                            break
                    
                    if is_actual_call:
                        res = SearchResult(fname, start, end, None, func, func_code)
                        results.append(res)
        
        # Search in all methods
        for class_name in self.class_func_index:
            for method_name in self.class_func_index[class_name]:
                # Skip the method itself if it has the same name
                if method_name == function_name:
                    continue
                    
                for fname, (start, end) in self.class_func_index[class_name][method_name]:
                    method_code = search_utils.get_code_snippets(fname, start, end)
                    if pattern in method_code:
                        # Verify it's actually a call
                        lines = method_code.split('\n')
                        is_actual_call = False
                        for line in lines:
                            if pattern in line:
                                line_stripped = line.strip()
                                # Skip def lines
                                if line_stripped.startswith('def ' + function_name):
                                    continue
                                is_actual_call = True
                                break
                        
                        if is_actual_call:
                            res = SearchResult(fname, start, end, class_name, method_name, method_code)
                            results.append(res)
        
        return results[:5]  # Limit to 5 callers
    
    def find_callees(self, function_name: str) -> list[SearchResult]:
        """
        Find functions called by the specified function
        
        Args:
            function_name: Name of the function
            
        Returns:
            List of SearchResult objects for callee functions (functions this function calls)
        """
        results = []
        
        # First, find the target function's code
        target_function_code = None
        target_file = None
        target_start = None
        
        # Search in top-level functions
        if function_name in self.function_index:
            for fname, (start, end) in self.function_index[function_name]:
                target_function_code = search_utils.get_code_snippets(fname, start, end)
                target_file = fname
                target_start = start
                break
        
        # Search in class methods
        if not target_function_code:
            for class_name in self.class_func_index:
                if function_name in self.class_func_index[class_name]:
                    for fname, (start, end) in self.class_func_index[class_name][function_name]:
                        target_function_code = search_utils.get_code_snippets(fname, start, end)
                        target_file = fname
                        target_start = start
                        break
                    if target_function_code:
                        break
        
        if not target_function_code:
            return results  # Function not found
        
        # Extract function calls from the target function
        # Pattern: something(...) or obj.method(...)
        import re
        
        # Match both function calls and method calls
        # Pattern 1: function_name(...)
        # Pattern 2: obj.method_name(...)
        call_pattern = r'(?:\.)?([a-z_][a-z0-9_]*)\s*\('
        
        # Find all potential function calls
        potential_calls = re.findall(call_pattern, target_function_code, re.IGNORECASE)
        
        # Filter out Python built-ins, keywords, and the function itself
        python_builtins = {
            'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple',
            'open', 'range', 'enumerate', 'zip', 'map', 'filter', 'sorted',
            'isinstance', 'hasattr', 'getattr', 'setattr', 'super', 'connect',
            'if', 'for', 'while', 'return', 'yield', 'raise', 'assert', 'append',
            'extend', 'split', 'join', 'strip', 'format', 'replace', 'startswith',
            'endswith', 'lower', 'upper', 'read', 'write', 'close', 'get', 'items',
            'keys', 'values', 'cursor', 'execute', 'fetchone', 'fetchall'
        }
        
        seen_callees = set()
        for callee_name in potential_calls:
            # Skip built-ins, the function itself, and already seen
            if (callee_name in python_builtins or 
                callee_name == function_name or 
                callee_name in seen_callees):
                continue
            
            # Try to find this callee in our index
            callee_found = False
            
            # Search in functions
            if callee_name in self.function_index:
                for fname, (start, end) in self.function_index[callee_name]:
                    callee_code = search_utils.get_code_snippets(fname, start, end)
                    res = SearchResult(fname, start, end, None, callee_name, callee_code)
                    results.append(res)
                    seen_callees.add(callee_name)
                    callee_found = True
                    break
            
            # Search in class methods
            if not callee_found:
                for class_name in self.class_func_index:
                    if callee_name in self.class_func_index[class_name]:
                        for fname, (start, end) in self.class_func_index[class_name][callee_name]:
                            callee_code = search_utils.get_code_snippets(fname, start, end)
                            res = SearchResult(fname, start, end, class_name, callee_name, callee_code)
                            results.append(res)
                            seen_callees.add(callee_name)
                            callee_found = True
                            break
                        if callee_found:
                            break
        
        return results[:10]  # Limit to 10 callees
    
    # Advanced analysis methods
    
    def _get_call_graph(self):
        """Get or build call graph (lazy initialization)"""
        if self._call_graph is None:
            from .call_graph import CallGraph
            self._call_graph = CallGraph()
            self._call_graph.build_from_indexes(
                self.function_index,
                self.class_func_index,
                search_utils.get_code_snippets
            )
        return self._call_graph
    
    def _get_ast_for_file(self, file_path: str):
        """Get AST for a file (with caching)"""
        import ast
        
        if file_path not in self.ast_cache:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.ast_cache[file_path] = ast.parse(content)
            except Exception:
                return None
        
        return self.ast_cache[file_path]
    
    def _get_function_ast(self, function_name: str):
        """Get AST node for a specific function"""
        import ast
        
        # Search in top-level functions
        if function_name in self.function_index:
            for file_path, (start, end) in self.function_index[function_name]:
                tree = self._get_ast_for_file(file_path)
                if tree:
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and node.name == function_name:
                            if node.lineno == start:
                                return node, file_path
        
        # Search in class methods
        for class_name in self.class_func_index:
            if function_name in self.class_func_index[class_name]:
                for file_path, (start, end) in self.class_func_index[class_name][function_name]:
                    tree = self._get_ast_for_file(file_path)
                    if tree:
                        for node in ast.walk(tree):
                            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                                if node.lineno == start:
                                    return node, file_path
        
        return None, None
    
    def find_call_chain(
        self,
        start_function: str,
        depth: int = 3,
        direction: str = "forward"
    ) -> list:
        """
        Build multi-level call chain starting from a function
        
        Args:
            start_function: Starting function name
            depth: How many levels to traverse (default 3)
            direction: "forward" for callees, "backward" for callers
        
        Returns:
            List of CallChainResult showing all paths up to depth
        """
        from .data_structures import CallChainResult
        from pathlib import Path
        
        call_graph = self._get_call_graph()
        chains = call_graph.find_call_chain(start_function, depth, direction)
        
        results = []
        for chain in chains:
            # Get details for each function in the chain
            details = []
            files = []
            
            for func_name in chain:
                # Find function details
                func_results = self.search_function(func_name)
                if func_results:
                    details.append(func_results[0])
                    files.append(Path(func_results[0].file_path).name)
            
            results.append(CallChainResult(
                chain=chain,
                depth=len(chain) - 1,
                files=list(set(files)),
                details=details
            ))
        
        return results
    
    def find_taint_flow(
        self,
        source_pattern: str,
        sink_function: str,
        max_depth: int = 3
    ) -> list:
        """
        Find if tainted data from source reaches dangerous sink
        
        Args:
            source_pattern: Pattern to identify taint source
            sink_function: Dangerous function that should not receive tainted data
            max_depth: Maximum call chain depth to analyze
        
        Returns:
            List of TaintPath objects showing vulnerability paths
        """
        from .data_structures import TaintPath
        from .taint_analysis import TaintTracker, InterProceduralTaintTracker
        
        paths = []
        
        # Find functions that use the source pattern
        source_functions = []
        for func_name in self.function_index.keys():
            func_ast, file_path = self._get_function_ast(func_name)
            if func_ast:
                # Check if source pattern appears in function
                import ast
                func_code = ast.unparse(func_ast) if hasattr(ast, 'unparse') else ""
                if source_pattern in func_code:
                    source_functions.append(func_name)
        
        # For each source function, analyze taint flow
        for source_func in source_functions:
            func_ast, file_path = self._get_function_ast(source_func)
            if not func_ast:
                continue
            
            tracker = TaintTracker()
            result = tracker.analyze_function(func_ast, source_func)
            
            # Check if any dangerous flows reach the sink
            for flow in result.get('dangerous_flows', []):
                if flow['sink'] == sink_function:
                    paths.append(TaintPath(
                        source=source_pattern,
                        sink=sink_function,
                        path=[source_func],
                        variables=flow['tainted_args'],
                        confidence=flow['confidence']
                    ))
        
        # Try inter-procedural analysis using call graph
        call_graph = self._get_call_graph()
        inter_tracker = InterProceduralTaintTracker(call_graph)
        inter_paths = inter_tracker.find_taint_paths(source_pattern, sink_function, max_depth)
        
        for ip in inter_paths:
            paths.append(TaintPath(
                source=source_pattern,
                sink=sink_function,
                path=ip['path'],
                variables=[],
                confidence=ip['confidence']
            ))
        
        return paths
    
    def find_guards_for_call(
        self,
        function_name: str,
        dangerous_call: str
    ) -> list:
        """
        Find conditional checks (guards) protecting a dangerous call
        
        Args:
            function_name: Function to analyze
            dangerous_call: The dangerous operation to check
        
        Returns:
            List of guard information (if-statements, try-except, etc.)
        """
        from .control_flow import find_guards_for_call
        
        func_ast, file_path = self._get_function_ast(function_name)
        if not func_ast:
            return []
        
        guards = find_guards_for_call(func_ast, dangerous_call)
        return guards
    
    def track_variable(
        self,
        function_name: str,
        variable_name: str
    ) -> dict:
        """
        Track how a variable flows through a function
        
        Args:
            function_name: Name of the function to analyze
            variable_name: Name of the variable to track
        
        Returns:
            Dict with assignments, uses, modifications, and return flows
        """
        from .analysis_utils import extract_variables, build_def_use_chains, find_return_statements
        
        func_ast, file_path = self._get_function_ast(function_name)
        if not func_ast:
            return {}
        
        # Extract variable information
        assignments, uses = extract_variables(func_ast)
        def_use_chains = build_def_use_chains(func_ast)
        returns = find_return_statements(func_ast)
        
        # Check if variable is returned
        returned = any(var_name == variable_name for _, var_name in returns if var_name)
        
        return {
            'variable': variable_name,
            'function': function_name,
            'assignments': assignments.get(variable_name, []),
            'uses': uses.get(variable_name, []),
            'def_use_chains': def_use_chains.get(variable_name, []),
            'returned': returned,
            'file': file_path
        }

