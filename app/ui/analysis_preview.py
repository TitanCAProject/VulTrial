"""Analysis Preview - Shows what will happen before running"""

from pathlib import Path
from typing import Optional
from .components import colored, Colors, print_divider
from .keyboard_handler import KeyboardHandler
from .constants import UIConstants


class AnalysisPreview:
    """Preview analysis configuration"""
    
    @staticmethod  
    def show_preview(file_path, codebase_path, analysis_config, num_functions, price_input, price_output):
        """Show preview and get confirmation"""
        print()
        print_divider("═", UIConstants.DIVIDER_WIDTH, Colors.BRIGHT_CYAN)
        print(colored("  Ready to Analyze", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", UIConstants.DIVIDER_WIDTH, Colors.BRIGHT_CYAN)
        print()
        
        # File info
        file_obj = Path(file_path)
        file_size = file_obj.stat().st_size
        with open(file_obj, 'r', encoding='utf-8', errors='ignore') as f:
            line_count = len(f.readlines())
        
        print(f"  {colored('File:', Colors.BRIGHT_WHITE):15s}  {colored(file_obj.name, Colors.BRIGHT_CYAN, bold=True)}")
        print(f"  {colored('Size:', Colors.BRIGHT_WHITE):15s}  {colored(f'{file_size:,} bytes, {line_count} lines', Colors.BRIGHT_BLACK)}")
        
        # Show if standalone mode (no codebase)
        if not codebase_path:
            print(f"  {colored('Context:', Colors.BRIGHT_WHITE):15s}  {colored('Standalone (no codebase)', Colors.BRIGHT_YELLOW)}")
            print(f"  {colored('', Colors.BRIGHT_WHITE):15s}  {colored('⚠ Research assistants disabled', Colors.DIM)}")
        
        mode = analysis_config.get('mode', 'all_functions')
        analysis_mode = analysis_config.get('analysis_mode', 'detailed')
        
        if num_functions:
            print(f"  {colored('Functions:', Colors.BRIGHT_WHITE):15s}  {colored(f'{num_functions} to analyze', Colors.BRIGHT_CYAN)}")
        
        mode_display = "Detailed" if analysis_mode == 'detailed' else "Consensus (fast)"
        print(f"  {colored('Mode:', Colors.BRIGHT_WHITE):15s}  {colored(mode_display, Colors.BRIGHT_MAGENTA)}")
        
        # Time estimate
        est_time = AnalysisPreview.estimate_time(num_functions or 1, analysis_mode)
        est_min = est_time // 60
        est_sec = est_time % 60
        time_str = f"{est_min}min {est_sec}s" if est_min > 0 else f"{est_sec}s"
        print(f"  {colored('Est. Time:', Colors.BRIGHT_WHITE):15s}  {colored(time_str, Colors.BRIGHT_YELLOW)}")
        
        # Cost estimate
        if price_input and price_output:
            cost = AnalysisPreview.estimate_cost(file_size, num_functions or 1, analysis_mode, price_input, price_output)
            print(f"  {colored('Est. Cost:', Colors.BRIGHT_WHITE):15s}  {colored(f'~${cost:.3f}', Colors.BRIGHT_GREEN)}")
        
        print()
        print_divider("═", UIConstants.DIVIDER_WIDTH, Colors.BRIGHT_CYAN)
        print()
        
        return KeyboardHandler.confirm("Continue?", default=True)
    
    @staticmethod
    def estimate_time(num_functions: int, mode: str) -> int:
        """Estimate time in seconds"""
        seconds_per_function = 37 if mode == 'detailed' else 17
        return num_functions * seconds_per_function
    
    @staticmethod
    def estimate_cost(file_size, num_functions, mode, price_input, price_output):
        """Estimate cost"""
        turns = 3 if mode == 'detailed' else 1.5
        total_input = num_functions * 2000 * turns
        total_output = num_functions * 1000 * turns
        return (total_input / 1_000_000 * price_input) + (total_output / 1_000_000 * price_output)

