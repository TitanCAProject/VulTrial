"""
Snippet Matcher - Smart code snippet matching in files

Uses a two-strategy approach:
1. Function extraction (if snippet looks like a function)
2. Multi-level fuzzy matching (for code blocks)
"""

import re
from typing import Optional, Tuple

from .code_loader import CodeLoader
from .function_extractor import FunctionExtractor


class SnippetMatcher:
    """Matches code snippets in files with intelligent strategies"""
    
    @staticmethod
    def match_code_snippet_in_file(
        file_path: str,
        code_snippet: str
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Match a code snippet in a file and return its location
        
        Strategy:
        1. If snippet looks like a function, try function extraction first (more robust)
        2. Fall back to fuzzy snippet matching (6 levels of matching)
        
        Args:
            file_path: Path to the code file
            code_snippet: Code snippet to find (can have different whitespace)
            
        Returns:
            Tuple of (matched_code, start_line, end_line) or (None, None, None) if not found
        """
        # STRATEGY 1: Try function extraction if snippet looks like a function
        function_name = FunctionExtractor.extract_function_name_from_snippet(code_snippet)
        if function_name:
            try:
                func_code, start_line, end_line = FunctionExtractor.extract_function_from_file(
                    file_path, function_name
                )
                if func_code:
                    # Success! Return the matched function
                    return func_code, start_line, end_line
            except Exception:
                # Function extraction failed, continue to snippet matching
                pass
        
        # STRATEGY 2: Fall back to multi-level fuzzy snippet matching
        return SnippetMatcher._fuzzy_match_snippet(file_path, code_snippet)
    
    @staticmethod
    def _fuzzy_match_snippet(
        file_path: str,
        code_snippet: str
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        Multi-level fuzzy matching for code snippets
        
        Tries 6 levels of matching (from strict to fuzzy):
        1. Exact normalized match
        2. Line-by-line with whitespace tolerance
        3. Partial line matching (truncated first/last lines)
        4. High-similarity matching (≥95%)
        5. Non-trivial line matching (ignores blank lines)
        6. Super fuzzy (all whitespace removed)
        
        Args:
            file_path: Path to the code file
            code_snippet: Code snippet to find
            
        Returns:
            Tuple of (matched_code, start_line, end_line) or (None, None, None)
        """
        content = CodeLoader.load_code_file(file_path)
        
        # Normalize both for comparison
        normalized_content = CodeLoader.normalize_code_for_matching(content)
        normalized_snippet = CodeLoader.normalize_code_for_matching(code_snippet)
        
        # Split into lines
        content_lines = normalized_content.split('\n')
        snippet_lines = normalized_snippet.split('\n')
        
        # Remove empty lines from start and end of snippet
        while snippet_lines and not snippet_lines[0].strip():
            snippet_lines.pop(0)
        while snippet_lines and not snippet_lines[-1].strip():
            snippet_lines.pop()
        
        if not snippet_lines:
            return None, None, None
        
        snippet_len = len(snippet_lines)
        snippet_text = '\n'.join(snippet_lines)
        
        # LEVEL 1: Exact normalized match
        result = SnippetMatcher._exact_match(content, content_lines, snippet_text, snippet_lines)
        if result:
            return result
        
        # LEVEL 2: Line-by-line with whitespace tolerance
        result = SnippetMatcher._line_by_line_match(content, content_lines, snippet_lines, snippet_len)
        if result:
            return result
        
        # LEVEL 3: Partial line matching (truncated first/last lines)
        result = SnippetMatcher._partial_line_match(content, content_lines, snippet_lines, snippet_len)
        if result:
            return result
        
        # LEVEL 4: High-similarity matching (≥95%)
        result = SnippetMatcher._similarity_match(content, content_lines, snippet_lines, snippet_len)
        if result:
            return result
        
        # LEVEL 5: Non-trivial line matching (ignores blank lines)
        result = SnippetMatcher._non_trivial_match(content, content_lines, snippet_lines, snippet_len)
        if result:
            return result
        
        # LEVEL 6: Super fuzzy (all whitespace removed)
        result = SnippetMatcher._super_fuzzy_match(content, content_lines, snippet_text, snippet_len)
        if result:
            return result
        
        return None, None, None
    
    # ==================== Matching Levels ====================
    
    @staticmethod
    def _exact_match(content, content_lines, snippet_text, snippet_lines):
        """Level 1: Exact normalized match"""
        normalized_content = '\n'.join(content_lines)
        if snippet_text in normalized_content:
            start_idx = normalized_content.index(snippet_text)
            lines_before = normalized_content[:start_idx].count('\n')
            start_line = lines_before + 1
            end_line = start_line + len(snippet_lines)
            
            original_lines = content.split('\n')
            matched_code = '\n'.join(original_lines[lines_before:lines_before + len(snippet_lines)])
            
            return matched_code, start_line, end_line
        return None
    
    @staticmethod
    def _line_by_line_match(content, content_lines, snippet_lines, snippet_len):
        """Level 2: Line-by-line with whitespace tolerance"""
        for i in range(len(content_lines) - snippet_len + 1):
            window = content_lines[i:i + snippet_len]
            
            match = True
            for j, snippet_line in enumerate(snippet_lines):
                if snippet_line.strip() != window[j].strip():
                    match = False
                    break
            
            if match:
                start_line = i + 1
                end_line = i + snippet_len + 1
                original_lines = content.split('\n')
                matched_code = '\n'.join(original_lines[i:i + snippet_len])
                return matched_code, start_line, end_line
        return None
    
    @staticmethod
    def _partial_line_match(content, content_lines, snippet_lines, snippet_len):
        """Level 3: Partial line matching (truncated first/last lines)"""
        for i in range(len(content_lines) - snippet_len + 1):
            window = content_lines[i:i + snippet_len]
            
            match = True
            for j, snippet_line in enumerate(snippet_lines):
                snippet_stripped = snippet_line.strip()
                window_stripped = window[j].strip()
                
                # For first and last lines, allow partial matching
                if j == 0 or j == len(snippet_lines) - 1:
                    if not (window_stripped.startswith(snippet_stripped) or 
                            snippet_stripped.startswith(window_stripped) or
                            snippet_stripped == window_stripped):
                        match = False
                        break
                else:
                    if snippet_stripped != window_stripped:
                        match = False
                        break
            
            if match:
                start_line = i + 1
                end_line = i + snippet_len + 1
                original_lines = content.split('\n')
                matched_code = '\n'.join(original_lines[i:i + snippet_len])
                return matched_code, start_line, end_line
        return None
    
    @staticmethod
    def _similarity_match(content, content_lines, snippet_lines, snippet_len):
        """Level 4: High-similarity matching (≥95%)"""
        if snippet_len < 20:  # Only for substantial code blocks
            return None
        
        for i in range(len(content_lines) - snippet_len + 1):
            window = content_lines[i:i + snippet_len]
            
            matching_lines = sum(1 for j in range(snippet_len) 
                               if snippet_lines[j].strip() == window[j].strip())
            
            similarity = matching_lines / snippet_len
            
            if similarity >= 0.95:
                start_line = i + 1
                end_line = i + snippet_len + 1
                original_lines = content.split('\n')
                matched_code = '\n'.join(original_lines[i:i + snippet_len])
                return matched_code, start_line, end_line
        return None
    
    @staticmethod
    def _non_trivial_match(content, content_lines, snippet_lines, snippet_len):
        """Level 5: Non-trivial line matching (ignores blank lines and comments)"""
        def get_non_trivial_lines(lines):
            return [line for line in lines 
                   if line.strip() and not line.strip().startswith('//') 
                   and not line.strip().startswith('/*') and not line.strip().startswith('*')]
        
        snippet_non_trivial = get_non_trivial_lines(snippet_lines)
        
        if len(snippet_non_trivial) < 5:  # Only for substantial snippets
            return None
        
        for i in range(len(content_lines)):
            for length_delta in range(-10, 11):
                window_len = snippet_len + length_delta
                if window_len < len(snippet_non_trivial) or i + window_len > len(content_lines):
                    continue
                
                window = content_lines[i:i + window_len]
                window_non_trivial = get_non_trivial_lines(window)
                
                if len(window_non_trivial) == len(snippet_non_trivial):
                    if all(snippet_non_trivial[k].strip() == window_non_trivial[k].strip() 
                          for k in range(len(snippet_non_trivial))):
                        start_line = i + 1
                        end_line = i + window_len + 1
                        original_lines = content.split('\n')
                        matched_code = '\n'.join(original_lines[i:i + window_len])
                        return matched_code, start_line, end_line
        return None
    
    @staticmethod
    def _super_fuzzy_match(content, content_lines, snippet_text, snippet_len):
        """Level 6: Super fuzzy (all whitespace removed)"""
        def remove_all_whitespace(text):
            return re.sub(r'\s+', '', text)
        
        snippet_no_ws = remove_all_whitespace(snippet_text)
        
        if len(snippet_no_ws) <= 100:  # Only for reasonably sized snippets
            return None
        
        for i in range(len(content_lines)):
            for length in range(max(1, snippet_len - 20), snippet_len + 21):
                if i + length > len(content_lines):
                    continue
                
                window = content_lines[i:i + length]
                window_text = '\n'.join(window)
                window_no_ws = remove_all_whitespace(window_text)
                
                # Exact match after removing whitespace
                if snippet_no_ws == window_no_ws:
                    start_line = i + 1
                    end_line = i + length + 1
                    original_lines = content.split('\n')
                    matched_code = '\n'.join(original_lines[i:i + length])
                    return matched_code, start_line, end_line
                
                # Partial match (for very long snippets)
                if len(snippet_no_ws) > 200 and len(window_no_ws) > len(snippet_no_ws):
                    if window_no_ws.startswith(snippet_no_ws[:len(snippet_no_ws)-10]):
                        similarity = len(snippet_no_ws) / len(window_no_ws)
                        if similarity > 0.85:
                            start_line = i + 1
                            end_line = i + length + 1
                            original_lines = content.split('\n')
                            matched_code = '\n'.join(original_lines[i:i + length])
                            return matched_code, start_line, end_line
        return None

