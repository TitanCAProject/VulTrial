"""
Utility functions for Java code analysis
Supports AST parsing using javalang and regex-based fallbacks
"""

import glob
import re
import os
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set


def find_java_files(dir_path: str) -> List[str]:
    """
    Get all Java files recursively from a directory
    
    Args:
        dir_path: Path to the directory
    
    Returns:
        List of absolute file paths
    """
    pattern = os.path.join(dir_path, "**/*.java")
    files = glob.glob(pattern, recursive=True)
    return files


def check_javalang_available() -> bool:
    """Check if javalang is available for AST parsing"""
    try:
        import javalang
        return True
    except ImportError:
        return False


def extract_package_name(file_content: str) -> Optional[str]:
    """Extract package name from Java file content"""
    package_match = re.search(r'^\s*package\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*;', file_content, re.MULTILINE)
    return package_match.group(1) if package_match else None


def extract_imports(file_content: str) -> List[str]:
    """Extract import statements from Java file content"""
    import_pattern = r'^\s*import\s+(?:static\s+)?([a-zA-Z_][a-zA-Z0-9_.*]*)\s*;'
    imports = re.findall(import_pattern, file_content, re.MULTILINE)
    return imports


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


def extract_method_with_braces(
    lines: List[str], 
    start_line: int
) -> Tuple[str, int, int]:
    """
    Extract complete method definition by counting braces
    
    Args:
        lines: File lines
        start_line: Approximate start line (1-based)
    
    Returns:
        (definition, actual_start_line, end_line)
    """
    actual_start = start_line
    
    # Look backwards for method signature start (annotations, modifiers)
    for i in range(start_line - 1, max(0, start_line - 20), -1):
        line = lines[i].strip()
        if not line or line.startswith('//') or line.startswith('/*'):
            continue
        # Check for method modifiers or annotations
        if any(keyword in line for keyword in ['public', 'private', 'protected', 'static', '@']):
            actual_start = i + 1
            break
        # Multi-line method signature
        if ('(' in line and ')' not in line) or line.endswith(','):
            actual_start = i + 1
            break
    
    # Find method end by counting braces
    brace_count = 0
    end_line = start_line
    found_opening = False
    in_string = False
    in_char = False
    escape_next = False
    
    for i in range(actual_start - 1, len(lines)):
        line = lines[i]
        
        for char in line:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not in_char:
                in_string = not in_string
            elif char == "'" and not in_string:
                in_char = not in_char
            elif not in_string and not in_char:
                if char == '{':
                    brace_count += 1
                    found_opening = True
                elif char == '}':
                    brace_count -= 1
        
        if found_opening and brace_count == 0:
            end_line = i + 1
            break
        
        # Handle abstract methods or interface methods (no body)
        if not found_opening and ';' in line:
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
    
    # Look backwards for class signature start (annotations, modifiers)
    for i in range(start_line - 1, max(0, start_line - 10), -1):
        line = lines[i].strip()
        if not line or line.startswith('//') or line.startswith('/*'):
            continue
        # Check for class modifiers or annotations
        if any(keyword in line for keyword in ['public', 'private', 'protected', 'abstract', 'final', '@']):
            actual_start = i + 1
            break
    
    # Find class end by counting braces
    brace_count = 0
    end_line = start_line
    found_opening = False
    in_string = False
    in_char = False
    escape_next = False
    
    for i in range(actual_start - 1, len(lines)):
        line = lines[i]
        
        for char in line:
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"' and not in_char:
                in_string = not in_string
            elif char == "'" and not in_string:
                in_char = not in_char
            elif not in_string and not in_char:
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


def parse_java_file_with_ast(file_path: str) -> Optional[Dict]:
    """
    Parse Java file using javalang AST
    
    Returns:
        Dict with classes, methods, package info, or None if parsing fails
    """
    if not check_javalang_available():
        return None
    
    try:
        import javalang
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Parse the Java file
        tree = javalang.parse.parse(content)
        
        result = {
            'package': tree.package.name if tree.package else None,
            'imports': [imp.path for imp in tree.imports] if tree.imports else [],
            'classes': [],
            'interfaces': [],
            'methods': []
        }
        
        # Extract classes and their methods (including nested classes)
        # Need to track parent classes for nested class detection
        def extract_class_info(class_node, parent_class=None):
            """Recursively extract class and nested class information"""
            class_info = {
                'name': class_node.name,
                'line': class_node.position.line if class_node.position else 1,
                'modifiers': class_node.modifiers,
                'methods': [],
                'is_nested': parent_class is not None,
                'parent_class': parent_class
            }
            
            # Extract methods from this class
            for method_path, method_node in class_node.filter(javalang.tree.MethodDeclaration):
                method_info = {
                    'name': method_node.name,
                    'line': method_node.position.line if method_node.position else 1,
                    'modifiers': method_node.modifiers,
                    'return_type': str(method_node.return_type) if method_node.return_type else 'void',
                    'parameters': [str(param.type) + ' ' + param.name for param in method_node.parameters] if method_node.parameters else []
                }
                class_info['methods'].append(method_info)
                
                # Also add to global methods list
                result['methods'].append({
                    **method_info,
                    'class_name': class_node.name
                })
            
            # Extract nested classes
            for nested_path, nested_node in class_node.filter(javalang.tree.ClassDeclaration):
                # Only process immediate children (not deeper nested)
                if nested_node != class_node:
                    nested_info = extract_class_info(nested_node, parent_class=class_node.name)
                    result['classes'].append(nested_info)
            
            return class_info
        
        # Process top-level classes
        for path, node in tree.filter(javalang.tree.ClassDeclaration):
            # Only process top-level classes (no parent in path)
            # This is a heuristic - if the path has only the class, it's top-level
            if len([p for p in path if isinstance(p, javalang.tree.ClassDeclaration)]) == 1:
                class_info = extract_class_info(node, parent_class=None)
                result['classes'].append(class_info)
        
        # Extract interfaces (only top-level ones, nested are handled above)
        for path, node in tree.filter(javalang.tree.InterfaceDeclaration):
            # Only process top-level interfaces
            if len([p for p in path if isinstance(p, javalang.tree.InterfaceDeclaration)]) == 1:
                interface_info = {
                    'name': node.name,
                    'line': node.position.line if node.position else 1,
                    'modifiers': node.modifiers,
                    'methods': [],
                    'is_nested': False,
                    'parent_class': None
                }
                
                # Extract methods from interface
                for method_path, method_node in node.filter(javalang.tree.MethodDeclaration):
                    method_info = {
                        'name': method_node.name,
                        'line': method_node.position.line if method_node.position else 1,
                        'modifiers': method_node.modifiers,
                        'return_type': str(method_node.return_type) if method_node.return_type else 'void',
                        'parameters': [str(param.type) + ' ' + param.name for param in method_node.parameters] if method_node.parameters else []
                    }
                    interface_info['methods'].append(method_info)
                    
                    # Also add to global methods list
                    result['methods'].append({
                        **method_info,
                        'class_name': node.name
                    })
                
                result['interfaces'].append(interface_info)
        
        return result
        
    except Exception as e:
        print(f"AST parsing failed for {file_path}: {e}")
        return None


