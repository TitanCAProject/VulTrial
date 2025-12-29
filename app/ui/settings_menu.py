"""
Settings Menu

Organized settings management
"""

from typing import Any
from .components import colored, Colors, print_header, print_success, print_error, print_info, print_warning, print_divider
from .keyboard_handler import KeyboardHandler
from .constants import UIConstants
from .path_utils import resolve_directory

from ..models import ClaudeModel, OpenAIModel, GrokModel, GeminiModel


class SettingsMenu:
    """Settings management with organized sections"""
    
    @staticmethod
    def show_settings(config_manager) -> Any:
        """
        Show settings menu and handle configuration
        
        Args:
            config_manager: ConfigManager instance
        
        Returns:
            Updated model if changed, or None
        """
        updated_model = None
        
        while True:
            try:
                config = config_manager.get_all()
                
                print_header("Settings & Preferences", Colors.BRIGHT_CYAN)
                print()
                print_info(f"Config file: {colored(config_manager.get_config_path(), Colors.BRIGHT_BLACK)}")
                print()
                
                # Model settings
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(colored("  AI Model", Colors.BRIGHT_WHITE, bold=True))
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                current_model = f"{config.get('model_type')} ({config.get('model_id')})"
                print(f"  {colored('1', Colors.BRIGHT_CYAN)}. 🤖  Current: {colored(current_model, Colors.BRIGHT_MAGENTA, bold=True)}")
                
                # Check if model has temperature restriction
                model_id = config.get('model_id', '')
                model_lower = model_id.lower() if model_id else ''
                temp_restricted = 'o1' in model_lower or 'o3' in model_lower or 'gpt-5' in model_lower
                
                if temp_restricted:
                    print(f"  {colored('2', Colors.BRIGHT_CYAN)}. 🎚️   Temperature: {colored('1.0', Colors.BRIGHT_YELLOW)} {colored('(fixed)', Colors.BRIGHT_BLACK)}")
                else:
                    print(f"  {colored('2', Colors.BRIGHT_CYAN)}. 🎚️   Temperature: {colored(str(config.get('temperature')), Colors.BRIGHT_YELLOW)}")
                
                print(f"  {colored('m', Colors.BRIGHT_CYAN)}. 🔢  Max Tokens: {colored(str(config.get('max_tokens', UIConstants.DEFAULT_MAX_TOKENS)), Colors.BRIGHT_YELLOW)}")
                
                # Pricing
                print()
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(colored("  Cost Tracking", Colors.BRIGHT_WHITE, bold=True))
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                
                price_in = config.get("price_input_per_million")
                price_out = config.get("price_output_per_million")
                if price_in and price_out:
                    pricing = f"${price_in} / ${price_out} per million"
                else:
                    pricing = "Not configured"
                print(f"  {colored('3', Colors.BRIGHT_CYAN)}. 💰  Pricing: {colored(pricing, Colors.BRIGHT_YELLOW)}")
                
                # Analysis settings
                print()
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(colored("  Analysis", Colors.BRIGHT_WHITE, bold=True))
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(f"  {colored('4', Colors.BRIGHT_CYAN)}. 🔄  Max Turns: {colored(str(config.get('max_turns', 3)), Colors.BRIGHT_YELLOW)}")
                print(f"  {colored('5', Colors.BRIGHT_CYAN)}. 💾  Auto-save: {colored('Yes' if config.get('auto_save_results') else 'No', Colors.BRIGHT_YELLOW)}")
                
                output_dir = config.get('output_directory', 'output')
                print(f"  {colored('o', Colors.BRIGHT_CYAN)}. 📂  Output Dir: {colored(output_dir, Colors.BRIGHT_YELLOW)}")
                
                # Advanced
                print()
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(colored("  Advanced", Colors.BRIGHT_WHITE, bold=True))
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(f"  {colored('6', Colors.BRIGHT_CYAN)}. 🎛️   Context management settings")
                
                # Actions
                print()
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(f"  {colored('9', Colors.BRIGHT_CYAN)}. 🔄  Reset to defaults")
                print(f"  {colored('0', Colors.BRIGHT_CYAN)}. ◀️   Back")
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                print(colored("  (Press Ctrl+C to go back)", Colors.DIM))
                
                choice = KeyboardHandler.get_input("\nSelect option (0-9, m, o)", None)
            
            except KeyboardInterrupt:
                print("\n")
                print_info("Returning to main menu...")
                print()
                break
            
            if choice == "0" or choice == "back":
                break
            
            elif choice == "1":
                # Change model
                new_model = SettingsMenu._configure_model(config_manager)
                if new_model:
                    updated_model = new_model  # Only update if successfully created
                    
                    # Check if model has restrictions and update config
                    model_lower = new_model.model_id.lower()
                    if 'o1' in model_lower or 'o3' in model_lower or 'gpt-5' in model_lower:
                        # Reasoning models require temperature=1.0
                        config_manager.set("temperature", 1.0)
                        new_model.temperature = 1.0
                        print()
                        print_warning("Note: This model only supports temperature=1.0 (updated automatically)")
                    
                    print()
                    print_info("Model will be active after exiting settings")
            
            elif choice == "2":
                # Temperature
                # Check if current model has temperature restrictions
                model_id = config_manager.get("model_id", "")
                model_lower = model_id.lower()
                
                if 'o1' in model_lower or 'o3' in model_lower or 'gpt-5' in model_lower:
                    print()
                    print_warning(f"Model {model_id} only supports temperature=1.0 (fixed)")
                    print_info("Temperature cannot be changed for reasoning models (o1, o3, GPT-5)")
                else:
                    SettingsMenu._set_temperature(config_manager)
                    # If model exists, update its temperature
                    if updated_model:
                        updated_model.temperature = config_manager.get("temperature")
            
            elif choice == "m":
                # Max tokens
                SettingsMenu._set_max_tokens(config_manager)
                # If model exists, update its max_tokens
                if updated_model:
                    updated_model.max_tokens = config_manager.get("max_tokens")
            
            elif choice == "3":
                # Pricing
                SettingsMenu._set_pricing(config_manager)
            
            elif choice == "4":
                # Max turns
                SettingsMenu._set_max_turns(config_manager)
            
            elif choice == "5":
                # Auto-save toggle
                current = config_manager.get("auto_save_results", True)
                config_manager.set("auto_save_results", not current)
                status = "enabled" if not current else "disabled"
                print_success(f"Auto-save {status}")
            
            elif choice == "o":
                # Output directory
                SettingsMenu._set_output_directory(config_manager)
            
            elif choice == "6":
                # Advanced settings
                SettingsMenu._show_advanced_settings(config_manager)
            
            elif choice == "9":
                # Reset
                print()
                print_warning("This will reset ALL settings to defaults!")
                print_info("You will need to reconfigure your model and API key")
                print()
                if KeyboardHandler.confirm("Are you sure you want to reset?", default=False):
                    config_manager.reset()
                    print()
                    print_success("Settings reset to defaults")
                    print_info("Please reconfigure your model in the settings menu")
                    updated_model = None  # Will need to reconfigure
            
            else:
                print_error("Invalid option")
            
            print()
        
        return updated_model
    
    @staticmethod
    def _configure_model(config_manager):
        """Configure AI model"""
        print()
        print_header("Configure AI Model", Colors.BRIGHT_MAGENTA)
        print()
        
        # Step 1: Select provider
        print(colored("  Step 1: Select AI Provider", Colors.BRIGHT_CYAN, bold=True))
        print()
        
        providers = [
            ("1", "Claude (Anthropic)", "claude"),
            ("2", "OpenAI (ChatGPT)", "openai"),
            ("3", "Grok (xAI)", "grok"),
            ("4", "Gemini (Google)", "gemini"),
        ]
        
        for num, name, type_id in providers:
            print(f"  {colored(num, Colors.BRIGHT_CYAN)}. {name}")
        
        print()
        print(colored("  (Press Ctrl+C to cancel)", Colors.DIM))
        print()
        
        try:
            provider_choice = KeyboardHandler.get_input("Select provider (1-4)", "1")
        except KeyboardInterrupt:
            print("\n")
            print_info("Model configuration cancelled")
            print()
            return None
        
        if provider_choice not in ['1', '2', '3', '4']:
            return None
        
        _, provider_name, type_id = providers[int(provider_choice) - 1]
        
        # Step 2: Enter model ID
        print()
        print(colored("  Step 2: Enter Model ID", Colors.BRIGHT_CYAN, bold=True))
        print()
        
        # Show examples based on provider
        model_examples = {
            "claude": [
                "claude-3-5-sonnet-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
                "claude-3-haiku-20240307",
            ],
            "openai": [
                "gpt-4o",
                "gpt-4-turbo",
                "gpt-4",
                "gpt-3.5-turbo",
            ],
            "grok": [
                "grok-2-1212",
                "grok-beta",
            ],
            "gemini": [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-pro",
            ],
        }
        
        examples = model_examples.get(type_id, [])
        
        print(colored("  Common model IDs:", Colors.BRIGHT_WHITE))
        for example in examples:
            print(f"    • {colored(example, Colors.BRIGHT_CYAN)}")
        
        print()
        print_info("Check your provider's documentation for the latest model IDs")
        print()
        
        # Get default from current config
        current_model_id = config_manager.get("model_id") if config_manager.get("model_type") == type_id else ""
        default_ids = {
            "claude": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4o",
            "grok": "grok-2-1212",
            "gemini": "gemini-1.5-pro",
        }
        default_model_id = current_model_id or default_ids.get(type_id, "")
        
        try:
            model_id = KeyboardHandler.get_input("Model ID", default_model_id)
        except KeyboardInterrupt:
            print("\n")
            print_info("Model configuration cancelled")
            print()
            return None
        
        if model_id:
            config_manager.set_model_config(type_id, model_id)
            print()
            print_success(f"Model configured successfully!")
            print_info(f"Provider: {colored(provider_name, Colors.BRIGHT_MAGENTA)}")
            print_info(f"Model ID: {colored(model_id, Colors.BRIGHT_CYAN)}")
            
            # Create model instance
            try:
                temperature = config_manager.get("temperature", UIConstants.DEFAULT_TEMPERATURE)
                max_tokens = config_manager.get("max_tokens", UIConstants.DEFAULT_MAX_TOKENS)
                
                # Check if model has temperature restrictions (OpenAI reasoning models)
                model_lower = model_id.lower() if model_id else ''
                if type_id == "openai":
                    if 'o1' in model_lower or 'o3' in model_lower or 'gpt-5' in model_lower:
                        # Force temperature=1.0 for reasoning models
                        temperature = 1.0
                        config_manager.set("temperature", 1.0)
                
                if type_id == "claude":
                    return ClaudeModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
                elif type_id == "openai":
                    return OpenAIModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
                elif type_id == "grok":
                    return GrokModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
                elif type_id == "gemini":
                    return GeminiModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            except Exception as e:
                print_error(f"Failed to initialize model: {e}")
                print_info("Check that your API key is set correctly")
                return None
        
        return None
    
    @staticmethod
    def _set_temperature(config_manager):
        """Set model temperature"""
        print()
        current = config_manager.get("temperature", UIConstants.DEFAULT_TEMPERATURE)
        new_value = KeyboardHandler.get_input("Temperature (0.0-1.0)", str(current))
        
        try:
            temp = float(new_value)
            if 0.0 <= temp <= 1.0:
                config_manager.set("temperature", temp)
                print_success(f"Temperature set to {temp}")
            else:
                print_error(f"Temperature must be between 0.0 and 1.0 (you entered: {temp})")
        except ValueError:
            print_error(f"'{new_value}' is not a valid number. Please enter a decimal value like 0.7")
    
    @staticmethod
    def _set_max_tokens(config_manager):
        """Set max tokens for model responses"""
        print()
        print_header("Configure Max Tokens", Colors.BRIGHT_YELLOW)
        print()
        print_info("Maximum tokens the model can generate per response")
        print()
        print(colored("  Common Values:", Colors.BRIGHT_BLACK))
        print(colored("    • Standard:  32000 (balanced)", Colors.DIM))
        print(colored("    • Large:     64000 (long responses)", Colors.DIM))
        print(colored("    • Small:     16000 (shorter, faster)", Colors.DIM))
        print()
        print_warning("Note: Some models have maximum token limits")
        print()
        
        current = config_manager.get("max_tokens", UIConstants.DEFAULT_MAX_TOKENS)
        new_value = KeyboardHandler.get_input(f"Max tokens (1000-200000)", str(current))
        
        try:
            tokens = int(new_value)
            if 1000 <= tokens <= 200000:
                config_manager.set("max_tokens", tokens)
                print()
                print_success(f"Max tokens set to {tokens}")
            else:
                print_error(f"Max tokens must be between 1000 and 200000 (you entered: {tokens})")
        except ValueError:
            print_error(f"'{new_value}' is not a valid number. Please enter a whole number like 32000")
    
    @staticmethod
    def _set_pricing(config_manager):
        """Set pricing for cost tracking"""
        print()
        print_header("Configure Pricing", Colors.BRIGHT_YELLOW)
        print()
        print_info("Enter prices per 1 million tokens")
        print()
        print(colored("  Common Pricing:", Colors.BRIGHT_BLACK))
        print(colored("    • OpenAI GPT-4:  $2.50 / $10.00", Colors.DIM))
        print(colored("    • Claude Sonnet: $3.00 / $15.00", Colors.DIM))
        print(colored("    • Gemini Pro:    FREE", Colors.DIM))
        print()
        
        current_in = config_manager.get("price_input_per_million", "")
        input_price = KeyboardHandler.get_input("Input price ($/million)", str(current_in) if current_in else "")
        
        current_out = config_manager.get("price_output_per_million", "")
        output_price = KeyboardHandler.get_input("Output price ($/million)", str(current_out) if current_out else "")
        
        try:
            price_in = float(input_price) if input_price else None
            price_out = float(output_price) if output_price else None
            
            if price_in is not None and price_in >= 0:
                config_manager.set("price_input_per_million", price_in)
            if price_out is not None and price_out >= 0:
                config_manager.set("price_output_per_million", price_out)
            
            if price_in and price_out:
                print()
                print_success(f"Pricing set: ${price_in} / ${price_out} per million")
            else:
                print()
                print_info("Pricing cleared")
        except ValueError as e:
            print_error(f"Invalid price value. Please enter numbers like 3.0 or 15.00")
            print_error(f"Details: {str(e)}")
    
    @staticmethod
    def _set_max_turns(config_manager):
        """Set max debate turns"""
        print()
        current = config_manager.get("max_turns", UIConstants.DEFAULT_MAX_TURNS)
        new_value = KeyboardHandler.get_input("Max debate turns", str(current))
        
        try:
            turns = int(new_value)
            if turns > 0:
                config_manager.set("max_turns", turns)
                print_success(f"Max turns set to {turns}")
            else:
                print_error(f"Max turns must be a positive number (you entered: {turns})")
        except ValueError:
            print_error(f"'{new_value}' is not a valid number. Please enter a whole number like 3 or 4")
    
    @staticmethod
    def _set_output_directory(config_manager):
        """Set output directory for results"""
        print()
        print_header("Configure Output Directory", Colors.BRIGHT_YELLOW)
        print()
        print_info("Directory where analysis results will be saved")
        print()
        print(colored("  Examples:", Colors.BRIGHT_BLACK))
        print(colored("    • output (default)", Colors.DIM))
        print(colored("    • results", Colors.DIM))
        print(colored("    • /path/to/custom/output", Colors.DIM))
        print()
        
        current = config_manager.get("output_directory", "output")
        new_value = KeyboardHandler.get_input("Output directory", current)
        
        if new_value and new_value.strip():
            resolved_dir = resolve_directory(new_value, must_exist=False, create=True, show_feedback=True)
            if resolved_dir:
                config_manager.set("output_directory", str(resolved_dir))
                print()
                print_success(f"Output directory set to: {str(resolved_dir)}")
                print_info("Results will be saved to this directory")
        else:
            print_error("Output directory cannot be empty")
    
    @staticmethod
    def _show_advanced_settings(config_manager):
        """Show advanced context management settings"""
        print()
        print_header("Advanced Settings", Colors.BRIGHT_YELLOW)
        print()
        print_info("Context Management:")
        print()
        
        settings = [
            ("max_evidence_items", "Max evidence items", "5", 1, 20),
            ("max_evidence_tokens", "Max tokens per item", "1000", 500, 5000),
            ("max_evidence_lines", "Max lines per item", "100", 30, 500),
            ("history_compression_turn", "Compression start turn", "3", 2, 10),
        ]
        
        for key, name, default, min_val, max_val in settings:
            current = config_manager.get(key, default)
            print(f"  {colored(name + ':', Colors.BRIGHT_WHITE):30s} {colored(str(current), Colors.BRIGHT_YELLOW)}")
        
        print()
        if KeyboardHandler.confirm("Modify advanced settings?", default=False):
            for key, name, default, min_val, max_val in settings:
                current = config_manager.get(key, default)
                new_value = KeyboardHandler.get_input(f"{name} ({min_val}-{max_val})", str(current))
                
                try:
                    value = int(new_value)
                    if min_val <= value <= max_val:
                        config_manager.set(key, value)
                    else:
                        print_error(f"{name} must be between {min_val} and {max_val} (you entered: {value})")
                except ValueError:
                    print_error(f"'{new_value}' is not a valid number for {name}")
            
            print()
            print_success("Advanced settings updated")

