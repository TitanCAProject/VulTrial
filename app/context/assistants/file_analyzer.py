"""File analyzer - analyzes files, functions, and codebase structure"""

import glob
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, Union, List
from ..search_py.search_backend import SearchBackend
from ..search_c.search_backend import CSearchBackend
from ..search_java.search_backend import JavaSearchBackend
from ..search_js.search_backend import JSSearchBackend
from ...models.base import BaseLLMModel
from ...utils.persistent_cache import PersistentCache
from ...prompts import FILE_SUMMARY_PROMPT, README_SUMMARY_PROMPT


class FileAnalyzer:
    """Analyzes files, functions, and codebase structure"""
    
    def __init__(
        self,
        agent_name: str,
        model: BaseLLMModel,
        search_backend: Union[SearchBackend, CSearchBackend, JavaSearchBackend, JSSearchBackend],
        role: str,
        verbose: bool = False,
        logger: Any = None
    ):
        self.agent_name = agent_name
        self.model = model
        self.search_backend = search_backend
        self.role = role
        self.verbose = verbose
        self.logger = logger
        self.persistent_cache = PersistentCache("file_summaries")
    
    def summarize_file(self, file_path: str) -> Optional[str]:
        """Summarize what a file does with persistent caching"""
        try:
            file_path_obj = Path(file_path)
            if not file_path_obj.exists() or not file_path_obj.is_file():
                if self.verbose:
                    print(f"[{self.role}] File not found: {file_path}")
                return None
            
            cached_summary = self.persistent_cache.get(file_path)
            if cached_summary:
                if self.verbose:
                    print(f"[{self.role}] Using persistent cache for {file_path_obj.name}")
                return cached_summary
            
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            if len(content) > 3000:
                content = content[:3000] + "\n... [truncated]"
            
            prompt = f"{FILE_SUMMARY_PROMPT}\n\nFile: {Path(file_path).name}\n\n```\n{content}\n```"
            messages = [{"role": "user", "content": prompt}]
            
            result = self.model.generate_with_metadata(messages, temperature=0.2)
            summary = result.get('content', result.get('response', ''))
            
            if self.logger and result.get('tokens_used'):
                self.logger.log_agent_response(f"{self.agent_name}_assistant_file_summary", summary, result.get('tokens_used'))
            
            self.persistent_cache.set(file_path, summary.strip())
            return summary.strip()
            
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] Error summarizing file: {e}")
            return None
    
    def list_functions_in_file(self, file_path: str) -> Optional[str]:
        """List all functions in a file"""
        try:
            from ...utils.input_handler import InputHandler
            
            content = InputHandler.load_code_file(file_path)
            lines = content.split('\n')
            file_ext = Path(file_path).suffix.lower()
            
            functions = []
            
            if file_ext in ['.py', '.pyx']:
                functions = self._extract_python_functions(lines)
            elif file_ext in ['.c', '.cpp', '.cc', '.h', '.hpp']:
                functions = self._extract_c_cpp_functions(lines)
            elif file_ext == '.java':
                functions = self._extract_java_methods(lines)
            elif file_ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']:
                functions = self._extract_js_functions(lines)
            
            if functions:
                return f"Functions in {Path(file_path).name} (showing first 30):\n" + "\n".join(functions[:30])
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] Error listing functions: {e}")
            return None
    
    def get_file_context(self, file_path: str) -> Optional[str]:
        """Get imports/dependencies of a file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')[:100]
            
            file_ext = Path(file_path).suffix.lower()
            imports = []
            
            if file_ext in ['.py', '.pyx']:
                imports = self._extract_python_imports(lines)
            elif file_ext in ['.c', '.cpp', '.cc', '.h', '.hpp']:
                imports = self._extract_c_includes(lines)
            elif file_ext == '.java':
                imports = self._extract_java_imports(lines)
            elif file_ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']:
                imports = self._extract_js_imports(lines)
            
            if imports:
                return f"Dependencies for {Path(file_path).name}:\n" + "\n".join(imports[:30])
            return None
        
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] Error getting file context: {e}")
            return None
    
    def find_readme_or_docs(self, search_cache: Dict[str, Any]) -> Optional[str]:
        """Find and retrieve README or documentation"""
        cache_key = "readme_content"
        
        if cache_key in search_cache:
            return search_cache[cache_key]
        
        readme_content = None
        
        try:
            if hasattr(self.search_backend, 'project_path'):
                project_path = str(self.search_backend.project_path)
                
                readme_patterns = ['README*', 'readme*', 'README.*', 'readme.*']
                for pattern in readme_patterns:
                    matches = glob.glob(os.path.join(project_path, pattern))
                    if matches:
                        with open(matches[0], 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        
                        if len(content) > 500:
                            prompt = f"{README_SUMMARY_PROMPT}\n\n```\n{content[:2000]}\n```"
                            messages = [{"role": "user", "content": prompt}]
                            try:
                                result = self.model.generate_with_metadata(messages, temperature=0.2)
                                readme_content = result.get('content', result.get('response', '')).strip()
                                
                                if self.logger and result.get('tokens_used'):
                                    self.logger.log_agent_response(f"{self.agent_name}_assistant_readme_summary", readme_content, result.get('tokens_used'))
                            except:
                                readme_content = content[:500]
                        else:
                            readme_content = content
                        break
            
            search_cache[cache_key] = readme_content
            
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] Could not load README: {e}")
        
        return readme_content
    
    def summarize_codebase(self, search_cache: Dict[str, Any]) -> Optional[str]:
        """Get high-level codebase summary"""
        cache_key = "codebase_summary"
        
        if cache_key in search_cache:
            return search_cache[cache_key]
        
        try:
            readme_content = self.find_readme_or_docs(search_cache)
            
            if hasattr(self.search_backend, 'project_path'):
                project_path = str(self.search_backend.project_path)
                
                py_files = len(glob.glob(os.path.join(project_path, '**/*.py'), recursive=True))
                c_files = len(glob.glob(os.path.join(project_path, '**/*.c'), recursive=True))
                cpp_files = len(glob.glob(os.path.join(project_path, '**/*.cpp'), recursive=True))
                h_files = len(glob.glob(os.path.join(project_path, '**/*.h'), recursive=True))
                java_files = len(glob.glob(os.path.join(project_path, '**/*.java'), recursive=True))
                js_files = len(glob.glob(os.path.join(project_path, '**/*.js'), recursive=True))
                ts_files = len(glob.glob(os.path.join(project_path, '**/*.ts'), recursive=True))
                
                summary = f"Codebase: {Path(project_path).name}\n"
                summary += f"Structure: {py_files} Python, {c_files} C, {cpp_files} C++, {h_files} headers, {java_files} Java, {js_files} JS, {ts_files} TS files\n"
                
                if readme_content:
                    summary += f"\nProject Description:\n{readme_content[:800]}"
                
                search_cache[cache_key] = summary
                return summary
        
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] Error summarizing codebase: {e}")
        
        return None
    
    def _extract_python_functions(self, lines: List[str]) -> List[str]:
        """Extract Python function signatures"""
        functions = []
        for i, line in enumerate(lines, 1):
            match = re.match(r'^\s*def\s+(\w+)\s*\(([^)]*)\)', line)
            if match:
                func_name = match.group(1)
                params = match.group(2).strip()
                functions.append(f"  Line {i:4d}: {func_name}({params})")
        return functions
    
    def _extract_c_cpp_functions(self, lines: List[str]) -> List[str]:
        """Extract C/C++ function signatures"""
        functions = []
        for i, line in enumerate(lines, 1):
            match = re.search(r'^\s*(?:static\s+|inline\s+|extern\s+)?(?:\w+\s+)+(\w+)\s*\([^)]*\)\s*\{?', line)
            if match and not line.strip().startswith('//'):
                func_name = match.group(1)
                if func_name not in ['if', 'for', 'while', 'switch']:
                    functions.append(f"  Line {i:4d}: {func_name}()")
        return functions
    
    def _extract_java_methods(self, lines: List[str]) -> List[str]:
        """Extract Java method signatures"""
        functions = []
        for i, line in enumerate(lines, 1):
            match = re.search(r'^\s*(?:public|private|protected)?\s*(?:static)?\s*(?:\w+\s+)+(\w+)\s*\([^)]*\)', line)
            if match and not line.strip().startswith('//'):
                method_name = match.group(1)
                if method_name not in ['class', 'interface']:
                    functions.append(f"  Line {i:4d}: {method_name}()")
        return functions
    
    def _extract_js_functions(self, lines: List[str]) -> List[str]:
        """Extract JavaScript/TypeScript function signatures"""
        functions = []
        for i, line in enumerate(lines, 1):
            match = re.match(r'^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', line)
            if match:
                func_name = match.group(1)
                params = match.group(2).strip()
                functions.append(f"  Line {i:4d}: {func_name}({params})")
                continue
            
            match = re.match(r'^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>', line)
            if match:
                func_name = match.group(1)
                functions.append(f"  Line {i:4d}: {func_name}() [arrow]")
                continue
            
            match = re.match(r'^\s*(?:async\s+)?(\w+)\s*\([^)]*\)\s*\{', line)
            if match and not line.strip().startswith('//'):
                method_name = match.group(1)
                if method_name not in ['if', 'for', 'while', 'switch', 'catch', 'function']:
                    functions.append(f"  Line {i:4d}: {method_name}()")
        return functions
    
    def _extract_python_imports(self, lines: List[str]) -> List[str]:
        """Extract Python imports"""
        imports = []
        for line in lines:
            if line.strip().startswith('import ') or line.strip().startswith('from '):
                imports.append(line.strip())
        return imports
    
    def _extract_c_includes(self, lines: List[str]) -> List[str]:
        """Extract C/C++ includes"""
        imports = []
        for line in lines:
            match = re.match(r'^\s*#include\s*[<"]([^>"]+)[>"]', line)
            if match:
                imports.append(line.strip())
        return imports
    
    def _extract_java_imports(self, lines: List[str]) -> List[str]:
        """Extract Java imports"""
        imports = []
        for line in lines:
            if line.strip().startswith('import ') or line.strip().startswith('package '):
                imports.append(line.strip())
        return imports
    
    def _extract_js_imports(self, lines: List[str]) -> List[str]:
        """Extract JavaScript/TypeScript imports"""
        imports = []
        for line in lines:
            if line.strip().startswith('import ') or 'require(' in line:
                imports.append(line.strip())
        return imports

