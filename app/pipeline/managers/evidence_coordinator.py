"""Coordinates evidence gathering between research assistants"""

import json
from typing import Dict, Any, Optional
from ...context.research_assistant import ResearchAssistant


class EvidenceCoordinator:
    """Coordinates evidence gathering across research assistants"""
    
    def __init__(
        self,
        sr_assistant: Optional[ResearchAssistant],
        ca_assistant: Optional[ResearchAssistant],
        search_cache: Dict[str, Any],
        verbose: bool = False
    ):
        """
        Initialize evidence coordinator
        
        Args:
            sr_assistant: Security Researcher's research assistant
            ca_assistant: Code Author's research assistant
            search_cache: Shared search cache
            verbose: Whether to print verbose output
        """
        self.sr_assistant = sr_assistant
        self.ca_assistant = ca_assistant
        self.search_cache = search_cache
        self.verbose = verbose
    
    def prepare_initial_context(
        self,
        target_code: str,
        input_metadata: Dict[str, Any]
    ) -> str:
        """
        Prepare initial context summary before debate
        
        Args:
            target_code: The code to analyze
            input_metadata: Metadata about what's being analyzed
            
        Returns:
            Formatted context string
        """
        if not self.sr_assistant:
            return ""
        
        return self.sr_assistant.prepare_initial_context(
            target_code=target_code,
            input_metadata=input_metadata,
            search_cache=self.search_cache
        )
    
    def gather_evidence_for_turn(
        self,
        sr_response: str,
        ca_response: str,
        debate_context: str
    ) -> Dict[str, Any]:
        """
        Gather evidence from both assistants for the current turn
        
        Args:
            sr_response: Security Researcher's response
            ca_response: Code Author's response
            debate_context: Full debate context
            
        Returns:
            Dict with evidence from both assistants
        """
        if not self.sr_assistant or not self.ca_assistant:
            return {}
        
        # Both assistants gather evidence
        sr_evidence = self.sr_assistant.gather_evidence(
            agent_argument=sr_response,
            debate_context=debate_context,
            search_cache=self.search_cache
        )
        
        ca_evidence = self.ca_assistant.gather_evidence(
            agent_argument=ca_response,
            debate_context=debate_context,
            search_cache=self.search_cache
        )
        
        return {
            "security_researcher": sr_evidence,
            "code_author": ca_evidence
        }
    
    def format_evidence_for_agent(self, evidence: Dict[str, Any], agent_name: str) -> Optional[str]:
        """
        Format evidence for agent consumption
        
        Args:
            evidence: Evidence dict from research assistant
            agent_name: Name of the agent receiving the evidence
            
        Returns:
            Formatted evidence string or None if no evidence
        """
        if not evidence or not evidence.get('needs_search') or not evidence.get('evidence'):
            return None
        
        evidence_msg = f"\n[YOUR ASSISTANT'S EVIDENCE]:\n{evidence['summary']}\n"
        evidence_msg += f"\n\nBased on the evidence above, strengthen your argument or respond to the opponent's claims:"
        
        if self.verbose:
            print(f"  → {agent_name} using evidence from previous turn\n")
        
        return evidence_msg
    
    @staticmethod
    def check_if_evidence_needed(moderator_response: str, verbose: bool = False) -> bool:
        """
        Extract need_more_evidence from moderator response
        
        Args:
            moderator_response: JSON response from moderator
            verbose: Whether to print verbose output
            
        Returns:
            Boolean indicating if more evidence is needed
        """
        try:
            # Try to extract JSON from response
            response_clean = moderator_response.strip()
            if '```json' in response_clean:
                response_clean = response_clean.split('```json')[1].split('```')[0]
            elif '```' in response_clean:
                response_clean = response_clean.split('```')[1].split('```')[0]
            
            moderator_data = json.loads(response_clean)
            need_evidence = moderator_data.get('need_more_evidence', False)
            
            return bool(need_evidence)
            
        except Exception as e:
            if verbose:
                print(f"[Moderator] Could not parse need_more_evidence: {e}")
            return False
    
    def has_evidence(self, evidence: Dict[str, Any]) -> bool:
        """
        Check if evidence dict contains actual evidence
        
        Args:
            evidence: Evidence dict from research assistant
            
        Returns:
            True if evidence was found, False otherwise
        """
        return bool(evidence.get('needs_search') and evidence.get('evidence'))

