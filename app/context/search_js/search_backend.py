"""
JavaScript/TypeScript Search Backend using AST parsing and pattern matching
Provides production-quality search APIs for JS/TS vulnerability analysis
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set

from . import search_utils
from .data_structures import JSSearchResult, JSCallChainResult, JSTaintPath


RESULT_SHOW_LIMIT = 3


class JSSearchBackend:
    """Production-quality JavaScript/TypeScript search backend"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        
        # Cache for file operations
        self._file_cache = {}
        self._parsed_files_cache = {}
        
        # Check tool availability
        self.has_tsmorph = search_utils.check_tsmorph_available()
        
        # Build index
        self.file_index = {}  # {filename: content}
        self.class_index = {}  # {class_name: [(file, line, info)]}
        self.function_index = {}  # {function_name: [(file, line, info)]}
        self.method_index = {}  # {method_name: [(file, line, info)]}
        self.module_index = {}  # {module_path: file}
        
        # Cache for advanced analysis
        self._call_chain_cache: Dict[str, Dict[str, List[List[str]]]] = {}
        
        self._build_index()
    
    def _build_index(self) -> None:
        """Build index of JavaScript/TypeScript files"""
        print(f"Building JS/TS index {'with ts-morph' if self.has_tsmorph else 'with regex'}...")
        
        # Find all JS/TS files
        js_ts_files = search_utils.find_js_ts_files(str(self.project_path))
        
        for file_path in js_ts_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Store file content
                rel_path = str(Path(file_path).relative_to(self.project_path))
                self.file_index[rel_path] = content
                
                # Parse file structure
                if self.has_tsmorph:
                    parsed_info = search_utils.parse_js_file_with_tsmorph(file_path)
                    if not parsed_info:
                        parsed_info = search_utils.parse_js_file_with_regex(file_path)
                else:
                    parsed_info = search_utils.parse_js_file_with_regex(file_path)
                
                if parsed_info:
                    self._index_parsed_info(rel_path, parsed_info)
                    self._parsed_files_cache[rel_path] = parsed_info
                
            except Exception as e:
                print(f"Warning: Could not index {file_path}: {e}")
                continue
        
        print(f"Indexed {len(js_ts_files)} files, {len(self.class_index)} classes, "
              f"{len(self.function_index)} functions, {len(self.method_index)} methods")
    
    def _index_parsed_info(self, file_path: str, parsed_info: Dict) -> None:
        """Index the parsed information from a JavaScript/TypeScript file"""
        # Index classes
        for class_info in parsed_info.get('classes', []):
            class_name = class_info['name']
            if class_name not in self.class_index:
                self.class_index[class_name] = []
            self.class_index[class_name].append((file_path, class_info['line'], class_info))
        
        # Index functions
        for func_info in parsed_info.get('functions', []):
            # Compute function boundaries once and cache them on the info dict
            try:
                _def_text, start, end = self._extract_complete_definition(file_path, func_info['line'], 'function')
                func_info['start_line'] = start
                func_info['end_line'] = end
            except Exception:
                func_info['start_line'] = func_info['line']
                func_info['end_line'] = func_info['line']
            func_name = func_info['name']
            if func_name not in self.function_index:
                self.function_index[func_name] = []
            self.function_index[func_name].append((file_path, func_info['line'], func_info))
        
        # Index methods (class methods)
        for method_info in parsed_info.get('methods', []):
            try:
                _def_text, start, end = self._extract_complete_definition(file_path, method_info['line'], 'function')
                method_info['start_line'] = start
                method_info['end_line'] = end
            except Exception:
                method_info['start_line'] = method_info['line']
                method_info['end_line'] = method_info['line']
            method_name = method_info['name']
            if method_name not in self.method_index:
                self.method_index[method_name] = []
            self.method_index[method_name].append((file_path, method_info['line'], method_info))
    
    def search_class(self, class_name: str) -> Tuple[str, List[JSSearchResult], bool]:
        """
        Search for JavaScript/TypeScript class definitions
        
        Args:
            class_name: Name of the class
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        if class_name in self.class_index:
            for file_path, line_num, class_info in self.class_index[class_name]:
                # Extract complete class definition
                definition, start, end = self._extract_complete_definition(
                    file_path, line_num, 'class'
                )
                
                abs_path = str(self.project_path / file_path)
                is_ts = search_utils.is_typescript_file(abs_path)
                
                search_result = JSSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=None,
                    class_name=class_name,
                    module_path=file_path,
                    code=definition,
                    extraction_method="ast" if self.has_tsmorph else "regex",
                    is_typescript=is_ts,
                    is_async=False,
                    is_arrow=False
                )
                results.append(search_result)
        
        if not results:
            return f"Could not find class {class_name}", [], False
        
        message = f"Found {len(results)} class definition(s) for {class_name}"
        return message, results, True
    
    def search_method_in_class(
        self, 
        method_name: str, 
        class_name: str
    ) -> Tuple[str, List[JSSearchResult], bool]:
        """
        Search for method in a JavaScript/TypeScript class
        
        Args:
            method_name: Name of the method
            class_name: Name of the class
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        if method_name in self.method_index:
            for file_path, line_num, method_info in self.method_index[method_name]:
                # Check if this method belongs to the specified class
                if method_info.get('class_name') == class_name:
                    # Extract complete method definition
                    definition, start, end = self._extract_complete_definition(
                        file_path, line_num, 'function'
                    )
                    
                    abs_path = str(self.project_path / file_path)
                    is_ts = search_utils.is_typescript_file(abs_path)
                    
                    search_result = JSSearchResult(
                        file_path=abs_path,
                        line_number=start,
                        end_line=end,
                        function_name=method_name,
                        class_name=class_name,
                        module_path=file_path,
                        code=definition,
                        extraction_method="ast" if self.has_tsmorph else "regex",
                        is_typescript=is_ts,
                        is_async=method_info.get('is_async', False),
                        is_arrow=method_info.get('is_arrow', False)
                    )
                    results.append(search_result)
        
        if not results:
            return f"Could not find method {method_name} in class {class_name}", [], False
        
        message = f"Found {len(results)} method(s) {method_name} in class {class_name}"
        return message, results, True
    
    def search_method(self, method_name: str) -> Tuple[str, List[JSSearchResult], bool]:
        """
        Search for a function/method in the entire codebase
        
        Args:
            method_name: Name of the function/method
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        # Search in top-level functions
        if method_name in self.function_index:
            for file_path, line_num, func_info in self.function_index[method_name]:
                definition, start, end = self._extract_complete_definition(
                    file_path, line_num, 'function'
                )
                
                abs_path = str(self.project_path / file_path)
                is_ts = search_utils.is_typescript_file(abs_path)
                
                search_result = JSSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=method_name,
                    class_name=None,
                    module_path=file_path,
                    code=definition,
                    extraction_method="ast" if self.has_tsmorph else "regex",
                    is_typescript=is_ts,
                    is_async=func_info.get('is_async', False),
                    is_arrow=func_info.get('is_arrow', False)
                )
                results.append(search_result)
        
        # Search in class methods
        if method_name in self.method_index:
            for file_path, line_num, method_info in self.method_index[method_name]:
                definition, start, end = self._extract_complete_definition(
                    file_path, line_num, 'function'
                )
                
                abs_path = str(self.project_path / file_path)
                is_ts = search_utils.is_typescript_file(abs_path)
                
                search_result = JSSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=method_name,
                    class_name=method_info.get('class_name'),
                    module_path=file_path,
                    code=definition,
                    extraction_method="ast" if self.has_tsmorph else "regex",
                    is_typescript=is_ts,
                    is_async=method_info.get('is_async', False),
                    is_arrow=method_info.get('is_arrow', False)
                )
                results.append(search_result)
        
        if not results:
            return f"Could not find function/method {method_name} in the codebase", [], False
        
        tool_output = f"Found {len(results)} function(s)/method(s) with name {method_name}:\n\n"
        
        if len(results) > RESULT_SHOW_LIMIT:
            tool_output += "They appeared in the following files:\n"
            for res in results:
                tool_output += f"- {Path(res.file_path).name}\n"
        else:
            for idx, res in enumerate(results):
                tool_output += f"- Search result {idx + 1}:\n```\n{res.code}\n```\n"
        
        return tool_output, results[:RESULT_SHOW_LIMIT], True
    
    def search_function(self, function_name: str) -> List[JSSearchResult]:
        """
        Search for function (top-level or in classes)
        
        Args:
            function_name: Name of the function
        
        Returns:
            List of JSSearchResult objects
        """
        results = []
        
        # Top-level functions
        if function_name in self.function_index:
            for file_path, line_num, func_info in self.function_index[function_name]:
                definition, start, end = self._extract_complete_definition(
                    file_path, line_num, 'function'
                )
                
                abs_path = str(self.project_path / file_path)
                is_ts = search_utils.is_typescript_file(abs_path)
                
                search_result = JSSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=function_name,
                    class_name=None,
                    module_path=file_path,
                    code=definition,
                    extraction_method="ast" if self.has_tsmorph else "regex",
                    is_typescript=is_ts,
                    is_async=func_info.get('is_async', False),
                    is_arrow=func_info.get('is_arrow', False)
                )
                results.append(search_result)
        
        # Methods in classes
        if function_name in self.method_index:
            for file_path, line_num, method_info in self.method_index[function_name]:
                definition, start, end = self._extract_complete_definition(
                    file_path, line_num, 'function'
                )
                
                abs_path = str(self.project_path / file_path)
                is_ts = search_utils.is_typescript_file(abs_path)
                
                search_result = JSSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=function_name,
                    class_name=method_info.get('class_name'),
                    module_path=file_path,
                    code=definition,
                    extraction_method="ast" if self.has_tsmorph else "regex",
                    is_typescript=is_ts,
                    is_async=method_info.get('is_async', False),
                    is_arrow=method_info.get('is_arrow', False)
                )
                results.append(search_result)
        
        return results
    
    def find_callers(self, function_name: str, file_path: Optional[str] = None) -> List[JSSearchResult]:
        """
        Find functions that call the specified function
        
        Args:
            function_name: Name of the function
            file_path: Optional file path to filter results
        
        Returns:
            List of JSSearchResult objects for caller functions
        """
        results = []
        pattern = f"{function_name}("
        seen: Set[Tuple[str, Optional[str], Optional[str]]] = set()
        
        # Patterns that indicate a definition rather than a call
        def is_definition_line(line: str) -> bool:
            stripped = line.strip()
            # function foo(...
            if re.match(rf"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+{re.escape(function_name)}\s*\(", stripped):
                return True
            # class/TS method: [modifiers] foo(...
            if re.match(rf"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:async\s+)?{re.escape(function_name)}\s*\(", stripped):
                return True
            # variable arrow/expr: const foo = (...)
            if re.match(rf"^\s*(?:export\s+)?(?:const|let|var)\s+{re.escape(function_name)}\s*=\s*(?:async\s+)?\(", stripped):
                return True
            return False
        
        # Search through all files
        for file_rel_path, content in self.file_index.items():
            # Filter by file if specified
            if file_path and not self._matches_file_path(file_rel_path, file_path):
                continue
            
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if pattern in line and not line.strip().startswith('//'):
                    # Skip matches that are actually the function/method definition
                    if is_definition_line(line):
                        continue
                    # Try to find which function contains this call
                    caller_func = self._find_containing_function(file_rel_path, i)
                    
                    if caller_func:
                        # Extract the caller function
                        definition, start, end = self._extract_complete_definition(
                            file_rel_path, caller_func['line'], 'function'
                        )
                        
                        abs_path = str(self.project_path / file_rel_path)
                        is_ts = search_utils.is_typescript_file(abs_path)
                        key = (file_rel_path, caller_func.get('class_name'), caller_func.get('name'))
                        if key in seen:
                            continue
                        seen.add(key)
                        search_result = JSSearchResult(
                            file_path=abs_path,
                            line_number=i,  # call site line
                            end_line=i,
                            function_name=caller_func['name'],
                            class_name=caller_func.get('class_name'),
                            module_path=file_rel_path,
                            code=line.strip(),
                            extraction_method="ast" if self.has_tsmorph else "regex",
                            is_typescript=is_ts,
                            is_async=caller_func.get('is_async', False),
                            is_arrow=caller_func.get('is_arrow', False)
                        )
                        results.append(search_result)
                    else:
                        # Call not in a function (maybe in module scope)
                        abs_path = str(self.project_path / file_rel_path)
                        is_ts = search_utils.is_typescript_file(abs_path)
                        key = (file_rel_path, None, None)
                        if key in seen:
                            continue
                        seen.add(key)
                        search_result = JSSearchResult(
                            file_path=abs_path,
                            line_number=i,
                            end_line=i,
                            function_name=None,
                            class_name=None,
                            module_path=file_rel_path,
                            code=line.strip(),
                            extraction_method="regex",
                            is_typescript=is_ts,
                            is_async=False,
                            is_arrow=False
                        )
                        results.append(search_result)
        
        return results[:10]  # Limit results
    
    def find_callees(self, function_name: str, file_path: Optional[str] = None) -> List[JSSearchResult]:
        """
        Find functions called by the specified function
        
        Args:
            function_name: Name of the function
            file_path: Optional file path to filter results
        
        Returns:
            List of JSSearchResult objects for callee functions
        """
        results = []
        
        # Find the function definition first
        target_functions = self.search_function(function_name)
        
        for target_func in target_functions:
            # Filter by file if specified
            if file_path and not self._matches_file_path(target_func.module_path or "", file_path):
                continue
            
            # Extract function calls from the body
            method_calls = self._extract_function_calls(target_func.code)
            
            for call_info in method_calls:
                # Skip the function's own definition line mistakenly matched as a call
                ctx = call_info['context']
                if call_info['function'] == function_name:
                    if re.search(rf"\bfunction\s+{re.escape(function_name)}\s*\(", ctx) or \
                       re.search(rf"\b(?:const|let|var)\s+{re.escape(function_name)}\s*=\s*\(", ctx):
                        continue
                abs_path = target_func.file_path
                is_ts = target_func.is_typescript
                # Map relative line in snippet to absolute file line
                abs_line = target_func.line_number + call_info['line'] - 1
                
                search_result = JSSearchResult(
                    file_path=abs_path,
                    line_number=abs_line,
                    end_line=abs_line,
                    function_name=call_info['function'],
                    class_name=call_info.get('class'),
                    module_path=target_func.module_path,
                    code=call_info['context'],
                    extraction_method="regex",
                    is_typescript=is_ts,
                    is_async=False,
                    is_arrow=False
                )
                results.append(search_result)
        
        return results[:10]
    
    def search_code(self, code_pattern: str) -> Tuple[str, List[JSSearchResult], bool]:
        """
        Search for code pattern in the codebase
        
        Args:
            code_pattern: Code pattern to search for
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        # Prepare regex for identifier-like patterns to avoid substring false-positives
        ident_regex: Optional[re.Pattern] = None
        if re.match(r'^[A-Za-z_][\w]*$', code_pattern):
            ident_regex = re.compile(rf"\b{re.escape(code_pattern)}\b")
        
        for file_rel_path, content in self.file_index.items():
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                # Skip comment-only lines
                if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                    continue
                matched = False
                if ident_regex is not None:
                    matched = bool(ident_regex.search(line))
                else:
                    matched = code_pattern in line
                if matched:
                    # Get context around the match
                    abs_path = self.project_path / file_rel_path
                    snippet = search_utils.get_code_region_around_line(
                        str(abs_path), i, window_size=5
                    )
                    
                    if snippet:
                        abs_path_str = str(abs_path)
                        is_ts = search_utils.is_typescript_file(abs_path_str)
                        
                        search_result = JSSearchResult(
                            file_path=abs_path_str,
                            line_number=i,
                            end_line=i,
                            function_name=None,
                            class_name=None,
                            module_path=file_rel_path,
                            code=snippet,
                            extraction_method="regex",
                            is_typescript=is_ts,
                            is_async=False,
                            is_arrow=False
                        )
                        results.append(search_result)
        
        if not results:
            return f"Could not find code pattern '{code_pattern}'", [], False
        
        message = f"Found {len(results)} occurrences of '{code_pattern}'"
        return message, results[:10], True
    
    def get_code_around_line(
        self,
        file_name: str,
        line_no: int,
        window_size: int = 10
    ) -> Tuple[str, List[JSSearchResult], bool]:
        """
        Get code region around a specific line
        
        Args:
            file_name: File name (can be partial)
            line_no: Line number
            window_size: Context window size
        
        Returns:
            (message, search_results, success)
        """
        # Find matching files
        candidate_files = self._find_matching_files(file_name)
        
        if not candidate_files:
            return f"Could not find file '{file_name}'", [], False
        
        results = []
        for file_path in candidate_files:
            snippet = search_utils.get_code_region_around_line(
                file_path, line_no, window_size
            )
            
            if snippet:
                is_ts = search_utils.is_typescript_file(file_path)
                
                search_result = JSSearchResult(
                    file_path=file_path,
                    line_number=max(1, line_no - window_size),
                    end_line=line_no + window_size,
                    function_name=None,
                    class_name=None,
                    module_path=None,
                    code=snippet,
                    extraction_method="manual",
                    is_typescript=is_ts,
                    is_async=False,
                    is_arrow=False
                )
                results.append(search_result)
        
        if not results:
            return f"Line {line_no} is invalid in file '{file_name}'", [], False
        
        message = f"Found code around line {line_no}"
        return message, results, True
    
    def _extract_complete_definition(
        self,
        file_path: str,
        line_number: int,
        definition_type: str
    ) -> Tuple[str, int, int]:
        """
        Extract complete definition (class or function)
        
        Returns:
            (definition_text, start_line, end_line)
        """
        try:
            abs_file_path = self.project_path / file_path
            with open(abs_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if line_number > len(lines):
                return "Line out of range", line_number, line_number
            
            if definition_type == 'function':
                definition, start, end = search_utils.extract_function_with_braces(lines, line_number)
            elif definition_type == 'class':
                definition, start, end = search_utils.extract_class_with_braces(lines, line_number)
            else:
                # Get context around line
                snippet = search_utils.get_code_region_around_line(
                    str(abs_file_path), line_number, window_size=5
                )
                return snippet or "", line_number, line_number
            
            return definition, start, end
            
        except Exception as e:
            return f"Error: {e}", line_number, line_number
    
    def _find_containing_function(self, file_path: str, line_number: int) -> Optional[Dict]:
        """Find which function contains the given line number"""
        parsed_info = self._parsed_files_cache.get(file_path)
        if not parsed_info:
            return None
        
        candidates: List[Dict] = []
        
        # Ensure end_line is available; compute lazily if missing
        def ensure_bounds(info: Dict) -> Tuple[int, int]:
            start_ln = info.get('start_line') or info.get('line')
            end_ln = info.get('end_line')
            if not end_ln:
                _def_text, start, end = self._extract_complete_definition(file_path, start_ln, 'function')
                info['start_line'] = start
                info['end_line'] = end
                start_ln, end_ln = start, end
            return start_ln, end_ln
        
        for func_info in parsed_info.get('functions', []):
            start_ln, end_ln = ensure_bounds(func_info)
            if start_ln <= line_number <= end_ln:
                candidates.append(func_info)
        for method_info in parsed_info.get('methods', []):
            start_ln, end_ln = ensure_bounds(method_info)
            if start_ln <= line_number <= end_ln:
                candidates.append(method_info)
        
        if not candidates:
            return None
        # Return the innermost (latest starting) function
        candidates.sort(key=lambda x: x.get('start_line') or x.get('line'), reverse=True)
        return candidates[0]
    
    def _extract_function_calls(self, function_body: str) -> List[Dict]:
        """Extract function calls from function body"""
        calls = []
        lines = function_body.split('\n')
        
        # Pattern to match function calls
        # Pattern 1: obj.method()
        # Pattern 2: function()
        # Pattern 3: await function()
        call_pattern = r'(\w+)\.(\w+)\s*\(|(?:await\s+)?(\w+)\s*\('
        
        for i, line in enumerate(lines, 1):
            matches = re.finditer(call_pattern, line)
            for match in matches:
                if match.group(1) and match.group(2):
                    # Object.method() call
                    calls.append({
                        'function': match.group(2),
                        'class': match.group(1),
                        'line': i,
                        'context': line.strip()
                    })
                elif match.group(3):
                    # function() call
                    func_name = match.group(3)
                    # Filter out keywords
                    if func_name not in ['if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'typeof']:
                        calls.append({
                            'function': func_name,
                            'class': None,
                            'line': i,
                            'context': line.strip()
                        })
        
        return calls
    
    def _find_matching_files(self, partial_filename: str) -> List[str]:
        """Find files matching the partial filename"""
        partial_lower = partial_filename.lower()
        all_files = search_utils.find_js_ts_files(str(self.project_path))
        
        candidates = []
        for file_path in all_files:
            if file_path.lower().endswith(partial_lower):
                candidates.append(file_path)
        
        return candidates
    
    def _matches_file_path(self, result_file: str, target_file: str) -> bool:
        """Check if result file matches target file with flexible matching"""
        result_normalized = result_file.replace('\\', '/')
        target_normalized = target_file.replace('\\', '/')
        
        # Exact match
        if result_normalized == target_normalized:
            return True
        
        # Basename match
        if Path(result_normalized).name == Path(target_normalized).name:
            return True
        
        # Suffix match
        if result_normalized.endswith(target_normalized):
            return True
        
        return False
    
    # ------------------------------------------------------------------
    # Helper utilities for advanced analysis
    # ------------------------------------------------------------------
    
    def _get_function_snippet(self, function_name: str) -> Optional[JSSearchResult]:
        """Return the first search result for a function."""
        try:
            results = self.search_function(function_name)
            if results:
                return results[0]
        except Exception:
            return None
        return None
    
    def _function_contains_pattern(self, function_name: str, pattern: str) -> bool:
        """Check if a function's code contains the given pattern."""
        if not pattern:
            return False
        snippet = self._get_function_snippet(function_name)
        if not snippet or not snippet.code:
            return False
        regex = re.compile(rf"\b{re.escape(pattern)}\b")
        return bool(regex.search(snippet.code))
    
    def _extract_function_name_from_context(self, context: str) -> Optional[str]:
        """Extract function name from a line of code."""
        if not context:
            return None
        # Try to match function calls: function() or obj.function()
        match = re.search(r'\.(\w+)\s*\(|(\w+)\s*\(', context)
        if not match:
            return None
        candidate = match.group(1) or match.group(2)
        if candidate in {'if', 'for', 'while', 'switch', 'catch', 'return', 'new', 'typeof'}:
            return None
        return candidate
    
    def _get_callees_names(self, function_name: str) -> List[str]:
        """Get the names of functions called by the given function."""
        names: List[str] = []
        for result in self.find_callees(function_name):
            callee_name = result.function_name or self._extract_function_name_from_context(result.code)
            if not callee_name:
                continue
            if result.class_name and result.function_name:
                display_name = f"{result.class_name}.{result.function_name}"
            else:
                display_name = callee_name
            if display_name != function_name and display_name not in names:
                names.append(display_name)
        return names
    
    def _get_callers_names(self, function_name: str) -> List[str]:
        """Get the names of functions that call the given function."""
        names: List[str] = []
        for result in self.find_callers(function_name):
            caller = result.function_name
            if not caller:
                caller = self._extract_function_name_from_context(result.code)
            if not caller:
                continue
            if result.class_name and result.function_name:
                display_name = f"{result.class_name}.{result.function_name}"
            else:
                display_name = caller
            if display_name != function_name and display_name not in names:
                names.append(display_name)
        return names
    
    def _find_functions_with_pattern(self, pattern: str) -> Set[str]:
        """Find functions whose code contains the given pattern."""
        matches: Set[str] = set()
        if not pattern:
            return matches
        
        # Search through all files for the pattern
        for file_path, content in self.file_index.items():
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    # Find containing function
                    func_info = self._find_containing_function(file_path, i)
                    if func_info:
                        matches.add(func_info['name'])
        
        return matches
    
    # ------------------------------------------------------------------
    # Advanced analysis APIs
    # ------------------------------------------------------------------
    
    def find_call_chain(
        self,
        start_function: str,
        depth: int = 3,
        direction: str = "forward"
    ) -> List[JSCallChainResult]:
        """
        Build multi-level call chains starting from the given function.
        
        ⚠️ WARNING: Pattern-based matching may include false positives.
        Functions with common names may be confused across different modules.
        Best results with unique function names.
        """
        if not start_function:
            return []
        
        direction = direction.lower()
        if direction not in {"forward", "backward"}:
            direction = "forward"
        depth = max(1, min(depth, 5))
        
        cache_dir = self._call_chain_cache.setdefault(direction, {})
        cache_key = f"{start_function}:{depth}"
        
        if cache_key in cache_dir:
            cached_paths = cache_dir[cache_key]
        else:
            paths: List[List[str]] = []
            visited: Set[str] = set()
            
            def dfs(current: str, path: List[str], remaining: int) -> None:
                if remaining == 0:
                    paths.append(path.copy())
                    return
                if current in visited:
                    paths.append(path.copy())
                    return
                visited.add(current)
                
                neighbours = (
                    self._get_callees_names(current)
                    if direction == "forward"
                    else self._get_callers_names(current)
                )
                
                if not neighbours:
                    paths.append(path.copy())
                else:
                    for neighbour in neighbours:
                        if neighbour in path:
                            continue
                        path.append(neighbour)
                        dfs(neighbour, path, remaining - 1)
                        path.pop()
                visited.discard(current)
            
            dfs(start_function, [start_function], depth)
            cache_dir[cache_key] = paths
            cached_paths = paths
        
        results: List[JSCallChainResult] = []
        for path in cached_paths:
            details: List[JSSearchResult] = []
            files: List[str] = []
            for function in path:
                snippet = self._get_function_snippet(function)
                if snippet:
                    details.append(snippet)
                    files.append(snippet.file_path)
            results.append(
                JSCallChainResult(
                    chain=path,
                    depth=max(0, len(path) - 1),
                    files=list(dict.fromkeys(files)),
                    details=details
                )
            )
        return results
    
    def find_taint_flow(
        self,
        source_pattern: str,
        sink_function: str,
        max_depth: int = 3
    ) -> List[JSTaintPath]:
        """
        Find taint paths from source pattern to sink function.
        
        ⚠️ WARNING: Best-effort analysis. May miss paths or report false positives.
        Cannot track taint through closures, promises, or complex data flows.
        """
        max_depth = max(1, min(max_depth, 5))
        paths: List[JSTaintPath] = []
        
        # Strategy 1: Find direct taint flows (source and sink in same function/scope)
        direct_paths = self._find_direct_taint_flows(source_pattern, sink_function)
        paths.extend(direct_paths)
        
        # Strategy 2: Find inter-procedural taint flows through function calls
        sources = self._find_functions_with_pattern(source_pattern)
        
        for source in sources:
            path: List[str] = [source]
            visited: Set[str] = set()
            
            def dfs(current: str, remaining: int) -> None:
                # Check if current function contains the sink
                if self._function_contains_pattern(current, sink_function):
                    confidence = 'high' if current == source else 'medium'
                    paths.append(
                        JSTaintPath(
                            source=source_pattern,
                            sink=sink_function,
                            path=path.copy(),
                            variables=[source_pattern],
                            confidence=confidence
                        )
                    )
                    return
                
                if remaining == 0:
                    return
                if current in visited:
                    return
                
                visited.add(current)
                for callee in self._get_callees_names(current):
                    if callee in path:
                        continue
                    path.append(callee)
                    dfs(callee, remaining - 1)
                    path.pop()
                visited.discard(current)
            
            dfs(source, max_depth)
        
        # Deduplicate paths
        unique_paths = {}
        for tp in paths:
            key = tuple(tp.path)
            if key not in unique_paths:
                unique_paths[key] = tp
        return list(unique_paths.values())
    
    def _find_direct_taint_flows(self, source_pattern: str, sink_pattern: str) -> List[JSTaintPath]:
        """
        Find direct taint flows where source and sink appear in the same function or code block.
        This handles cases like:
          const x = req.query.q;
          res.send(x);
        """
        paths: List[JSTaintPath] = []
        
        # Search all files for locations containing both source and sink
        for file_path, content in self.file_index.items():
            lines = content.split('\n')
            
            # Find all functions/scopes that contain both patterns
            source_locations = []
            sink_locations = []
            
            for i, line in enumerate(lines, 1):
                if source_pattern in line:
                    source_locations.append(i)
                if sink_pattern in line:
                    sink_locations.append(i)
            
            # If we found both in the same file, check if they're in the same scope
            if source_locations and sink_locations:
                for source_line in source_locations:
                    for sink_line in sink_locations:
                        # Check if they're close enough to be in the same function
                        # (within 50 lines is a reasonable heuristic for same scope)
                        if abs(source_line - sink_line) <= 50:
                            # Find the containing function/scope
                            func_info = self._find_containing_function(file_path, source_line)
                            sink_func_info = self._find_containing_function(file_path, sink_line)
                            
                            # Determine function names (handle None for anonymous functions)
                            if func_info:
                                func_name = func_info.get('name', 'anonymous')
                            else:
                                func_name = None
                            
                            if sink_func_info:
                                sink_func_name = sink_func_info.get('name', 'anonymous')
                            else:
                                sink_func_name = None
                            
                            # Check if they're in the same scope
                            # Case 1: Both in the same named function
                            # Case 2: Both in anonymous/None scope (module level or anonymous functions)
                            # Case 3: Within a reasonable line distance (likely same code block)
                            same_scope = False
                            
                            if func_name and sink_func_name and func_name == sink_func_name:
                                same_scope = True
                            elif func_name is None and sink_func_name is None:
                                # Both are module-level or in anonymous functions
                                # Check if they're in the same code block by looking for braces
                                same_scope = self._in_same_code_block(lines, source_line, sink_line)
                            
                            if same_scope:
                                # Track variable flow between source and sink
                                variables = self._extract_taint_variables(lines, source_line, sink_line, source_pattern)
                                
                                # Create a meaningful path name
                                if func_name:
                                    path_name = func_name
                                else:
                                    path_name = f"{Path(file_path).name}:L{source_line}"
                                
                                paths.append(
                                    JSTaintPath(
                                        source=source_pattern,
                                        sink=sink_pattern,
                                        path=[path_name],
                                        variables=variables,
                                        confidence='high'
                                    )
                                )
        
        return paths
    
    def _in_same_code_block(self, lines: List[str], line1: int, line2: int) -> bool:
        """
        Check if two lines are in the same code block (between the same braces).
        This is a heuristic for anonymous functions and code blocks.
        """
        # Ensure line1 is before line2
        if line1 > line2:
            line1, line2 = line2, line1
        
        # Simple heuristic: count braces between the lines
        # If we're within 20 lines and don't cross function boundaries, consider them same scope
        if line2 - line1 > 20:
            return False
        
        # Check for function declarations between the lines (indicates different scopes)
        for i in range(line1 - 1, line2):
            if i < 0 or i >= len(lines):
                continue
            line = lines[i]
            # Look for function declarations that would indicate a new scope
            if re.match(r'^\s*(?:async\s+)?function\s+\w+', line):
                return False
            if re.match(r'^\s*(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?function', line):
                return False
            # Look for closing brace followed by opening brace (end of one block, start of another)
            if re.search(r'\}\s*,?\s*(?:async\s+)?\(', line):
                # This is likely the end of one callback and start of another
                continue
        
        return True
    
    def _extract_taint_variables(self, lines: List[str], source_line: int, sink_line: int, source_pattern: str) -> List[str]:
        """Extract variable names involved in taint flow between source and sink."""
        variables = [source_pattern]
        
        # Look for variable assignments from source
        start = max(0, source_line - 1)
        end = min(len(lines), sink_line)
        
        for i in range(start, end):
            line = lines[i]
            # Match patterns like: const x = req.query.q; or let y = source;
            match = re.search(r'(?:const|let|var)\s+(\w+)\s*=.*' + re.escape(source_pattern), line)
            if match:
                var_name = match.group(1)
                if var_name not in variables:
                    variables.append(var_name)
            
            # Match destructuring: const { x } = req.body;
            match = re.search(r'(?:const|let|var)\s*\{\s*(\w+)\s*\}\s*=.*' + re.escape(source_pattern), line)
            if match:
                var_name = match.group(1)
                if var_name not in variables:
                    variables.append(var_name)
        
        return variables
    
    def track_variable(
        self,
        function_name: str,
        variable_name: str
    ) -> Dict[str, object]:
        """
        Track variable usage inside a function.
        
        Works for local variables and parameters.
        Limited support for closure tracking.
        
        ⚠️ WARNING: Cannot track destructuring or complex patterns.
        """
        snippet = self._get_function_snippet(function_name)
        if not snippet:
            return {}
        
        assignments: List[int] = []
        uses: List[int] = []
        code_lines = snippet.code.splitlines()
        current_line = snippet.line_number
        
        # JS/TS-specific patterns
        # Declaration: const/let/var varName = ...
        decl_pattern = rf"(?:const|let|var)\s+{re.escape(variable_name)}\s*="
        # Assignment: varName = ...
        assign_pattern = rf"{re.escape(variable_name)}\s*="
        # Use: varName anywhere
        use_pattern = rf"\b{re.escape(variable_name)}\b"
        # Return: return varName
        return_pattern = rf"return[^;]*\b{re.escape(variable_name)}\b"
        
        decl_regex = re.compile(decl_pattern)
        assign_regex = re.compile(assign_pattern)
        use_regex = re.compile(use_pattern)
        return_regex = re.compile(return_pattern)
        returned = False
        
        for line in code_lines:
            stripped = line.strip()
            # Skip comments
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
                current_line += 1
                continue
            
            # Check for declaration (counts as assignment)
            if decl_regex.search(line):
                assignments.append(current_line)
            # Check for regular assignment
            elif assign_regex.search(line):
                assignments.append(current_line)
            
            if use_regex.search(line):
                uses.append(current_line)
            if return_regex.search(line):
                returned = True
            current_line += 1
        
        return {
            'variable': variable_name,
            'function': function_name,
            'assignments': assignments,
            'uses': uses,
            'returned': returned,
            'file': snippet.file_path,
            'code': snippet.code
        }

