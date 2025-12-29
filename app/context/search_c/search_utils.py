"""
Utility functions for C/C++ code analysis
Supports tree-sitter for precise AST parsing and ctags as fallback
"""

import subprocess
import glob
import re
from os.path import join as pjoin
from pathlib import Path
from typing import List, Optional, Tuple


def find_c_cpp_files(dir_path: str, extensions: List[str] = None) -> List[str]:
    """
    Get all C/C++ files recursively from a directory
    
    Args:
        dir_path: Path to the directory
        extensions: File extensions to search (default: common C/C++ extensions)
    
    Returns:
        List of absolute file paths
    """
    if extensions is None:
        extensions = ['.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx', '.C']
    
    files = []
    for ext in extensions:
        pattern = pjoin(dir_path, f"**/*{ext}")
        files.extend(glob.glob(pattern, recursive=True))
    
    return files


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
                snippet += f"{i+1} {lines[i]}"
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
                snippet += f"{i} {lines[i - 1]}"
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
    
    # Look backwards for function signature start
    # We need to find the first line of the function signature, which may have
    # attributes, modifiers, or split across multiple lines
    for i in range(start_line - 1, max(0, start_line - 10), -1):
        line = lines[i].strip()
        if not line or line.startswith('//') or line.startswith('/*'):
            continue
        
        # Check if this line looks like a function signature component
        # It should either:
        # 1. Have function modifiers (inline/static/extern) followed by a paren
        # 2. Have an open paren without close (multi-line signature)
        # 3. End with comma or backslash (continued line)
        has_modifier_and_paren = (
            any(kw in line for kw in ['inline', 'static', 'extern', 'virtual', '__attribute__']) 
            and '(' in lines[i]  # Full line not stripped
        )
        multi_line_sig = ('(' in line and ')' not in line)
        continued_line = line.endswith(',') or line.endswith('\\')
        
        if has_modifier_and_paren or multi_line_sig or continued_line:
            actual_start = i + 1
            break
        
        # Stop if we hit another function definition or end of previous function
        if '}' in line or '{' in line:
            break
    
    # Find function end by counting braces
    brace_count = 0
    end_line = start_line
    found_opening = False
    in_string = False
    in_comment = False
    escape_next = False
    
    # Search forward to find opening brace (may be on next line after signature)
    opening_brace_line = None
    for i in range(actual_start - 1, min(actual_start + 10, len(lines))):
        if '{' in lines[i]:
            opening_brace_line = i
            break
        # If we hit a semicolon before opening brace, it's just a declaration
        if ';' in lines[i] and '{' not in lines[i]:
            # Just return the declaration
            end_line = i + 1
            definition = ''.join(lines[actual_start - 1:end_line])
            return definition.rstrip(), actual_start, end_line
    
    # If no opening brace found in reasonable range, it's likely a declaration
    if opening_brace_line is None:
        # Return what we have (likely just the signature)
        for i in range(actual_start - 1, min(actual_start + 5, len(lines))):
            if ';' in lines[i]:
                end_line = i + 1
                break
        else:
            end_line = min(actual_start + 5, len(lines))
        definition = ''.join(lines[actual_start - 1:end_line])
        return definition.rstrip(), actual_start, end_line
    
    # Now count braces starting from actual_start to find the closing brace
    for i in range(actual_start - 1, len(lines)):
        line = lines[i]
        
        for char in line:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not in_string:
                in_string = True
            elif char == '"' and in_string:
                in_string = False
            elif not in_string:
                if char == '{':
                    brace_count += 1
                    found_opening = True
                elif char == '}':
                    brace_count -= 1
        
        if found_opening and brace_count == 0:
            end_line = i + 1
            break
        
        # Safety: don't go too far (max 500 lines for a function)
        if i - (actual_start - 1) > 500:
            end_line = i + 1
            break
    
    definition = ''.join(lines[actual_start - 1:end_line])
    return definition.rstrip(), actual_start, end_line


def check_ctags_available() -> bool:
    """Check if ctags is installed"""
    try:
        result = subprocess.run(
            ['ctags', '--version'], 
            capture_output=True, 
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_tree_sitter_available() -> bool:
    """Check if tree-sitter for C++ is available"""
    try:
        import tree_sitter_cpp
        return True
    except ImportError:
        return False


def extract_function_with_ctags(
    file_path: str, 
    function_name: str, 
    approximate_line: int
) -> Optional[Tuple[str, int, int]]:
    """
    Extract function using ctags
    
    Returns:
        (definition, start_line, end_line) or None
    """
    if not check_ctags_available():
        return None
    
    try:
        result = subprocess.run(
            ['ctags', '-x', '--c-kinds=f', '--language-force=C++', file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return None
        
        # Parse ctags output to find function
        for line in result.stdout.strip().split('\n'):
            if line:
                parts = line.split()
                if len(parts) >= 4:
                    tag_name = parts[0]
                    line_num = int(parts[2])
                    
                    if tag_name == function_name:
                        # Extract function from file
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            lines = f.readlines()
                        
                        definition, start, end = extract_function_with_braces(lines, line_num)
                        return definition, start, end
        
        return None
    
    except Exception:
        return None


def extract_function_with_tree_sitter(
    file_path: str,
    function_name: str,
    approximate_line: int
) -> Optional[Tuple[str, int, int]]:
    """
    Extract function using tree-sitter AST
    
    Returns:
        (definition, start_line, end_line) or None
    """
    if not check_tree_sitter_available():
        return None
    
    try:
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
        
        PY_LANGUAGE = Language(tscpp.language())
        parser = Parser(PY_LANGUAGE)
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_code = f.read()
        
        tree = parser.parse(source_code.encode())
        root_node = tree.root_node
        
        # Find function definition node
        candidates = []
        
        def traverse(node):
            if node.type == 'function_definition':
                # Try to extract function name
                declarator = _find_child_by_type(node, 'function_declarator')
                if declarator:
                    identifier = _find_identifier_in_node(declarator)
                    if identifier and identifier.text.decode() == function_name:
                        node_line = node.start_point[0] + 1
                        candidates.append((node, abs(node_line - approximate_line)))
            
            for child in node.children:
                traverse(child)
        
        traverse(root_node)
        
        if candidates:
            # Get closest match
            candidates.sort(key=lambda x: x[1])
            func_node = candidates[0][0]
            
            start_byte = func_node.start_byte
            end_byte = func_node.end_byte
            definition_text = source_code[start_byte:end_byte]
            
            start_line = func_node.start_point[0] + 1
            end_line = func_node.end_point[0] + 1
            
            return definition_text, start_line, end_line
        
        return None
    
    except Exception:
        return None


def _find_child_by_type(node, node_type: str):
    """Find first child node of given type"""
    for child in node.children:
        if child.type == node_type:
            return child
    return None


def _find_identifier_in_node(node):
    """Recursively find identifier in node"""
    if node.type == 'identifier':
        return node
    
    for child in node.children:
        if child.type == 'identifier':
            return child
        result = _find_identifier_in_node(child)
        if result:
            return result
    
    return None


def get_include_dependencies(file_path: str) -> List[str]:
    """
    Extract #include statements from a file
    
    Returns:
        List of included header files
    """
    includes = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                match = re.search(r'#include\s*[<"]([^>"]+)[>"]', line)
                if match:
                    includes.append(match.group(1))
    except Exception:
        pass
    
    return includes

