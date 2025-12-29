"""
First Run Experience

Onboarding wizard for new users
"""

import os
from pathlib import Path
from typing import Optional, Tuple

from .components import (
    colored, Colors, print_header, print_success, print_error, 
    print_info, print_warning, print_divider, print_banner
)
from .keyboard_handler import KeyboardHandler
from .constants import UIConstants


class FirstRunWizard:
    """Guide users through initial setup"""
    
    @staticmethod
    def is_first_run(config_manager) -> bool:
        """
        Check if this is the first run
        
        Returns:
            True if first run (no config or no model set up)
        """
        # Check if config file exists
        config_path = Path(config_manager.get_config_path())
        if not config_path.exists():
            return True
        
        # Check if model is configured
        model_type = config_manager.get("model_type")
        if not model_type:
            return True
        
        # Check if API key is set
        api_key_set = FirstRunWizard._check_api_key(model_type)
        if not api_key_set:
            return True
        
        return False
    
    @staticmethod
    def _check_api_key(model_type: str) -> bool:
        """Check if API key is set for the model"""
        key_vars = {
            'claude': 'ANTHROPIC_API_KEY',
            'openai': 'OPENAI_API_KEY',
            'grok': 'XAI_API_KEY',
            'gemini': 'GOOGLE_API_KEY'
        }
        
        key_var = key_vars.get(model_type)
        if not key_var:
            return False
        
        return bool(os.getenv(key_var))
    
    @staticmethod
    def run_wizard(config_manager) -> Tuple[bool, Optional[any]]:
        """
        Run the first-run setup wizard
        
        Args:
            config_manager: ConfigManager instance
        
        Returns:
            Tuple of (success, model_instance)
        """
        print_banner()
        print()
        print_header("Welcome to VulTrial! 🎉", Colors.BRIGHT_CYAN)
        print()
        print(colored("  VulTrial uses AI agents to find security vulnerabilities in your code.", Colors.BRIGHT_WHITE))
        print(colored("  Let's get you set up in a few quick steps.", Colors.BRIGHT_WHITE))
        print()
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        
        # Step 1: Choose provider
        print()
        print(colored("  Step 1: Choose AI Provider", Colors.BRIGHT_CYAN, bold=True))
        print()
        
        providers = [
            ("1", "Claude (Anthropic)", "claude", "ANTHROPIC_API_KEY", "Security analysis"),
            ("2", "OpenAI (ChatGPT)", "openai", "OPENAI_API_KEY", "General code analysis"),
            ("3", "Grok (xAI)", "grok", "XAI_API_KEY", "Fast analysis"),
            ("4", "Gemini (Google)", "gemini", "GOOGLE_API_KEY", "Free tier, large context"),
        ]
        
        for num, name, _, _, best_for in providers:
            marker = colored('(Recommended)', Colors.BRIGHT_GREEN) if num == "1" else ""
            print(f"  {colored(num, Colors.BRIGHT_CYAN)}. {name:25s} {marker}")
            print(f"      • Best for: {best_for}")
        
        print()
        print(colored("  (Press Ctrl+C to exit setup)", Colors.DIM))
        print()
        
        try:
            provider_choice = KeyboardHandler.get_input("Select provider (1-4)", "1")
        except KeyboardInterrupt:
            print("\n")
            print_info("Setup cancelled")
            print()
            return False, None
        
        if provider_choice not in ['1', '2', '3', '4']:
            provider_choice = '1'  # Default to Claude
        
        _, provider_name, type_id, api_key_var, _ = providers[int(provider_choice) - 1]
        
        # Step 1.5: Enter model ID
        print()
        print(colored("  Step 1.5: Enter Model ID", Colors.BRIGHT_CYAN, bold=True))
        print()
        
        # Show examples based on provider
        model_examples = {
            "claude": [
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-haiku-20240307",
            ],
            "openai": [
                "gpt-4o",
                "gpt-4-turbo",
                "gpt-4",
            ],
            "grok": [
                "grok-2-1212",
                "grok-beta",
            ],
            "gemini": [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
            ],
        }
        
        examples = model_examples.get(type_id, [])
        
        print(colored("  Common model IDs:", Colors.BRIGHT_WHITE))
        for example in examples:
            print(f"    • {colored(example, Colors.BRIGHT_CYAN)}")
        
        print()
        print(colored("  (Press Ctrl+C to cancel)", Colors.DIM))
        print()
        
        default_ids = {
            "claude": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o",
            "grok": "grok-2-1212",
            "gemini": "gemini-1.5-pro",
        }
        default_model_id = default_ids.get(type_id, "")
        
        try:
            model_id = KeyboardHandler.get_input("Model ID", default_model_id)
        except KeyboardInterrupt:
            print("\n")
            print_info("Setup cancelled")
            print()
            return False, None
        
        if not model_id:
            model_id = default_model_id
        
        print()
        print_success(f"Model ID: {colored(model_id, Colors.BRIGHT_MAGENTA, bold=True)}")
        print_info(f"Provider: {provider_name}")
        
        # Step 2: Check API key
        print()
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print()
        print(colored("  Step 2: API Key Setup", Colors.BRIGHT_CYAN, bold=True))
        print()
        
        api_key_set = bool(os.getenv(api_key_var))
        
        if api_key_set:
            print_success(f"{api_key_var} is set!")
        else:
            print_warning(f"{api_key_var} not found in environment")
            print()
            print(colored("  To set your API key:", Colors.BRIGHT_WHITE))
            print()
            print(colored(f"  export {api_key_var}=\"your-api-key-here\"", Colors.BRIGHT_YELLOW))
            print()
            print(colored("  Or add it to your ~/.bashrc or ~/.zshrc to persist", Colors.BRIGHT_BLACK))
            print()
            
            try:
                if not KeyboardHandler.confirm("Have you set the API key now?", default=False):
                    print()
                    print_info("You can set it up later and run VulTrial again")
                    print_info("Saving configuration for when you're ready...")
                    
                    # Save config even without API key
                    config_manager.set_model_config(type_id, model_id)
                    
                    print()
                    print_divider("─", 70, Colors.BRIGHT_BLACK)
                    print()
                    print(colored("  Setup incomplete - Please set your API key and restart", Colors.BRIGHT_YELLOW))
                    print()
                    return False, None
            except KeyboardInterrupt:
                print("\n")
                print_info("Setup cancelled")
                print()
                return False, None
        
        # Step 3: Save configuration
        print()
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print()
        print(colored("  Step 3: Finalizing Setup", Colors.BRIGHT_CYAN, bold=True))
        print()
        
        # Save model config
        config_manager.set_model_config(type_id, model_id)
        
        # Try to initialize model
        try:
            from ..models import ClaudeModel, OpenAIModel, GrokModel, GeminiModel
            
            temperature = UIConstants.DEFAULT_TEMPERATURE
            max_tokens = UIConstants.DEFAULT_MAX_TOKENS
            
            if type_id == "claude":
                model = ClaudeModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            elif type_id == "openai":
                model = OpenAIModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            elif type_id == "grok":
                model = GrokModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            elif type_id == "gemini":
                model = GeminiModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            else:
                model = None
            
            print_success("Model initialized successfully!")
            print()
            print_divider("─", 70, Colors.BRIGHT_BLACK)
            print()
            print(colored("  🎉 Setup Complete!", Colors.BRIGHT_GREEN, bold=True))
            print()
            print(colored("  Next steps:", Colors.BRIGHT_WHITE))
            print(f"    {colored('1.', Colors.BRIGHT_CYAN)} Select a codebase to analyze")
            print(f"    {colored('2.', Colors.BRIGHT_CYAN)} Choose a file")
            print(f"    {colored('3.', Colors.BRIGHT_CYAN)} Run vulnerability analysis")
            print()
            print_divider("─", 70, Colors.BRIGHT_BLACK)
            print()
            
            KeyboardHandler.press_any_key("Press Enter to continue to main menu...")
            
            return True, model
            
        except Exception as e:
            print_error(f"Failed to initialize model: {e}")
            print()
            print_warning("This usually means:")
            print(f"  • Your API key is incorrect or expired")
            print(f"  • You don't have access to {name}")
            print(f"  • Network connection issues")
            print()
            print_info(f"Please check your {api_key_var} and try again")
            print()
            
            return False, None
    
    @staticmethod
    def show_quick_start_tip():
        """Show a quick start tip after wizard"""
        print()
        print(colored("  💡 Quick Tip:", Colors.BRIGHT_YELLOW, bold=True))
        print(colored("     Try analyzing one of the demo files first:", Colors.BRIGHT_WHITE))
        print(colored("     → data/demo-py/ or data/demo1/", Colors.BRIGHT_CYAN))
        print()