def parse_java_file_with_regex(file_path: str) -> Dict:
    """
    Parse Java file using regex patterns as fallback
    
    Returns:
        Dict with classes, methods, package info
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
        
        result = {
            'package': extract_package_name(content),
            'imports': extract_imports(content),
            'classes': [],
            'interfaces': [],
            'methods': []
        }
        
        # Find classes (including nested classes) using a stack-based approach
        class_stack = []  # Stack to track nested classes
        brace_depth = 0
        class_brace_depths = {}  # Track brace depth where each class starts
        
        # Enhanced pattern to catch nested classes too
        class_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:abstract|final)?\s*class\s+(\w+)'
        interface_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*interface\s+(\w+)'
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Skip comments
            if line_stripped.startswith('//') or line_stripped.startswith('/*'):
                continue
            
            # Track brace depth
            old_depth = brace_depth
            brace_depth += line.count('{') - line.count('}')
            
            # Check for class definition (including nested)
            class_match = re.search(class_pattern, line)
            if class_match:
                class_name = class_match.group(1)
                result['classes'].append({
                    'name': class_name,
                    'line': i,
                    'modifiers': ['static'] if 'static' in line else [],
                    'methods': [],
                    'is_nested': len(class_stack) > 0,
                    'parent_class': class_stack[-1] if class_stack else None
                })
                class_stack.append(class_name)
                class_brace_depths[class_name] = brace_depth
                continue
            
            # Check for interface definition
            interface_match = re.search(interface_pattern, line)
            if interface_match:
                interface_name = interface_match.group(1)
                result['interfaces'].append({
                    'name': interface_name,
                    'line': i,
                    'modifiers': ['static'] if 'static' in line else [],
                    'methods': [],
                    'is_nested': len(class_stack) > 0,
                    'parent_class': class_stack[-1] if class_stack else None
                })
                class_stack.append(interface_name)
                class_brace_depths[interface_name] = brace_depth
                continue
            
            # Pop from class stack when we exit a class (based on brace depth)
            while class_stack and brace_depth < class_brace_depths.get(class_stack[-1], float('inf')):
                class_stack.pop()
        
        # Find methods and associate them with classes
        current_class = None
        brace_depth = 0
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            
            # Skip comments
            if line_stripped.startswith('//') or line_stripped.startswith('/*'):
                continue
            
            # Track brace depth to know when we're inside/outside classes
            brace_depth += line.count('{') - line.count('}')
            
            # Check for class/interface start
            class_match = re.search(r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:abstract|final)?\s*(?:class|interface)\s+(\w+)', line)
            if class_match:
                current_class = class_match.group(1)
                continue
            
            # Reset current class when we exit the class (brace depth back to 0 or negative)
            if current_class and brace_depth <= 0:
                current_class = None
            
            # Find methods
            method_pattern = r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:final)?\s*(?:\w+\s+)*(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+(?:\s*,\s*\w+)*)?\s*[{;]'
            match = re.search(method_pattern, line)
            if match and not line_stripped.startswith('//'):
                method_name = match.group(1)
                # Skip constructors and common keywords
                if method_name not in ['class', 'interface', 'if', 'for', 'while', 'switch', 'catch']:
                    result['methods'].append({
                        'name': method_name,
                        'line': i,
                        'modifiers': [],
                        'return_type': 'unknown',
                        'parameters': [],
                        'class_name': current_class  # Now we track the containing class!
                    })
        
        return result
        
    except Exception as e:
        print(f"Regex parsing failed for {file_path}: {e}")
        return {
            'package': None,
            'imports': [],
            'classes': [],
            'interfaces': [],
            'methods': []
        }
