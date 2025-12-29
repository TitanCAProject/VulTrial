"""
Utility functions for JavaScript/TypeScript code analysis
Supports AST parsing using ts-morph (via Node.js bridge) and regex-based fallbacks
"""

import glob
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple, Dict


def find_js_ts_files(dir_path: str) -> List[str]:
    """
    Get all JavaScript and TypeScript files recursively from a directory
    
    Args:
        dir_path: Path to the directory
    
    Returns:
        List of absolute file paths
    """
    patterns = [
        os.path.join(dir_path, "**/*.js"),
        os.path.join(dir_path, "**/*.jsx"),
        os.path.join(dir_path, "**/*.ts"),
        os.path.join(dir_path, "**/*.tsx"),
        os.path.join(dir_path, "**/*.mjs"),
        os.path.join(dir_path, "**/*.cjs")
    ]
    
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=True))
    
    # Filter out common directories to skip
    skip_dirs = {'node_modules', 'dist', 'build', '.next', 'out', 'coverage', '.git'}
    filtered_files = []
    for file in files:
        # Check if any skip_dir is in the path
        path_parts = Path(file).parts
        if not any(skip_dir in path_parts for skip_dir in skip_dirs):
            filtered_files.append(file)
    
    return filtered_files


def is_typescript_file(file_path: str) -> bool:
    """Check if a file is TypeScript based on extension"""
    ext = Path(file_path).suffix.lower()
    return ext in ['.ts', '.tsx']


