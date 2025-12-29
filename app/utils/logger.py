"""
Enhanced logging system for VulTrial
Provides detailed file logging and simple console output
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class VulTrialLogger:
    """Logger that outputs detailed logs to file and simple messages to console"""
    
    def __init__(self, log_file: Optional[str] = None, verbose: bool = True):
        """
        Initialize logger
        
        Args:
            log_file: Path to detailed log file (auto-generated if None)
            verbose: Whether to print to console
        """
        self.verbose = verbose
        
        # Create log file
        if log_file is None:
            log_dir = Path("output/logs")
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = log_dir / f"vultrial_{timestamp}.log"
        
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize log file
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write(f"VulTrial Detailed Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")
        
        self.session_start = datetime.now()
        
        # Token usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_tokens = 0
    
    def log_phase(self, phase_name: str, details: Optional[str] = None):
        """Log a new phase of execution"""
        # Console: Simple
        if self.verbose:
            print(f"\n{'='*70}")
            print(f"  {phase_name}")
            print(f"{'='*70}")
        
        # File: Detailed
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'#'*80}\n")
            f.write(f"# PHASE: {phase_name}\n")
            f.write(f"# Time: {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"{'#'*80}\n\n")
            if details:
                f.write(f"{details}\n\n")
    
    def log_agent_start(self, agent_name: str, turn: Optional[int] = None):
        """Log when an agent starts processing"""
        # Console: Simple with emoji
        emoji = {
            'security_researcher': '🔍',
            'code_author': '👨‍💻',
            'moderator': '⚖️',
            'review_board': '🏛️'
        }.get(agent_name, '🤖')
        
        display_name = agent_name.replace('_', ' ').title()
        
        if self.verbose:
            turn_str = f" (Turn {turn})" if turn else ""
            print(f"\n{emoji} {display_name}{turn_str} is analyzing...")
        
        # File: Detailed
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'─'*80}\n")
            f.write(f"AGENT: {agent_name.upper()}\n")
            if turn:
                f.write(f"TURN: {turn}\n")
            f.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"{'─'*80}\n\n")
    
    def log_agent_prompt(self, agent_name: str, prompt: str):
        """Log the full prompt sent to an agent (file only)"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[PROMPT TO {agent_name.upper()}]:\n")
            f.write(f"{'-'*80}\n")
            f.write(f"{prompt}\n")  # Full prompt, no truncation
            f.write(f"{'-'*80}\n\n")
    
    def log_agent_response(self, agent_name: str, response: str, tokens_used: Optional[Dict[str, int]] = None):
        """Log agent response with token tracking"""
        # Track tokens if provided
        if tokens_used and isinstance(tokens_used, dict):
            input_tokens = tokens_used.get('prompt', 0) or tokens_used.get('input', 0)
            output_tokens = tokens_used.get('completion', 0) or tokens_used.get('output', 0)
            total = tokens_used.get('total', input_tokens + output_tokens)
            
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_tokens += total
        
        # Console: Just completion indicator
        if self.verbose:
            if tokens_used and isinstance(tokens_used, dict):
                total = tokens_used.get('total', 0)
                token_str = f" ({total} tokens)" if total else ""
            else:
                token_str = f" ({tokens_used} tokens)" if tokens_used else ""
            print(f"  ✓ Response received{token_str}")
        
        # File: Full response
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[RESPONSE FROM {agent_name.upper()}]:\n")
            if tokens_used:
                f.write(f"Tokens: {tokens_used}\n")
            f.write(f"{'-'*80}\n")
            f.write(f"{response}\n")
            f.write(f"{'-'*80}\n\n")
    
    def log_assistant_start(self, assistant_name: str):
        """Log when research assistant starts"""
        # Console: Simple
        if self.verbose:
            print(f"    🔎 {assistant_name} researching...")
        
        # File: Detailed
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'~'*80}\n")
            f.write(f"RESEARCH ASSISTANT: {assistant_name}\n")
            f.write(f"Time: {datetime.now().strftime('%H:%M:%S')}\n")
            f.write(f"{'~'*80}\n\n")
    
    def log_tool_use(self, tool_name: str, parameters: Dict[str, Any], results_count: Optional[int] = None):
        """Log tool usage"""
        # Console: Simple
        if self.verbose:
            params_str = ', '.join(f"{k}={v}" for k, v in list(parameters.items())[:2])
            if len(parameters) > 2:
                params_str += "..."
            result_str = f" → {results_count} results" if results_count is not None else ""
            print(f"      🔧 {tool_name}({params_str}){result_str}")
        
        # File: Detailed
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[TOOL USED]: {tool_name}\n")
            f.write(f"Parameters: {json.dumps(parameters, indent=2)}\n")
            if results_count is not None:
                f.write(f"Results: {results_count} items found\n")
            f.write(f"\n")
    
    def log_tool_results(self, tool_name: str, results: Any):
        """Log detailed tool results (file only)"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[TOOL RESULTS - {tool_name}]:\n")
            f.write(f"{'-'*80}\n")
            
            if isinstance(results, list):
                for i, item in enumerate(results, 1):  # Show ALL results, no limit
                    f.write(f"\nResult {i}:\n")
                    if isinstance(item, dict):
                        f.write(json.dumps(item, indent=2))
                    else:
                        f.write(str(item))
                    f.write("\n")
            else:
                f.write(str(results))
            
            f.write(f"\n{'-'*80}\n\n")
    
    def log_cache_hit(self, cache_key: str):
        """Log cache hit (file only)"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[CACHE HIT]: {cache_key}\n\n")
    
    def log_cache_miss(self, cache_key: str):
        """Log cache miss (file only)"""
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"[CACHE MISS]: {cache_key} - will fetch\n\n")
    
    def log_decision(self, decision: str):
        """Log final decision"""
        # Console: Highlight
        if self.verbose:
            print(f"\n{'='*70}")
            print(f"  📋 DECISION")
            print(f"{'='*70}")
            print(f"{decision[:300]}...")
            print(f"{'='*70}\n")
        
        # File: Full decision
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'#'*80}\n")
            f.write(f"# FINAL DECISION\n")
            f.write(f"{'#'*80}\n\n")
            f.write(f"{decision}\n\n")
    
    def log_summary(self, message: str):
        """Log summary message"""
        # Both console and file
        if self.verbose:
            print(f"  {message}")
        
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{message}\n")
    
    def log_error(self, error_msg: str, exception: Optional[Exception] = None):
        """Log error"""
        # Console: Simple
        if self.verbose:
            print(f"  ❌ Error: {error_msg}")
        
        # File: Detailed with traceback
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n[ERROR]: {error_msg}\n")
            if exception:
                import traceback
                f.write(f"Exception: {type(exception).__name__}: {str(exception)}\n")
                f.write(f"Traceback:\n")
                f.write(traceback.format_exc())
            f.write(f"\n")
    
    def log_completion(self):
        """Log session completion"""
        duration = (datetime.now() - self.session_start).total_seconds()
        
        # Console
        if self.verbose:
            print(f"\n{'='*70}")
            print(f"  ✅ Analysis Complete ({duration:.1f}s)")
            print(f"  📄 Detailed log: {self.log_file}")
            print(f"{'='*70}\n")
        
        # File
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"SESSION COMPLETED\n")
            f.write(f"Duration: {duration:.1f} seconds\n")
            f.write(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*80}\n")
    
    def get_log_path(self) -> str:
        """Get the path to the log file"""
        return str(self.log_file)
    
    def get_token_usage(self) -> Dict[str, int]:
        """Get total token usage statistics"""
        return {
            'input_tokens': self.total_input_tokens,
            'output_tokens': self.total_output_tokens,
            'total_tokens': self.total_tokens
        }
    
    def calculate_cost(self, price_input_per_million: float, price_output_per_million: float) -> Dict[str, float]:
        """
        Calculate cost based on token usage and pricing
        
        Args:
            price_input_per_million: Price per 1 million input tokens
            price_output_per_million: Price per 1 million output tokens
            
        Returns:
            Dict with input_cost, output_cost, and total_cost
        """
        input_cost = (self.total_input_tokens / 1_000_000) * price_input_per_million
        output_cost = (self.total_output_tokens / 1_000_000) * price_output_per_million
        total_cost = input_cost + output_cost
        
        return {
            'input_cost': input_cost,
            'output_cost': output_cost,
            'total_cost': total_cost
        }

