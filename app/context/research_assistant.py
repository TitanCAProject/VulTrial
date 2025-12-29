"""Research assistants for agents - each agent has their own assistant (Refactored)"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from ..models.base import BaseLLMModel
from ..prompts import (
    ANALYSIS_MODE_DETAILED,
    ANALYSIS_MODE_CONSENSUS,
    SECURITY_RESEARCHER_ASSISTANT_PROMPT,
    CODE_AUTHOR_ASSISTANT_PROMPT,
    SECURITY_RESEARCHER_ASSISTANT_PROMPT_CONSENSUS,
    CODE_AUTHOR_ASSISTANT_PROMPT_CONSENSUS,
    CONTEXT_SUMMARIZER_PROMPT,
)
from .search_py.search_backend import SearchBackend
from .search_c.search_backend import CSearchBackend
from .search_java.search_backend import JavaSearchBackend
from .search_js.search_backend import JSSearchBackend
from ..utils.context_compressor import ContextCompressor

# Import refactored modules
from .assistants.evidence_gatherer import EvidenceGatherer
from .assistants.file_analyzer import FileAnalyzer
from .assistants.result_formatter import ResultFormatter


class ResearchAssistant:
    """Research assistant that helps an agent find evidence in the codebase"""
    
    def __init__(
        self,
        agent_name: str,
        model: BaseLLMModel,
        search_backend: Union[SearchBackend, CSearchBackend, JavaSearchBackend, JSSearchBackend],
        verbose: bool = False,
        logger: Any = None,
        analysis_mode: str = ANALYSIS_MODE_DETAILED,
        max_evidence_items: int = None,
        max_evidence_tokens_per_item: int = None,
        max_evidence_lines_per_item: int = None,
        evidence_total_token_budget: int = None,
        enable_knowledge_base: bool = True
    ):
        """Initialize research assistant"""
        try:
            from ..ui.constants import UIConstants
        except ImportError:
            class UIConstants:
                MAX_EVIDENCE_ITEMS = 5
                MAX_EVIDENCE_TOKENS_PER_ITEM = 1000
                MAX_EVIDENCE_LINES_PER_ITEM = 100
                EVIDENCE_TOTAL_TOKEN_BUDGET = 4000
        
        self.agent_name = agent_name
        self.model = model
        self.search_backend = search_backend
        self.verbose = verbose
        self._logger = logger
        self.analysis_mode = analysis_mode
        
        # Evidence configuration
        self.max_evidence_items = max_evidence_items if max_evidence_items is not None else UIConstants.MAX_EVIDENCE_ITEMS
        self.max_evidence_tokens_per_item = max_evidence_tokens_per_item if max_evidence_tokens_per_item is not None else UIConstants.MAX_EVIDENCE_TOKENS_PER_ITEM
        self.max_evidence_lines_per_item = max_evidence_lines_per_item if max_evidence_lines_per_item is not None else UIConstants.MAX_EVIDENCE_LINES_PER_ITEM
        self.evidence_total_token_budget = evidence_total_token_budget if evidence_total_token_budget is not None else UIConstants.EVIDENCE_TOTAL_TOKEN_BUDGET
        
        # Detect backend type
        self.is_c_backend = isinstance(search_backend, CSearchBackend)
        self.is_java_backend = isinstance(search_backend, JavaSearchBackend)
        self.is_js_backend = isinstance(search_backend, JSSearchBackend)
        
        if self.is_c_backend:
            self.backend_type = "C/C++"
        elif self.is_java_backend:
            self.backend_type = "Java"
        elif self.is_js_backend:
            self.backend_type = "JavaScript/TypeScript"
        else:
            self.backend_type = "Python"
        
        # Select appropriate prompt
        if agent_name == "security_researcher":
            if analysis_mode == ANALYSIS_MODE_CONSENSUS:
                self.assistant_prompt = SECURITY_RESEARCHER_ASSISTANT_PROMPT_CONSENSUS
            else:
                self.assistant_prompt = SECURITY_RESEARCHER_ASSISTANT_PROMPT
            self.role = "Security Researcher's Assistant"
        elif agent_name == "code_author":
            if analysis_mode == ANALYSIS_MODE_CONSENSUS:
                self.assistant_prompt = CODE_AUTHOR_ASSISTANT_PROMPT_CONSENSUS
            else:
                self.assistant_prompt = CODE_AUTHOR_ASSISTANT_PROMPT
            self.role = "Code Author's Assistant"
        else:
            raise ValueError(f"Unknown agent name: {agent_name}")
        
        # Initialize knowledge retriever if enabled
        self.knowledge_retriever = None
        if enable_knowledge_base:
            try:
                from ..knowledge.knowledge_retriever import KnowledgeRetriever
                self.knowledge_retriever = KnowledgeRetriever()
            except Exception as e:
                if verbose:
                    print(f"[{self.role}] Knowledge base not available: {e}")
        
        # Initialize sub-components
        self.file_analyzer = FileAnalyzer(
            agent_name=agent_name,
            model=model,
            search_backend=search_backend,
            role=self.role,
            verbose=verbose,
            logger=logger
        )
        
        self.evidence_gatherer = EvidenceGatherer(
            agent_name=agent_name,
            model=model,
            search_backend=search_backend,
            assistant_prompt=self.assistant_prompt,
            role=self.role,
            verbose=verbose,
            logger=self._logger,
            file_analyzer=self.file_analyzer,
            knowledge_retriever=self.knowledge_retriever
        )
    
    @property
    def logger(self):
        """Get logger"""
        return self._logger
    
    @logger.setter
    def logger(self, logger):
        """Set logger on this component and all sub-components"""
        self._logger = logger
        # Update logger on sub-components
        if hasattr(self, 'evidence_gatherer'):
            self.evidence_gatherer.logger = logger
        if hasattr(self, 'file_analyzer'):
            self.file_analyzer.logger = logger
    
    def gather_evidence(
        self,
        agent_argument: str,
        debate_context: str,
        search_cache: Optional[Dict[str, Any]] = None,
        sr_evidence: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Gather evidence from codebase to support agent's argument"""
        # Show via logger (always visible) OR verbose mode
        if self.logger:
            self.logger.log_summary(f"{self.role}: Analyzing evidence needs")
        
        if self.verbose:
            print(f"\n{'~'*60}")
            print(f"{self.role}: Analyzing if evidence search is needed")
            print(f"{'~'*60}")
        
        # Determine if search is needed (pass SR evidence if this is CA Assistant)
        search_decision = self.evidence_gatherer.determine_searches(agent_argument, debate_context, sr_evidence)
        
        # Support both old and new format
        actions = search_decision.get('actions', search_decision.get('search_actions', []))
        reasoning = search_decision.get('reasoning', '')
        needs_search = search_decision.get('needs_search', len(actions) > 0)
        
        if self.verbose:
            print(f"[{self.role}] Needs search: {needs_search}")
            print(f"[{self.role}] Reasoning: {reasoning}")
            print(f"[{self.role}] Actions: {actions}")
        
        if not needs_search or not actions:
            return {
                "evidence": [],
                "summary": f"No evidence gathering needed. {reasoning}",
                "key_findings": [],
                "needs_search": False,
                "query": "N/A (no actions performed)",
                "actions": []  # No actions were taken
            }
        
        # Execute searches/actions
        if search_cache is None:
            search_cache = {}
        
        evidence = self.evidence_gatherer.execute_searches(actions, search_cache)
        
        query_str = "; ".join([f"{action.get('tool_name', action.get('search_type', 'tool'))}({', '.join(f'{k}={v}' for k,v in action.get('parameters', {}).items())})" for action in actions])
        
        if not evidence:
            return {
                "evidence": [],
                "summary": f"Searched but found no evidence. {reasoning}",
                "key_findings": [],
                "needs_search": True,
                "query": query_str,
                "actions": actions  # Store the actions that were taken
            }
        
        # Compress evidence
        compressed_evidence = ContextCompressor.compress_evidence(
            evidence,
            max_items=self.max_evidence_items,
            max_tokens_per_item=self.max_evidence_tokens_per_item,
            max_lines_per_item=self.max_evidence_lines_per_item
        )
        
        if self.verbose and len(evidence) > len(compressed_evidence):
            print(f"[{self.role}] Compressed evidence: {len(evidence)} → {len(compressed_evidence)} items")
        
        if self.verbose:
            summarization_count = sum(1 for item in compressed_evidence if item.get('needs_summarization'))
            if summarization_count > 0:
                print(f"[{self.role}] {summarization_count} evidence items marked for truncation")
        
        # Summarize findings
        summary_result = self._summarize_for_agent(compressed_evidence, agent_argument, debate_context)
        summary_result['needs_search'] = True
        summary_result['query'] = query_str
        summary_result['actions'] = actions  # Store the actions that were taken
        
        return summary_result
    
    def prepare_initial_context(
        self,
        target_code: str,
        input_metadata: Dict[str, Any],
        search_cache: Optional[Dict[str, Any]] = None
    ) -> str:
        """Prepare initial context summary before debate"""
        if search_cache is None:
            search_cache = {}
        
        context_parts = []
        
        # File summary
        file_path = input_metadata.get('file_path')
        if file_path:
            file_summary = self._get_or_create_file_summary(file_path, search_cache)
            if file_summary:
                context_parts.append(f"[FILE CONTEXT - {Path(file_path).name}]:\n{file_summary}\n")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def _get_or_create_file_summary(self, file_path: str, search_cache: Dict[str, Any]) -> Optional[str]:
        """Get file summary from cache or create it"""
        cache_key = f"file_summary_{file_path}"
        
        if cache_key in search_cache:
            if self.verbose:
                print(f"[{self.role}] Using cached file summary for {Path(file_path).name}")
            return search_cache[cache_key]
        
        if self.verbose:
            print(f"[{self.role}] Generating file summary for {Path(file_path).name}...")
        
        summary = self.file_analyzer.summarize_file(file_path)
        search_cache[cache_key] = summary
        return summary
    
    def _summarize_for_agent(
        self,
        evidence: List[Dict[str, Any]],
        agent_argument: str,
        debate_context: str
    ) -> Dict[str, Any]:
        """Summarize evidence for the agent"""
        
        if not evidence:
            return {
                "evidence": [],
                "summary": "No evidence found in codebase.",
                "key_findings": []
            }
        
        # Calculate total size
        total_lines = sum(
            evidence_item.get('code', evidence_item.get('context', '')).count('\n') + 1
            for evidence_item in evidence
        )
        
        all_evidence_text = "\n\n".join([
            item.get('code', item.get('context', '')) for item in evidence
        ])
        estimated_total_tokens = ContextCompressor.estimate_tokens(all_evidence_text)
        
        has_extreme_items = any(item.get('needs_summarization', False) for item in evidence)
        
        # Return directly if fits in budget
        if estimated_total_tokens <= self.evidence_total_token_budget and not has_extreme_items:
            if self.verbose:
                print(f"[{self.role}] Evidence fits in budget ({estimated_total_tokens}/{self.evidence_total_token_budget} tokens) - returning directly")
            
            summary_parts = [f"Found {len(evidence)} pieces of evidence ({total_lines} lines, ~{estimated_total_tokens} tokens):\n"]
            key_findings = []
            
            code_language = ResultFormatter.get_code_language(self.backend_type)
            
            for i, item in enumerate(evidence, 1):
                summary_parts.append(f"\n--- Evidence {i} ---")
                summary_parts.append(f"Type: {item.get('type', 'unknown')}")
                summary_parts.append(f"File: {item.get('file_path', 'unknown')}")
                summary_parts.append(f"Reason: {item.get('search_reason', 'N/A')}")
                summary_parts.append(f"Code:\n```{code_language}\n{item.get('code', item.get('context', ''))}\n```")
                
                key_findings.append({
                    "type": item.get('type'),
                    "file": item.get('file_path'),
                    "reason": item.get('search_reason')
                })
            
            return {
                "evidence": evidence,
                "summary": "\n".join(summary_parts),
                "key_findings": key_findings
            }
        
        # Evidence exceeds budget - use LLM to summarize
        if self.verbose:
            print(f"[{self.role}] Evidence exceeds budget ({estimated_total_tokens}/{self.evidence_total_token_budget} tokens) - using LLM summarization")
        
        prompt = f"{CONTEXT_SUMMARIZER_PROMPT}\n\n"
        prompt += f"Agent Role: {self.agent_name}\n"
        prompt += f"Agent's Argument:\n{agent_argument[:500]}...\n\n"
        prompt += f"Retrieved Evidence ({len(evidence)} items):\n\n"
        
        for i, item in enumerate(evidence, 1):
            prompt += f"Evidence {i}:\n"
            prompt += f"Type: {item.get('type')}\n"
            prompt += f"File: {item.get('file_path')}\n"
            prompt += f"Reason searched: {item.get('search_reason')}\n"
            
            code_full = item.get('code', item.get('context', ''))
            if item.get('needs_summarization'):
                code_snippet = ContextCompressor.truncate_code(code_full, max_lines=self.max_evidence_lines_per_item)
                prompt += f"Code (truncated from {item.get('original_size', len(code_full))} chars to ~{self.max_evidence_lines_per_item} lines):\n```\n{code_snippet}\n```\n\n"
            else:
                char_limit = self.max_evidence_tokens_per_item * 4
                code_snippet = code_full[:char_limit] if len(code_full) > char_limit else code_full
                if len(code_full) > char_limit:
                    prompt += f"Code:\n```\n{code_snippet}...\n```\n\n"
                else:
                    prompt += f"Code:\n```\n{code_snippet}\n```\n\n"
        
        messages = [{"role": "user", "content": prompt}]
        
        try:
            result = self.model.generate_with_metadata(messages, temperature=0.3)
            response = result.get('content', result.get('response', ''))
            
            if self.logger and result.get('tokens_used'):
                self.logger.log_agent_response(f"{self.agent_name}_assistant_summarize", response, result.get('tokens_used'))
            
            response_clean = response.strip()
            if '```json' in response_clean:
                response_clean = response_clean.split('```json')[1].split('```')[0]
            elif '```' in response_clean:
                response_clean = response_clean.split('```')[1].split('```')[0]
            
            summary_data = json.loads(response_clean)
            
            return {
                "evidence": evidence,
                "summary": summary_data.get('summary', response),
                "key_findings": summary_data.get('key_findings', []),
                "verdict": summary_data.get('verdict', 'neutral'),
                "code_snippets": summary_data.get('code_snippets', [])
            }
            
        except Exception as e:
            if self.verbose:
                print(f"[{self.role}] Summarization error: {e}")
            
            return {
                "evidence": evidence,
                "summary": f"Found {len(evidence)} pieces of evidence but could not summarize.",
                "key_findings": [{"type": item.get('type'), "file": item.get('file_path')} for item in evidence[:5]]
            }
    
    # Legacy methods for backward compatibility - delegate to FileAnalyzer
    def _summarize_file(self, file_path: str) -> Optional[str]:
        """Summarize file (delegated to FileAnalyzer)"""
        return self.file_analyzer.summarize_file(file_path)
    
    def _list_functions_in_file(self, file_path: str) -> Optional[str]:
        """List functions in file (delegated to FileAnalyzer)"""
        return self.file_analyzer.list_functions_in_file(file_path)
    
    def _get_file_context(self, file_path: str) -> Optional[str]:
        """Get file context (delegated to FileAnalyzer)"""
        return self.file_analyzer.get_file_context(file_path)
    
    def _find_readme_or_docs(self, search_cache: Dict[str, Any]) -> Optional[str]:
        """Find README (delegated to FileAnalyzer)"""
        return self.file_analyzer.find_readme_or_docs(search_cache)
    
    def _summarize_codebase(self, search_cache: Dict[str, Any]) -> Optional[str]:
        """Summarize codebase (delegated to FileAnalyzer)"""
        return self.file_analyzer.summarize_codebase(search_cache)