def check_tsmorph_available() -> bool:
    """Check if ts-morph is available via Node.js"""
    try:
        # Try to find the ts-morph bridge script
        bridge_path = Path(__file__).parent / 'tsmorph_bridge.js'
        if not bridge_path.exists():
            return False
        
        # Check if Node.js is available
        result = subprocess.run(
            ['node', '--version'],
            capture_output=True,
            text=True,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False


def parse_js_file_with_tsmorph(file_path: str) -> Optional[Dict]:
    """
    Parse JavaScript/TypeScript file using ts-morph via Node.js bridge
    
    Returns:
        Dict with classes, functions, imports info, or None if parsing fails
    """
    if not check_tsmorph_available():
        return None
    
    try:
        bridge_path = Path(__file__).parent / 'tsmorph_bridge.js'
        
        result = subprocess.run(
            ['node', str(bridge_path), file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return None
        
        parsed_data = json.loads(result.stdout)
        return parsed_data
        
    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception) as e:
        print(f"ts-morph parsing failed for {file_path}: {e}")
        return None


def parse_js_file_with_regex(file_path: str) -> Dict:
    """
    Parse JavaScript/TypeScript file using regex patterns as fallback
    
    Returns:
        Dict with classes, functions, imports info
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        result = {
            'file_type': 'typescript' if is_typescript_file(file_path) else 'javascript',
            'imports': extract_imports_regex(content),
            'exports': extract_exports_regex(content),
            'classes': [],
            'functions': [],
            'methods': []
        }
        
        # Find classes
        class_pattern = r'^\s*(?:export\s+)?(?:default\s+)?class\s+(\w+)'
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue
            
            match = re.search(class_pattern, line)
            if match:
                class_name = match.group(1)
                result['classes'].append({
                    'name': class_name,
                    'line': i,
                    'is_exported': 'export' in line,
                    'is_default': 'default' in line,
                    'methods': []
                })
        
        # Find functions (regular, arrow, async)
        # Pattern 1: function declarations
        func_pattern1 = r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)'
        # Pattern 2: const/let/var with arrow function
        func_pattern2 = r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>'
        # Pattern 3: object method shorthand
        func_pattern3 = r'^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{'
        
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue
            
            # Check function declaration
            match = re.search(func_pattern1, line)
            if match:
                func_name = match.group(1)
                result['functions'].append({
                    'name': func_name,
                    'line': i,
                    'is_async': 'async' in line,
                    'is_arrow': False,
                    'is_exported': 'export' in line,
                    'class_name': None
                })
                continue
            
            # Check arrow function
            match = re.search(func_pattern2, line)
            if match:
                func_name = match.group(1)
                result['functions'].append({
                    'name': func_name,
                    'line': i,
                    'is_async': 'async' in line,
                    'is_arrow': True,
                    'is_exported': 'export' in line,
                    'class_name': None
                })
                continue
        
        # Find class methods (inside classes)
        in_class = None
        brace_depth = 0
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*'):
                continue
            
            # Track brace depth
            brace_depth += line.count('{') - line.count('}')
            
            # Check if entering a class
            class_match = re.search(class_pattern, line)
            if class_match:
                in_class = class_match.group(1)
                continue
            
            # Exit class when braces balance
            if in_class and brace_depth <= 0:
                in_class = None
            
            # Find methods inside classes
            if in_class:
                # Method pattern: methodName() { or async methodName() {
                method_pattern = r'^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{'
                match = re.search(method_pattern, line)
                if match:
                    method_name = match.group(1)
                    # Skip constructor and common keywords
                    if method_name not in ['if', 'for', 'while', 'switch', 'catch', 'constructor']:
                        result['methods'].append({
                            'name': method_name,
                            'line': i,
                            'is_async': 'async' in line,
                            'is_arrow': False,
                            'class_name': in_class
                        })
                        
                        # Also add to the class's methods list
                        for cls in result['classes']:
                            if cls['name'] == in_class:
                                cls['methods'].append({
                                    'name': method_name,
                                    'line': i,
                                    'is_async': 'async' in line
                                })
        
        return result
        
    except Exception as e:
        print(f"Regex parsing failed for {file_path}: {e}")
        return {
            'file_type': 'unknown',
            'imports': [],
            'exports': [],
            'classes': [],
            'functions': [],
            'methods': []
        }


def extract_imports_regex(content: str) -> List[Dict]:
    """Extract import statements from JavaScript/TypeScript content"""
    imports = []
    
    # ES6 imports: import { x } from 'module'
    es6_pattern = r"import\s+(?:{[^}]+}|[\w,\s*]+)\s+from\s+['\"]([^'\"]+)['\"]"
    for match in re.finditer(es6_pattern, content):
        imports.append({
            'type': 'es6',
            'module': match.group(1),
            'statement': match.group(0)
        })
    
    # CommonJS require: const x = require('module')
    require_pattern = r"(?:const|let|var)\s+[\w{},\s]+\s*=\s*require\s*\(['\"]([^'\"]+)['\"]\)"
    for match in re.finditer(require_pattern, content):
        imports.append({
            'type': 'commonjs',
            'module': match.group(1),
            'statement': match.group(0)
        })
    
    return imports


def extract_exports_regex(content: str) -> List[Dict]:
    """Extract export statements from JavaScript/TypeScript content"""
    exports = []
    
    # ES6 exports: export { x }
    export_pattern = r"export\s+(?:default\s+)?(?:class|function|const|let|var)?\s*(\w+)"
    for match in re.finditer(export_pattern, content):
        exports.append({
            'type': 'es6',
            'name': match.group(1),
            'statement': match.group(0)
        })
    
    # CommonJS exports: module.exports = x
    module_exports_pattern = r"module\.exports\s*=\s*(\w+)"
    for match in re.finditer(module_exports_pattern, content):
        exports.append({
            'type': 'commonjs',
            'name': match.group(1),
            'statement': match.group(0)
        })
    
    return exports


def get_code_snippet(file_path: str, start_line: int, end_line: int, with_lineno: bool = True) -> str:
    """
    Get code snippet from file
    
    Args:
        file_path: Full path to file
        start_line: Start line (1-based)
        end_line: End line (1-based, inclusive)
        with_lineno: Include line numbers
    
    Returns:
        Code snippet as string
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        snippet = ""
        for i in range(start_line - 1, min(end_line, len(lines))):
            if with_lineno:
                snippet += f"{i+1:4d}: {lines[i]}"
            else:
                snippet += lines[i]
        return snippet
    except Exception as e:
        return f"Error reading file: {e}"


def get_code_region_around_line(
    file_path: str, 
    line_no: int, 
    window_size: int = 10, 
    with_lineno: bool = True
) -> Optional[str]:
    """
    Get code region around a specific line
    
    Args:
        file_path: Full path to file
        line_no: Line number (1-based)
        window_size: Number of lines before and after
        with_lineno: Include line numbers
    
    Returns:
        Code snippet or None if invalid
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        if line_no < 1 or line_no > len(lines):
            return None
        
        start = max(1, line_no - window_size)
        end = min(len(lines) + 1, line_no + window_size)
        
        snippet = ""
        for i in range(start, end):
            if with_lineno:
                snippet += f"{i:4d}: {lines[i - 1]}"
            else:
                snippet += lines[i - 1]
        
        return snippet
    except Exception:
        return None


def extract_function_with_braces(
    lines: List[str], 
    start_line: int
) -> Tuple[str, int, int]:
    """
    Extract complete function definition by counting braces
    
    Args:
        lines: File lines
        start_line: Approximate start line (1-based)
    
    Returns:
        (definition, actual_start_line, end_line)
    """
    actual_start = start_line
    
    # Look backwards for function signature start (decorators, export, async)
    for i in range(start_line - 1, max(0, start_line - 10), -1):
        line = lines[i].strip()
        if not line or line.startswith('//') or line.startswith('/*'):
            continue
        # Check for function keywords, export, async
        if any(keyword in line for keyword in ['function', 'export', 'async', '@', '=>']):
            actual_start = i + 1
            break
        # Multi-line function signature
        if '(' in line and ')' not in line:
            actual_start = i + 1
            break
    
    # Find function end by counting braces
    brace_count = 0
    end_line = start_line
    found_opening = False
    in_string = False
    in_template = False
    in_regex = False
    escape_next = False
    quote_char = None
    
    for i in range(actual_start - 1, len(lines)):
        line = lines[i]
        
        j = 0
        while j < len(line):
            char = line[j]
            
            if escape_next:
                escape_next = False
                j += 1
                continue
            
            if char == '\\':
                escape_next = True
                j += 1
                continue
            
            # Handle strings
            if char in ['"', "'"] and not in_template and not in_regex:
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None
            
            # Handle template literals
            elif char == '`' and not in_string and not in_regex:
                in_template = not in_template
            
            # Handle regex (simple heuristic)
            elif char == '/' and not in_string and not in_template:
                # Check if it's a regex literal (after =, (, [, return, etc.)
                prev_chars = line[:j].strip()
                if prev_chars and prev_chars[-1] in ['=', '(', '[', ',', ':', 'n']:  # 'n' for return
                    in_regex = not in_regex
            
            # Count braces only outside strings/templates/regex
            elif not in_string and not in_template and not in_regex:
                if char == '{':
                    brace_count += 1
                    found_opening = True
                elif char == '}':
                    brace_count -= 1
            
            j += 1
        
        if found_opening and brace_count == 0:
            end_line = i + 1
            break
        
        # Handle arrow functions without braces: const f = () => value;
        if '=>' in line and not found_opening and ';' in line:
            end_line = i + 1
            break
    
    definition = ''.join(lines[actual_start - 1:end_line])
    return definition.rstrip(), actual_start, end_line


def extract_class_with_braces(
    lines: List[str], 
    start_line: int
) -> Tuple[str, int, int]:
    """
    Extract complete class definition by counting braces
    
    Args:
        lines: File lines
        start_line: Approximate start line (1-based)
    
    Returns:
        (definition, actual_start_line, end_line)
    """
    actual_start = start_line
    
    # Look backwards for class signature start (decorators, export)
    for i in range(start_line - 1, max(0, start_line - 10), -1):
        line = lines[i].strip()
        if not line or line.startswith('//') or line.startswith('/*'):
            continue
        # Check for export, decorators
        if any(keyword in line for keyword in ['export', '@']):
            actual_start = i + 1
            break
    
    # Find class end by counting braces (same logic as function)
    brace_count = 0
    end_line = start_line
    found_opening = False
    in_string = False
    in_template = False
    escape_next = False
    quote_char = None
    
    for i in range(actual_start - 1, len(lines)):
        line = lines[i]
        
        for char in line:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char in ['"', "'"] and not in_template:
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None
            
            elif char == '`' and not in_string:
                in_template = not in_template
            
            elif not in_string and not in_template:
                if char == '{':
                    brace_count += 1
                    found_opening = True
                elif char == '}':
                    brace_count -= 1
        
        if found_opening and brace_count == 0:
            end_line = i + 1
            break
    
    definition = ''.join(lines[actual_start - 1:end_line])
    return definition.rstrip(), actual_start, end_line

