"""Base agent class"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from ..models.base import BaseLLMModel


class BaseAgent(ABC):
    """Abstract base class for all agents"""
    
    def __init__(
        self,
        name: str,
        model: BaseLLMModel,
        role_description: str,
        prompt_template: str,
        receivers: Optional[List[str]] = None,
        verbose: bool = False
    ):
        """
        Initialize base agent
        
        Args:
            name: Agent name (e.g., 'security_researcher')
            model: LLM model instance
            role_description: Role-specific prompt/description
            prompt_template: Base prompt template
            receivers: List of agent names that receive this agent's messages
            verbose: Whether to print verbose output
        """
        self.name = name
        self.model = model
        self.role_description = role_description
        self.prompt_template = prompt_template
        self.receivers = receivers or []
        self.verbose = verbose
        
        # Memory/conversation history
        self.conversation_history: List[Dict[str, Any]] = []
        
    def add_to_history(self, role: str, content: str, metadata: Optional[Dict] = None):
        """
        Add a message to conversation history
        
        Args:
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            metadata: Optional metadata
        """
        entry = {
            'role': role,
            'content': content,
        }
        if metadata:
            entry['metadata'] = metadata
        
        self.conversation_history.append(entry)
    
    def get_history_as_messages(self) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM
        
        Returns:
            List of message dicts for LLM input
        """
        return [
            {'role': msg['role'], 'content': msg['content']}
            for msg in self.conversation_history
        ]
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation_history = []
    
    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> str:
        """
        Process input and generate response
        
        Args:
            input_data: Input data dict
            
        Returns:
            Agent's response text
        """
        pass
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', model={self.model})"

