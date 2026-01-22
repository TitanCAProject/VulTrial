"""
VulTrial Pipeline - Multi-Agent Debate for Vulnerability Detection

Simple pipeline with four agents debating about code vulnerabilities.
"""

import json
from typing import Dict, Any, Optional, List

from ..agents.conversation_agent import ConversationAgent
from ..models.base import BaseLLMModel
from ..utils.logger import VulTrialLogger
from ..prompts import (
    SECURITY_RESEARCHER_PROMPT,
    CODE_AUTHOR_PROMPT,
    MODERATOR_PROMPT,
    REVIEW_BOARD_PROMPT,
    SECURITY_RESEARCHER_PROMPT_LATER,
    CODE_AUTHOR_PROMPT_LATER,
    MODERATOR_PROMPT_LATER,
)


class HistoryManager:
    """Manages conversation history"""
    
    def __init__(self):
        self.conversation_log: List[Dict[str, str]] = []
    
    def add_message(self, agent_name: str, message: str):
        """Add message to conversation log"""
        self.conversation_log.append({
            "agent": agent_name,
            "message": message
        })
    
    def build_history_for_agent(self, agent_name: str) -> str:
        """Build chat history string for an agent"""
        if not self.conversation_log:
            return ""
        
        history_parts = []
        
        if agent_name == "review_board":
            # Review board gets full history
            history_parts.append("[DEBATE HISTORY]:\n")
            for entry in self.conversation_log:
                agent = entry["agent"]
                message = entry["message"]
                history_parts.append(f"[{agent.upper()}]:\n{message}\n\n")
        
        elif agent_name == "moderator":
            # Moderator sees current turn (last 2 messages: SR, CA)
            recent_entries = self.conversation_log[-2:] if len(self.conversation_log) >= 2 else self.conversation_log
            
            history_parts.append("[CURRENT TURN]:\n")
            for entry in recent_entries:
                agent = entry["agent"]
                message = entry["message"]
                history_parts.append(f"[{agent.upper()}]:\n{message}\n\n")
            
            # Add previous moderator summaries
            if len(self.conversation_log) > 2:
                moderator_entries = [e for e in self.conversation_log[:-2] if e["agent"] == "moderator"]
                if moderator_entries:
                    history_parts.append("[PREVIOUS SUMMARIES]:\n")
                    for i, entry in enumerate(moderator_entries, 1):
                        history_parts.append(f"Turn {i}: {entry['message'][:200]}...\n\n")
        
        else:
            # SR and CA see full history
            history_parts.append("[DEBATE SO FAR]:\n")
            for entry in self.conversation_log:
                agent = entry["agent"]
                message = entry["message"]
                history_parts.append(f"[{agent.upper()}]:\n{message}\n\n")
        
        return "".join(history_parts)
    
    def clear(self):
        """Clear conversation log"""
        self.conversation_log = []
    
    def get_conversation_log(self) -> List[Dict[str, str]]:
        """Get raw conversation log"""
        return self.conversation_log


