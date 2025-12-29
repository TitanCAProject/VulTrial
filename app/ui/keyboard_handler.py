"""
Input Handler Utilities

Provides utility methods for user input handling
"""

from typing import Optional


class KeyboardHandler:
    """Handle user input with defaults and confirmations"""
    
    @staticmethod
    def get_input(prompt: str, default: Optional[str] = None) -> str:
        """
        Get user input with optional default value
        
        Args:
            prompt: Prompt message
            default: Default value if user presses Enter
        
        Returns:
            User input string
        """
        # Build prompt string
        prompt_str = f"  {prompt}"
        
        # Add default hint
        if default:
            full_prompt = f"{prompt_str} [{default}]: "
        else:
            full_prompt = f"{prompt_str}: "
        
        # Get input
        user_input = input(full_prompt).strip()
        
        # Use default if empty
        if not user_input and default:
            return default
        
        return user_input
    
    @staticmethod
    def confirm(prompt: str, default: bool = True) -> bool:
        """
        Ask for yes/no confirmation
        
        Args:
            prompt: Question to ask
            default: Default value
        
        Returns:
            True for yes, False for no
        """
        default_str = "Y/n" if default else "y/N"
        response = input(f"  {prompt} ({default_str}): ").strip().lower()
        
        if not response:
            return default
        
        return response in ['y', 'yes']
    
    @staticmethod
    def press_any_key(message: str = "Press any key to continue..."):
        """Wait for user to press any key"""
        input(f"  {message}")


