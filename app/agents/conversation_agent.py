"""Conversation agent implementation"""

from typing import Dict, Any, Optional, List
from .base_agent import BaseAgent
from ..models.base import BaseLLMModel


class ConversationAgent(BaseAgent):
    """Agent that engages in conversations using an LLM"""
    
    def __init__(
        self,
        name: str,
        model: BaseLLMModel,
        role_description: str,
        receivers: Optional[List[str]] = None,
        verbose: bool = False
    ):
        """
        Initialize conversation agent
        
        Args:
            name: Agent name (e.g., 'security_researcher')
            model: LLM model instance
            role_description: Role-specific prompt/description
            receivers: List of agent names that receive this agent's messages
            verbose: Whether to print verbose output
        """
        super().__init__(
            name=name,
            model=model,
            role_description=role_description,
            prompt_template="",  # Not needed since we build messages directly
            receivers=receivers,
            verbose=verbose
        )
        
        # Track last token usage for cost calculation
        self.last_tokens_used = None
    
    def update_role_description(self, new_role_description: str):
        """
        Update the agent's role description (for consensus mode turn switching)
        
        Args:
            new_role_description: New role prompt to use
        """
        self.role_description = new_role_description
    
    def process(self, input_data: Dict[str, Any]) -> str:
        """
        Process input and generate response
        
        Args:
            input_data: Dict containing:
                - 'code': The code snippet to analyze
                - 'chat_history': Optional conversation history string
                - Any other context needed
                
        Returns:
            Agent's response text
        """
        # Build the prompt
        code = input_data.get('code', '')
        chat_history = input_data.get('chat_history', '')
        
        # Construct the user message
        user_message = self.role_description + "\n\n"
        
        if chat_history:
            user_message += f"{chat_history}\n\n"
        
        user_message += f"<code>\n{code}\n</code>"
        
        # Build messages for LLM
        messages = [
            {"role": "user", "content": user_message}
        ]
        
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Agent: {self.name}")
            print(f"{'='*60}")
            print(f"Input:\n{user_message}")
            print(f"{'='*60}")
        
        # Generate response with token tracking
        try:
            result = self.model.generate_with_metadata(messages)
            response = result.get('content', result.get('response', ''))
            self.last_tokens_used = result.get('tokens_used', None)
        except (AttributeError, NotImplementedError):
            # Fallback if generate_with_metadata not available
            response = self.model.generate(messages)
            self.last_tokens_used = None
        
        # Store in history
        self.add_to_history('user', user_message)
        self.add_to_history('assistant', response)
        
        if self.verbose:
            print(f"Response:\n{response}")
            if self.last_tokens_used:
                total = self.last_tokens_used.get('total', 0)
                print(f"Tokens used: {total}")
            print(f"{'='*60}\n")
        
        return response

