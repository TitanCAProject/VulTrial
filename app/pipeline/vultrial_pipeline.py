"""Main pipeline for vulnerability detection with multi-agent debate (Refactored)"""

from pathlib import Path
from typing import Dict, Any, Optional
from ..agents.conversation_agent import ConversationAgent
from ..models.base import BaseLLMModel
from ..context.research_assistant import ResearchAssistant
from ..prompts import (
    # Analysis modes
    ANALYSIS_MODE_DETAILED,
    ANALYSIS_MODE_CONSENSUS,
    # Detailed mode prompts
    SECURITY_RESEARCHER_PROMPT,
    CODE_AUTHOR_PROMPT,
    MODERATOR_PROMPT,
    REVIEW_BOARD_PROMPT,
    # Detailed mode - later turns
    SECURITY_RESEARCHER_PROMPT_LATER,
    CODE_AUTHOR_PROMPT_LATER,
    # Consensus mode prompts
    SECURITY_RESEARCHER_PROMPT_CONSENSUS,
    CODE_AUTHOR_PROMPT_CONSENSUS,
    MODERATOR_PROMPT_CONSENSUS,
    REVIEW_BOARD_PROMPT_CONSENSUS,
)
from ..utils.logger import VulTrialLogger

# Import refactored modules
from .utils.backend_detector import BackendDetector
from .managers.history_manager import HistoryManager
from .managers.evidence_coordinator import EvidenceCoordinator
from .managers.assessment_generator import AssessmentGenerator
from .analyzers.single_analyzer import SingleAnalyzer
from .analyzers.multi_function_analyzer import MultiFunctionAnalyzer
from .analyzers.codebase_analyzer import CodebaseAnalyzer


