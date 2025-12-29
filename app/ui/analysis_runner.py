"""
Analysis Runner

Handles running vulnerability analysis with progress display
"""

import time
from pathlib import Path
from typing import Dict, Any, Optional

from .components import colored, Colors, print_header, print_success, print_error, print_info, print_warning, print_divider
from .keyboard_handler import KeyboardHandler
from .analysis_preview import AnalysisPreview
from .results_display import ResultsDisplay
from .progress_display import ProgressDisplay

from ..pipeline import VulTrialPipeline
from ..utils import InputHandler, VulTrialLogger, unescape_snippet


class AnalysisRunner:
    """Run and monitor vulnerability analysis"""
    
    @staticmethod
    def run_analysis(
        file_path: str,
        codebase_path: Optional[str],
        model,
        config_manager,
        history_manager
    ) -> Optional[Dict[str, Any]]:
        """
        Run vulnerability analysis with preview and progress
        
        Args:
            file_path: Path to file to analyze (can be None for standalone mode)
            codebase_path: Path to codebase (optional, None for standalone mode)
            model: LLM model instance
            config_manager: Configuration manager
            history_manager: History manager for tracking
        
        Returns:
            Analysis results, or None if cancelled/failed
        """
        print_header("Vulnerability Analysis", Colors.BRIGHT_GREEN)
        print()
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        
        # Ask for analysis scope
        print(colored("  Analysis Scope:", Colors.BRIGHT_WHITE))
        print()
        print(f"  {colored('1', Colors.BRIGHT_CYAN)}. 🎯 Specific function")
        print(f"      Analyze just one function by name")
        print()
        print(f"  {colored('2', Colors.BRIGHT_CYAN)}. 📄 Entire file {colored('(Recommended)', Colors.BRIGHT_GREEN)}")
        print(f"      Analyze the whole file as a single unit")
        print()
        print(f"  {colored('3', Colors.BRIGHT_CYAN)}. 📁 Entire codebase")
        print(f"      Analyze all files in the codebase directory")
        print()
        print(f"  {colored('4', Colors.BRIGHT_CYAN)}. 📝 Code snippet")
        print(f"      Analyze a specific code block (with or without codebase)")
        print()
        
        # Get default from config or use "2" if file exists, "4" if not
        if file_path:
            default_scope = config_manager.get("default_analysis_scope", "2")
        else:
            default_scope = config_manager.get("default_analysis_scope", "4")
        
        scope = KeyboardHandler.get_input("Select scope (1-4)", default_scope)
        
        function_name = None
        analyze_codebase = False
        code_snippet = None
        snippet_start_line = None
        snippet_end_line = None
        
        if scope == "1":
            # Specific function
            function_name = input(colored("  Function name: ", Colors.BRIGHT_WHITE)).strip()
            if not function_name:
                print_error("No function name provided")
                print_info("Tip: Enter the exact function name you want to analyze")
                return None
        elif scope == "3":
            # Entire codebase
            analyze_codebase = True
            print()
            print_warning("Analyzing entire codebase - this may take a while!")
            if not KeyboardHandler.confirm("Continue with codebase analysis?", default=True):
                print_info("Analysis cancelled")
                return None
        elif scope == "4":
            # Code snippet
            print()
            
            # ASK: Use codebase context or not?
            print(colored("  Codebase Context:", Colors.BRIGHT_WHITE, bold=True))
            print()
            print(f"  {colored('1', Colors.BRIGHT_CYAN)}. With codebase context")
            print(f"      Match snippet in file, enable research assistants")
            print()
            print(f"  {colored('2', Colors.BRIGHT_CYAN)}. Standalone (no codebase)")
            print(f"      Pure agent debate based on code only")
            print()
            
            use_codebase = KeyboardHandler.get_input("Select mode (1-2)", "2")
            
            if use_codebase == "1":
                # Need codebase and file
                if not codebase_path:
                    print()
                    print_info("Codebase path needed for context")
                    from .file_selector import FileSelector
                    codebase_path = FileSelector.select_codebase()
                    if not codebase_path:
                        print_error("Codebase required for context mode")
                        return None
                
                if not file_path:
                    print()
                    print_info("File path needed to match snippet")
                    from .file_selector import FileSelector
                    file_path = FileSelector.select_file(codebase_path)
                    if not file_path:
                        print_error("File required for context mode")
                        return None
            else:
                # Standalone mode - clear codebase and file
                print()
                print_info("🎯 Standalone mode selected - no codebase context")
                codebase_path = None
                file_path = None
            
            print()
            print_divider("─", 70, Colors.BRIGHT_BLACK)
            print(colored("  Code Snippet Input", Colors.BRIGHT_WHITE, bold=True))
            print_divider("─", 70, Colors.BRIGHT_BLACK)
            print()
            print_info("Option 1: Paste code directly (multi-line supported)")
            print_info("          When done, press Ctrl+D (Unix/Mac) or Ctrl+Z then Enter (Windows)")
            print()
            print_info("Option 2: Enter a file path containing the snippet")
            print_info("          Example: snippet.txt or /path/to/snippet.c")
            print()
            print_divider("─", 70, Colors.BRIGHT_BLACK)
            print()
            print(colored("  Paste code or enter file path:", Colors.BRIGHT_WHITE))
            
            # Try to read multi-line input
            snippet_lines = []
            try:
                while True:
                    line = input()
                    snippet_lines.append(line)
            except EOFError:
                # User pressed Ctrl+D/Ctrl+Z - finished pasting
                pass
            
            snippet_input = '\n'.join(snippet_lines).strip()
            
            if not snippet_input:
                print_error("No snippet provided")
                return None
            
            # Strip quotes if present (users often paste paths with quotes)
            if snippet_input.startswith('"') and snippet_input.endswith('"'):
                snippet_input = snippet_input[1:-1]
            elif snippet_input.startswith("'") and snippet_input.endswith("'"):
                snippet_input = snippet_input[1:-1]
            
            # Handle literal \n in pasted text (convert to actual newlines)
            if '\\n' in snippet_input and '\n' not in snippet_input:
                snippet_input = snippet_input.replace('\\n', '\n')
            
            # Check if it's a file path - only check if it's a single line and looks like a path
            snippet_from_file = False
            is_multiline = '\n' in snippet_input
            
            print()  # Add spacing after input
            
            if not is_multiline and len(snippet_input) < 260:  # Max path length on most systems
                # Single line - might be a file path
                try:
                    potential_path = Path(snippet_input)
                    if potential_path.exists() and potential_path.is_file():
                        # It's a file path - load the snippet from file
                        try:
                            with open(potential_path, 'r', encoding='utf-8', errors='ignore') as f:
                                code_snippet = f.read()
                            
                            # Unescape literal \n, \t etc. (common in JSON-extracted snippets)
                            code_snippet = unescape_snippet(code_snippet)
                            
                            snippet_from_file = True
                            snippet_lines_count = len(code_snippet.split('\n'))
                            print_success(f"✓ Loaded snippet from file: {colored(str(potential_path), Colors.BRIGHT_CYAN)}")
                            print_info(f"  Snippet size: {len(code_snippet)} chars, {snippet_lines_count} lines")
                        except Exception as e:
                            print_error(f"Could not read snippet file: {e}")
                            return None
                    else:
                        # Not a valid file path - treat as direct code
                        code_snippet = snippet_input
                        snippet_lines_count = len(code_snippet.split('\n'))
                        print_info(f"✓ Received code snippet ({len(code_snippet)} chars, {snippet_lines_count} lines)")
                except (OSError, ValueError):
                    # Invalid path format - treat as direct code
                    code_snippet = snippet_input
                    snippet_lines_count = len(code_snippet.split('\n'))
                    print_info(f"✓ Received code snippet ({len(code_snippet)} chars, {snippet_lines_count} lines)")
            else:
                # Multi-line or too long - definitely direct code input
                code_snippet = snippet_input
                snippet_lines_count = len(code_snippet.split('\n'))
                print_info(f"✓ Received code snippet ({len(code_snippet)} chars, {snippet_lines_count} lines)")
        
        # Ask for detection mode
        print()
        print(colored("  Detection Mode:", Colors.BRIGHT_WHITE))
        print(f"  {colored('1', Colors.BRIGHT_CYAN)}. 🔍 Detailed - Find ALL vulnerabilities")
        print(f"  {colored('2', Colors.BRIGHT_CYAN)}. ⚡ Consensus - Only obvious issues (faster)")
        print()
        
        # Get default from config or use "1"
        default_mode = config_manager.get("default_analysis_mode", "1")
        detection = KeyboardHandler.get_input("Select mode (1-2)", default_mode)
        
        # Save selected mode as default for next time
        config_manager.set("default_analysis_scope", scope)
        config_manager.set("default_analysis_mode", detection)
        
        analysis_mode = "detailed" if detection == "1" else "consensus"
        
        # Max turns
        default_turns = str(config_manager.get("max_turns", 4))
        max_turns_input = KeyboardHandler.get_input("Max debate turns", default_turns)
        try:
            max_turns = int(max_turns_input)
            if max_turns < 1:
                print_warning(f"Max turns must be positive, using default: {default_turns}")
                max_turns = int(default_turns)
        except ValueError as e:
            print_warning(f"Invalid number '{max_turns_input}', using default: {default_turns}")
            max_turns = int(default_turns)
        
        # Load code
        try:
            if analyze_codebase:
                # Entire codebase analysis
                print()
                print_info("Running codebase-wide analysis...")
                print()
                
                # Create metadata for codebase
                metadata = InputHandler.prepare_input_metadata(
                    codebase_path=codebase_path
                )
                
                # Use empty code string - pipeline will scan all files
                code = ""
                mode_for_preview = 'codebase'
                num_functions = None  # Unknown until we scan
            elif code_snippet:
                # Code snippet analysis
                print()
                
                if file_path:
                    # MODE 1: With file - try to locate snippet in file for context
                    print(f"  {colored('⟳', Colors.BRIGHT_YELLOW)} Locating snippet in file...", end='', flush=True)
                    matched_code, snippet_start_line, snippet_end_line = InputHandler.match_code_snippet_in_file(
                        file_path, code_snippet
                    )
                    print("\r" + " "*50 + "\r", end='')
                    
                    if not matched_code:
                        print_error("Could not find snippet in file")
                        print_info("Make sure the snippet matches the file content (whitespace variations are handled)")
                        return None
                    
                    # Use the PROVIDED snippet for analysis (not the matched code)
                    code = code_snippet
                    
                    metadata = InputHandler.prepare_input_metadata(
                        file_path=file_path,
                        codebase_path=codebase_path,
                        code_snippet=code_snippet,
                        snippet_start_line=snippet_start_line,
                        snippet_end_line=snippet_end_line
                    )
                    print_success(f"Located at lines {colored(f'{snippet_start_line}-{snippet_end_line}', Colors.BRIGHT_YELLOW)} • Analyzing {len(code)} chars")
                else:
                    # MODE 2: Standalone - direct snippet analysis (no file)
                    code = code_snippet
                    snippet_start_line = None
                    snippet_end_line = None
                    
                    metadata = InputHandler.prepare_input_metadata(
                        file_path=None,
                        codebase_path=None,
                        code_snippet=code_snippet
                    )
                    print_success(f"Standalone snippet • {len(code)} chars • {colored('No codebase context', Colors.BRIGHT_YELLOW)}")
                
                mode_for_preview = 'code_snippet'
                num_functions = 1
            elif function_name:
                print()
                print(f"  {colored('⟳', Colors.BRIGHT_YELLOW)} Extracting function...", end='', flush=True)
                code, start, end = InputHandler.extract_function_from_file(file_path, function_name)
                print("\r" + " "*50 + "\r", end='')
                
                if not code:
                    print_error(f"Function '{function_name}' not found")
                    return None
                
                metadata = InputHandler.prepare_input_metadata(
                    file_path=file_path,
                    function_name=function_name,
                    codebase_path=codebase_path
                )
                print_success(f"Extracted {colored(function_name, Colors.BRIGHT_YELLOW)}() • {len(code)} chars")
                mode_for_preview = 'specific_function'
                num_functions = 1
            
            else:
                # Entire file (scope == "2")
                print()
                print(f"  {colored('⟳', Colors.BRIGHT_YELLOW)} Loading file...", end='', flush=True)
                code = InputHandler.load_and_preprocess(file_path)
                print("\r" + " "*50 + "\r", end='')
                
                metadata = InputHandler.prepare_input_metadata(
                    file_path=file_path,
                    codebase_path=codebase_path
                )
                print_success(f"Loaded {len(code)} characters")
                mode_for_preview = 'whole_file'
                num_functions = 1
        
        except Exception as e:
            print_error(f"Failed to load file: {e}")
            return None
        
        # Show preview and get confirmation (skip for codebase and standalone snippet)
        if not analyze_codebase and file_path:
            analysis_config = {
                'mode': mode_for_preview,
                'analysis_mode': analysis_mode,
                'max_turns': max_turns,
                'function_name': function_name
            }
            
            price_input = config_manager.get("price_input_per_million")
            price_output = config_manager.get("price_output_per_million")
            
            confirmed = AnalysisPreview.show_preview(
                file_path, codebase_path, analysis_config, 
                num_functions, price_input, price_output
            )
            
            if not confirmed:
                print_info("Analysis cancelled")
                return None
        elif not file_path and code_snippet:
            # Standalone snippet - simple confirmation
            print()
            print_info(f"Ready to analyze {len(code)} character snippet in standalone mode")
            if not KeyboardHandler.confirm("Continue?", default=True):
                print_info("Analysis cancelled")
                return None
        
        # Create logger
        logger = VulTrialLogger(verbose=False)  # Quiet mode - details go to file only
        
        print()
        print_divider("═", 70, Colors.BRIGHT_CYAN)
        print(colored("  🔍 Analysis in Progress", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", 70, Colors.BRIGHT_CYAN)
        print()
        
        # Get context settings
        max_evidence_items = config_manager.get("max_evidence_items", 5)
        max_evidence_tokens = config_manager.get("max_evidence_tokens", 1000)
        max_evidence_lines = config_manager.get("max_evidence_lines", 100)
        evidence_token_budget = config_manager.get("evidence_token_budget", None)
        history_compression_turn = config_manager.get("history_compression_turn", 3)
        
        # Initialize pipeline
        # Note: When codebase_path is None, it's standalone mode (no research assistants)
        pipeline = VulTrialPipeline(
            model=model,
            max_turns=max_turns,
            verbose=False,  # Quiet mode - use custom progress display
            codebase_path=codebase_path,  # None = standalone mode
            enable_context_retrieval=codebase_path is not None,
            enable_pre_debate_summary=codebase_path is not None,  # Only if we have codebase
            analysis_mode=analysis_mode,
            max_evidence_items=max_evidence_items,
            max_evidence_tokens_per_item=max_evidence_tokens,
            max_evidence_lines_per_item=max_evidence_lines,
            evidence_total_token_budget=evidence_token_budget,
            history_compression_start_turn=history_compression_turn
        )
        
        # Wrap logger with clean progress display
        progress = ProgressDisplay(logger, pipeline)
        
        # Use pipeline's set_logger method to set logger on all components
        pipeline.set_logger(progress)
        
        # Turn off verbose for assistants (use progress display instead)
        if pipeline.sr_assistant:
            pipeline.sr_assistant.verbose = False
        if pipeline.ca_assistant:
            pipeline.ca_assistant.verbose = False
        
        # Run analysis
        start_time = time.time()
        try:
            results = pipeline.run(code, input_metadata=metadata)
            elapsed = time.time() - start_time
            
            print()
            print_success(f"Analysis completed in {int(elapsed)}s")
            
            # Add to history
            if analyze_codebase:
                summary = f"{results.get('total_files', 0)} files, {results.get('total_functions', 0)} functions analyzed"
            elif scope == "2":
                summary = f"{len(results.get('function_analyses', []))} functions analyzed"
            elif scope == "4":
                if snippet_start_line and snippet_end_line:
                    summary = f"Code snippet (lines {snippet_start_line}-{snippet_end_line})"
                else:
                    summary = f"Code snippet (standalone, {len(code)} chars)"
            else:
                summary = "Completed"
            
            history_manager.add_analysis(
                file_path or codebase_path or "standalone_snippet", codebase_path, mode_for_preview, 
                analysis_mode, summary
            )
            
            return {
                'results': results,
                'logger': logger,
                'elapsed_time': elapsed
            }
        
        except Exception as e:
            print()
            print_error(f"Analysis failed: {e}")
            import traceback
            traceback.print_exc()
            return None

