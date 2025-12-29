"""
Function Extractor - Extracts functions from source code files

Supports Python, C/C++, Java, JavaScript/TypeScript and more.
Uses language-specific patterns for accurate extraction.
"""

import re
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any

from .code_loader import CodeLoader


class FunctionExtractor:
    """Extracts functions from source code files"""
    
    @staticmethod
    def extract_function_from_file(
        file_path: str,
        function_name: str
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Extract a specific function from a file
        
        Args:
            file_path: Path to the code file
            function_name: Name of the function to extract
            
        Returns:
            Tuple of (function_code, start_line, end_line) or (None, None, None) if not found
        """
        content = CodeLoader.load_code_file(file_path)
        lines = content.split('\n')
        
        # Detect language
        language = CodeLoader.detect_language(file_path)
        
        if language == 'python':
            return FunctionExtractor._extract_python_function(lines, function_name)
        elif language in ['c', 'cpp']:
            return FunctionExtractor._extract_c_function(lines, function_name)
        elif language == 'java':
            return FunctionExtractor._extract_java_function(lines, function_name)
        elif language in ['javascript', 'typescript']:
            return FunctionExtractor._extract_js_function(lines, function_name)
        else:
            # Generic extraction
            return FunctionExtractor._extract_generic_function(lines, function_name)
    
    @staticmethod
    def extract_function_name_from_snippet(code_snippet: str) -> Optional[str]:
        """
        Try to extract function name from a code snippet
        
        Looks for common function definition patterns:
        - C/C++: type function_name(args)
        - Python: def function_name(args)
        - Java: modifiers type function_name(args)
        - JavaScript: function function_name(args) or const function_name = 
        
        Args:
            code_snippet: Code snippet that might contain a function definition
            
        Returns:
            Function name if found, None otherwise
        """
        lines = code_snippet.split('\n')
        if not lines:
            return None
        
        # Check first few lines for function definition
        for line in lines[:5]:
            line = line.strip()
            if not line or line.startswith('//') or line.startswith('/*') or line.startswith('#'):
                continue
            
            # Python: def function_name(
            match = re.match(r'def\s+(\w+)\s*\(', line)
            if match:
                return match.group(1)
            
            # JavaScript: function function_name( or const function_name = 
            match = re.match(r'(?:function|const|let|var)\s+(\w+)\s*[=(]', line)
            if match:
                return match.group(1)
            
            # C/C++/Java: ... function_name(
            # Look for identifier followed by opening paren
            match = re.search(r'\b(\w+)\s*\(', line)
            if match:
                func_name = match.group(1)
                # Filter out keywords
                keywords = {
                    'if', 'while', 'for', 'switch', 'sizeof', 'return', 
                    'catch', 'class', 'struct', 'enum', 'union', 'typeof',
                    'new', 'delete', 'throw', 'assert', 'static_cast',
                    'dynamic_cast', 'reinterpret_cast', 'const_cast'
                }
                if func_name not in keywords:
                    return func_name
        
        return None
    
    @staticmethod
    def list_all_functions_in_file(file_path: str) -> List[Dict[str, Any]]:
        """
        List all functions in a file with their locations
        
        Args:
            file_path: Path to the code file
            
        Returns:
            List of dicts with function info: {'name': str, 'start_line': int, 'end_line': int, 'code': str}
        """
        content = CodeLoader.load_code_file(file_path)
        lines = content.split('\n')
        
        # Detect language
        language = CodeLoader.detect_language(file_path)
        
        if language == 'python':
            return FunctionExtractor._list_python_functions(lines)
        elif language in ['c', 'cpp']:
            return FunctionExtractor._list_c_functions(lines)
        elif language == 'java':
            return FunctionExtractor._list_java_functions(lines)
        else:
            return []
    
    # ==================== Python ====================
    
    @staticmethod
    def _extract_python_function(lines: list, function_name: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Extract Python function"""
        pattern = re.compile(rf'^\s*def\s+{re.escape(function_name)}\s*\(')
        
        for i, line in enumerate(lines):
            if pattern.match(line):
                start_line = i + 1
                indent = len(line) - len(line.lstrip())
                
                # Find end of function
                end_line = len(lines)
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    if next_line.strip() and not next_line.startswith(' ' * (indent + 1)) and not next_line.startswith('\t'):
                        end_line = j
                        break
                
                function_code = '\n'.join(lines[i:end_line])
                return function_code, start_line, end_line
        
        return None, None, None
    
    @staticmethod
    def _list_python_functions(lines: list) -> List[Dict[str, Any]]:
        """List all Python functions"""
        functions = []
        pattern = re.compile(r'^\s*def\s+(\w+)\s*\(')
        
        for i, line in enumerate(lines):
            match = pattern.match(line)
            if match:
                func_name = match.group(1)
                start_line = i + 1
                indent = len(line) - len(line.lstrip())
                
                # Find end of function
                end_line = len(lines)
                for j in range(i + 1, len(lines)):
                    next_line = lines[j]
                    if next_line.strip():
                        next_indent = len(next_line) - len(next_line.lstrip())
                        if next_indent <= indent:
                            end_line = j
                            break
                
                function_code = '\n'.join(lines[i:end_line])
                functions.append({
                    'name': func_name,
                    'start_line': start_line,
                    'end_line': end_line,
                    'code': function_code,
                    'language': 'python'
                })
        
        return functions
    
    # ==================== C/C++ ====================
    
    @staticmethod
    def _extract_c_function(lines: list, function_name: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Extract C/C++ function"""
        # Look for function definition
        pattern = re.compile(rf'\b{re.escape(function_name)}\s*\(')
        
        for i, line in enumerate(lines):
            if pattern.search(line):
                start_line = i + 1
                
                # Find opening brace
                brace_count = 0
                found_opening = False
                end_line = len(lines)
                
                for j in range(i, len(lines)):
                    for char in lines[j]:
                        if char == '{':
                            brace_count += 1
                            found_opening = True
                        elif char == '}':
                            brace_count -= 1
                    
                    if found_opening and brace_count == 0:
                        end_line = j + 1
                        break
                
                function_code = '\n'.join(lines[i:end_line])
                return function_code, start_line, end_line
        
        return None, None, None
    
    @staticmethod
    def _list_c_functions(lines: list) -> List[Dict[str, Any]]:
        """List all C/C++ functions"""
        functions = []
        
        # Improved pattern to handle pointers, templates, multi-line
        pattern = re.compile(
            r'^\s*(?:static\s+|inline\s+|extern\s+|const\s+|virtual\s+)?'  # Optional modifiers
            r'(?:(?:unsigned\s+|signed\s+)?'  # Optional signed/unsigned
            r'(?:void|int|char|long|short|float|double|size_t|uint\w*|bool|'  # Basic types
            r'struct\s+\w+|enum\s+\w+|class\s+\w+|'  # Struct/enum/class types
            r'\w+)\s*\**\s+)'  # Type name with optional pointers
            r'(\w+(?:::\w+)?)\s*\(',  # Function name (including C++ Class::method)
            re.MULTILINE
        )
        
        # Track which lines we've already processed
        processed_lines = set()
        
        for i, line in enumerate(lines):
            if i in processed_lines or line.strip().startswith('//'):
                continue
            
            match = pattern.search(line)
            if match:
                func_name = match.group(1)
                # Extract simple name if it's a C++ method (Class::method -> method)
                simple_name = func_name.split('::')[-1] if '::' in func_name else func_name
                
                if simple_name in ['if', 'for', 'while', 'switch', 'return']:
                    continue
                
                start_line = i + 1
                
                # Look for opening brace (might be on next few lines)
                opening_brace_line = None
                for k in range(i, min(i + 5, len(lines))):
                    if '{' in lines[k]:
                        opening_brace_line = k
                        break
                    # If we hit semicolon first, it's just a declaration
                    if ';' in lines[k]:
                        break
                
                if opening_brace_line is None:
                    continue  # No function body, skip
                
                # Find end by counting braces
                brace_count = 0
                end_line = len(lines)
                found_opening = False
                
                for j in range(i, len(lines)):
                    processed_lines.add(j)
                    for char in lines[j]:
                        if char == '{':
                            brace_count += 1
                            found_opening = True
                        elif char == '}':
                            brace_count -= 1
                    
                    if found_opening and brace_count == 0:
                        end_line = j + 1
                        break
                    
                    # Safety: don't go too far
                    if j - i > 1000:  # Increased from 500
                        end_line = j + 1
                        break
                
                function_code = '\n'.join(lines[i:end_line])
                functions.append({
                    'name': simple_name,
                    'start_line': start_line,
                    'end_line': end_line,
                    'code': function_code,
                    'language': 'c'
                })
        
        return functions
    
    # ==================== Java ====================
    
    @staticmethod
    def _extract_java_function(lines: list, function_name: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Extract Java method"""
        pattern = re.compile(rf'\b{re.escape(function_name)}\s*\(')
        
        for i, line in enumerate(lines):
            if pattern.search(line):
                start_line = i + 1
                
                # Find opening brace
                brace_count = 0
                found_opening = False
                end_line = len(lines)
                
                for j in range(i, len(lines)):
                    for char in lines[j]:
                        if char == '{':
                            brace_count += 1
                            found_opening = True
                        elif char == '}':
                            brace_count -= 1
                    
                    if found_opening and brace_count == 0:
                        end_line = j + 1
                        break
                
                function_code = '\n'.join(lines[i:end_line])
                return function_code, start_line, end_line
        
        return None, None, None
    
    @staticmethod
    def _list_java_functions(lines: list) -> List[Dict[str, Any]]:
        """List all Java methods"""
        functions = []
        pattern = re.compile(r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{')
        
        for i, line in enumerate(lines):
            match = pattern.search(line)
            if match and not line.strip().startswith('//'):
                method_name = match.group(1)
                if method_name in ['class', 'interface']:
                    continue
                
                start_line = i + 1
                
                # Find end by counting braces
                brace_count = 0
                end_line = len(lines)
                
                for j in range(i, len(lines)):
                    for char in lines[j]:
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                    
                    if brace_count == 0 and '{' in lines[i]:
                        end_line = j + 1
                        break
                
                function_code = '\n'.join(lines[i:end_line])
                functions.append({
                    'name': method_name,
                    'start_line': start_line,
                    'end_line': end_line,
                    'code': function_code,
                    'language': 'java'
                })
        
        return functions
    
    # ==================== JavaScript/TypeScript ====================
    
    @staticmethod
    def _extract_js_function(lines: list, function_name: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Extract JavaScript/TypeScript function"""
        # Patterns for JS functions:
        # function name() { }
        # const name = () => { }
        # const name = function() { }
        # name: function() { }
        # async function name() { }
        
        patterns = [
            re.compile(rf'^\s*(?:async\s+)?function\s+{re.escape(function_name)}\s*\('),
            re.compile(rf'^\s*(?:const|let|var)\s+{re.escape(function_name)}\s*='),
            re.compile(rf'^\s*{re.escape(function_name)}\s*:\s*function'),
            re.compile(rf'^\s*{re.escape(function_name)}\s*:\s*\('),
        ]
        
        for i, line in enumerate(lines):
            for pattern in patterns:
                if pattern.search(line):
                    start_line = i + 1
                    
                    # Find opening brace
                    brace_count = 0
                    found_opening = False
                    end_line = len(lines)
                    
                    for j in range(i, len(lines)):
                        for char in lines[j]:
                            if char == '{':
                                brace_count += 1
                                found_opening = True
                            elif char == '}':
                                brace_count -= 1
                        
                        if found_opening and brace_count == 0:
                            end_line = j + 1
                            break
                    
                    function_code = '\n'.join(lines[i:end_line])
                    return function_code, start_line, end_line
        
        return None, None, None
    
    # ==================== Generic ====================
    
    @staticmethod
    def _extract_generic_function(lines: list, function_name: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """Generic function extraction (simple pattern matching)"""
        pattern = re.compile(rf'\b{re.escape(function_name)}\s*[(\{{]')
        
        for i, line in enumerate(lines):
            if pattern.search(line):
                start_line = i + 1
                
                # Try to find end by brace counting
                brace_count = 0
                found_opening = False
                end_line = min(i + 100, len(lines))  # Increased from 50
                
                for j in range(i, min(i + 100, len(lines))):
                    for char in lines[j]:
                        if char == '{':
                            brace_count += 1
                            found_opening = True
                        elif char == '}':
                            brace_count -= 1
                    
                    if found_opening and brace_count == 0:
                        end_line = j + 1
                        break
                
                function_code = '\n'.join(lines[i:end_line])
                return function_code, start_line, end_line
        
        return None, None, None

