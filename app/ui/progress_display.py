"""
Progress Display

Clean progress indicators (no verbose prompts/responses shown on screen)
"""

from .components import colored, Colors


class ProgressDisplay:
    """
    Wrapper around logger that shows clean progress on screen
    while logging full details to file
    """
    
    def __init__(self, original_logger, pipeline):
        """
        Initialize progress display
        
        Args:
            original_logger: VulTrialLogger instance (logs to file)
            pipeline: VulTrialPipeline instance (for max_turns)
        """
        self.original_logger = original_logger
        self.pipeline = pipeline
        self.current_turn = 0
        self.current_agent = None
    
    def log_agent_start(self, agent_name, turn=None):
        """Show agent starting (clean, no verbose)"""
        if turn and turn != self.current_turn:
            self.current_turn = turn
            print()
            print(colored(f"  Turn {turn}/{self.pipeline.max_turns}", Colors.BRIGHT_BLACK))
        
        self.current_agent = agent_name
        agent_display = {
            'security_researcher': ('Security Researcher', '🔍', Colors.BRIGHT_RED),
            'code_author': ('Code Author', '👨‍💻', Colors.BRIGHT_BLUE),
            'moderator': ('Moderator', '⚖️ ', Colors.BRIGHT_YELLOW),
            'review_board': ('Review Board', '🏛️ ', Colors.BRIGHT_MAGENTA)
        }
        
        name, emoji, color = agent_display.get(agent_name, (agent_name, '🤖', Colors.BRIGHT_WHITE))
        print(f"  {emoji}  {colored(name, color)} analyzing...", end='', flush=True)
        
        # Log to file (full details)
        self.original_logger.log_agent_start(agent_name, turn)
    
    def log_agent_response(self, agent_name, response, tokens=None):
        """Show completion (clean, no verbose)"""
        # Clear line first (80 spaces to remove any leftover text from "analyzing...")
        print(f"\r{' ' * 80}\r  {colored('✓', Colors.BRIGHT_GREEN)}  {colored(agent_name.replace('_', ' ').title(), Colors.BRIGHT_WHITE)} complete")
        
        # Log to file (full response)
        self.original_logger.log_agent_response(agent_name, response, tokens)
    
    def log_tool_use(self, tool_name, parameters, results_count=None):
        """Show tool usage"""
        # Get the main parameter value for display
        param_value = ""
        if parameters:
            # Show the most relevant parameter
            if 'function_name' in parameters:
                param_value = parameters['function_name']
            elif 'class_name' in parameters:
                param_value = parameters['class_name']
            elif 'code_pattern' in parameters:
                param_value = parameters['code_pattern']
            elif 'source_pattern' in parameters:
                param_value = f"{parameters['source_pattern']} → {parameters.get('sink_function', '?')}"
            elif 'variable_name' in parameters:
                param_value = f"{parameters['variable_name']} in {parameters.get('function_name', '?')}"
            else:
                param_value = list(parameters.values())[0] if parameters.values() else ""
        
        if isinstance(param_value, str) and len(param_value) > 35:
            param_value = param_value[:32] + "..."
        
        # Clean tool name for display
        tool_display = tool_name.replace('_', ' ').title()
        
        # Show results count
        if results_count is not None:
            if results_count > 0:
                result_str = colored(f" → {results_count} found", Colors.BRIGHT_GREEN)
            else:
                result_str = colored(f" → none found", Colors.BRIGHT_YELLOW)
        else:
            result_str = ""
        
        print(f"      {colored('🔧', Colors.BRIGHT_CYAN)} {colored(tool_display, Colors.BRIGHT_WHITE)}: {colored(param_value, Colors.BRIGHT_YELLOW)}{result_str}")
        
        self.original_logger.log_tool_use(tool_name, parameters, results_count)
    
    def log_cache_hit(self, cache_key):
        self.original_logger.log_cache_hit(cache_key)
    
    def log_cache_miss(self, cache_key):
        self.original_logger.log_cache_miss(cache_key)
    
    def log_tool_results(self, tool_name, results):
        self.original_logger.log_tool_results(tool_name, results)
    
    def log_agent_prompt(self, agent_name, prompt):
        # Don't show on screen - only log to file
        self.original_logger.log_agent_prompt(agent_name, prompt)
    
    def log_phase(self, phase_name, details=None):
        """Show only important phases on console"""
        if "Function" in phase_name and "/" in phase_name:
            # Multi-function progress
            print()
            print(colored(f"  {phase_name}", Colors.BRIGHT_BLACK))
        elif "Evidence Gathering" in phase_name:
            # Show evidence gathering phase with better formatting
            print(colored(f"      🔍 Research Assistants gathering evidence...", Colors.BRIGHT_CYAN))
        elif phase_name == "Vulnerability Detection Started":
            # Don't show, we already showed it
            pass
        else:
            # Other phases - minimal
            pass
        
        self.original_logger.log_phase(phase_name, details)
    
    def log_decision(self, decision):
        self.original_logger.log_decision(decision)
    
    def log_summary(self, message):
        """Show summary messages on screen (evidence gathering, etc.)"""
        # Show assistant activity messages
        if "SR Assistant:" in message or "CA Assistant:" in message:
            # Clean format for assistant messages
            if "Found" in message and "pieces of evidence" in message:
                # Extract count
                import re
                match = re.search(r'Found (\d+)', message)
                if match:
                    count = match.group(1)
                    agent = "SR" if "SR" in message else "CA"
                    print(f"      {colored('✓', Colors.BRIGHT_GREEN)} {colored(f'{agent} Assistant: {count} evidence items found', Colors.BRIGHT_WHITE)}")
            elif "No search needed" in message:
                agent = "SR" if "SR" in message else "CA"
                print(f"      {colored('○', Colors.BRIGHT_BLACK)} {colored(f'{agent} Assistant: No search needed', Colors.BRIGHT_BLACK)}")
            elif "Searched but found nothing" in message:
                agent = "SR" if "SR" in message else "CA"
                print(f"      {colored('○', Colors.BRIGHT_YELLOW)} {colored(f'{agent} Assistant: No evidence found', Colors.BRIGHT_YELLOW)}")
        elif "Analyzing evidence needs" in message:
            # Starting evidence analysis - show quietly
            pass
        
        self.original_logger.log_summary(message)
    
    def log_error(self, error_msg, exception=None):
        self.original_logger.log_error(error_msg, exception)
    
    def log_completion(self):
        self.original_logger.log_completion()
    
    def get_log_path(self):
        return self.original_logger.get_log_path()
    
    def get_token_usage(self):
        """Get token usage from original logger"""
        return self.original_logger.get_token_usage()
    
    def calculate_cost(self, price_input, price_output):
        """Calculate cost from original logger"""
        return self.original_logger.calculate_cost(price_input, price_output)

