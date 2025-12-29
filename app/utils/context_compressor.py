"""Context compression utilities for managing prompt size"""

import re
from typing import List, Dict, Any, Optional


class ContextCompressor:
    """Compress context to stay within token limits while preserving key information"""
    
    # Approximate tokens estimation (1 token ≈ 4 characters for English)
    CHARS_PER_TOKEN = 4
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for text
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // ContextCompressor.CHARS_PER_TOKEN
    
    @staticmethod
    def compress_chat_history(
        conversation_log: List[Dict[str, str]],
        current_turn: int,
        max_tokens: int = 8000
    ) -> str:
        """
        Compress chat history intelligently based on turn number
        
        Strategy:
        - Keep recent turns in full
        - For older turns, keep only moderator summaries
        - Drop verbose evidence and detailed arguments from old turns
        
        Args:
            conversation_log: List of conversation entries
            current_turn: Current turn number
            max_tokens: Maximum tokens for history
            
        Returns:
            Compressed chat history string
        """
        if not conversation_log:
            return ""
        
        # Group messages by turn (approximately)
        # Assume SR → CA → Moderator → SR_enhanced → CA_enhanced pattern
        compressed_parts = []
        
        # For turn 3+, we only keep moderator summaries from turn 1
        # For turn 2+, we keep last turn in full
        
        # Find moderator responses (they contain summaries)
        moderator_responses = []
        for entry in conversation_log:
            if entry["agent"] == "moderator":
                moderator_responses.append(entry["message"])
        
        if current_turn >= 3:
            # LATEST FIRST: Show recent turn first, then older summaries for context
            recent_messages = conversation_log[-8:]  # Last ~2 turns worth
            
            # Add recent messages FIRST (most important)
            compressed_parts.append("[LATEST DISCUSSION]:\n")
            for entry in recent_messages:
                agent = entry["agent"]
                message = entry["message"]
                # Truncate very long messages
                if len(message) > 2000:
                    message = message[:2000] + "\n...[truncated for brevity]..."
                compressed_parts.append(f"[{agent.upper()}]:\n{message}\n\n")
            
            # Add moderator summaries from older turns SECOND (context)
            if len(moderator_responses) > 1:
                compressed_parts.append("\n[EARLIER TURNS SUMMARY]:\n")
                for i, mod_resp in enumerate(moderator_responses[:-1], 1):
                    # Extract just the summary part
                    summary = ContextCompressor._extract_moderator_summary(mod_resp)
                    compressed_parts.append(f"Turn {i}: {summary}\n")
                compressed_parts.append("\n")
        
        else:
            # Turn 1-2: Keep full history but truncate if needed
            for entry in conversation_log:
                agent = entry["agent"]
                message = entry["message"]
                compressed_parts.append(f"[{agent.upper()}]:\n{message}\n\n")
        
        full_history = "".join(compressed_parts)
        
        # If still too long, do aggressive compression
        if ContextCompressor.estimate_tokens(full_history) > max_tokens:
            full_history = ContextCompressor._aggressive_compress(full_history, max_tokens)
        
        return full_history
    
    @staticmethod
    def _extract_moderator_summary(moderator_response: str) -> str:
        """Extract key summary from moderator response"""
        try:
            # Try to extract JSON
            if '```json' in moderator_response:
                json_part = moderator_response.split('```json')[1].split('```')[0]
            elif '```' in moderator_response:
                json_part = moderator_response.split('```')[1].split('```')[0]
            else:
                json_part = moderator_response
            
            import json
            data = json.loads(json_part)
            
            # Extract summaries
            sr_summary = data.get('researcher_summary', '')
            ca_summary = data.get('author_summary', '')
            need_evidence = data.get('need_more_evidence', False)
            
            summary = f"SR: {sr_summary[:200]}... | CA: {ca_summary[:200]}... | Need evidence: {need_evidence}"
            return summary
        
        except:
            # Fallback: just take first 300 chars
            return moderator_response[:300] + "..."
    
    @staticmethod
    def _aggressive_compress(text: str, max_tokens: int) -> str:
        """Aggressively compress text to fit token limit"""
        target_chars = max_tokens * ContextCompressor.CHARS_PER_TOKEN
        
        if len(text) <= target_chars:
            return text
        
        # Keep the most recent portion
        return "...[earlier discussion compressed]...\n\n" + text[-target_chars:]
    
    @staticmethod
    def compress_evidence(
        evidence_list: List[Dict[str, Any]],
        max_items: int = 5,
        max_tokens_per_item: int = 1000,
        max_lines_per_item: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Compress evidence list to top N items with size limits
        
        Args:
            evidence_list: List of evidence items
            max_items: Maximum number of evidence items to keep
            max_tokens_per_item: Maximum tokens per evidence item
            max_lines_per_item: Maximum lines per evidence item
            
        Returns:
            Compressed evidence list with 'needs_summarization' flag for large items
        """
        if not evidence_list:
            return []
        
        # Take top N items
        compressed = evidence_list[:max_items]
        
        # Check each item and mark for summarization if too large
        for item in compressed:
            code = item.get('code') or item.get('context', '')
            
            if code:
                lines_count = code.count('\n') + 1
                estimated_tokens = ContextCompressor.estimate_tokens(code)
                
                # Mark for summarization if exceeds EITHER token OR line limit
                # This handles extreme cases (huge functions with 500+ lines, 3000+ tokens)
                if estimated_tokens > max_tokens_per_item or lines_count > max_lines_per_item:
                    item['needs_summarization'] = True
                    item['original_size'] = len(code)
                    item['original_lines'] = lines_count
                    item['estimated_tokens'] = estimated_tokens
                else:
                    item['needs_summarization'] = False
        
        return compressed
    
    @staticmethod
    def should_summarize_evidence(evidence_item: Dict[str, Any]) -> bool:
        """
        Check if evidence item should be summarized
        
        Args:
            evidence_item: Evidence dictionary
            
        Returns:
            True if should summarize, False otherwise
        """
        code = evidence_item.get('code') or evidence_item.get('context', '')
        
        if not code:
            return False
        
        # Count lines
        lines = code.count('\n') + 1
        
        # Summarize if:
        # - More than 100 lines
        # - More than 500 tokens estimated
        if lines > 100:
            return True
        
        if ContextCompressor.estimate_tokens(code) > 500:
            return True
        
        return False
    
    @staticmethod
    def truncate_code(code: str, max_lines: int = 100) -> str:
        """
        Intelligently truncate code to max lines, keeping beginning and end
        
        For extreme cases (500+ line functions), we keep:
        - First section: function signature, key logic
        - Last section: return statements, cleanup
        
        Args:
            code: Code string
            max_lines: Maximum lines to keep (default: 100)
            
        Returns:
            Truncated code with ellipsis marker
        """
        lines = code.split('\n')
        
        if len(lines) <= max_lines:
            return code
        
        # For very large functions (500+ lines), be more aggressive
        # Keep first 60% and last 40% of the max_lines budget
        keep_start = int(max_lines * 0.6)
        keep_end = max_lines - keep_start
        
        truncated_lines = (
            lines[:keep_start] +
            [f"", f"... [truncated {len(lines) - max_lines} lines - function body continues] ...", ""] +
            lines[-keep_end:]
        )
        
        return '\n'.join(truncated_lines)

