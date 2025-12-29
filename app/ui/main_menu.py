"""
Main Menu Controller

Orchestrates all UI components for a smooth user experience
"""

from pathlib import Path
from typing import Optional

from .components import (
    colored, Colors, print_header, print_success, print_error, 
    print_info, print_warning, print_divider, print_banner
)
from .keyboard_handler import KeyboardHandler
from .history_manager import HistoryManager
from .help_system import HelpSystem
from .file_selector import FileSelector
from .settings_menu import SettingsMenu
from .analysis_runner import AnalysisRunner
from .results_display import ResultsDisplay
from .first_run import FirstRunWizard
from .constants import UIConstants

from ..models import ClaudeModel, OpenAIModel, GrokModel, GeminiModel
from ..utils import ConfigManager, ResultsSaver


class VulTrialUI:
    """Main UI controller - uses modular components"""
    
    def __init__(self):
        """Initialize UI"""
        self.config = ConfigManager()
        self.history = HistoryManager()
        
        self.model = None
        self.current_codebase = None
        self.current_file = None
        self.logger = None
        
        # Try to auto-load model and last paths
        self._auto_load_model()
        self._load_last_paths()
    
    def run(self):
        """Main UI loop"""
        # Check for first run and show wizard
        if FirstRunWizard.is_first_run(self.config):
            success, model = FirstRunWizard.run_wizard(self.config)
            if success and model:
                self.model = model
                FirstRunWizard.show_quick_start_tip()
            elif not success:
                # User didn't complete setup
                return
        else:
            # Normal startup
            print_banner()  # Use version from UIConstants
            
            # Show loaded configuration
            model_type = self.config.get("model_type")
            model_id = self.config.get("model_id")
            
            if model_type and model_id:
                if self.model:
                    print_success(f"Model ready: {colored(model_type.title(), Colors.BRIGHT_MAGENTA)} ({model_id})")
                else:
                    print_warning(f"Model configured but not loaded: {colored(model_type.title(), Colors.BRIGHT_MAGENTA)}")
                    print_info("Check your API key or go to Settings to reconfigure")
                print()
        
        while True:
            self._print_main_menu()
            
            try:
                choice = input("\n  Select option: ").strip()
                
                # Handle menu options
                if choice == '1':
                    self._set_codebase_and_file()
                elif choice == '2':
                    self._run_analysis()
                elif choice == '3':
                    updated_model = SettingsMenu.show_settings(self.config)
                    if updated_model:
                        self.model = updated_model
                        print()
                        print_success(f"Model updated to: {self.model.model_id}")
                elif choice == '4':
                    print()
                    print(colored("  👋 Thank you for using VulTrial!", Colors.BRIGHT_CYAN, bold=True))
                    print()
                    break
                elif choice == '?':
                    HelpSystem.show_help_menu()
                else:
                    print_error("Invalid option. Try 1-4 or ? for help")
            
            except KeyboardInterrupt:
                print("\n")
                try:
                    if KeyboardHandler.confirm("Exit VulTrial?", default=True):
                        print()
                        print(colored("  👋 Thank you for using VulTrial!", Colors.BRIGHT_CYAN, bold=True))
                        print()
                        break
                    else:
                        continue
                except KeyboardInterrupt:
                    # User pressed Ctrl+C again during confirmation - force exit
                    print("\n")
                    print(colored("  👋 Thank you for using VulTrial!", Colors.BRIGHT_CYAN, bold=True))
                    print()
                    break
            except Exception as e:
                print()
                print_error(f"Unexpected error: {e}")
    
    def _print_main_menu(self):
        """Print main menu with status"""
        print()
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print(colored("  Main Menu", Colors.BRIGHT_WHITE, bold=True))
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        
        # Status bar
        print()
        status_parts = []
        
        # Show actual loaded model (not just config)
        if self.model:
            model_display = f"{self.model.model_id}"
            status_parts.append(colored(f"🤖 {model_display}", Colors.BRIGHT_MAGENTA))
        else:
            model_type = self.config.get("model_type")
            if model_type:
                status_parts.append(colored(f"🤖 {model_type.title()} (not loaded)", Colors.BRIGHT_YELLOW))
            else:
                status_parts.append(colored("🤖 Not configured", Colors.BRIGHT_BLACK))
        
        if self.current_codebase:
            codebase_name = Path(self.current_codebase).name
            status_parts.append(colored(f"📁 {codebase_name}", Colors.BRIGHT_CYAN))
        
        if self.current_file:
            file_name = Path(self.current_file).name
            status_parts.append(colored(f"📄 {file_name}", Colors.BRIGHT_YELLOW))
        
        if status_parts:
            print("  " + colored("Status: ", Colors.BRIGHT_BLACK) + " │ ".join(status_parts))
            print()
        
        # Menu options
        print(f"  {colored('1', Colors.BRIGHT_CYAN)}. 📁  Set codebase & file (optional)")
        print(f"  {colored('2', Colors.BRIGHT_CYAN)}. 🚀  Run vulnerability analysis")
        print(f"  {colored('3', Colors.BRIGHT_CYAN)}. ⚙️   Settings")
        print(f"  {colored('4', Colors.BRIGHT_CYAN)}. 👋  Exit")
        print()
        print(f"  {colored('?', Colors.BRIGHT_CYAN)}. ❓  Help & Tutorial")
        
        print_divider("─", 70, Colors.BRIGHT_BLACK)
    
    def _set_codebase_and_file(self):
        """Set codebase and select file"""
        # Select or change codebase
        if self.current_codebase:
            print_info(f"Current codebase: {colored(Path(self.current_codebase).name, Colors.BRIGHT_WHITE)}")
            print()
            if not KeyboardHandler.confirm("Change to a different codebase?", default=False):
                # Keep current codebase, just select file
                selected_file = FileSelector.select_file(self.current_codebase)
                if selected_file:
                    self.current_file = selected_file
                    self._save_last_paths()
                return
        
        # Select new codebase
        codebase = FileSelector.select_codebase()
        if codebase:
            self.current_codebase = codebase
            # Clear the old file since it's from a different codebase
            self.current_file = None
            self._save_last_paths()
            
            # Now select file
            print()
            if KeyboardHandler.confirm("Select a file now?", default=True):
                selected_file = FileSelector.select_file(self.current_codebase)
                if selected_file:
                    self.current_file = selected_file
                    self._save_last_paths()
            else:
                print()
                print_info("No file selected - you'll need to select one before running analysis")
    
    def _run_analysis(self):
        """Run vulnerability analysis"""
        # Check model first
        if not self.model:
            print_error("No model configured. Press 3 to open Settings")
            return
        
        # Run analysis (user chooses mode in analysis runner)
        result = AnalysisRunner.run_analysis(
            self.current_file,
            self.current_codebase,
            self.model,
            self.config,
            self.history
        )
        
        if result:
            # Display results
            ResultsDisplay.show_results(result['results'], result['logger'])
            
            # Show log location
            print()
            print_info(f"Detailed log: {colored(result['logger'].get_log_path(), Colors.BRIGHT_CYAN)}")
            
            # Save results
            self._save_analysis_results(result)
    
    def _auto_load_model(self):
        """Auto-load model from saved configuration"""
        try:
            model_type = self.config.get("model_type")
            model_id = self.config.get("model_id")
            
            # Skip if no model configured
            if not model_type or not model_id:
                self.model = None
                return
            
            temperature = self.config.get("temperature", UIConstants.DEFAULT_TEMPERATURE)
            max_tokens = self.config.get("max_tokens", UIConstants.DEFAULT_MAX_TOKENS)
            
            if model_type == "claude":
                self.model = ClaudeModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            elif model_type == "grok":
                self.model = GrokModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            elif model_type == "openai":
                self.model = OpenAIModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            elif model_type == "gemini":
                self.model = GeminiModel(model_id=model_id, temperature=temperature, max_tokens=max_tokens)
            else:
                self.model = None
                
        except Exception as e:
            # Show error but don't crash - user can configure manually
            self.model = None
            print_warning(f"Could not load model: {str(e)}")
            print_info("You may need to set your API key (e.g., ANTHROPIC_API_KEY)")
            print()
    
    def _load_last_paths(self):
        """Load last used codebase and file from config"""
        last_codebase = self.config.get("last_codebase")
        last_file = self.config.get("last_file")
        
        # Validate codebase exists
        if last_codebase and Path(last_codebase).exists():
            self.current_codebase = last_codebase
        else:
            self.current_codebase = None
            if last_codebase:
                # Codebase was set but doesn't exist anymore
                self.config.set("last_codebase", None)
        
        # Validate file exists AND belongs to current codebase
        mismatch_detected = False
        if last_file and Path(last_file).exists():
            if self.current_codebase:
                # Check if file is within the codebase
                try:
                    file_path = Path(last_file).resolve()
                    codebase_path = Path(self.current_codebase).resolve()
                    
                    # Check if file is inside codebase directory
                    if codebase_path in file_path.parents or file_path.parent == codebase_path:
                        self.current_file = last_file
                    else:
                        # File is not in this codebase - clear it
                        self.current_file = None
                        self.config.set("last_file", None)
                        mismatch_detected = True
                except Exception:
                    # Path resolution failed - clear file
                    self.current_file = None
                    self.config.set("last_file", None)
            else:
                # No codebase set, but file exists - allow it
                self.current_file = last_file
        else:
            self.current_file = None
            if last_file:
                # File was set but doesn't exist anymore
                self.config.set("last_file", None)
        
        # Show helpful message if mismatch was detected
        if mismatch_detected:
            print_warning("Previous file was from a different codebase - cleared")
            print_info(f"Please select a file from {colored(Path(self.current_codebase).name, Colors.BRIGHT_CYAN)}")
            print()
    
    def _save_last_paths(self):
        """Save current paths to config"""
        # Always save codebase (or None)
        self.config.set("last_codebase", self.current_codebase)
        
        # Always save file (or None) to keep them in sync
        self.config.set("last_file", self.current_file)
    
    def _save_analysis_results(self, result: dict):
        """
        Save analysis results to file with proper naming and config respect
        
        Args:
            result: Analysis result dictionary
        """
        # Check if auto-save is enabled
        auto_save = self.config.get("auto_save_results", True)
        
        # Get output directory from config
        output_dir = self.config.get("output_directory", UIConstants.RESULTS_DIR)
        
        # Generate output file path
        output_file = ResultsSaver.generate_output_filename(
            file_path=self.current_file,
            codebase_path=self.current_codebase,
            output_dir=output_dir,
            extension="json"
        )
        
        # Prepare data
        data = ResultsSaver.prepare_json_data(
            results=result['results'],
            file_path=self.current_file,
            codebase_path=self.current_codebase,
            model_type=self.config.get('model_type'),
            model_id=self.config.get('model_id'),
            token_usage=result['logger'].get_token_usage() if result.get('logger') else None,
            elapsed_time=result.get('elapsed_time', 0)
        )
        
        # Auto-save or ask user
        should_save = auto_save
        if not auto_save:
            print()
            should_save = KeyboardHandler.confirm("Save results to file?", default=True)
        elif output_file.exists():
            # File exists - this shouldn't happen with timestamps, but just in case
            print()
            print_warning(f"File already exists: {output_file.name}")
            should_save = KeyboardHandler.confirm("Overwrite?", default=True)
        
        if should_save:
            # Save JSON
            if ResultsSaver.save_json(data, output_file):
                print()
                print_success(f"Results saved: {colored(str(output_file), Colors.BRIGHT_CYAN)}")
                
                # Also offer to save a simple text summary
                if not auto_save:  # Only ask if user is in interactive mode
                    if KeyboardHandler.confirm("Also save text summary?", default=False):
                        text_file = output_file.with_suffix('.txt')
                        if ResultsSaver.save_text_summary(data, text_file):
                            print_success(f"Summary saved: {colored(str(text_file), Colors.BRIGHT_CYAN)}")
            else:
                print()
                print_error("Failed to save results")
        
        print()


def main():
    """Entry point for new modular UI"""
    ui = VulTrialUI()
    ui.run()


if __name__ == "__main__":
    main()


