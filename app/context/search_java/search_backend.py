"""
Java Search Backend using AST parsing and pattern matching
Provides production-quality search APIs for Java vulnerability analysis
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set

from . import search_utils
from .data_structures import JavaSearchResult, JavaCallChainResult, JavaTaintPath


class JavaSearchBackend:
    """Production-quality Java search backend using AST parsing"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        
        # Cache for file operations
        self._file_cache = {}
        self._parsed_files_cache = {}
        
        # Check tool availability
        self.has_javalang = search_utils.check_javalang_available()
        
        # Build index
        self.file_index = {}  # {filename: content}
        self.class_index = {}  # {class_name: [(file, line, info)]}
        self.method_index = {}  # {method_name: [(file, line, info)]}
        self.package_index = {}  # {package_name: [files]}
        
        # Cache for advanced analysis
        self._call_chain_cache: Dict[str, Dict[str, List[List[str]]]] = {}
        
        self._build_index()
    
    def _build_index(self) -> None:
        """Build index of Java files"""
        print(f"Building Java index {'with AST' if self.has_javalang else 'with regex'}...")
        
        # Find all Java files
        java_files = search_utils.find_java_files(str(self.project_path))
        
        for file_path in java_files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Store file content
                rel_path = str(Path(file_path).relative_to(self.project_path))
                self.file_index[rel_path] = content
                
                # Parse file structure
                if self.has_javalang:
                    parsed_info = search_utils.parse_java_file_with_ast(file_path)
                else:
                    parsed_info = search_utils.parse_java_file_with_regex(file_path)
                
                if parsed_info:
                    self._index_parsed_info(rel_path, parsed_info)
                    self._parsed_files_cache[rel_path] = parsed_info
                
            except Exception as e:
                print(f"Warning: Could not index {file_path}: {e}")
                continue
        
        print(f"Indexed {len(java_files)} files, {len(self.class_index)} classes, {len(self.method_index)} methods")
    
    def _index_parsed_info(self, file_path: str, parsed_info: Dict) -> None:
        """Index the parsed information from a Java file"""
        # Index package
        if parsed_info.get('package'):
            package_name = parsed_info['package']
            if package_name not in self.package_index:
                self.package_index[package_name] = []
            self.package_index[package_name].append(file_path)
        
        # Index classes
        for class_info in parsed_info.get('classes', []):
            class_name = class_info['name']
            if class_name not in self.class_index:
                self.class_index[class_name] = []
            self.class_index[class_name].append((file_path, class_info['line'], class_info))
        
        # Index interfaces
        for interface_info in parsed_info.get('interfaces', []):
            interface_name = interface_info['name']
            if interface_name not in self.class_index:
                self.class_index[interface_name] = []
            self.class_index[interface_name].append((file_path, interface_info['line'], interface_info))
        
        # Index methods
        for method_info in parsed_info.get('methods', []):
            method_name = method_info['name']
            if method_name not in self.method_index:
                self.method_index[method_name] = []
            self.method_index[method_name].append((file_path, method_info['line'], method_info))
    
    def search_class(self, class_name: str) -> Tuple[str, List[JavaSearchResult], bool]:
        """
        Search for Java class or interface definitions
        
        Args:
            class_name: Name of the class/interface
        
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
                
                # Get package info
                parsed_info = self._parsed_files_cache.get(file_path, {})
                package_name = parsed_info.get('package')
                
                abs_path = str(self.project_path / file_path)
                search_result = JavaSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    method_name=None,
                    class_name=class_name,
                    package_name=package_name,
                    code=definition,
                    extraction_method="ast" if self.has_javalang else "regex"
                )
                results.append(search_result)
        
        if not results:
            return f"Could not find class {class_name}", [], False
        
        message = f"Found {len(results)} class/interface definition(s) for {class_name}"
        return message, results, True
    
    def search_method_in_class(
        self, 
        method_name: str, 
        class_name: str
    ) -> Tuple[str, List[JavaSearchResult], bool]:
        """
        Search for method in a Java class
        
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
                        file_path, line_num, 'method'
                    )
                    
                    # Get package info
                    parsed_info = self._parsed_files_cache.get(file_path, {})
                    package_name = parsed_info.get('package')
                    
                    abs_path = str(self.project_path / file_path)
                    search_result = JavaSearchResult(
                        file_path=abs_path,
                        line_number=start,
                        end_line=end,
                        method_name=method_name,
                        class_name=class_name,
                        package_name=package_name,
                        code=definition,
                        extraction_method="ast" if self.has_javalang else "regex"
                    )
                    results.append(search_result)
        
        if not results:
            return f"Could not find method {method_name} in class {class_name}", [], False
        
        message = f"Found {len(results)} method(s) {method_name} in class {class_name}"
        return message, results, True
    
    def search_function(self, method_name: str) -> List[JavaSearchResult]:
        """
        Search for method definitions (Java equivalent of function search)
        
        Args:
            method_name: Name of the method
        
        Returns:
            List of JavaSearchResult objects
        """
        results = []
        
        if method_name in self.method_index:
            for file_path, line_num, method_info in self.method_index[method_name]:
                # Extract complete method definition
                definition, start, end = self._extract_complete_definition(
                    file_path, line_num, 'method'
                )
                
                # Get package and class info
                parsed_info = self._parsed_files_cache.get(file_path, {})
                package_name = parsed_info.get('package')
                class_name = method_info.get('class_name')
                
                abs_path = str(self.project_path / file_path)
                search_result = JavaSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    method_name=method_name,
                    class_name=class_name,
                    package_name=package_name,
                    code=definition,
                    extraction_method="ast" if self.has_javalang else "regex"
                )
                results.append(search_result)
        
        return results
    
    def find_callers(self, method_name: str, file_path: Optional[str] = None) -> List[JavaSearchResult]:
        """
        Find methods that call the specified method
        
        Args:
            method_name: Name of the method
            file_path: Optional file path to filter results
        
        Returns:
            List of JavaSearchResult objects for caller methods
        """
        results = []
        pattern = f"{method_name}("
        
        # Search through all files
        for file_rel_path, content in self.file_index.items():
            # Filter by file if specified
            if file_path and not self._matches_file_path(file_rel_path, file_path):
                continue
            
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if pattern in line and not line.strip().startswith('//'):
                    # Try to find which method contains this call
                    caller_method = self._find_containing_method(file_rel_path, i)
                    
                    if caller_method:
                        # Extract the caller method
                        definition, start, end = self._extract_complete_definition(
                            file_rel_path, caller_method['line'], 'method'
                        )
                        
                        # Get package info
                        parsed_info = self._parsed_files_cache.get(file_rel_path, {})
                        package_name = parsed_info.get('package')
                        
                        abs_path = str(self.project_path / file_rel_path)
                        search_result = JavaSearchResult(
                            file_path=abs_path,
                            line_number=start,
                            end_line=end,
                            method_name=caller_method['name'],
                            class_name=caller_method.get('class_name'),
                            package_name=package_name,
                            code=definition,
                            extraction_method="ast" if self.has_javalang else "regex"
                        )
                        results.append(search_result)
                    else:
                        # Call not in a method (maybe in static block or field initialization)
                        abs_path = str(self.project_path / file_rel_path)
                        search_result = JavaSearchResult(
                            file_path=abs_path,
                            line_number=i,
                            end_line=i,
                            method_name=None,
                            class_name=None,
                            package_name=None,
                            code=line.strip(),
                            extraction_method="regex"
                        )
                        results.append(search_result)
        
        return results[:10]  # Limit results
    
    def find_callees(self, method_name: str, file_path: Optional[str] = None) -> List[JavaSearchResult]:
        """
        Find methods called by the specified method
        
        Args:
            method_name: Name of the method
            file_path: Optional file path to filter results
        
        Returns:
            List of JavaSearchResult objects for callee methods
        """
        results = []
        
        # Find the method definition first
        if method_name in self.method_index:
            for file_rel_path, line_num, method_info in self.method_index[method_name]:
                # Filter by file if specified
                if file_path and not self._matches_file_path(file_rel_path, file_path):
                    continue
                
                # Extract method body
                definition, start, end = self._extract_complete_definition(
                    file_rel_path, line_num, 'method'
                )
                
                # Find method calls in the body
                method_calls = self._extract_method_calls(definition)
                
                for call_info in method_calls:
                    abs_path = str(self.project_path / file_rel_path)
                    search_result = JavaSearchResult(
                        file_path=abs_path,
                        line_number=call_info['line'],
                        end_line=call_info['line'],
                        method_name=call_info['method'],
                        class_name=call_info.get('class'),
                        package_name=None,
                        code=call_info['context'],
                        extraction_method="regex"
                    )
                    results.append(search_result)
        
        return results
    
    def search_code(self, code_pattern: str) -> Tuple[str, List[JavaSearchResult], bool]:
        """
        Search for code pattern in the codebase
        
        Args:
            code_pattern: Code pattern to search for
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        for file_rel_path, content in self.file_index.items():
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if code_pattern in line:
                    # Get context around the match
                    abs_path = self.project_path / file_rel_path
                    snippet = search_utils.get_code_region_around_line(
                        str(abs_path), i, window_size=5
                    )
                    
                    if snippet:
                        abs_path_str = str(abs_path)
                        search_result = JavaSearchResult(
                            file_path=abs_path_str,
                            line_number=max(1, i - 5),
                            end_line=i + 5,
                            method_name=None,
                            class_name=None,
                            package_name=None,
                            code=snippet,
                            extraction_method="regex"
                        )
                        results.append(search_result)
        
        if not results:
            return f"Could not find code pattern '{code_pattern}'", [], False
        
        message = f"Found {len(results)} occurrences of '{code_pattern}'"
        return message, results[:10], True  # Limit results
    
    def get_code_around_line(
        self,
        file_name: str,
        line_no: int,
        window_size: int = 10
    ) -> Tuple[str, List[JavaSearchResult], bool]:
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
                search_result = JavaSearchResult(
                    file_path=file_path,
                    line_number=max(1, line_no - window_size),
                    end_line=line_no + window_size,
                    method_name=None,
                    class_name=None,
                    package_name=None,
                    code=snippet,
                    extraction_method="manual"
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
        Extract complete definition (class or method)
        
        Returns:
            (definition_text, start_line, end_line)
        """
        try:
            abs_file_path = self.project_path / file_path
            with open(abs_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if line_number > len(lines):
                return "Line out of range", line_number, line_number
            
            if definition_type == 'method':
                definition, start, end = search_utils.extract_method_with_braces(lines, line_number)
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
    
    def _find_containing_method(self, file_path: str, line_number: int) -> Optional[Dict]:
        """Find which method contains the given line number"""
        parsed_info = self._parsed_files_cache.get(file_path)
        if not parsed_info:
            return None
        
        # Find the method that contains this line
        for method_info in parsed_info.get('methods', []):
            method_line = method_info['line']
            # Simple heuristic: if the call is after the method declaration
            # and before the next method, it's probably in this method
            if method_line <= line_number:
                # Check if there's a next method
                next_method_line = float('inf')
                for other_method in parsed_info.get('methods', []):
                    if other_method['line'] > method_line:
                        next_method_line = min(next_method_line, other_method['line'])
                
                if line_number < next_method_line:
                    return method_info
        
        return None
    
    def _extract_method_calls(self, method_body: str) -> List[Dict]:
        """Extract method calls from method body"""
        calls = []
        lines = method_body.split('\n')
        
        # Pattern to match method calls
        call_pattern = r'(\w+)\.(\w+)\s*\(|(\w+)\s*\('
        
        for i, line in enumerate(lines, 1):
            matches = re.finditer(call_pattern, line)
            for match in matches:
                if match.group(1) and match.group(2):
                    # Object.method() call
                    calls.append({
                        'method': match.group(2),
                        'class': match.group(1),
                        'line': i,
                        'context': line.strip()
                    })
                elif match.group(3):
                    # method() call
                    method_name = match.group(3)
                    # Filter out keywords
                    if method_name not in ['if', 'for', 'while', 'switch', 'catch', 'synchronized']:
                        calls.append({
                            'method': method_name,
                            'class': None,
                            'line': i,
                            'context': line.strip()
                        })
        
        return calls
    
    def _find_matching_files(self, partial_filename: str) -> List[str]:
        """Find files matching the partial filename"""
        partial_lower = partial_filename.lower()
        all_files = search_utils.find_java_files(str(self.project_path))
        
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
    
    def _get_method_snippet(self, method_name: str) -> Optional[JavaSearchResult]:
        """Return the first search result for a method."""
        try:
            results = self.search_function(method_name)
            if results:
                return results[0]
        except Exception:
            return None
        return None
    
    def _method_contains_pattern(self, method_name: str, pattern: str) -> bool:
        """Check if a method's code contains the given pattern."""
        if not pattern:
            return False
        snippet = self._get_method_snippet(method_name)
        if not snippet or not snippet.code:
            return False
        # Use word boundary for better matching
        regex = re.compile(rf"\b{re.escape(pattern)}\b")
        return bool(regex.search(snippet.code))
    
    def _extract_method_name_from_context(self, context: str) -> Optional[str]:
        """Extract method name from a line of code."""
        if not context:
            return None
        # Try to match method calls: method() or obj.method()
        match = re.search(r'\.(\w+)\s*\(|(\w+)\s*\(', context)
        if not match:
            return None
        candidate = match.group(1) or match.group(2)
        if candidate in {'if', 'for', 'while', 'switch', 'catch', 'synchronized', 'return'}:
            return None
        return candidate
    
    def _get_callees_names(self, method_name: str) -> List[str]:
        """Get the names of methods called by the given method."""
        names: List[str] = []
        for result in self.find_callees(method_name):
            callee = result.method_name or self._extract_method_name_from_context(result.code)
            if callee and callee != method_name and callee not in names:
                names.append(callee)
        return names
    
    def _get_callers_names(self, method_name: str) -> List[str]:
        """Get the names of methods that call the given method."""
        names: List[str] = []
        for result in self.find_callers(method_name):
            caller = result.method_name
            if not caller:
                caller = self._extract_method_name_from_context(result.code)
            if caller and caller != method_name and caller not in names:
                names.append(caller)
        return names
    
    def _find_methods_with_pattern(self, pattern: str) -> Set[str]:
        """Find methods whose code contains the given pattern."""
        matches: Set[str] = set()
        if not pattern:
            return matches
        
        # Search through all files for the pattern
        for file_path, content in self.file_index.items():
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    # Find containing method
                    method_info = self._find_containing_method(file_path, i)
                    if method_info:
                        matches.add(method_info['name'])
        
        return matches
    
    # ------------------------------------------------------------------
    # Advanced analysis APIs
    # ------------------------------------------------------------------
    
    def find_call_chain(
        self,
        start_method: str,
        depth: int = 3,
        direction: str = "forward"
    ) -> List[JavaCallChainResult]:
        """
        Build multi-level call chains starting from the given method.
        
        ⚠️ WARNING: Pattern-based matching may include false positives.
        Methods with common names may be confused across different classes.
        Best results with unique method names.
        """
        if not start_method:
            return []
        
        direction = direction.lower()
        if direction not in {"forward", "backward"}:
            direction = "forward"
        depth = max(1, min(depth, 5))
        
        cache_dir = self._call_chain_cache.setdefault(direction, {})
        cache_key = f"{start_method}:{depth}"
        
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
            
            dfs(start_method, [start_method], depth)
            cache_dir[cache_key] = paths
            cached_paths = paths
        
        results: List[JavaCallChainResult] = []
        for path in cached_paths:
            details: List[JavaSearchResult] = []
            files: List[str] = []
            for method in path:
                snippet = self._get_method_snippet(method)
                if snippet:
                    details.append(snippet)
                    files.append(snippet.file_path)
            results.append(
                JavaCallChainResult(
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
        sink_method: str,
        max_depth: int = 3
    ) -> List[JavaTaintPath]:
        """
        Find taint paths from source pattern to sink method.
        
        ⚠️ WARNING: Best-effort analysis. May miss paths or report false positives.
        Cannot track taint through fields, collections, or complex data flows.
        """
        max_depth = max(1, min(max_depth, 5))
        sources = self._find_methods_with_pattern(source_pattern)
        
        if not sources:
            return []
        
        paths: List[JavaTaintPath] = []
        
        for source in sources:
            path: List[str] = [source]
            visited: Set[str] = set()
            
            def dfs(current: str, remaining: int) -> None:
                # Check if current method contains the sink
                if self._method_contains_pattern(current, sink_method):
                    confidence = 'high' if current == source else 'medium'
                    paths.append(
                        JavaTaintPath(
                            source=source_pattern,
                            sink=sink_method,
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
    
    def track_variable(
        self,
        method_name: str,
        variable_name: str
    ) -> Dict[str, object]:
        """
        Track variable usage inside a method.
        
        Works for local variables and parameters.
        Limited support for field tracking.
        
        ⚠️ WARNING: Cannot track aliasing or complex data flows.
        """
        snippet = self._get_method_snippet(method_name)
        if not snippet:
            return {}
        
        assignments: List[int] = []
        uses: List[int] = []
        code_lines = snippet.code.splitlines()
        current_line = snippet.line_number
        
        # Java-specific patterns
        # Declaration: Type varName = ..., var varName = ...
        decl_pattern = rf"(?:var|int|long|short|byte|float|double|boolean|char|String|Object|\w+(?:<.*?>)?)\s+{re.escape(variable_name)}\s*="
        # Assignment: varName = ..., this.varName = ...
        assign_pattern = rf"(?:this\.)?{re.escape(variable_name)}\s*="
        # Use: varName anywhere (method call, parameter, etc.)
        use_pattern = rf"\b{re.escape(variable_name)}\b"
        # Return: return varName
        return_pattern = rf"return[^;]*\b{re.escape(variable_name)}\b"
        
        decl_regex = re.compile(decl_pattern, re.IGNORECASE)
        assign_regex = re.compile(assign_pattern, re.IGNORECASE)
        use_regex = re.compile(use_pattern, re.IGNORECASE)
        return_regex = re.compile(return_pattern, re.IGNORECASE)
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
            'function': method_name,
            'assignments': assignments,
            'uses': uses,
            'returned': returned,
            'file': snippet.file_path,
            'code': snippet.code
        }


