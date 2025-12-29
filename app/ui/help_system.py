"""
Help System

Tutorials and keyboard shortcut reference
"""

from .components import colored, Colors, print_header, print_divider, print_info


class HelpSystem:
    """Display help and tutorials"""
    
    @staticmethod
    def show_quick_tutorial():
        """Show quick start tutorial"""
        print_header("Quick Tutorial", Colors.BRIGHT_YELLOW)
        print()
        
        steps = [
            ("1. Set up your project", "Choose a codebase folder to analyze"),
            ("2. Select a file", "Pick which file to check for vulnerabilities"),
            ("3. Run analysis", "AI agents will debate security issues"),
            ("4. Review results", "See vulnerabilities with severity and confidence scores"),
        ]
        
        for step, desc in steps:
            print(f"  {colored(step, Colors.BRIGHT_CYAN, bold=True)}")
            print(f"     {colored(desc, Colors.BRIGHT_BLACK)}")
            print()
        
        print_divider()
        print()
    
    @staticmethod
    def show_analysis_modes():
        """Explain analysis modes"""
        print_header("Analysis Modes Explained", Colors.BRIGHT_MAGENTA)
        print()
        
        print(f"  {colored('🔍 Detailed Mode', Colors.BRIGHT_CYAN, bold=True)}")
        print(f"     • Finds ALL potential vulnerabilities")
        print(f"     • Deep debate on every issue")
        print(f"     • Best for: Security audits, thorough reviews")
        print(f"     • Speed: Slower but comprehensive")
        print()
        
        print(f"  {colored('⚡ Consensus Mode', Colors.BRIGHT_YELLOW, bold=True)}")
        print(f"     • Finds OBVIOUS, high-severity vulnerabilities only")
        print(f"     • Skips minor or contested issues")
        print(f"     • Best for: Quick scans, CI/CD pipelines")
        print(f"     • Speed: 2-3x faster")
        print()
        
        print_divider()
        print()
    
    @staticmethod
    def show_help_menu():
        """Show main help menu"""
        print_header("Help & Documentation", Colors.BRIGHT_CYAN)
        print()
        
        options = [
            ("1", "Quick Tutorial", "📚"),
            ("2", "Analysis Modes Explained", "🎯"),
            ("3", "Cost Tracking Guide", "💰"),
            ("0", "Back to Main Menu", "◀️ "),
        ]
        
        for num, text, emoji in options:
            print(f"  {colored(num, Colors.BRIGHT_CYAN)}. {emoji}  {text}")
        
        print()
        print_divider()
        print(colored("  (Press Ctrl+C to go back)", Colors.DIM))
        
        try:
            choice = input("\n  Select option: ").strip()
            
            if choice == "1":
                HelpSystem.show_quick_tutorial()
            elif choice == "2":
                HelpSystem.show_analysis_modes()
            elif choice == "3":
                HelpSystem.show_cost_tracking_guide()
            
            input(colored("\n  Press Enter to continue...", Colors.BRIGHT_BLACK))
        
        except KeyboardInterrupt:
            print("\n")
            print_info("Returning to main menu...")
            print()
    
    @staticmethod
    def show_cost_tracking_guide():
        """Show cost tracking guide"""
        print_header("Cost Tracking Guide", Colors.BRIGHT_GREEN)
        print()
        
        print(f"  {colored('Step 1: Set Pricing', Colors.BRIGHT_CYAN, bold=True)}")
        print(f"     Go to Settings → Option P → Set Pricing")
        print()
        
        print(f"  {colored('Common Model Pricing (per 1M tokens):', Colors.BRIGHT_WHITE)}")
        print(f"     • OpenAI GPT-4:  Input: $2.50  | Output: $10.00")
        print(f"     • Claude Sonnet: Input: $3.00  | Output: $15.00")
        print(f"     • Gemini Pro:    Input: FREE   | Output: FREE")
        print()
        
        print(f"  {colored('Step 2: Run Analysis', Colors.BRIGHT_CYAN, bold=True)}")
        print(f"     After analysis, you'll see:")
        print(f"     • Input tokens used")
        print(f"     • Output tokens used")
        print(f"     • Total cost calculated")
        print()
        
        print_divider()
        print()

