"""
C/C++ Search Backend using cscope
Provides production-quality search APIs for C/C++ vulnerability analysis
"""

import subprocess
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, Set, Dict

from collections import deque

from . import search_utils
from .data_structures import CSearchResult, CCallChainResult, CTaintPath


class CSearchBackend:
    """Production-quality C/C++ search backend using cscope"""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.cscope_files = self.project_path / 'cscope.files'
        self.cscope_out = self.project_path / 'cscope.out'
        
        # Cache for file operations
        self._file_cache = {}
        self._include_cache = {}
        
        # Check tool availability
        self.has_tree_sitter = search_utils.check_tree_sitter_available()
        self.has_ctags = search_utils.check_ctags_available()
        self.has_cscope = False
        
        # Simple fallback index when cscope not available
        self.file_index = {}  # {filename: content}
        self.function_index = {}  # {function_name: [(file, line, code)]}
        self.class_index = {}  # {class_name: [(file, line, code)]}
        self._call_chain_cache: Dict[str, Dict[str, List[List[str]]]] = {}
        
        # Build cscope database or fallback index
        self._build_cscope_database()
    
    def _build_cscope_database(
        self, 
        extensions: List[str] = None
    ) -> bool:
        """Build cscope database for the project"""
        if extensions is None:
            extensions = ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.C']
        
        try:
            # Check if cscope is available
            subprocess.run(['cscope', '--version'], capture_output=True, check=True, timeout=5)
            
            # Find all source files
            find_cmd = ['find', str(self.project_path)]
            for ext in extensions:
                find_cmd.extend(['-name', f'*{ext}', '-o'])
            find_cmd = find_cmd[:-1]  # Remove last '-o'
            
            # Write file list
            with open(self.cscope_files, 'w') as f:
                subprocess.run(find_cmd, stdout=f, check=True, timeout=60)
            
            # Build cscope database with cross-reference
            subprocess.run(
                ['cscope', '-b', '-q', '-k'], 
                cwd=self.project_path, 
                check=True,
                timeout=120,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.has_cscope = True
            return True
        
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"Warning: cscope not available, using fallback mode: {e}")
            self.has_cscope = False
            # Build simple file index for fallback
            self._build_simple_index(extensions)
            return False
    
    def _build_simple_index(self, extensions: List[str]) -> None:
        """Build simple index when cscope is not available"""
        print("Building simple fallback index...")
        
        # Find all C/C++ files
        files = search_utils.find_c_cpp_files(str(self.project_path), extensions)
        
        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # Store file content
                rel_path = str(Path(file_path).relative_to(self.project_path))
                self.file_index[rel_path] = content
                
                # Simple pattern matching for functions and classes
                for i, line in enumerate(lines, 1):
                    line_stripped = line.strip()
                    
                    # Look for function definitions (including pointers like char*, int*)
                    # Pattern: [modifiers] return_type [*] function_name ( params ) [{|;]
                    func_match = re.search(
                        r'^\s*(?:static\s+|inline\s+|extern\s+|const\s+)?'  # Optional modifiers
                        r'(?:(?:unsigned\s+|signed\s+)?(?:void|int|char|long|short|float|double|size_t|uint\w*|struct\s+\w+|enum\s+\w+)\s*\**\s+)'  # Return type with optional *
                        r'(\w+(?:::\w+)?)\s*\([^)]*\)\s*[{;]?',  # Function name and params
                        line
                    )
                    if func_match and not line_stripped.startswith('//'):
                        func_name = func_match.group(1)
                        # Extract just the method name if it's a C++ method (Class::method -> method)
                        simple_name = func_name.split('::')[-1] if '::' in func_name else func_name
                        
                        if simple_name not in ['if', 'for', 'while', 'switch']:
                            if simple_name not in self.function_index:
                                self.function_index[simple_name] = []
                            # Store both the full qualified name and simple name
                            self.function_index[simple_name].append((rel_path, str(i), line_stripped))
                    
                    # Look for class definitions
                    class_match = re.search(r'^\s*(?:class|struct)\s+(\w+)', line)
                    if class_match and not line_stripped.startswith('//'):
                        class_name = class_match.group(1)
                        if class_name not in self.class_index:
                            self.class_index[class_name] = []
                        self.class_index[class_name].append((rel_path, str(i), line_stripped))
                        
            except Exception as e:
                print(f"Warning: Could not index {file_path}: {e}")
                continue
        
        print(f"Indexed {len(files)} files, {len(self.function_index)} functions, {len(self.class_index)} classes")
    
    def _query_cscope(self, query_type: int, symbol: str) -> List[dict]:
        """
        Execute cscope query or fallback to simple search
        
        Query types:
            0: Find this C symbol
            1: Find this global definition
            2: Find functions called by this function
            3: Find functions calling this function
            4: Find this text string
            6: Find this egrep pattern
            7: Find this file
            8: Find files #including this file
        
        Returns:
            List of results with 'file', 'function', 'line', 'code'
        """
        if self.has_cscope:
            try:
                result = subprocess.run(
                    ['cscope', '-d', '-L', f'-{query_type}', symbol],
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30
                )
                
                results = []
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split(' ', 3)
                        if len(parts) >= 4:
                            results.append({
                                'file': parts[0],
                                'function': parts[1],
                                'line': parts[2],
                                'code': parts[3]
                            })
                return results
            
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return []
        else:
            # Fallback to simple search
            return self._fallback_query(query_type, symbol)
    
    def _fallback_query(self, query_type: int, symbol: str) -> List[dict]:
        """Fallback query when cscope is not available"""
        results = []
        
        if query_type == 0 or query_type == 1:  # Find symbol/definition
            # Check function index
            if symbol in self.function_index:
                for file_path, line, code in self.function_index[symbol]:
                    results.append({
                        'file': file_path,
                        'function': '<global>',
                        'line': line,
                        'code': code
                    })
            
            # Check class index
            if symbol in self.class_index:
                for file_path, line, code in self.class_index[symbol]:
                    results.append({
                        'file': file_path,
                        'function': '<global>',
                        'line': line,
                        'code': code
                    })
        
        elif query_type == 3:  # Find callers
            # Simple text search for function calls
            pattern = f"{symbol}("
            for file_path, content in self.file_index.items():
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    line_stripped = line.strip()
                    
                    # Skip comments
                    if line_stripped.startswith('//') or line_stripped.startswith('/*'):
                        continue
                    
                    if pattern in line:
                        # Filter out function definitions and declarations
                        # Check if this line is a function definition (has return type before function name)
                        is_definition = re.match(
                            r'^\s*(?:static\s+|inline\s+|extern\s+|const\s+)?'
                            r'(?:void|int|char|long|short|float|double|size_t|uint\w*|struct\s+\w+)\s*\**\s+'
                            rf'{symbol}\s*\(',
                            line
                        )
                        
                        # Check if it's a header declaration (ends with ;)
                        is_header_decl = file_path.endswith('.h') and line_stripped.endswith(';')
                        
                        # Only add if it's actually a call, not a definition/declaration
                        if not is_definition and not is_header_decl:
                            # Try to find which function contains this call
                            caller_name = self._find_containing_function(file_path, i, lines)
                            
                            results.append({
                                'file': file_path,
                                'function': caller_name or '<global>',
                                'line': str(i),
                                'code': line.strip()
                            })
        
        elif query_type == 2:  # Find callees (functions called BY this function)
            # Find the function first, then extract calls from its body
            if symbol in self.function_index:
                for file_path, line, code in self.function_index[symbol]:
                    # Get the function body
                    abs_path = str(self.project_path / file_path)
                    with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines_list = f.readlines()
                    
                    # Extract complete function
                    from . import search_utils
                    func_body, start, end = search_utils.extract_function_with_braces(lines_list, int(line))
                    
                    # Find function calls in the body
                    call_pattern = r'\b([a-z_][a-z0-9_]*)\s*\('
                    potential_calls = re.findall(call_pattern, func_body, re.IGNORECASE)
                    
                    # For each call, check if it's in our index
                    for call_name in set(potential_calls):
                        if call_name == symbol:  # Skip self
                            continue
                        if call_name in ['if', 'for', 'while', 'switch', 'return', 'sizeof', 'printf', 'fprintf']:
                            continue
                        
                        # Check if this is a user-defined function in our index
                        if call_name in self.function_index:
                            for callee_file, callee_line, callee_code in self.function_index[call_name]:
                                results.append({
                                    'file': callee_file,
                                    'function': call_name,
                                    'line': callee_line,
                                    'code': f'{call_name}() called in {symbol}'
                                })
                                break  # One result per callee
        
        elif query_type == 4:  # Text search
            for file_path, content in self.file_index.items():
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if symbol in line:
                        results.append({
                            'file': file_path,
                            'function': '<global>',
                            'line': str(i),
                            'code': line.strip()
                        })
        
        return results[:10]  # Limit results
    
    def _find_containing_function(self, file_path: str, line_number: int, lines: List[str]) -> Optional[str]:
        """Find which function contains the given line number"""
        # Search backwards from the line to find the function definition
        for i in range(line_number - 1, -1, -1):
            line = lines[i]
            
            # Look for function definition pattern
            func_match = re.search(
                r'^\s*(?:static\s+|inline\s+|extern\s+|const\s+)?'
                r'(?:(?:unsigned\s+|signed\s+)?(?:void|int|char|long|short|float|double|size_t|uint\w*|struct\s+\w+|enum\s+\w+)\s*\**\s+)'
                r'(\w+)\s*\([^)]*\)\s*\{?',
                line
            )
            
            if func_match:
                func_name = func_match.group(1)
                # Make sure it's not a keyword
                if func_name not in ['if', 'for', 'while', 'switch']:
                    return func_name
            
            # Stop if we've gone too far (200 lines)
            if line_number - i > 200:
                break
        
        return None
    
    def _extract_complete_definition(
        self,
        file_path: str,
        line_number: int,
        symbol_name: str,
        definition_type: str = 'function'
    ) -> Tuple[str, int, int, str]:
        """
        Extract complete definition using tree-sitter, ctags, or manual fallback
        
        Returns:
            (definition_text, start_line, end_line, extraction_method)
        """
        abs_file_path = self.project_path / file_path
        
        if not abs_file_path.exists():
            return "File not found", line_number, line_number, "error"
        
        # Try tree-sitter first (most accurate)
        if self.has_tree_sitter and definition_type == 'function':
            result = search_utils.extract_function_with_tree_sitter(
                str(abs_file_path), symbol_name, line_number
            )
            if result:
                definition, start, end = result
                return definition, start, end, "tree-sitter"
        
        # Try ctags as fallback
        if self.has_ctags and definition_type == 'function':
            result = search_utils.extract_function_with_ctags(
                str(abs_file_path), symbol_name, line_number
            )
            if result:
                definition, start, end = result
                return definition, start, end, "ctags"
        
        # Manual fallback with brace counting
        return self._extract_manual(abs_file_path, line_number, definition_type)
    
    def _extract_manual(
        self,
        file_path: Path,
        line_number: int,
        definition_type: str
    ) -> Tuple[str, int, int, str]:
        """Manual extraction using brace counting"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            if line_number > len(lines):
                return "Line out of range", line_number, line_number, "error"
            
            if definition_type == 'function':
                definition, start, end = search_utils.extract_function_with_braces(
                    lines, line_number
                )
                return definition, start, end, "manual"
            else:
                # For other types, just get context
                snippet = search_utils.get_code_region_around_line(
                    str(file_path), line_number, window_size=5
                )
                return snippet or "", line_number, line_number, "manual"
        
        except Exception as e:
            return f"Error: {e}", line_number, line_number, "error"
    
    def search_function(self, function_name: str) -> List[CSearchResult]:
        """
        Search for function definitions
        
        Prioritizes implementations (.c, .cpp) over declarations (.h, .hpp)
        
        Args:
            function_name: Name of the function
        
        Returns:
            List of CSearchResult objects with complete function bodies
        """
        # Query cscope for function definitions
        cscope_results = self._query_cscope(1, function_name)
        
        # If no results, try general symbol search
        if not cscope_results:
            cscope_results = self._query_cscope(0, function_name)
            # Filter for definitions (marked as '<global>')
            cscope_results = [r for r in cscope_results if r['function'] == '<global>']
        
        # Separate declarations from implementations
        declarations = []
        implementations = []
        
        for result in cscope_results:
            file_path = result['file']
            line_num = int(result['line'])
            
            # Extract complete function definition
            definition, start, end, method = self._extract_complete_definition(
                file_path, line_num, function_name, 'function'
            )
            
            abs_path = str(self.project_path / file_path)
            search_result = CSearchResult(
                file_path=abs_path,
                line_number=start,
                end_line=end,
                function_name=function_name,
                class_name=None,
                code=definition,
                extraction_method=method
            )
            
            # Categorize: is this a declaration or implementation?
            # Check if we actually got a function body (not just signature)
            has_opening_brace = '{' in definition
            has_closing_brace = '}' in definition
            is_just_signature = (
                definition.strip().endswith(';') or 
                (not has_opening_brace and not has_closing_brace) or
                definition.count('\n') < 2  # Very short, likely just signature
            )
            
            is_header_file = file_path.endswith(('.h', '.hpp', '.hxx', '.hh'))
            
            # It's a declaration if:
            # 1. It's just a signature (no body), OR
            # 2. It's in a header and doesn't have a complete body
            is_declaration = is_just_signature or (is_header_file and not (has_opening_brace and has_closing_brace))
            
            if is_declaration:
                declarations.append(search_result)
            else:
                implementations.append(search_result)
        
        # Prefer implementations over declarations
        # Only return declarations if no implementations found
        if implementations:
            return implementations
        else:
            return declarations
    
    def find_callers(self, function_name: str, file_path: Optional[str] = None) -> List[CSearchResult]:
        """
        Find functions that call the specified function
        
        Args:
            function_name: Name of the function
            file_path: Optional file path to filter results
        
        Returns:
            List of CSearchResult objects for caller functions
        """
        results = []
        
        # Query cscope for callers
        cscope_results = self._query_cscope(3, function_name)
        
        # Filter by file if specified
        if file_path:
            cscope_results = self._filter_by_include(cscope_results, file_path)
        
        for result in cscope_results:
            caller_file = result['file']
            caller_function = result['function']
            line_num = int(result['line'])
            context = result['code']
            
            # Filter out false positives:
            # 1. Skip if it's the function definition itself (line looks like "type funcname(...) {")
            # 2. Skip if it's a declaration in a header file
            # 3. Skip if the line contains return type keywords before the function name
            
            is_definition_pattern = re.match(
                r'^\s*(?:static\s+|inline\s+|extern\s+|const\s+)?'
                r'(?:void|int|char|long|short|float|double|size_t|uint\w*|struct\s+\w+)\s*\**\s+'
                rf'{function_name}\s*\(',
                context
            )
            is_header_file = caller_file.endswith(('.h', '.hpp', '.hxx', '.hh'))
            ends_with_semicolon = context.strip().endswith(';')
            
            # Skip function definitions and header declarations
            if is_definition_pattern:
                # This is the function definition itself, not a call
                continue
            
            if is_header_file and ends_with_semicolon:
                # This is a declaration in a header, not a call
                continue
            
            # Skip global scope calls
            if caller_function == '<global>':
                abs_path = str(self.project_path / caller_file)
                search_result = CSearchResult(
                    file_path=abs_path,
                    line_number=line_num,
                    end_line=line_num,
                    function_name=None,
                    class_name=None,
                    code=context,
                    extraction_method="cscope"
                )
                results.append(search_result)
                continue
            
            # Extract complete caller function
            definition, start, end, method = self._extract_complete_definition(
                caller_file, line_num, caller_function, 'function'
            )
            
            # Verify the caller actually calls the target
            if function_name + '(' in definition:
                abs_path = str(self.project_path / caller_file)
                search_result = CSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=caller_function,
                    class_name=None,
                    code=definition,
                    extraction_method=method
                )
                results.append(search_result)
        
        return results[:10]  # Limit results
    
    def find_callees(self, function_name: str, file_path: Optional[str] = None) -> List[CSearchResult]:
        """
        Find functions called by the specified function
        
        Args:
            function_name: Name of the function
            file_path: Optional file path to filter results
        
        Returns:
            List of CSearchResult objects for callee functions
        """
        results = []
        
        # Query cscope for callees
        cscope_results = self._query_cscope(2, function_name)
        
        # Filter by file if specified
        if file_path:
            cscope_results = [r for r in cscope_results if r['file'] == file_path]
        
        for result in cscope_results:
            callee_function = result.get('function', 'unknown')
            file = result['file']
            line_num = int(result['line'])
            context = result['code']
            
            # Skip self-references (function definition line)
            if function_name == callee_function:
                if any(keyword in context for keyword in ['void', 'int', 'bool', 'static']):
                    continue
            
            abs_path = str(self.project_path / file)
            search_result = CSearchResult(
                file_path=abs_path,
                line_number=line_num,
                end_line=line_num,
                function_name=callee_function,
                class_name=None,
                code=context,
                extraction_method="cscope"
            )
            results.append(search_result)
        
        return results
    
    def search_code(self, code_pattern: str) -> Tuple[str, List[CSearchResult], bool]:
        """
        Search for code pattern in the codebase
        
        Args:
            code_pattern: Code pattern to search for
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        # Use cscope text search
        cscope_results = self._query_cscope(4, code_pattern)
        
        for result in cscope_results[:10]:  # Limit results
            file_path = result['file']
            line_num = int(result['line'])
            context = result['code']
            
            # Get more context around the match
            abs_path = self.project_path / file_path
            snippet = search_utils.get_code_region_around_line(
                str(abs_path), line_num, window_size=5
            )
            
            if snippet:
                abs_path_str = str(abs_path)
                search_result = CSearchResult(
                    file_path=abs_path_str,
                    line_number=max(1, line_num - 5),
                    end_line=line_num + 5,
                    function_name=result.get('function'),
                    class_name=None,
                    code=snippet,
                    extraction_method="cscope"
                )
                results.append(search_result)
        
        if not results:
            return f"Could not find code pattern '{code_pattern}'", [], False
        
        message = f"Found {len(cscope_results)} occurrences of '{code_pattern}'"
        return message, results, True
    
    def search_class(self, class_name: str) -> Tuple[str, List[CSearchResult], bool]:
        """
        Search for C++ class definitions
        
        Args:
            class_name: Name of the class
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        # Search for class definition using cscope
        # Query type 1 finds global definitions
        cscope_results = self._query_cscope(1, class_name)
        
        # Also try general symbol search
        if not cscope_results:
            cscope_results = self._query_cscope(0, class_name)
        
        # Filter for class definitions
        class_results = []
        for result in cscope_results:
            code = result.get('code', '')
            # Look for class definition patterns
            if 'class ' + class_name in code or 'struct ' + class_name in code:
                class_results.append(result)
        
        for result in class_results[:3]:  # Limit to 3
            file_path = result['file']
            line_num = int(result['line'])
            
            # Extract class definition
            definition, start, end, method = self._extract_complete_definition(
                file_path, line_num, class_name, 'class'
            )
            
            abs_path = str(self.project_path / file_path)
            search_result = CSearchResult(
                file_path=abs_path,
                line_number=start,
                end_line=end,
                function_name=None,
                class_name=class_name,
                code=definition,
                extraction_method=method
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
    ) -> Tuple[str, List[CSearchResult], bool]:
        """
        Search for method in a C++ class
        
        Args:
            method_name: Name of the method
            class_name: Name of the class
        
        Returns:
            (message, search_results, success)
        """
        results = []
        
        # Try to find the method - cscope doesn't distinguish class methods,
        # so we search for the function and filter by context
        method_results = self._query_cscope(1, method_name)
        
        if not method_results:
            method_results = self._query_cscope(0, method_name)
        
        # Separate declarations from implementations
        declarations = []
        implementations = []
        
        # Filter for methods that might belong to this class
        for result in method_results:
            file_path = result['file']
            line_num = int(result['line'])
            
            # Extract the method
            definition, start, end, method_type = self._extract_complete_definition(
                file_path, line_num, method_name, 'function'
            )
            
            # Check if this method belongs to the class
            # Look for class_name:: prefix or if it's in the class definition
            if (f"{class_name}::" in definition or 
                self._is_method_in_class(file_path, start, end, class_name)):
                
                abs_path = str(self.project_path / file_path)
                search_result = CSearchResult(
                    file_path=abs_path,
                    line_number=start,
                    end_line=end,
                    function_name=method_name,
                    class_name=class_name,
                    code=definition,
                    extraction_method=method_type
                )
                
                # Prioritize implementations over declarations
                if file_path.endswith('.h') or file_path.endswith('.hpp'):
                    # This is likely a declaration
                    if '{' not in definition and definition.strip().endswith(';'):
                        declarations.append(search_result)
                    else:
                        implementations.append(search_result)
                else:
                    # This is likely an implementation (.cpp, .c, etc.)
                    implementations.append(search_result)
        
        # Prefer implementations, fall back to declarations if no implementations found
        if implementations:
            results.extend(implementations)
        else:
            results.extend(declarations)
        
        if not results:
            return f"Could not find method {method_name} in class {class_name}", [], False
        
        message = f"Found {len(results)} method(s) {method_name} in class {class_name}"
        return message, results[:3], True  # Limit to 3
    
    def _is_method_in_class(
        self, 
        file_path: str, 
        method_start: int, 
        method_end: int, 
        class_name: str
    ) -> bool:
        """Check if a method is defined within a class"""
        try:
            abs_path = self.project_path / file_path
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # Search backwards from method for class definition
            for i in range(method_start - 1, max(0, method_start - 100), -1):
                line = lines[i].strip()
                if f'class {class_name}' in line or f'struct {class_name}' in line:
                    # Found class definition before this method
                    return True
                # If we hit another class, this isn't in our target class
                if line.startswith('class ') or line.startswith('struct '):
                    if class_name not in line:
                        return False
            
            return False
        except Exception:
            return False
    
    def get_code_around_line(
        self,
        file_name: str,
        line_no: int,
        window_size: int = 10
    ) -> Tuple[str, List[CSearchResult], bool]:
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
                search_result = CSearchResult(
                    file_path=file_path,
                    line_number=max(1, line_no - window_size),
                    end_line=line_no + window_size,
                    function_name=None,
                    class_name=None,
                    code=snippet,
                    extraction_method="manual"
                )
                results.append(search_result)
        
        if not results:
            return f"Line {line_no} is invalid in file '{file_name}'", [], False
        
        message = f"Found code around line {line_no}"
        return message, results, True
    
    def _find_matching_files(self, partial_filename: str) -> List[str]:
        """Find files matching the partial filename"""
        partial_lower = partial_filename.lower()
        all_files = search_utils.find_c_cpp_files(str(self.project_path))
        
        candidates = []
        for file_path in all_files:
            if file_path.lower().endswith(partial_lower):
                candidates.append(file_path)
        
        return candidates
    
    def _filter_by_include(
        self,
        results: List[dict],
        target_file: str
    ) -> List[dict]:
        """
        Filter results based on include dependencies
        
        Keep callers that:
        1. Are in the same file as the target
        2. Include the header file associated with the target
        """
        target_path = Path(target_file)
        possible_headers = {
            target_path.with_suffix('.h').name,
            target_path.with_suffix('.hpp').name,
        }
        
        filtered = []
        for result in results:
            caller_file = result['file']
            
            # Same file - always keep
            if caller_file == target_file:
                filtered.append(result)
                continue
            
            # Check if caller includes the target's header
            caller_includes = self._get_includes(caller_file)
            if possible_headers.intersection(caller_includes):
                filtered.append(result)
        
        return filtered
    
    def _get_includes(self, file_path: str) -> Set[str]:
        """Get include dependencies for a file (with caching)"""
        if file_path in self._include_cache:
            return self._include_cache[file_path]
        
        abs_path = self.project_path / file_path
        includes = set(search_utils.get_include_dependencies(str(abs_path)))
        
        # Also add just the filename from each include
        include_names = set()
        for inc in includes:
            include_names.add(Path(inc).name)
        includes.update(include_names)
        
        self._include_cache[file_path] = includes
        return includes

    # ------------------------------------------------------------------
    # Helper utilities for advanced analysis
    # ------------------------------------------------------------------

    def _get_function_snippet(self, function_name: str) -> Optional[CSearchResult]:
        """Return the first search result for a function (implementation preferred)."""
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

    def _extract_callee_from_context(self, context: str) -> Optional[str]:
        """Extract the called function name from a line of code."""
        if not context:
            return None
        match = re.search(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(', context)
        if not match:
            return None
        candidate = match.group(1)
        if candidate in {'if', 'for', 'while', 'switch', 'return', 'sizeof'}:
            return None
        return candidate

    def _get_callees_names(self, function_name: str) -> List[str]:
        """Get the names of functions called by the given function."""
        names: List[str] = []
        for result in self.find_callees(function_name):
            callee = result.function_name or self._extract_callee_from_context(result.code)
            if not callee or callee == 'unknown':
                callee = self._extract_callee_from_context(result.code)
            if callee and callee != function_name and callee not in names:
                names.append(callee)
        return names

    def _get_callers_names(self, function_name: str) -> List[str]:
        """Get the names of functions that call the given function."""
        names: List[str] = []
        for result in self.find_callers(function_name):
            caller = result.function_name
            if not caller or caller == '<global>':
                caller = self._extract_callee_from_context(result.code)
            if caller and caller != function_name and caller not in names:
                names.append(caller)
        return names

    def _find_functions_with_pattern(self, pattern: str) -> Set[str]:
        """Find functions whose code contains the given pattern."""
        matches: Set[str] = set()
        if not pattern:
            return matches
        query_results = self._query_cscope(4, pattern)
        for hit in query_results:
            file_path = hit.get('file')
            line_no = int(hit.get('line', 0)) if hit.get('line') else 0
            abs_path = self.project_path / file_path if file_path else None
            func_name = hit.get('function')
            if func_name and func_name != '<global>':
                matches.add(func_name)
                continue
            if not abs_path or not abs_path.exists():
                continue
            try:
                with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                containing = self._find_containing_function(file_path, line_no, lines)
                if containing:
                    matches.add(containing)
            except Exception:
                continue
        return matches

    # ------------------------------------------------------------------
    # Advanced analysis APIs
    # ------------------------------------------------------------------

    def find_call_chain(
        self,
        start_function: str,
        depth: int = 3,
        direction: str = "forward"
    ) -> List[CCallChainResult]:
        """Build multi-level call chains starting from the given function."""
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

        results: List[CCallChainResult] = []
        for path in cached_paths:
            details: List[CSearchResult] = []
            files: List[str] = []
            for func in path:
                snippet = self._get_function_snippet(func)
                if snippet:
                    details.append(snippet)
                    files.append(snippet.file_path)
            results.append(
                CCallChainResult(
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
    ) -> List[CTaintPath]:
        """Find simple taint paths from source pattern to sink function."""
        max_depth = max(1, min(max_depth, 5))
        sources = self._find_functions_with_pattern(source_pattern)
        if not sources:
            return []

        paths: List[CTaintPath] = []

        for source in sources:
            path: List[str] = [source]
            visited: Set[str] = set()

            def dfs(current: str, remaining: int) -> None:
                if self._function_contains_pattern(current, sink_function):
                    confidence = 'high' if current == source else 'medium'
                    paths.append(
                        CTaintPath(
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

        # Deduplicate paths by tuple
        unique_paths = {}
        for tp in paths:
            key = tuple(tp.path)
            if key not in unique_paths:
                unique_paths[key] = tp
        return list(unique_paths.values())

    def track_variable(
        self,
        function_name: str,
        variable_name: str
    ) -> Dict[str, object]:
        """Track variable usage inside a function."""
        snippet = self._get_function_snippet(function_name)
        if not snippet:
            return {}

        assignments: List[int] = []
        uses: List[int] = []
        code_lines = snippet.code.splitlines()
        current_line = snippet.line_number
        
        # Handle C declarations and assignments
        # Match: type var = ..., type var[...], *var = ..., var = ...
        # Declaration: int data[256]; or char data[100];
        decl_pattern = rf"(?:int|char|short|long|float|double|void|size_t|uint\w*|struct\s+\w+|enum\s+\w+)\s+(?:\*\s*)?{re.escape(variable_name)}(?:\[.*?\])?"
        # Assignment: var = ..., *var = ..., var[...] = ...
        assign_pattern = rf"(?:\*\s*)?{re.escape(variable_name)}(?:\[.*?\])?\s*="
        # Match: var, *var, &var, var[...], var(...), ->var
        use_pattern = rf"(?:[*&]|\-\>)?\b{re.escape(variable_name)}\b"
        return_pattern = rf"return[^;]*\b{re.escape(variable_name)}\b"
        
        decl_regex = re.compile(decl_pattern, re.IGNORECASE)
        assign_regex = re.compile(assign_pattern, re.IGNORECASE)
        use_regex = re.compile(use_pattern, re.IGNORECASE)
        return_regex = re.compile(return_pattern, re.IGNORECASE)
        returned = False

        for line in code_lines:
            stripped = line.strip()
            # Skip comments
            if stripped.startswith('//') or stripped.startswith('/*'):
                current_line += 1
                continue
            
            # Check for declaration (counts as assignment in C)
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

