"""
Snippet Normalizer - Converts escaped characters to actual characters

Handles cases where code snippets are stored with literal escape sequences
(e.g., extracted from JSON files where \n is stored as \\n)
"""

import codecs


def unescape_snippet(snippet: str) -> str:
    """
    Convert literal escape sequences to actual characters
    
    Handles common escape sequences that might appear in snippets
    extracted from JSON or other text formats:
    - \\n → newline
    - \\t → tab
    - \\r → carriage return
    - \\" → double quote
    - \\' → single quote
    - \\\\ → backslash
    
    Args:
        snippet: Code snippet with potential literal escape sequences
        
    Returns:
        Snippet with escape sequences converted to actual characters
        
    Example:
        >>> snippet = "if (x) {\\n    return y;\\n}"
        >>> print(unescape_snippet(snippet))
        if (x) {
            return y;
        }
    """
    if not snippet:
        return snippet
    
    # Check if the snippet likely has escaped characters
    # (contains \n or \t but no actual newlines/tabs)
    has_escaped_newline = '\\n' in snippet
    has_actual_newline = '\n' in snippet
    has_escaped_tab = '\\t' in snippet
    has_actual_tab = '\t' in snippet
    
    # If it has escaped chars but no actual chars, it's likely from JSON/text
    likely_escaped = (has_escaped_newline and not has_actual_newline) or \
                     (has_escaped_tab and not has_actual_tab)
    
    if not likely_escaped:
        # Already has actual characters, no need to unescape
        return snippet
    
    # Use Python's decode to handle escape sequences
    # This handles \n, \t, \r, \\, etc.
    try:
        # Try unicode-escape first (most common)
        unescaped = snippet.encode().decode('unicode-escape')
        return unescaped
    except (UnicodeDecodeError, AttributeError):
        # If that fails, try manual replacement of common sequences
        return manual_unescape(snippet)


def manual_unescape(snippet: str) -> str:
    """
    Manually replace common escape sequences
    
    Fallback when unicode-escape doesn't work
    
    Args:
        snippet: Code snippet with literal escape sequences
        
    Returns:
        Snippet with escape sequences replaced
    """
    # Replace in order to avoid conflicts
    replacements = [
        ('\\n', '\n'),      # Newline
        ('\\t', '\t'),      # Tab
        ('\\r', '\r'),      # Carriage return
        ('\\"', '"'),       # Double quote
        ("\\'", "'"),       # Single quote
        ('\\\\', '\\'),     # Backslash (must be last)
    ]
    
    result = snippet
    for escaped, actual in replacements:
        result = result.replace(escaped, actual)
    
    return result


def normalize_snippet_from_file(file_path: str) -> str:
    """
    Load a snippet from file and normalize escape sequences
    
    Args:
        file_path: Path to file containing the snippet
        
    Returns:
        Normalized snippet content
        
    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file can't be read
    """
    from pathlib import Path
    
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Snippet file not found: {file_path}")
    
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Unescape if needed
        return unescape_snippet(content)
    
    except Exception as e:
        raise IOError(f"Error reading snippet file {file_path}: {str(e)}")


def is_likely_escaped(text: str) -> bool:
    """
    Check if text likely contains escaped characters
    
    Args:
        text: Text to check
        
    Returns:
        True if text likely has literal escape sequences
    """
    if not text:
        return False
    
    # Check for common patterns
    has_escaped_newline = '\\n' in text
    has_actual_newline = '\n' in text
    has_escaped_tab = '\\t' in text
    has_actual_tab = '\t' in text
    
    # If it has \n but no actual newlines, it's escaped
    if has_escaped_newline and not has_actual_newline:
        return True
    
    # If it has \t but no actual tabs, it's escaped
    if has_escaped_tab and not has_actual_tab:
        return True
    
    return False