class VulTrialPipeline:
    """
    Pipeline for multi-agent vulnerability detection with adversarial research assistants
    
    Flow: SR → CA → Moderator → [Need Evidence?] → SR_Assistant & CA_Assistant → SR & CA (enhanced) → Moderator → [iterate] → ReviewBoard
    """
    
    def __init__(
        self,
        model: BaseLLMModel,
        max_turns: int = None,
        verbose: bool = True,
        codebase_path: Optional[str] = None,
        enable_context_retrieval: bool = False,
        enable_pre_debate_summary: bool = True,
        analysis_mode: str = ANALYSIS_MODE_DETAILED,
        # Configurable context management thresholds
        max_evidence_items: int = None,
        max_evidence_tokens_per_item: int = None,
        max_evidence_lines_per_item: int = None,
        evidence_total_token_budget: Optional[int] = None,
        history_compression_start_turn: int = None,
        history_compression_token_budget: Optional[int] = None
    ):
        """
        Initialize the pipeline
        
        Args:
            model: LLM model to use for all agents
            max_turns: Maximum number of debate rounds before final review
            verbose: Whether to print detailed output
            codebase_path: Path to codebase for context retrieval (optional)
            enable_context_retrieval: Whether to enable context retrieval
            enable_pre_debate_summary: Whether to enable pre-debate summarization
            analysis_mode: Analysis mode - 'detailed' (find ALL vulnerabilities) or 'consensus' (only obvious ones)
            max_evidence_items: Maximum number of evidence items to keep (default: 5)
            max_evidence_tokens_per_item: Max tokens per evidence item before truncation (default: 1000)
            max_evidence_lines_per_item: Max lines per evidence item before truncation (default: 100)
            evidence_total_token_budget: Total token budget for all evidence (default: auto from model)
            history_compression_start_turn: Turn number to start compressing history (default: 3)
            history_compression_token_budget: Token budget for compressed history (default: auto from model)
        """
        from ..ui.constants import UIConstants
        
        self.model = model
        self.max_turns = max_turns if max_turns is not None else UIConstants.DEFAULT_MAX_TURNS
        self.verbose = verbose
        self.enable_context_retrieval = enable_context_retrieval
        self.enable_pre_debate_summary = enable_pre_debate_summary
        self.analysis_mode = analysis_mode
        
        # Context management configuration
        self.max_evidence_items = max_evidence_items if max_evidence_items is not None else UIConstants.MAX_EVIDENCE_ITEMS
        self.max_evidence_tokens_per_item = max_evidence_tokens_per_item if max_evidence_tokens_per_item is not None else UIConstants.MAX_EVIDENCE_TOKENS_PER_ITEM
        self.max_evidence_lines_per_item = max_evidence_lines_per_item if max_evidence_lines_per_item is not None else UIConstants.MAX_EVIDENCE_LINES_PER_ITEM
        self.history_compression_start_turn = history_compression_start_turn if history_compression_start_turn is not None else UIConstants.HISTORY_COMPRESSION_START_TURN
        
        # Calculate token budgets based on model capacity
        model_max_tokens = getattr(model, 'max_tokens', 16000)
        self.evidence_total_token_budget = evidence_total_token_budget or min(4000, model_max_tokens // 4)
        self.history_compression_token_budget = history_compression_token_budget or min(8000, model_max_tokens // 3)
        
        # Select prompts based on analysis mode
        if analysis_mode == ANALYSIS_MODE_CONSENSUS:
            sr_prompt = SECURITY_RESEARCHER_PROMPT_CONSENSUS
            ca_prompt = CODE_AUTHOR_PROMPT_CONSENSUS
            mod_prompt = MODERATOR_PROMPT_CONSENSUS
            rb_prompt = REVIEW_BOARD_PROMPT_CONSENSUS
        else:
            sr_prompt = SECURITY_RESEARCHER_PROMPT
            ca_prompt = CODE_AUTHOR_PROMPT
            mod_prompt = MODERATOR_PROMPT
            rb_prompt = REVIEW_BOARD_PROMPT
        
        # Initialize agents
        self.security_researcher = ConversationAgent(
            name="security_researcher",
            model=model,
            role_description=sr_prompt,
            receivers=["code_author", "moderator", "review_board"],
            verbose=verbose
        )
        
        self.code_author = ConversationAgent(
            name="code_author",
            model=model,
            role_description=ca_prompt,
            receivers=["security_researcher", "moderator", "review_board"],
            verbose=verbose
        )
        
        self.moderator = ConversationAgent(
            name="moderator",
            model=model,
            role_description=mod_prompt,
            receivers=["review_board", "security_researcher", "code_author"],
            verbose=verbose
        )
        
        self.review_board = ConversationAgent(
            name="review_board",
            model=model,
            role_description=rb_prompt,
            receivers=[],
            verbose=verbose
        )
        
        # Search cache
        self.search_cache: Dict[str, Any] = {}
        
        # Initialize search backend and assistants
        self.search_backend = None
        self.sr_assistant = None
        self.ca_assistant = None
        
        if enable_context_retrieval and codebase_path:
            # Detect backend type and create backend
            backend_type = BackendDetector.detect_code_type(codebase_path)
            self.search_backend = BackendDetector.create_backend(backend_type, codebase_path, verbose)
            
            # Create research assistants
            self.sr_assistant = ResearchAssistant(
                agent_name="security_researcher",
                model=model,
                search_backend=self.search_backend,
                verbose=verbose,
                logger=None,
                analysis_mode=analysis_mode,
                max_evidence_items=self.max_evidence_items,
                max_evidence_tokens_per_item=self.max_evidence_tokens_per_item,
                max_evidence_lines_per_item=self.max_evidence_lines_per_item,
                evidence_total_token_budget=self.evidence_total_token_budget
            )
            
            self.ca_assistant = ResearchAssistant(
                agent_name="code_author",
                model=model,
                search_backend=self.search_backend,
                verbose=verbose,
                logger=None,
                analysis_mode=analysis_mode,
                max_evidence_items=self.max_evidence_items,
                max_evidence_tokens_per_item=self.max_evidence_tokens_per_item,
                max_evidence_lines_per_item=self.max_evidence_lines_per_item,
                evidence_total_token_budget=self.evidence_total_token_budget
            )
        
        # Initialize managers
        self.history_manager = HistoryManager(
            compression_start_turn=self.history_compression_start_turn,
            compression_token_budget=self.history_compression_token_budget
        )
        
        self.evidence_coordinator = EvidenceCoordinator(
            sr_assistant=self.sr_assistant,
            ca_assistant=self.ca_assistant,
            search_cache=self.search_cache,
            verbose=verbose
        )
        
        self.assessment_generator = AssessmentGenerator(
            model=model,
            verbose=verbose
        )
        
        # Initialize analyzers
        self.single_analyzer = SingleAnalyzer(
            security_researcher=self.security_researcher,
            code_author=self.code_author,
            moderator=self.moderator,
            review_board=self.review_board,
            history_manager=self.history_manager,
            evidence_coordinator=self.evidence_coordinator,
            max_turns=self.max_turns,
            analysis_mode=analysis_mode,
            enable_context_retrieval=enable_context_retrieval,
            enable_pre_debate_summary=enable_pre_debate_summary,
            verbose=verbose,
            logger=None
        )
        
        self.multi_function_analyzer = MultiFunctionAnalyzer(
            single_analyzer=self.single_analyzer,
            assessment_generator=self.assessment_generator,
            security_researcher=self.security_researcher,
            code_author=self.code_author,
            moderator=self.moderator,
            review_board=self.review_board,
            sr_assistant=self.sr_assistant,
            search_cache=self.search_cache,
            analysis_mode=analysis_mode,
            verbose=verbose,
            logger=None
        )
        
        self.codebase_analyzer = CodebaseAnalyzer(
            multi_function_analyzer=self.multi_function_analyzer,
            assessment_generator=self.assessment_generator,
            verbose=verbose,
            logger=None
        )
        
        # Logger
        self.logger: Optional[VulTrialLogger] = None
    
    def set_logger(self, logger: VulTrialLogger):
        """Set logger for pipeline and all components"""
        self.logger = logger
        if self.sr_assistant:
            self.sr_assistant.logger = logger
        if self.ca_assistant:
            self.ca_assistant.logger = logger
        
        # Set logger for analyzers
        self.single_analyzer.logger = logger
        self.multi_function_analyzer.logger = logger
        self.codebase_analyzer.logger = logger
    
    def run(self, code: str, input_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run the vulnerability detection pipeline
        
        Args:
            code: Code snippet to analyze
            input_metadata: Optional metadata about the input (file, function, codebase info)
            
        Returns:
            Dict containing results from all agents
        """
        # Check if we're analyzing entire codebase
        if self._is_codebase_analysis(input_metadata):
            return self.codebase_analyzer.analyze(input_metadata)
        
        # Check if we need to analyze multiple functions
        elif self._is_multi_function_analysis(input_metadata):
            return self.multi_function_analyzer.analyze(code, input_metadata)
        
        # Single analysis mode (function or whole file)
        else:
            return self.single_analyzer.analyze(code, input_metadata)
    
    def _is_codebase_analysis(self, input_metadata: Optional[Dict[str, Any]]) -> bool:
        """Check if this is a codebase analysis"""
        return (
            input_metadata is not None and
            input_metadata.get('input_type') == 'codebase' and
            input_metadata.get('codebase_path') is not None
        )
    
    def _is_multi_function_analysis(self, input_metadata: Optional[Dict[str, Any]]) -> bool:
        """Check if this is a multi-function analysis"""
        return (
            input_metadata is not None and
            input_metadata.get('input_type') == 'file' and
            not input_metadata.get('function_name') and
            input_metadata.get('file_path') is not None
        )
    
    def reset(self):
        """Reset the pipeline state"""
        self.history_manager.clear()
        self.search_cache = {}
        self.security_researcher.clear_history()
        self.code_author.clear_history()
        self.moderator.clear_history()
        self.review_board.clear_history()
