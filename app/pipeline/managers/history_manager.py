"""Manages conversation history with smart compression"""

from typing import List, Dict
from ...utils.context_compressor import ContextCompressor


class HistoryManager:
    """Manages conversation history with smart compression"""
    
    def __init__(self, compression_start_turn: int = 3, compression_token_budget: int = 8000):
        """
        Initialize history manager
        
        Args:
            compression_start_turn: Turn number to start compressing history
            compression_token_budget: Token budget for compressed history
        """
        self.conversation_log: List[Dict[str, str]] = []
        self.compression_start_turn = compression_start_turn
        self.compression_token_budget = compression_token_budget
    
    def add_message(self, agent_name: str, message: str):
        """
        Add message to conversation log
        
        Args:
            agent_name: Name of the agent
            message: Message content
        """
        self.conversation_log.append({
            "agent": agent_name,
            "message": message
        })
    
    def build_history_for_agent(
        self,
        agent_name: str,
        use_compression: bool = False,
        current_turn: int = 1
    ) -> str:
        """
        Build chat history string for an agent
        
        Args:
            agent_name: Name of the agent receiving the history
            use_compression: Whether to compress old history
            current_turn: Current turn number
            
        Returns:
            Formatted chat history string
        """
        if not self.conversation_log:
            return ""
        
        # If compression enabled, use smart compression
        if use_compression and current_turn >= self.compression_start_turn:
            return ContextCompressor.compress_chat_history(
                self.conversation_log,
                current_turn,
                max_tokens=self.compression_token_budget
            )
        
        # REVIEW BOARD: Only final turn + moderator summaries
        if agent_name == "review_board":
            history_parts = []
            
            # Get final turn (last SR, CA, Moderator)
            final_turn = []
            for entry in reversed(self.conversation_log):
                final_turn.insert(0, entry)
                # Stop after we have SR, CA, Moderator
                if len(final_turn) >= 3:
                    break
            
            history_parts.append("[FINAL TURN - Make decision based on this]:\n")
            for entry in final_turn:
                agent = entry["agent"]
                message = entry["message"]
                history_parts.append(f"[{agent.upper()}]:\n{message}\n")
            
            # Add moderator summaries from previous turns (context only)
            if len(self.conversation_log) > 3:
                moderator_summaries = []
                turn_num = 1
                for entry in self.conversation_log[:-3]:
                    if entry["agent"] == "moderator":
                        moderator_summaries.append((turn_num, entry["message"]))
                        turn_num += 1
                
                if moderator_summaries:
                    history_parts.append("\n[DEBATE EVOLUTION - Previous moderator summaries]:\n")
                    for turn, summary in moderator_summaries:
                        history_parts.append(f"Turn {turn}: {summary[:200]}...\n\n")
            
            return "\n".join(history_parts)
        
        # MODERATOR: Current turn first + previous summaries
        elif agent_name == "moderator":
            history_parts = []
            
            # Add current turn (last 2 messages: SR, CA)
            recent_entries = self.conversation_log[-2:] if len(self.conversation_log) >= 2 else self.conversation_log
            
            history_parts.append("[CURRENT TURN - Focus on this]:\n")
            for entry in recent_entries:
                agent = entry["agent"]
                message = entry["message"]
                history_parts.append(f"[{agent.upper()}]:\n{message}\n")
            
            # Add previous moderator summaries only (not full SR/CA)
            if len(self.conversation_log) > 2:
                moderator_summaries = []
                turn_num = 1
                for entry in self.conversation_log[:-2]:
                    if entry["agent"] == "moderator":
                        moderator_summaries.append((turn_num, entry["message"]))
                        turn_num += 1
                
                if moderator_summaries:
                    history_parts.append("\n[PREVIOUS SUMMARIES]:\n")
                    for turn, summary in moderator_summaries:
                        history_parts.append(f"Turn {turn}: {summary[:150]}...\n")
            
            return "\n".join(history_parts)
        else:
            # SR and CA: Optimized ordering based on current turn
            history_parts = []
            
            # Group messages by turn (rough grouping: every 3-4 messages is a turn)
            # Find SR, CA, Moderator from latest turn
            latest_turn = []
            moderator_summaries = []
            
            # Collect latest turn messages and moderator summaries
            current_turn_num = 1
            temp_turn = []
            
            for entry in self.conversation_log:
                temp_turn.append(entry)
                
                # When we see a moderator, that's end of a turn
                if entry["agent"] == "moderator":
                    if len(self.conversation_log) - len(temp_turn) < 5:
                        # This is the latest turn
                        latest_turn = temp_turn.copy()
                    else:
                        # This is an earlier turn - save moderator summary
                        moderator_summaries.append((current_turn_num, entry["message"]))
                    
                    temp_turn = []
                    current_turn_num += 1
            
            # If no moderator yet in current turn, latest turn is everything
            if not latest_turn and temp_turn:
                latest_turn = temp_turn
            
            # Build history based on agent type
            if agent_name == "security_researcher":
                # SR sees: Last SR → CA → Moderator → evidence → earlier moderators
                history_parts.append("[THIS TURN]:\n")
            else:  # code_author
                # CA sees: This turn SR → SR evidence → CA evidence → last turn → earlier moderators
                history_parts.append("[THIS TURN]:\n")
            
            for entry in latest_turn:
                agent = entry["agent"]
                message = entry["message"]
                history_parts.append(f"[{agent.upper()}]:\n{message}\n")
            
            # Add earlier moderator summaries for context
            if moderator_summaries:
                history_parts.append("\n[EARLIER TURNS]:\n")
                for turn, summary in moderator_summaries:
                    history_parts.append(f"Turn {turn} Moderator: {summary[:200]}...\n\n")
            
            return "\n".join(history_parts)
    
    def build_full_history(self) -> str:
        """
        Build complete uncompressed chat history
        
        Returns:
            Full conversation history
        """
        return self.build_history_for_agent("", use_compression=False)
    
    def clear(self):
        """Clear conversation log"""
        self.conversation_log = []
    
    def get_conversation_log(self) -> List[Dict[str, str]]:
        """
        Get raw conversation log
        
        Returns:
            List of conversation entries
        """
        return self.conversation_log