class VulTrialPipeline:
    """
    Pipeline for multi-agent vulnerability detection
    
    Flow: Security Researcher → Code Author → Moderator → [iterate] → Review Board
    """
    
    def __init__(
        self,
        model: BaseLLMModel,
        max_turns: int = 4,
        verbose: bool = True
    ):
        """
        Initialize the pipeline
        
        Args:
            model: LLM model to use for all agents
            max_turns: Maximum number of debate rounds
            verbose: Whether to print detailed output
        """
        self.model = model
        self.max_turns = max_turns
        self.verbose = verbose
        
        # Initialize agents
        self.security_researcher = ConversationAgent(
            name="security_researcher",
            model=model,
            role_description=SECURITY_RESEARCHER_PROMPT,
            receivers=["code_author", "moderator", "review_board"],
            verbose=verbose
        )
        
        self.code_author = ConversationAgent(
            name="code_author",
            model=model,
            role_description=CODE_AUTHOR_PROMPT,
            receivers=["security_researcher", "moderator", "review_board"],
            verbose=verbose
        )
        
        self.moderator = ConversationAgent(
            name="moderator",
            model=model,
            role_description=MODERATOR_PROMPT,
            receivers=["review_board", "security_researcher", "code_author"],
            verbose=verbose
        )
        
        self.review_board = ConversationAgent(
            name="review_board",
            model=model,
            role_description=REVIEW_BOARD_PROMPT,
            receivers=[],
            verbose=verbose
        )
        
        # History manager
        self.history_manager = HistoryManager()
        
        # Logger
        self.logger: Optional[VulTrialLogger] = None
    
    def set_logger(self, logger: VulTrialLogger):
        """Set logger for pipeline"""
        self.logger = logger
    
    def run(self, code: str, input_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run the vulnerability detection pipeline
        
        Args:
            code: Code snippet to analyze
            input_metadata: Optional metadata (unused, kept for compatibility)
            
        Returns:
            Dict containing results from all agents
        """
        if self.verbose:
            print("\n" + "="*70)
            print("VulTrial Pipeline Starting")
            print("="*70)
        
        results = {
            "code": code,
            "turns": [],
            "final_decision": None
        }
        
        # Multi-turn debate
        for turn in range(1, self.max_turns + 1):
            if self.verbose:
                print(f"\n{'#'*70}")
                print(f"# TURN {turn}/{self.max_turns}")
                print(f"{'#'*70}\n")
            
            turn_results = {}
            
            # Switch to "later turn" prompts for turn 2+
            if turn >= 2:
                self.security_researcher.update_role_description(SECURITY_RESEARCHER_PROMPT_LATER)
                self.code_author.update_role_description(CODE_AUTHOR_PROMPT_LATER)
                self.moderator.update_role_description(MODERATOR_PROMPT_LATER)
            
            # Step 1: Security Researcher
            sr_response = self._run_agent(
                self.security_researcher, code, turn, "security_researcher"
            )
            turn_results["security_researcher"] = sr_response
            
            # Check if SR found no vulnerabilities
            if self._check_empty_vulnerability_array(sr_response):
                if self.verbose:
                    print(f"\n{'*'*60}")
                    print(f"Security Researcher found no vulnerabilities - Ending early")
                    print(f"{'*'*60}\n")
                
                results["turns"].append(turn_results)
                results["final_decision"] = "[]"
                return results
            
            # Step 2: Code Author
            ca_response = self._run_agent(
                self.code_author, code, turn, "code_author"
            )
            turn_results["code_author"] = ca_response
            
            # Step 3: Moderator
            mod_response = self._run_agent(
                self.moderator, code, turn, "moderator"
            )
            turn_results["moderator"] = mod_response
            
            # Save turn results
            results["turns"].append(turn_results)
            
            # Check if moderator says no more debate needed
            if self._check_debate_complete(mod_response):
                if self.verbose:
                    print(f"\n{'*'*60}")
                    print(f"Moderator: Debate complete - Moving to final decision")
                    print(f"{'*'*60}\n")
                break
        
        # Final step: Review Board decision
        final_decision = self._get_review_board_decision(code)
        results["final_decision"] = final_decision
        
        if self.verbose:
            print("\n" + "="*70)
            print("VulTrial Pipeline Completed")
            print("="*70 + "\n")
        
        return results
    
    def _run_agent(
        self,
        agent: ConversationAgent,
        code: str,
        turn: int,
        agent_name: str
    ) -> str:
        """Run a single agent"""
        if self.logger:
            self.logger.log_agent_start(agent_name, turn)
        
        chat_history = self.history_manager.build_history_for_agent(agent_name)
        
        agent_input = {
            "code": code,
            "chat_history": chat_history
        }
        
        response = agent.process(agent_input)
        self.history_manager.add_message(agent_name, response)
        
        if self.logger:
            tokens_used = agent.last_tokens_used
            self.logger.log_agent_response(agent_name, response, tokens_used)
        
        return response
    
    def _get_review_board_decision(self, code: str) -> str:
        """Get final Review Board decision"""
        if self.verbose:
            print(f"\n{'#'*70}")
            print(f"# FINAL REVIEW BOARD DECISION")
            print(f"{'#'*70}\n")
        
        if self.logger:
            self.logger.log_agent_start("review_board")
        
        review_chat_history = self.history_manager.build_history_for_agent("review_board")
        review_input = {
            "code": code,
            "chat_history": review_chat_history
        }
        
        final_decision = self.review_board.process(review_input)
        self.history_manager.add_message("review_board", final_decision)
        
        if self.logger:
            tokens_used = self.review_board.last_tokens_used
            self.logger.log_agent_response("review_board", final_decision, tokens_used)
            self.logger.log_decision(final_decision)
        
        return final_decision
    
    @staticmethod
    def _check_empty_vulnerability_array(researcher_response: str) -> bool:
        """Check if Security Researcher found no vulnerabilities"""
        try:
            response_clean = researcher_response.strip()
            if '```json' in response_clean:
                response_clean = response_clean.split('```json')[1].split('```')[0]
            elif '```' in response_clean:
                response_clean = response_clean.split('```')[1].split('```')[0]
            
            vulnerabilities = json.loads(response_clean)
            return isinstance(vulnerabilities, list) and len(vulnerabilities) == 0
        except:
            return False
    
    @staticmethod
    def _check_debate_complete(moderator_response: str) -> bool:
        """Check if moderator indicates debate is complete"""
        lower_response = moderator_response.lower()
        complete_indicators = [
            "no further debate",
            "debate complete",
            "no additional evidence needed",
            "parties have reached",
            "consensus reached",
            "both parties agree"
        ]
        return any(indicator in lower_response for indicator in complete_indicators)
    
    def reset(self):
        """Reset the pipeline state"""
        self.history_manager.clear()
        self.security_researcher.clear_history()
        self.code_author.clear_history()
        self.moderator.clear_history()
        self.review_board.clear_history()
