"""Multi-function analyzer - analyzes all functions in a file one-by-one"""

import json
from pathlib import Path
from typing import Dict, Any
from ...agents.conversation_agent import ConversationAgent
from ...prompts import (
    ANALYSIS_MODE_CONSENSUS,
    SECURITY_RESEARCHER_PROMPT,
    CODE_AUTHOR_PROMPT,
    SECURITY_RESEARCHER_PROMPT_CONSENSUS,
    CODE_AUTHOR_PROMPT_CONSENSUS
)
from ...utils.input_handler import InputHandler
from ...utils.logger import VulTrialLogger
from .single_analyzer import SingleAnalyzer
from ..managers.assessment_generator import AssessmentGenerator
from ...context.research_assistant import ResearchAssistant


class MultiFunctionAnalyzer:
    """Analyzes all functions in a file one-by-one"""
    
    def __init__(
        self,
        single_analyzer: SingleAnalyzer,
        assessment_generator: AssessmentGenerator,
        security_researcher: ConversationAgent,
        code_author: ConversationAgent,
        moderator: ConversationAgent,
        review_board: ConversationAgent,
        sr_assistant: ResearchAssistant,
        search_cache: Dict[str, Any],
        analysis_mode: str,
        verbose: bool = True,
        logger: VulTrialLogger = None
    ):
        """
        Initialize multi-function analyzer
        
        Args:
            single_analyzer: Single analyzer for each function
            assessment_generator: Generator for overall file assessment
            security_researcher: Security researcher agent (for reset)
            code_author: Code author agent (for reset)
            moderator: Moderator agent (for reset)
            review_board: Review board agent (for reset)
            sr_assistant: SR assistant (for file summarization)
            search_cache: Shared search cache
            analysis_mode: Analysis mode
            verbose: Whether to print verbose output
            logger: Optional logger
        """
        self.single_analyzer = single_analyzer
        self.assessment_generator = assessment_generator
        self.security_researcher = security_researcher
        self.code_author = code_author
        self.moderator = moderator
        self.review_board = review_board
        self.sr_assistant = sr_assistant
        self.search_cache = search_cache
        self.analysis_mode = analysis_mode
        self.verbose = verbose
        self.logger = logger
    
    def analyze(self, full_file_code: str, input_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze each function in a file one by one
        
        Args:
            full_file_code: The full file content
            input_metadata: Metadata about the file
            
        Returns:
            Combined results from analyzing all functions
        """
        file_path = input_metadata['file_path']
        
        if self.verbose:
            print("\n" + "="*80)
            print("VulTrial Multi-Function Analysis Mode")
            print("="*80)
            print(f"File: {file_path}")
            print("Strategy: Analyze each function one-by-one")
            print("="*80)
        
        # Step 1: Generate file summary ONCE (cached and reused)
        self._generate_file_summary(file_path)
        
        # Step 2: List all functions in the file
        functions = self._extract_functions(file_path, full_file_code, input_metadata)
        
        if not functions:
            # Fall back to single analysis
            return self.single_analyzer.analyze(full_file_code, input_metadata)
        
        if self.verbose:
            print(f"\nFound {len(functions)} functions in file:")
            for i, func in enumerate(functions[:10], 1):
                print(f"  {i}. {func['name']} (lines {func['start_line']}-{func['end_line']})")
            if len(functions) > 10:
                print(f"  ... and {len(functions) - 10} more")
            print("")
        
        # Step 3: Analyze each function one-by-one
        combined_results = {
            "code": full_file_code,
            "input_metadata": input_metadata,
            "function_analyses": [],
            "overall_assessment": None
        }
        
        for i, func_info in enumerate(functions, 1):
            func_name = func_info['name']
            func_code = func_info['code']
            
            if self.logger:
                self.logger.log_phase(f"Analyzing Function {i}/{len(functions)}: {func_name}")
            
            if self.verbose:
                print(f"\n{'#'*80}")
                print(f"# Analyzing Function {i}/{len(functions)}: {func_name}")
                print(f"# Lines {func_info['start_line']}-{func_info['end_line']}")
                print(f"{'#'*80}\n")
            
            # Create metadata for this function
            func_metadata = {
                'input_type': 'function',
                'file_path': file_path,
                'function_name': func_name,
                'analysis_scope': f"Function '{func_name}' in '{Path(file_path).name}'",
                'start_line': func_info['start_line'],
                'end_line': func_info['end_line']
            }
            
            # Reset agents for this function (but keep cache!)
            self._reset_agents_for_function()
            
            # Run analysis
            func_results = self.single_analyzer.analyze(func_code, func_metadata)
            
            combined_results["function_analyses"].append({
                "function_name": func_name,
                "function_info": func_info,
                "analysis_results": func_results
            })
            
            # Save intermediate progress
            self._save_progress(file_path, i, len(functions), combined_results)
            
            if self.verbose:
                print(f"\n✓ Completed analysis of {func_name}\n")
        
        # Step 4: Generate overall assessment
        if self.verbose:
            print(f"\n{'#'*80}")
            print(f"# Generating Overall Assessment for File")
            print(f"{'#'*80}\n")
        
        overall_assessment = self.assessment_generator.generate_file_assessment(combined_results)
        combined_results["overall_assessment"] = overall_assessment
        
        if self.verbose:
            print("\n" + "="*80)
            print("Multi-Function Analysis Completed")
            print("="*80 + "\n")
        
        return combined_results
    
    def _generate_file_summary(self, file_path: str):
        """Generate and cache file summary"""
        if self.verbose:
            print(f"\n{'~'*60}")
            print("Step 1: Generating file summary (shared for all functions)...")
            print(f"{'~'*60}")
        
        cache_key = f"file_summary_{file_path}"
        if cache_key not in self.search_cache and self.sr_assistant:
            file_summary = self.sr_assistant._summarize_file(file_path)
            self.search_cache[cache_key] = file_summary
            if self.verbose:
                print(f"✓ File summary generated and cached for reuse\n")
        elif cache_key in self.search_cache:
            if self.verbose:
                print(f"✓ Using cached file summary\n")
    
    def _extract_functions(self, file_path: str, full_file_code: str, input_metadata: Dict[str, Any]) -> list:
        """Extract all functions from file"""
        try:
            functions = InputHandler.list_all_functions_in_file(file_path)
            return functions
        except Exception as e:
            if self.verbose:
                print(f"Error listing functions: {e}")
                print("⚠ No functions found in file. Analyzing file as a whole.")
            return []
    
    def _reset_agents_for_function(self):
        """Reset conversation for a new function (but keep cache!)"""
        # Reset history manager
        self.single_analyzer.history_manager.clear()
        
        # Reset agents
        self.security_researcher.clear_history()
        self.code_author.clear_history()
        self.moderator.clear_history()
        self.review_board.clear_history()
        
        # IMPORTANT: Reset prompts for each function (back to Turn 1 prompts)
        if self.analysis_mode == ANALYSIS_MODE_CONSENSUS:
            self.security_researcher.update_role_description(SECURITY_RESEARCHER_PROMPT_CONSENSUS)
            self.code_author.update_role_description(CODE_AUTHOR_PROMPT_CONSENSUS)
        else:
            # Detailed mode - reset to base prompts
            self.security_researcher.update_role_description(SECURITY_RESEARCHER_PROMPT)
            self.code_author.update_role_description(CODE_AUTHOR_PROMPT)
        
        # NOTE: search_cache is NOT reset - it's shared!
    
    def _save_progress(self, file_path: str, current: int, total: int, results: Dict[str, Any]):
        """Save intermediate progress"""
        try:
            progress_dir = Path("output/.progress")
            progress_dir.mkdir(parents=True, exist_ok=True)
            
            file_name = Path(file_path).stem
            progress_file = progress_dir / f"{file_name}_progress.json"
            
            progress_data = {
                "file_path": file_path,
                "progress": f"{current}/{total}",
                "completed_functions": current,
                "total_functions": total,
                "results": results
            }
            
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2)
            
            if self.verbose and current < total:
                print(f"  💾 Progress saved ({current}/{total} functions)")
        
        except Exception as e:
            if self.verbose:
                print(f"  Warning: Could not save progress: {e}")

