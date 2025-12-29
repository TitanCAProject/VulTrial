"""Evidence gatherer - executes searches and collects evidence"""

import json
import re
from typing import Dict, Any, List, Optional, Union
from ..search_py.search_backend import SearchBackend
from ..search_c.search_backend import CSearchBackend
from ..search_java.search_backend import JavaSearchBackend
from ..search_js.search_backend import JSSearchBackend
from ...models.base import BaseLLMModel


class EvidenceGatherer:
    """Executes searches and collects evidence from codebase"""
    
    def __init__(
        self,
        agent_name: str,
        model: BaseLLMModel,
        search_backend: Union[SearchBackend, CSearchBackend, JavaSearchBackend, JSSearchBackend],
        assistant_prompt: str,
        role: str,
        verbose: bool = False,
        logger: Any = None,
        file_analyzer = None,
        knowledge_retriever = None
    ):
        self.agent_name = agent_name
        self.model = model
        self.search_backend = search_backend
        self.assistant_prompt = assistant_prompt
        self.role = role
        self.verbose = verbose
        self.logger = logger
        self.file_analyzer = file_analyzer
        self.knowledge_retriever = knowledge_retriever
    
    def determine_searches(
        self,
        agent_argument: str,
        debate_context: str,
        sr_evidence: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Determine if search is needed and what to search for"""
        
        # Extract fallback searches
        fallback_searches = self._extract_names_from_text(agent_argument)
        
        prompt = f"{self.assistant_prompt}\n\n"
        
        # If SR evidence is provided (for CA Assistant), show what SR already found
        # Support both 'actions' and 'search_actions' for backwards compatibility
        sr_actions = sr_evidence.get('actions', sr_evidence.get('search_actions', [])) if sr_evidence else []
        if sr_actions:
            prompt += "=== SR Assistant Already Searched (DO NOT REPEAT) ===\n"
            for action in sr_actions:
                tool_name = action.get('tool_name', action.get('search_type', 'unknown'))
                params = action.get('parameters', {})
                params_str = ', '.join(f"{k}={v}" for k, v in params.items())
                prompt += f"  ✗ {tool_name}({params_str})\n"
            prompt += "=== Focus on DIFFERENT evidence CA needs ===\n\n"
        
        prompt += f"Agent's Current Argument:\n{agent_argument[:1000]}\n\n"
        prompt += f"Recent Debate:\n{debate_context[-1000:] if len(debate_context) > 1000 else debate_context}\n\n"
        prompt += f"Decide: What DIFFERENT evidence do you need? Extract 2-3 specific names/actions."
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = self.model.generate_with_metadata(messages, temperature=0.2)
            response = result.get('content', result.get('response', ''))
            
            if self.logger and result.get('tokens_used'):
                self.logger.log_agent_response(f"{self.agent_name}_assistant", response, result.get('tokens_used'))
            
            response_clean = response.strip()
            if '```json' in response_clean:
                response_clean = response_clean.split('```json')[1].split('```')[0]
            elif '```' in response_clean:
                response_clean = response_clean.split('```')[1].split('```')[0]
            
            search_data = json.loads(response_clean)
            
            # Support both old and new format
            actions = search_data.get('actions', search_data.get('search_actions', []))
            reasoning = search_data.get('reasoning', '')
            
            actions = actions[:3]
            actions = self._validate_actions(actions)
            
            return {
                'needs_search': len(actions) > 0,  # Derived from whether there are actions
                'reasoning': reasoning,
                'actions': actions
            }
            
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] LLM failed, using fallback: {e}")
            
            return {
                'needs_search': len(fallback_searches) > 0,
                'reasoning': 'Fallback: extracted names from text',
                'actions': fallback_searches
            }
    
    def execute_searches(self, actions: List[Dict[str, Any]], search_cache: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute all search actions with caching"""
        evidence = []
        
        for action in actions:
            # Support both new 'tool_name' and old 'search_type' format
            tool_name = action.get('tool_name', action.get('search_type'))
            parameters = action.get('parameters', {})
            reason = action.get('reason', 'No reason provided')
            
            cache_key = f"{tool_name}_{json.dumps(parameters, sort_keys=True)}"
            
            if cache_key in search_cache:
                if self.logger:
                    self.logger.log_cache_hit(cache_key)
                
                results = search_cache[cache_key]
                
                # Show in UI even when using cache (user needs to see what CA retrieved)
                if self.logger:
                    self.logger.log_tool_use(tool_name, parameters, len(results))
                
                if self.verbose:
                    params_str = ', '.join(f"{k}={v}" for k, v in parameters.items())
                    print(f"[{self.role}] {tool_name}({params_str}) - Using cached result")
                
                for result in results:
                    result_copy = result.copy()
                    result_copy['search_reason'] = reason
                    evidence.append(result_copy)
                continue
            
            if self.logger:
                self.logger.log_cache_miss(cache_key)
            
            if self.verbose:
                params_str = ', '.join(f"{k}={v}" for k, v in parameters.items())
                print(f"[{self.role}] {tool_name}({params_str})")
            
            try:
                results = self._execute_single_search(tool_name, parameters)
                search_cache[cache_key] = results
                
                if self.logger:
                    if results:
                        self.logger.log_tool_results(tool_name, results)
                    # Always show tool use with results on screen
                    self.logger.log_tool_use(tool_name, parameters, len(results))
                
                for result in results:
                    result['search_reason'] = reason
                    evidence.append(result)
                
                if self.verbose:
                    if results:
                        print(f"[{self.role}]   ✓ Found {len(results)} results (cached for reuse)")
                    else:
                        print(f"[{self.role}]   ✗ No results")
                
            except Exception as e:
                if self.verbose:
                    print(f"[{self.role}]   ✗ Error: {e}")
                continue
        
        return evidence
    
    def _execute_single_search(self, tool_name: str, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a single search/tool"""
        if tool_name == 'search_function':
            func_name = parameters.get('function_name')
            search_results = self.search_backend.search_function(func_name)
            return [res.to_dict() for res in search_results]
            
        elif tool_name == 'search_class':
            class_name = parameters.get('class_name')
            _, search_results, success = self.search_backend.search_class(class_name)
            return [res.to_dict() for res in search_results] if success else []
            
        elif tool_name == 'search_method_in_class':
            method_name = parameters.get('method_name')
            class_name = parameters.get('class_name')
            _, search_results, success = self.search_backend.search_method_in_class(method_name, class_name)
            return [res.to_dict() for res in search_results] if success else []
            
        elif tool_name == 'search_code':
            code_str = parameters.get('code_pattern')
            _, search_results, success = self.search_backend.search_code(code_str)
            return [res.to_dict() for res in search_results] if success else []
            
        elif tool_name == 'find_callers':
            func_name = parameters.get('function_name')
            search_results = self.search_backend.find_callers(func_name)
            return [res.to_dict() for res in search_results]
            
        elif tool_name == 'find_callees':
            func_name = parameters.get('function_name')
            if hasattr(self.search_backend, 'find_callees'):
                search_results = self.search_backend.find_callees(func_name)
                return [res.to_dict() for res in search_results]
            return []
            
        elif tool_name == 'get_code_around_line':
            file_name = parameters.get('file_name')
            line_no = parameters.get('line_number')
            window_size = parameters.get('window_size', 10)
            _, search_results, success = self.search_backend.get_code_around_line(file_name, line_no, window_size)
            return [res.to_dict() for res in search_results] if success else []
        
        elif tool_name == 'find_call_chain':
            func_name = parameters.get('function_name')
            depth = parameters.get('depth', 3)
            direction = parameters.get('direction', 'forward')
            try:
                from .result_formatter import ResultFormatter
                chain_results = self.search_backend.find_call_chain(func_name, depth, direction)
                return [ResultFormatter.format_call_chain(cr) for cr in chain_results]
            except AttributeError:
                return []
        
        elif tool_name == 'find_taint_flow':
            source = parameters.get('source_pattern')
            sink = parameters.get('sink_function')
            max_depth = parameters.get('max_depth', 3)
            try:
                from .result_formatter import ResultFormatter
                taint_paths = self.search_backend.find_taint_flow(source, sink, max_depth)
                return [ResultFormatter.format_taint_path(tp) for tp in taint_paths]
            except AttributeError:
                return []
        
        elif tool_name == 'track_variable':
            func_name = parameters.get('function_name')
            var_name = parameters.get('variable_name')
            try:
                from .result_formatter import ResultFormatter
                var_flow = self.search_backend.track_variable(func_name, var_name)
                if var_flow:
                    return [ResultFormatter.format_variable_flow(var_flow)]
                return []
            except AttributeError:
                return []
        
        # Context tools (require file_analyzer)
        elif tool_name == 'summarize_file' and self.file_analyzer:
            file_path = parameters.get('file_path')
            summary = self.file_analyzer.summarize_file(file_path)
            if summary:
                return [{
                    'type': 'file_summary',
                    'file_path': file_path,
                    'code': summary,
                    'context': summary
                }]
            return []
        
        elif tool_name == 'list_functions' and self.file_analyzer:
            file_path = parameters.get('file_path')
            func_list = self.file_analyzer.list_functions_in_file(file_path)
            if func_list:
                return [{
                    'type': 'function_list',
                    'file_path': file_path,
                    'code': func_list,
                    'context': func_list
                }]
            return []
        
        elif tool_name == 'find_readme' and self.file_analyzer:
            readme_content = self.file_analyzer.find_readme_or_docs({})
            if readme_content:
                return [{
                    'type': 'readme',
                    'file_path': 'README',
                    'code': readme_content,
                    'context': readme_content
                }]
            return []
        
        elif tool_name == 'summarize_codebase' and self.file_analyzer:
            summary = self.file_analyzer.summarize_codebase({})
            if summary:
                return [{
                    'type': 'codebase_summary',
                    'file_path': 'codebase',
                    'code': summary,
                    'context': summary
                }]
            return []
        
        elif tool_name == 'get_file_context' and self.file_analyzer:
            file_path = parameters.get('file_path')
            context = self.file_analyzer.get_file_context(file_path)
            if context:
                return [{
                    'type': 'file_context',
                    'file_path': file_path,
                    'code': context,
                    'context': context
                }]
            return []
        
        # CWE Knowledge retrieval
        elif tool_name == 'retrieve_cwe' and self.knowledge_retriever:
            keywords = parameters.get('keywords', [])
            if not keywords:
                # Fallback to vulnerability_type parameter
                vuln_type = parameters.get('vulnerability_type', '')
                if vuln_type:
                    # Split into keywords (e.g., "SQL Injection" → ["sql", "injection"])
                    keywords = vuln_type.lower().split()
            
            if keywords:
                cwes = self.knowledge_retriever.search_cwe_by_keywords(keywords, max_results=2)
                if cwes:
                    formatted = self.knowledge_retriever.format_cwe_for_agent(cwes)
                    return [{
                        'type': 'cwe_knowledge',
                        'file_path': 'CWE Database',
                        'code': formatted,
                        'context': f"CWE knowledge for: {', '.join(keywords)}"
                    }]
            return []
        
        return []
    
    def _extract_names_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract function/class names from text as fallback"""
        searches = []
        
        func_pattern = r'\b([a-z_][a-z0-9_]{2,})\s*\('
        functions = re.findall(func_pattern, text, re.IGNORECASE)
        
        class_pattern = r'\b([A-Z][a-zA-Z0-9]{2,})\b'
        classes = re.findall(class_pattern, text)
        
        seen = set()
        for func in functions[:3]:
            if func not in seen and func not in ['json', 'str', 'int', 'list', 'dict']:
                searches.append({
                    'tool_name': 'search_function',
                    'parameters': {'function_name': func},
                    'reason': f'Function mentioned in argument'
                })
                seen.add(func)
        
        for cls in classes[:2]:
            if cls not in seen and cls not in ['JSON', 'SQL', 'HTTP', 'API', 'None', 'True', 'False']:
                searches.append({
                    'tool_name': 'search_class',
                    'parameters': {'class_name': cls},
                    'reason': f'Class mentioned in argument'
                })
                seen.add(cls)
        
        return searches[:3]
    
    def _validate_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validate and clean actions"""
        valid_actions = []
        
        for action in actions:
            # Support both new 'tool_name' and old 'search_type' format
            tool_name = action.get('tool_name', action.get('search_type', ''))
            parameters = action.get('parameters', {})
            
            if not tool_name or not parameters:
                continue
            
            # Normalize to new format
            if 'search_type' in action and 'tool_name' not in action:
                action['tool_name'] = action['search_type']
            
            if tool_name == 'search_function':
                func_name = parameters.get('function_name', '')
                if func_name and func_name.lower() not in ['none', 'true', 'false', 'and', 'or', 'not']:
                    valid_actions.append(action)
            
            elif tool_name == 'search_class':
                class_name = parameters.get('class_name', '')
                if class_name and class_name not in ['JSON', 'SQL', 'HTTP']:
                    valid_actions.append(action)
            
            elif tool_name == 'search_code':
                pattern = parameters.get('code_pattern', '')
                if pattern:
                    pattern = pattern.replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\')
                    parameters['code_pattern'] = pattern
                    valid_actions.append(action)
            
            else:
                valid_actions.append(action)
        
        return valid_actions

