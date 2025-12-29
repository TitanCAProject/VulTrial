"""Single function/file analyzer with multi-turn agent debate"""

import json
from typing import Dict, Any, Optional
from ...agents.conversation_agent import ConversationAgent
from ...models.base import BaseLLMModel
from ...prompts import (
    ANALYSIS_MODE_DETAILED,
    ANALYSIS_MODE_CONSENSUS,
    SECURITY_RESEARCHER_PROMPT_LATER,
    CODE_AUTHOR_PROMPT_LATER,
    MODERATOR_PROMPT_LATER,
    SECURITY_RESEARCHER_PROMPT_CONSENSUS_LATER,
    CODE_AUTHOR_PROMPT_CONSENSUS_LATER
)
from ..managers.history_manager import HistoryManager
from ..managers.evidence_coordinator import EvidenceCoordinator
from ...utils.logger import VulTrialLogger


class SingleAnalyzer:
    """Analyzes a single function or file with multi-turn agent debate"""
    
    def __init__(
        self,
        security_researcher: ConversationAgent,
        code_author: ConversationAgent,
        moderator: ConversationAgent,
        review_board: ConversationAgent,
        history_manager: HistoryManager,
        evidence_coordinator: EvidenceCoordinator,
        max_turns: int = 2,
        analysis_mode: str = ANALYSIS_MODE_DETAILED,
        enable_context_retrieval: bool = False,
        enable_pre_debate_summary: bool = True,
        verbose: bool = True,
        logger: Optional[VulTrialLogger] = None
    ):
        """
        Initialize single analyzer
        
        Args:
            security_researcher: Security Researcher agent
            code_author: Code Author agent
            moderator: Moderator agent
            review_board: Review Board agent
            history_manager: History manager for conversation tracking
            evidence_coordinator: Evidence coordinator for research assistants
            max_turns: Maximum number of debate rounds
            analysis_mode: Analysis mode ('detailed' or 'consensus')
            enable_context_retrieval: Whether to enable evidence gathering
            enable_pre_debate_summary: Whether to prepare initial context
            verbose: Whether to print verbose output
            logger: Optional logger for tracking
        """
        self.security_researcher = security_researcher
        self.code_author = code_author
        self.moderator = moderator
        self.review_board = review_board
        self.history_manager = history_manager
        self.evidence_coordinator = evidence_coordinator
        self.max_turns = max_turns
        self.analysis_mode = analysis_mode
        self.enable_context_retrieval = enable_context_retrieval
        self.enable_pre_debate_summary = enable_pre_debate_summary
        self.verbose = verbose
        self.logger = logger
    
    def analyze(self, code: str, input_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Run analysis on a single target (function or file)
        
        Args:
            code: Code to analyze
            input_metadata: Optional metadata about the input
            
        Returns:
            Analysis results dict
        """
        if self.verbose:
            print("\n" + "="*80)
            print("VulTrial Pipeline Starting (Assistant-Driven Architecture)")
            mode_display = "DETAILED MODE" if self.analysis_mode == ANALYSIS_MODE_DETAILED else "CONSENSUS MODE"
            print(f"Analysis Mode: {mode_display}")
            print("="*80)
        
        if input_metadata and self.verbose and input_metadata.get('analysis_scope'):
            print(f"Analysis Scope: {input_metadata['analysis_scope']}")
            print("="*80)
        
        results = {
            "code": code,
            "input_metadata": input_metadata,
            "turns": [],
            "prompts": [],
            "evidence_gathered": [],
            "final_decision": None
        }
        
        # AUTOMATIC CONTEXT: Generate file + function summary at start
        initial_context = ""
        if self.enable_pre_debate_summary:
            if self.verbose:
                print(f"\n{'*'*60}")
                print(f"Preparing context (file + function summaries)...")
                print(f"{'*'*60}\n")
            
            initial_context = self.evidence_coordinator.prepare_initial_context(
                target_code=code,
                input_metadata=input_metadata or {}
            )
            
            if self.verbose and initial_context:
                print(f"✓ Context prepared and will be provided to both agents\n")
        
        # Track evidence for CA (from previous turn)
        pending_ca_evidence = None
        need_evidence_next_turn = False
        
        # Multi-turn debate
        for turn in range(1, self.max_turns + 1):
            if self.verbose:
                print(f"\n{'#'*80}")
                print(f"# TURN {turn}/{self.max_turns}")
                print(f"{'#'*80}\n")
            
            turn_results = {}
            turn_prompts = {}
            
            # Switch to "later turn" prompts for turn 2+ (both modes)
            if turn >= 2:
                if self.analysis_mode == ANALYSIS_MODE_CONSENSUS:
                    if self.verbose:
                        print(f"  🎯 Consensus Mode: Turn {turn} - Focusing on HIGH-SEVERITY issues\n")
                    self.security_researcher.update_role_description(SECURITY_RESEARCHER_PROMPT_CONSENSUS_LATER)
                    self.code_author.update_role_description(CODE_AUTHOR_PROMPT_CONSENSUS_LATER)
                else:
                    # Detailed mode switches to refinement prompts
                    self.security_researcher.update_role_description(SECURITY_RESEARCHER_PROMPT_LATER)
                    self.code_author.update_role_description(CODE_AUTHOR_PROMPT_LATER)
                    self.moderator.update_role_description(MODERATOR_PROMPT_LATER)
            
            # Use compressed history based on turn number
            use_compressed_history = (turn >= self.history_manager.compression_start_turn)
            
            if use_compressed_history and self.verbose:
                print(f"  💡 Using compressed history (Turn {turn}) to stay within token limits")
                print(f"     Keeping: Recent discussion + moderator summaries from earlier turns\n")
            
            # SEQUENTIAL FLOW FOR TURN 2+
            # Step 1: SR Assistant gathers (if needed from previous turn)
            sr_evidence_for_turn = None
            if turn >= 2 and need_evidence_next_turn and self.enable_context_retrieval:
                sr_evidence_for_turn = self._gather_sr_evidence_at_turn_start(turn, results)
            
            # Step 2: SR responds (with evidence if gathered)
            sr_response, sr_prompt = self._handle_sr_turn(
                code, turn, use_compressed_history, initial_context, sr_evidence_for_turn
            )
            turn_results["security_researcher"] = sr_response
            turn_prompts["security_researcher"] = sr_prompt
            
            # Check if SR found no vulnerabilities
            if self._check_empty_vulnerability_array(sr_response):
                if self.verbose:
                    print(f"\n{'*'*60}")
                    print(f"Security Researcher found no vulnerabilities - Skipping debate")
                    print(f"{'*'*60}\n")
                
                results["turns"].append(turn_results)
                results["prompts"].append(turn_prompts)
                results["final_decision"] = "[]"
                
                if self.verbose:
                    print("\n" + "="*80)
                    print("VulTrial Pipeline Completed")
                    print("="*80 + "\n")
                
                return results
            
            # Step 3: CA Assistant gathers (NOW sees SR's Turn 2 response!)
            ca_evidence_for_turn = None
            if turn >= 2 and need_evidence_next_turn and self.enable_context_retrieval:
                ca_evidence_for_turn = self._gather_ca_evidence_after_sr_response(turn, results)
            
            # Step 4: CA responds (with evidence if gathered)
            ca_response, ca_prompt = self._handle_ca_turn(
                code, turn, use_compressed_history, initial_context, ca_evidence_for_turn
            )
            turn_results["code_author"] = ca_response
            turn_prompts["code_author"] = ca_prompt
            
            # Step 3: Moderator reviews
            mod_response, mod_prompt = self._handle_moderator_turn(
                code, use_compressed_history, turn
            )
            turn_results["moderator"] = mod_response
            turn_prompts["moderator"] = mod_prompt
            
            # Save turn results
            results["turns"].append(turn_results)
            results["prompts"].append(turn_prompts)
            
            # Step 4: Check if more evidence needed for NEXT turn
            need_evidence_next_turn = self.evidence_coordinator.check_if_evidence_needed(mod_response, self.verbose)
            
            if not need_evidence_next_turn:
                if self.verbose:
                    print(f"\n{'*'*60}")
                    print(f"Moderator: No more evidence needed - Ending debate")
                    print(f"{'*'*60}\n")
                break
            
            # If this is the last turn, don't gather evidence
            if turn >= self.max_turns:
                need_evidence_next_turn = False
        
        # Final step: Review Board decision
        final_decision, review_prompt = self._get_review_board_decision(code)
        results["final_decision"] = final_decision
        results["conversation_log"] = self.history_manager.get_conversation_log()
        results["review_board_prompt"] = review_prompt
        
        if self.verbose:
            print("\n" + "="*80)
            print("VulTrial Pipeline Completed")
            print("="*80)
            
            total_turns = len(results["turns"])
            if total_turns >= 3:
                print(f"\n💡 Context Management:")
                print(f"   - History compression used in turns 3+ to stay within token limits")
                print(f"   - Evidence limited to top 5 most relevant items per assistant")
            print()
        
        return results
    
    def _handle_sr_turn(
        self,
        code: str,
        turn: int,
        use_compressed_history: bool,
        initial_context: str,
        pending_evidence: Optional[Dict[str, Any]]
    ) -> tuple[str, str]:
        """Handle Security Researcher's turn"""
        if self.logger:
            self.logger.log_agent_start("security_researcher", turn)
        
        # Build chat history
        sr_chat_history = self.history_manager.build_history_for_agent(
            "security_researcher", use_compressed_history, turn
        )
        
        # Add initial context only in first turn
        if turn == 1 and initial_context:
            sr_chat_history = initial_context + sr_chat_history
        
        # Add evidence from previous turn if available
        evidence_msg = self.evidence_coordinator.format_evidence_for_agent(pending_evidence, "Security Researcher")
        if evidence_msg:
            sr_chat_history += evidence_msg
        
        researcher_input = {
            "code": code,
            "chat_history": sr_chat_history
        }
        
        # Store COMPLETE prompt for output
        sr_prompt = self.security_researcher.role_description + "\n\n"
        sr_prompt += sr_chat_history + "\n\n"
        sr_prompt += f"<code>\n{code}\n</code>"
        
        if self.logger:
            self.logger.log_agent_prompt("security_researcher", sr_prompt)
        
        researcher_response = self.security_researcher.process(researcher_input)
        self.history_manager.add_message("security_researcher", researcher_response)
        
        if self.logger:
            tokens_used = self.security_researcher.last_tokens_used
            self.logger.log_agent_response("security_researcher", researcher_response, tokens_used)
        
        return researcher_response, sr_prompt
    
    def _handle_ca_turn(
        self,
        code: str,
        turn: int,
        use_compressed_history: bool,
        initial_context: str,
        pending_evidence: Optional[Dict[str, Any]]
    ) -> tuple[str, str]:
        """Handle Code Author's turn"""
        if self.logger:
            self.logger.log_agent_start("code_author", turn)
        
        # Build chat history
        author_chat_history = self.history_manager.build_history_for_agent(
            "code_author", use_compressed_history, turn
        )
        
        # Add initial context only in first turn
        if turn == 1 and initial_context:
            author_chat_history = initial_context + author_chat_history
        
        # Add evidence from previous turn if available
        evidence_msg = self.evidence_coordinator.format_evidence_for_agent(pending_evidence, "Code Author")
        if evidence_msg:
            author_chat_history += evidence_msg
        
        author_input = {
            "code": code,
            "chat_history": author_chat_history
        }
        
        # Store COMPLETE prompt for output
        ca_prompt = self.code_author.role_description + "\n\n"
        ca_prompt += author_chat_history + "\n\n"
        ca_prompt += f"<code>\n{code}\n</code>"
        
        if self.logger:
            self.logger.log_agent_prompt("code_author", ca_prompt)
        
        author_response = self.code_author.process(author_input)
        self.history_manager.add_message("code_author", author_response)
        
        if self.logger:
            tokens_used = self.code_author.last_tokens_used
            self.logger.log_agent_response("code_author", author_response, tokens_used)
        
        return author_response, ca_prompt
    
    def _handle_moderator_turn(
        self,
        code: str,
        use_compressed_history: bool,
        turn: int
    ) -> tuple[str, str]:
        """Handle Moderator's turn"""
        if self.logger:
            self.logger.log_agent_start("moderator", turn)
        
        moderator_chat_history = self.history_manager.build_history_for_agent(
            "moderator", use_compressed_history, turn
        )
        
        moderator_input = {
            "code": code,
            "chat_history": moderator_chat_history
        }
        
        # Store COMPLETE prompt for output
        mod_prompt = self.moderator.role_description + "\n\n"
        mod_prompt += moderator_chat_history + "\n\n"
        mod_prompt += f"<code>\n{code}\n</code>"
        
        moderator_response = self.moderator.process(moderator_input)
        self.history_manager.add_message("moderator", moderator_response)
        
        if self.logger:
            tokens_used = self.moderator.last_tokens_used
            self.logger.log_agent_response("moderator", moderator_response, tokens_used)
        
        return moderator_response, mod_prompt
    
    def _get_review_board_decision(self, code: str) -> tuple[str, str]:
        """Get final Review Board decision"""
        if self.verbose:
            print(f"\n{'#'*80}")
            print(f"# FINAL REVIEW BOARD DECISION")
            print(f"{'#'*80}\n")
        
        if self.logger:
            self.logger.log_agent_start("review_board")
        
        review_chat_history = self.history_manager.build_history_for_agent("review_board")
        review_input = {
            "code": code,
            "chat_history": review_chat_history
        }
        
        # Store COMPLETE prompt for output
        review_prompt = self.review_board.role_description + "\n\n"
        review_prompt += review_chat_history + "\n\n"
        review_prompt += f"<code>\n{code}\n</code>"
        
        if self.logger:
            self.logger.log_agent_prompt("review_board", review_prompt)
        
        final_decision = self.review_board.process(review_input)
        self.history_manager.add_message("review_board", final_decision)
        
        if self.logger:
            tokens_used = self.review_board.last_tokens_used
            self.logger.log_agent_response("review_board", final_decision, tokens_used)
            self.logger.log_decision(final_decision)
        
        return final_decision, review_prompt
    
    def _gather_sr_evidence_at_turn_start(
        self,
        turn: int,
        results: Dict[str, Any]
    ) -> Optional[Dict]:
        """Gather SR evidence at turn start (before SR responds)"""
        if self.logger:
            self.logger.log_phase(f"Evidence Gathering (for Turn {turn})")
        
        if self.verbose:
            print(f"\n{'*'*60}")
            print(f"SR Assistant gathering evidence for Turn {turn}")
            print(f"{'*'*60}\n")
        
        # Get debate from previous turn
        debate_context = self.history_manager.build_full_history()
        
        # Get SR's previous response
        prev_sr_response = ""
        for entry in reversed(self.history_manager.conversation_log):
            if entry["agent"] == "security_researcher":
                prev_sr_response = entry["message"]
                break
        
        # SR Assistant gathers evidence
        sr_evidence = {}
        if self.evidence_coordinator.sr_assistant:
            sr_evidence = self.evidence_coordinator.sr_assistant.gather_evidence(
                agent_argument=prev_sr_response,
                debate_context=debate_context,
                search_cache=self.evidence_coordinator.search_cache
            )
        
        has_sr_evidence = self.evidence_coordinator.has_evidence(sr_evidence)
        
        # Show SR evidence results
        if self.logger:
            if has_sr_evidence:
                self.logger.log_summary(f"SR Assistant: Found {len(sr_evidence['evidence'])} pieces of evidence")
            elif sr_evidence.get('needs_search') == False:
                self.logger.log_summary("SR Assistant: No search needed")
            else:
                self.logger.log_summary("SR Assistant: Searched but found nothing")
        
        # Store SR evidence (CA evidence will be added later)
        turn_evidence = {
            "security_researcher": sr_evidence,
            "code_author": {}  # Will be filled when CA gathers
        }
        results["evidence_gathered"].append(turn_evidence)
        
        return sr_evidence if has_sr_evidence else None
    
    def _gather_ca_evidence_after_sr_response(
        self,
        turn: int,
        results: Dict[str, Any]
    ) -> Optional[Dict]:
        """Gather CA evidence AFTER SR has responded (so CA sees SR's Turn 2 response)"""
        if self.verbose:
            print(f"\n{'*'*60}")
            print(f"CA Assistant gathering evidence (after seeing SR's response)")
            print(f"{'*'*60}\n")
        
        # Get updated debate context (includes SR's Turn 2 response!)
        debate_context = self.history_manager.build_full_history()
        
        # Get CA's previous response
        prev_ca_response = ""
        for entry in reversed(self.history_manager.conversation_log):
            if entry["agent"] == "code_author":
                prev_ca_response = entry["message"]
                break
        
        # CA Assistant gathers evidence (sees SR's latest refined claims!)
        # Also pass SR's evidence so CA doesn't repeat the same searches
        sr_evidence = results["evidence_gathered"][-1].get("security_researcher", {}) if results.get("evidence_gathered") else {}
        
        ca_evidence = {}
        if self.evidence_coordinator.ca_assistant:
            ca_evidence = self.evidence_coordinator.ca_assistant.gather_evidence(
                agent_argument=prev_ca_response,
                debate_context=debate_context,  # Includes SR's Turn 2 response!
                search_cache=self.evidence_coordinator.search_cache,
                sr_evidence=sr_evidence  # Pass SR's evidence to avoid duplication
            )
        
        has_ca_evidence = self.evidence_coordinator.has_evidence(ca_evidence)
        
        # Show CA evidence results
        if self.logger:
            if has_ca_evidence:
                self.logger.log_summary(f"CA Assistant: Found {len(ca_evidence['evidence'])} pieces of evidence")
            elif ca_evidence.get('needs_search') == False:
                self.logger.log_summary("CA Assistant: No search needed")
            else:
                self.logger.log_summary("CA Assistant: Searched but found nothing")
        
        # Store both evidences for output
        turn_evidence = {
            "security_researcher": results["evidence_gathered"][-1].get("security_researcher", {}) if results.get("evidence_gathered") else {},
            "code_author": ca_evidence
        }
        
        # Update or append evidence
        if results.get("evidence_gathered") and len(results["evidence_gathered"]) > 0:
            # Update the last entry with CA evidence
            results["evidence_gathered"][-1]["code_author"] = ca_evidence
        else:
            results["evidence_gathered"].append(turn_evidence)
        
        return ca_evidence if has_ca_evidence else None
    
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

