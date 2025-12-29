"""Main entry point for VulTrial vulnerability detection"""

import argparse
import sys
from pathlib import Path

from .models import OpenAIModel, ClaudeModel, GeminiModel, GrokModel
from .pipeline import VulTrialPipeline
from .utils import InputHandler, VulTrialLogger, ConfigManager, ResultsSaver, unescape_snippet
from .prompts import ANALYSIS_MODE_DETAILED, ANALYSIS_MODE_CONSENSUS


def get_model(model_type: str, model_id: str, **kwargs):
    """
    Get model instance based on type
    
    Args:
        model_type: Type of model ('openai', 'claude', 'gemini', 'grok')
        model_id: Model identifier
        **kwargs: Additional model parameters
        
    Returns:
        Model instance
    """
    model_classes = {
        'openai': OpenAIModel,
        'claude': ClaudeModel,
        'gemini': GeminiModel,
        'grok': GrokModel,
    }
    
    if model_type.lower() not in model_classes:
        raise ValueError(f"Unknown model type: {model_type}. Choose from: {list(model_classes.keys())}")
    
    model_class = model_classes[model_type.lower()]
    return model_class(model_id=model_id, **kwargs)


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="VulTrial - Multi-Agent Vulnerability Detection Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Analysis Levels (determined by what you provide):
  
  1. CODEBASE LEVEL - Analyze all files in codebase:
     python -m app.main --codebase data/demo-py --model-type claude --model-id claude-3-5-sonnet-20241022
  
  2. FILE LEVEL - Analyze all functions in one file (with codebase context):
     python -m app.main --codebase data/demo-py --file cli.py --model-type claude --model-id claude-3-5-sonnet-20241022
  
  3. FUNCTION LEVEL - Analyze specific function (with codebase context):
     python -m app.main --codebase data/demo-py --file cli.py --function main --model-type claude --model-id claude-3-5-sonnet-20241022
  
  4. CODE SNIPPET LEVEL - Analyze specific code block (with codebase context):
     python -m app.main --codebase data/demo-py --file cli.py --code-snippet "if user_input:\\n    execute(user_input)" --model-type claude --model-id claude-3-5-sonnet-20241022

Standalone Mode (NO codebase context - pure debate without research assistants):
  
  # Analyze standalone file
  python -m app.main --file /path/to/auth.c --model-type claude --model-id claude-3-5-sonnet-20241022
  
  # Analyze standalone function
  python -m app.main --file /path/to/auth.c --function login --model-type claude --model-id claude-3-5-sonnet-20241022
  
  # Analyze code snippet directly (no file needed)
  python -m app.main --code-snippet "if (user) { admin_check(); }" --model-type claude --model-id claude-3-5-sonnet-20241022
  
  # Or load snippet from file
  python -m app.main --code-snippet /path/to/snippet.c --model-type claude --model-id claude-3-5-sonnet-20241022

Other Examples:
  # Using Gemini (free)
  python -m app.main --codebase data/demo-py --file test.py --model-type gemini --model-id gemini-1.5-pro
  
  # Consensus mode (faster, only obvious vulnerabilities)
  python -m app.main --codebase data/demo-py --mode consensus --max-turns 2
  
  # With output directory (auto-generates files inside)
  python -m app.main --codebase data/demo-py --output output/my-analysis --price-input 3.0 --price-output 15.0
  # Creates: output/my-analysis/codebase_demo-py_TIMESTAMP.json
  #          output/my-analysis/codebase_demo-py_TIMESTAMP.txt
  #          output/my-analysis/codebase_demo-py_TIMESTAMP.detailed.txt
  
  # With specific output file base name
  python -m app.main --codebase data/demo-py --file cli.py --output results
  # Creates: results.json, results.txt, results.detailed.txt
        """
    )
    
    # Analysis target arguments (new clear design)
    parser.add_argument(
        '--codebase', '-c',
        type=str,
        default=None,
        help='Path to codebase directory (optional - enables context retrieval; omit for standalone file analysis)'
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        default=None,
        help='Specific file to analyze (relative to codebase or absolute path)'
    )
    
    parser.add_argument(
        '--function',
        type=str,
        default=None,
        help='Specific function name to analyze (requires --file)'
    )
    
    parser.add_argument(
        '--code-snippet',
        type=str,
        default=None,
        help='Code snippet to analyze directly (standalone) OR path to file containing snippet. Use with --file to match snippet in that file for location context.'
    )
    
    parser.add_argument(
        '--model-type', '-t',
        type=str,
        default='openai',
        choices=['openai', 'claude', 'gemini', 'grok'],
        help='Type of LLM model to use (default: openai)'
    )
    
    parser.add_argument(
        '--model-id', '-m',
        type=str,
        default=None,
        help='Model identifier (e.g., gpt-4, claude-3-5-sonnet-20241022)'
    )
    
    parser.add_argument(
        '--max-turns',
        type=int,
        default=4,
        help='Maximum number of debate turns before final decision (default: 4)'
    )
    
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.7,
        help='Model temperature (0-1, default: 0.7)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=20000,
        help='Maximum tokens to generate (default: model default)'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress verbose output'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output directory or file base name (auto-generates .json, .txt, .detailed.txt)'
    )
    
    parser.add_argument(
        '--enable-context',
        action='store_true',
        help='Enable context retrieval from codebase (auto-enabled if --codebase is provided)'
    )
    
    parser.add_argument(
        '--no-pre-debate-summary',
        action='store_true',
        help='Disable pre-debate context summarization'
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        default='detailed',
        choices=['detailed', 'consensus'],
        help='Analysis mode: "detailed" (find ALL vulnerabilities, slow but thorough) or "consensus" (only obvious vulnerabilities, fast)'
    )
    
    # Context management configuration
    parser.add_argument(
        '--max-evidence-items',
        type=int,
        default=5,
        help='Maximum number of evidence items to keep per search (default: 5)'
    )
    
    parser.add_argument(
        '--max-evidence-tokens',
        type=int,
        default=1000,
        help='Maximum tokens per evidence item before truncation (default: 1000)'
    )
    
    parser.add_argument(
        '--max-evidence-lines',
        type=int,
        default=400,
        help='Maximum lines per evidence item before truncation (default: 400)'
    )
    
    parser.add_argument(
        '--evidence-token-budget',
        type=int,
        default=None,
        help='Total token budget for all evidence (default: auto-calculated from model capacity)'
    )
    
    parser.add_argument(
        '--history-compression-turn',
        type=int,
        default=3,
        help='Turn number to start compressing chat history (default: 3)'
    )
    
    # Pricing configuration (for cost tracking)
    parser.add_argument(
        '--price-input',
        type=float,
        default=None,
        help='Price per 1 million input tokens (e.g., 3.0 for $3.00) - enables cost tracking'
    )
    
    parser.add_argument(
        '--price-output',
        type=float,
        default=None,
        help='Price per 1 million output tokens (e.g., 15.0 for $15.00) - enables cost tracking'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    # IMPORTANT: Codebase is now optional - allows standalone file/snippet analysis
    if not args.codebase and not args.file and not args.code_snippet:
        parser.error("You must provide one of:\n"
                    "  • --file for standalone file analysis\n"
                    "  • --code-snippet for standalone snippet analysis\n"
                    "  • --codebase for full codebase analysis with context")
    
    if args.function and not args.file:
        parser.error("--function requires --file")
    
    # Note: --code-snippet can now work WITHOUT --file for direct snippet analysis
    
    if args.function and args.code_snippet:
        parser.error("--function and --code-snippet are mutually exclusive. Use one or the other.")
    
    # Set default model IDs if not provided
    from .ui.constants import ModelDefaults
    
    model_id = args.model_id or ModelDefaults.get_default_model_id(args.model_type, for_cli=True)
    
    # Display mode-friendly name
    mode_display = "Detailed (find ALL vulnerabilities)" if args.mode == 'detailed' else "Consensus (only obvious vulnerabilities)"
    
    print(f"\n{'='*80}")
    print(f"VulTrial - Vulnerability Detection Framework")
    print(f"{'='*80}")
    
    # Show what we're analyzing
    if args.codebase:
        print(f"Codebase: {args.codebase}")
    else:
        print(f"Mode: Standalone analysis (no codebase context)")
    
    if args.file:
        print(f"File: {args.file}")
    if args.function:
        print(f"Function: {args.function}")
    
    print(f"Model: {args.model_type} ({model_id})")
    print(f"Analysis mode: {mode_display}")
    print(f"Max turns: {args.max_turns}")
    print(f"Temperature: {args.temperature}")
    print(f"{'='*80}\n")
    
    try:
        # Determine analysis level based on arguments provided
        codebase_path = args.codebase
        
        if args.code_snippet:
            # CODE SNIPPET LEVEL: Can be used with or without --file
            
            # Check if code_snippet is a file path or direct code
            snippet_input = args.code_snippet
            snippet_from_file = False
            snippet_file_path = None
            
            # Strip quotes if present (users often provide paths with quotes)
            if snippet_input.startswith('"') and snippet_input.endswith('"'):
                snippet_input = snippet_input[1:-1]
            elif snippet_input.startswith("'") and snippet_input.endswith("'"):
                snippet_input = snippet_input[1:-1]
            
            # Handle literal \n in input (convert to actual newlines if needed)
            if '\\n' in snippet_input and '\n' not in snippet_input:
                snippet_input = snippet_input.replace('\\n', '\n')
            
            # Check if it's a file path - only if single line and reasonable length
            is_multiline = '\n' in snippet_input
            
            if not is_multiline and len(snippet_input) < 260:  # Max path length on most systems
                # Might be a file path - try to load it
                try:
                    potential_path = Path(snippet_input)
                    if potential_path.exists() and potential_path.is_file():
                        # It's a file path - load the snippet from file
                        try:
                            with open(potential_path, 'r', encoding='utf-8', errors='ignore') as f:
                                snippet_input = f.read()
                            
                            # Unescape literal \n, \t etc. (common in JSON-extracted snippets)
                            snippet_input = unescape_snippet(snippet_input)
                            
                            snippet_from_file = True
                            snippet_file_path = str(potential_path)
                            print(f"Loaded snippet from file: {snippet_file_path}")
                        except Exception as e:
                            raise ValueError(f"Could not read snippet file {potential_path}: {e}")
                except (OSError, ValueError):
                    # Not a valid path - treat as direct code
                    pass
            
            if args.file:
                # MODE 1: --file + --code-snippet (match snippet in file for context)
                file_path = args.file
                
                # Resolve file path (could be relative to codebase or absolute)
                if not Path(file_path).is_absolute():
                    if codebase_path:
                        file_path = str(Path(codebase_path) / file_path)
                    else:
                        # No codebase - file_path should be absolute or relative to current directory
                        file_path = str(Path(file_path).resolve())
                
                print(f"Analysis Level: CODE SNIPPET (in file)")
                if codebase_path:
                    print(f"Codebase: {codebase_path}")
                else:
                    print(f"Mode: Standalone snippet (no codebase context)")
                print(f"File: {file_path}")
                if snippet_from_file:
                    print(f"Snippet source: {snippet_file_path}")
                    print(f"Snippet preview: {snippet_input[:100]}..." if len(snippet_input) > 100 else f"Snippet: {snippet_input}")
                else:
                    print(f"Snippet: {snippet_input[:100]}..." if len(snippet_input) > 100 else f"Snippet: {snippet_input}")
                
                # Match code snippet in file (for context/location only)
                matched_code, start_line, end_line = InputHandler.match_code_snippet_in_file(
                    file_path, snippet_input
                )
                if not matched_code:
                    raise ValueError(f"Could not find the provided code snippet in {file_path}. "
                                   f"Make sure the snippet matches the file content (whitespace variations are handled automatically).")
                
                print(f"Located at: Lines {start_line}-{end_line}")
                
                # Use the PROVIDED snippet for analysis (not the matched code)
                code = snippet_input
                
                print(f"Analyzing: {len(code)} characters (provided snippet)")
                
                input_metadata = InputHandler.prepare_input_metadata(
                    file_path=file_path,
                    codebase_path=codebase_path,
                    code_snippet=snippet_input,
                    snippet_start_line=start_line,
                    snippet_end_line=end_line
                )
            else:
                # MODE 2: --code-snippet alone (direct snippet analysis, no file)
                print(f"Analysis Level: CODE SNIPPET (standalone)")
                print(f"Mode: Standalone snippet (no file, no codebase)")
                if snippet_from_file:
                    print(f"Snippet source: {snippet_file_path}")
                print(f"Snippet: {snippet_input[:200]}..." if len(snippet_input) > 200 else f"Snippet: {snippet_input}")
                print(f"Analyzing: {len(snippet_input)} characters")
                
                # Direct analysis - no file context
                code = snippet_input
                
                input_metadata = InputHandler.prepare_input_metadata(
                    codebase_path=None,  # No codebase
                    file_path=None,  # No file
                    code_snippet=snippet_input
                )
        
        elif args.function:
            # FUNCTION LEVEL: [--codebase] + --file + --function
            if not args.file:
                raise ValueError("--function requires --file to specify which file contains the function")
            
            file_path = args.file
            # Resolve file path (could be relative to codebase or absolute)
            if not Path(file_path).is_absolute():
                if codebase_path:
                    file_path = str(Path(codebase_path) / file_path)
                else:
                    # No codebase - file_path should be absolute or relative to current directory
                    file_path = str(Path(file_path).resolve())
            
            print(f"Analysis Level: FUNCTION")
            if codebase_path:
                print(f"Codebase: {codebase_path}")
            else:
                print(f"Mode: Standalone function (no codebase context)")
            print(f"File: {file_path}")
            print(f"Function: {args.function}")
            
            # Extract function
            code, start_line, end_line = InputHandler.extract_function_from_file(
                file_path, args.function
            )
            if not code:
                raise ValueError(f"Could not find function '{args.function}' in {file_path}")
            
            print(f"Extracted: Lines {start_line}-{end_line} ({len(code)} characters)")
            
            input_metadata = InputHandler.prepare_input_metadata(
                file_path=file_path,
                function_name=args.function,
                codebase_path=codebase_path
            )
        
        elif args.file:
            # FILE LEVEL: [--codebase] + --file
            file_path = args.file
            # Resolve file path
            if not Path(file_path).is_absolute():
                if codebase_path:
                    file_path = str(Path(codebase_path) / file_path)
                else:
                    # No codebase - file_path should be absolute or relative to current directory
                    file_path = str(Path(file_path).resolve())
            
            print(f"Analysis Level: FILE")
            if codebase_path:
                print(f"Codebase: {codebase_path}")
            else:
                print(f"Mode: Standalone file (no codebase context)")
            print(f"File: {file_path}")
            
            # Load entire file
            code = InputHandler.load_and_preprocess(file_path)
            print(f"Loaded: {len(code)} characters")
            
            input_metadata = InputHandler.prepare_input_metadata(
                file_path=file_path,
                codebase_path=codebase_path
            )
        
        else:
            # CODEBASE LEVEL: --codebase only (must have codebase for this)
            if not codebase_path:
                raise ValueError("Codebase analysis requires --codebase. For standalone file analysis, use --file.")
            
            print(f"Analysis Level: CODEBASE")
            print(f"Codebase: {codebase_path}")
            print(f"Mode: Full codebase scan - all source files will be analyzed")
            
            # Empty code - pipeline will scan all files
            code = ""
            input_metadata = InputHandler.prepare_input_metadata(
                codebase_path=codebase_path
            )
        
        if not args.quiet:
            print(f"Input metadata: {input_metadata}\n")
        
        # Initialize model
        print(f"Initializing {args.model_type} model...")
        model = get_model(
            model_type=args.model_type,
            model_id=model_id,
            temperature=args.temperature,
            max_tokens=args.max_tokens
        )
        print(f"Model initialized: {model}\n")
        
        # Initialize logger for token tracking
        logger = VulTrialLogger(verbose=not args.quiet)
        
        # Initialize pipeline
        print("Setting up VulTrial pipeline...")
        
        # Auto-enable context retrieval if we have a codebase
        enable_context = args.enable_context or (codebase_path is not None)
        
        pipeline = VulTrialPipeline(
            model=model,
            max_turns=args.max_turns,
            verbose=not args.quiet,
            codebase_path=codebase_path,
            enable_context_retrieval=enable_context,
            enable_pre_debate_summary=(not args.no_pre_debate_summary) and enable_context,
            analysis_mode=args.mode,
            # Context management configuration
            max_evidence_items=args.max_evidence_items,
            max_evidence_tokens_per_item=args.max_evidence_tokens,
            max_evidence_lines_per_item=args.max_evidence_lines,
            evidence_total_token_budget=args.evidence_token_budget,
            history_compression_start_turn=args.history_compression_turn
        )
        
        # Attach logger to pipeline
        pipeline.set_logger(logger)
        
        if enable_context and codebase_path:
            print(f"✓ Context retrieval enabled for: {codebase_path}")
            if not args.no_pre_debate_summary:
                print(f"✓ Pre-debate summarization enabled")
        elif not codebase_path:
            print(f"⚠ Standalone mode: Research assistants disabled (no codebase)")
            print(f"  Agents will debate based on the provided code only")
        print("Pipeline ready.\n")
        
        # Run analysis
        print("Starting vulnerability analysis...\n")
        results = pipeline.run(code, input_metadata=input_metadata)
        
        # Display token usage and cost
        print("\n" + "="*80)
        print("TOKEN USAGE & COST")
        print("="*80)
        
        usage = logger.get_token_usage()
        print(f"Input tokens:  {usage['input_tokens']:,}")
        print(f"Output tokens: {usage['output_tokens']:,}")
        print(f"Total tokens:  {usage['total_tokens']:,}")
        
        # Try to get pricing from args or config
        price_input = args.price_input
        price_output = args.price_output
        
        # If not provided, try to load from config file
        if price_input is None or price_output is None:
            try:
                config = ConfigManager()
                price_input = price_input or config.get("price_input_per_million")
                price_output = price_output or config.get("price_output_per_million")
            except:
                pass
        
        # Calculate costs if pricing provided
        costs = None
        if price_input is not None and price_output is not None:
            costs = logger.calculate_cost(price_input, price_output)
            print(f"\nInput cost:    ${costs['input_cost']:.4f}")
            print(f"Output cost:   ${costs['output_cost']:.4f}")
            print(f"Total cost:    ${costs['total_cost']:.4f}")
        else:
            print("\n💡 Set --price-input and --price-output to track costs")
        
        print("="*80)
        
        # Print final results
        print("\n" + "="*80)
        print("FINAL RESULTS")
        print("="*80)
        
        # Check analysis type
        if "file_analyses" in results:
            # Codebase analysis mode
            print(f"\nAnalyzed {results.get('total_files', 0)} files with {results.get('total_functions', 0)} total functions\n")
            print("="*80)
            print("CODEBASE SECURITY ASSESSMENT")
            print("="*80)
            print(results.get("summary", "N/A"))
            print("="*80)
            
            # Show vulnerable files summary
            print("\nVulnerable Files:")
            for file_analysis in results.get('file_analyses', []):
                if file_analysis.get('vulnerable_functions', 0) > 0:
                    rel_path = file_analysis['relative_path']
                    vuln_count = file_analysis['vulnerable_functions']
                    total_funcs = file_analysis['total_functions']
                    print(f"  ⚠️  {rel_path}: {vuln_count}/{total_funcs} functions vulnerable")
            
            print(f"\nSummary: {results.get('vulnerable_files', 0)} vulnerable files, " +
                  f"{results.get('safe_files', 0)} safe files")
        
        elif "function_analyses" in results:
            # Multi-function file analysis mode
            print(f"\nAnalyzed {len(results['function_analyses'])} functions in file\n")
            print("="*80)
            print("OVERALL ASSESSMENT")
            print("="*80)
            print(results.get("overall_assessment", "N/A"))
            print("="*80)
            
            # Show summary of each function
            print("\nPer-Function Results:")
            for func_analysis in results["function_analyses"]:
                func_name = func_analysis["function_name"]
                decision = func_analysis["analysis_results"].get("final_decision", "N/A")
                print(f"\n  • {func_name}: {decision[:200]}...")
        else:
            # Single analysis mode
            print("\nFinal Decision from Review Board:")
            print("-" * 80)
            print(results["final_decision"])
            print("-" * 80)
        
        # Save to file/directory if requested
        if args.output:
            output_arg = Path(args.output)
            
            # Determine file and codebase paths
            analyzed_file = None
            analyzed_codebase = args.codebase
            
            if args.file:
                # Resolve file path
                if not Path(args.file).is_absolute():
                    analyzed_file = str(Path(args.codebase) / args.file)
                else:
                    analyzed_file = args.file
            
            # Prepare comprehensive JSON data
            analysis_level = "snippet" if args.code_snippet else ("function" if args.function else ("file" if args.file else "codebase"))
            
            save_data = ResultsSaver.prepare_json_data(
                results=results,
                file_path=analyzed_file,
                codebase_path=analyzed_codebase,
                model_type=args.model_type,
                model_id=model_id,
                token_usage=usage,
                elapsed_time=0,  # Not tracked in CLI mode
                additional_metadata={
                    "analysis_level": analysis_level,
                    "function_name": args.function if args.function else None,
                    "code_snippet": args.code_snippet if args.code_snippet else None,
                    "max_turns": args.max_turns,
                    "analysis_mode": args.mode,
                    "temperature": args.temperature,
                }
            )
            
            # Check if output is a directory or file
            if output_arg.exists() and output_arg.is_dir():
                # Directory - auto-generate filenames inside
                output_dir = output_arg
                
                # Generate auto filenames
                json_file = ResultsSaver.generate_output_filename(
                    file_path=analyzed_file,
                    codebase_path=analyzed_codebase,
                    output_dir=str(output_dir),
                    extension="json"
                )
                text_file = json_file.with_suffix('.txt')
                detailed_file = json_file.with_name(json_file.stem + '.detailed.txt')
                
                print(f"\n📁 Output directory: {output_dir}")
                print(f"   Auto-generating filenames...")
            
            elif not output_arg.exists() and not output_arg.suffix:
                # Looks like a directory (no extension) - create it
                output_dir = output_arg
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Generate auto filenames
                json_file = ResultsSaver.generate_output_filename(
                    file_path=analyzed_file,
                    codebase_path=analyzed_codebase,
                    output_dir=str(output_dir),
                    extension="json"
                )
                text_file = json_file.with_suffix('.txt')
                detailed_file = json_file.with_name(json_file.stem + '.detailed.txt')
                
                print(f"\n📁 Created output directory: {output_dir}")
                print(f"   Auto-generating filenames...")
            
            else:
                # Specific file - use as base name
                json_file = output_arg.with_suffix('.json')
                text_file = output_arg.with_suffix('.txt')
                detailed_file = output_arg.with_name(output_arg.stem + '.detailed.txt')
            
            # Save JSON
            if ResultsSaver.save_json(save_data, json_file):
                print(f"\n✅ JSON results: {json_file}")
            else:
                print(f"\n❌ Failed to save JSON")
            
            # Save text summary
            if ResultsSaver.save_text_summary(save_data, text_file):
                print(f"✅ Text summary: {text_file}")
            else:
                print(f"❌ Failed to save text summary")
            
            # Store cache for output writing
            search_cache = pipeline.search_cache
            
            # Save detailed version with full debate history
            detailed_path = detailed_file
            with open(detailed_path, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("VulTrial Analysis Results (Detailed)\n")
                f.write("="*80 + "\n\n")
                
                # Write analysis target info
                f.write(f"Codebase: {args.codebase}\n")
                if args.file:
                    f.write(f"File: {args.file}\n")
                if args.code_snippet:
                    f.write(f"Code Snippet: {args.code_snippet[:100]}...\n" if len(args.code_snippet) > 100 else f"Code Snippet: {args.code_snippet}\n")
                    if results.get("input_metadata", {}).get("snippet_start_line"):
                        f.write(f"Lines: {results['input_metadata']['snippet_start_line']}-{results['input_metadata']['snippet_end_line']}\n")
                if args.function:
                    f.write(f"Function: {args.function}\n")
                
                f.write(f"Model: {args.model_type} ({model_id})\n")
                f.write(f"Turns: {args.max_turns}\n")
                if results.get("input_metadata", {}).get("analysis_scope"):
                    f.write(f"Scope: {results['input_metadata']['analysis_scope']}\n")
                
                # Add token usage and cost
                f.write(f"\n{'='*80}\n")
                f.write("TOKEN USAGE & COST\n")
                f.write(f"{'='*80}\n")
                f.write(f"Input tokens:  {usage['input_tokens']:,}\n")
                f.write(f"Output tokens: {usage['output_tokens']:,}\n")
                f.write(f"Total tokens:  {usage['total_tokens']:,}\n")
                
                if costs is not None:
                    f.write(f"\nInput cost:    ${costs['input_cost']:.4f} (${price_input}/M)\n")
                    f.write(f"Output cost:   ${costs['output_cost']:.4f} (${price_output}/M)\n")
                    f.write(f"Total cost:    ${costs['total_cost']:.4f}\n")
                f.write("\n")
                
                # Check analysis type
                if "file_analyses" in results:
                    # Codebase analysis output
                    f.write(f"\nMode: Codebase Analysis\n")
                    f.write(f"Files Analyzed: {results.get('total_files', 0)}\n")
                    f.write(f"Total Functions: {results.get('total_functions', 0)}\n")
                    f.write(f"Vulnerable Files: {results.get('vulnerable_files', 0)}\n")
                    f.write(f"Vulnerable Functions: {results.get('vulnerable_functions', 0)}\n\n")
                    
                    # Write overall codebase assessment
                    f.write(f"\n{'='*80}\n")
                    f.write("CODEBASE SECURITY ASSESSMENT\n")
                    f.write(f"{'='*80}\n\n")
                    f.write(results.get("summary", "N/A") + "\n")
                    
                    # Write each file's results
                    for file_analysis in results.get('file_analyses', []):
                        rel_path = file_analysis.get('relative_path', 'unknown')
                        vuln_count = file_analysis.get('vulnerable_functions', 0)
                        total_funcs = file_analysis.get('total_functions', 0)
                        
                        f.write(f"\n\n{'='*80}\n")
                        f.write(f"FILE: {rel_path}\n")
                        f.write(f"Vulnerable: {vuln_count}/{total_funcs} functions\n")
                        f.write(f"{'='*80}\n\n")
                        
                        # Write file results if available
                        if 'file_results' in file_analysis and 'overall_assessment' in file_analysis['file_results']:
                            f.write(file_analysis['file_results']['overall_assessment'] + "\n")
                
                elif "function_analyses" in results:
                    # Multi-function output
                    f.write(f"\nMode: Multi-Function Analysis\n")
                    f.write(f"Functions Analyzed: {len(results['function_analyses'])}\n\n")
                    
                    # Write file summary (from cache)
                    file_path = results.get("input_metadata", {}).get("file_path")
                    cache_key = f"file_summary_{file_path}"
                    if cache_key in search_cache:
                        f.write(f"\n{'='*80}\n")
                        f.write("FILE SUMMARY (Shared for all functions)\n")
                        f.write(f"{'='*80}\n\n")
                        f.write(search_cache[cache_key] + "\n")
                    
                    # Write each function analysis
                    for idx, func_analysis in enumerate(results["function_analyses"], 1):
                        func_name = func_analysis["function_name"]
                        func_results = func_analysis["analysis_results"]
                        
                        f.write(f"\n\n{'='*80}\n")
                        f.write(f"FUNCTION {idx}/{len(results['function_analyses'])}: {func_name}\n")
                        f.write(f"Lines: {func_analysis['function_info']['start_line']}-{func_analysis['function_info']['end_line']}\n")
                        f.write(f"{'='*80}\n\n")
                        
                        # Write turns for this function
                        for i, turn in enumerate(func_results.get("turns", []), 1):
                            f.write(f"\n{'='*60}\n")
                            f.write(f"Turn {i}\n")
                            f.write(f"{'='*60}\n\n")
                            
                            # Write prompts if available
                            if i <= len(func_results.get("prompts", [])):
                                turn_prompts = func_results["prompts"][i-1]
                                if turn_prompts:
                                    f.write(f"\n[PROMPTS]:\n")
                                    for agent, prompt in turn_prompts.items():
                                        f.write(f"  {agent}:\n{prompt}\n\n")
                            
                            # Write responses
                            for agent, response in turn.items():
                                f.write(f"\n[{agent.upper()}]:\n")
                                f.write("-" * 40 + "\n")
                                f.write(response + "\n")
                                f.write("-" * 40 + "\n")
                            
                            # Write evidence if available
                            if i <= len(func_results.get("evidence_gathered", [])):
                                turn_evidence = func_results["evidence_gathered"][i-1]
                                if turn_evidence:
                                    f.write(f"\n[EVIDENCE RETRIEVED]:\n")
                                    for agent, evidence_data in turn_evidence.items():
                                        if evidence_data.get('needs_search'):
                                            f.write(f"  {agent}: {len(evidence_data.get('evidence', []))} items found\n")
                        
                        # Write final decision for this function
                        f.write(f"\n{'='*60}\n")
                        f.write(f"FINAL DECISION FOR {func_name}\n")
                        f.write(f"{'='*60}\n\n")
                        
                        # Write Review Board prompt if available
                        if func_results.get("review_board_prompt"):
                            f.write(f"[PROMPT TO REVIEW BOARD]:\n")
                            f.write("-" * 40 + "\n")
                            # Truncate for multi-function to avoid very long output
                            rb_prompt = func_results["review_board_prompt"]
                            if len(rb_prompt) > 3000:
                                f.write(rb_prompt[:3000] + f"\n... (truncated, {len(rb_prompt)} total chars)\n")
                            else:
                                f.write(rb_prompt + "\n")
                            f.write("-" * 40 + "\n\n")
                        
                        f.write(f"[DECISION]:\n")
                        f.write(func_results.get("final_decision", "N/A") + "\n")
                    
                    # Write overall assessment
                    f.write(f"\n\n{'='*80}\n")
                    f.write("OVERALL FILE ASSESSMENT\n")
                    f.write(f"{'='*80}\n\n")
                    f.write(results.get("overall_assessment", "N/A") + "\n")
                
                else:
                    # Single analysis output
                    # Write file summary if available (from cache)
                    file_path = results.get("input_metadata", {}).get("file_path")
                    if file_path:
                        cache_key = f"file_summary_{file_path}"
                        if cache_key in search_cache:
                            f.write(f"\n{'='*80}\n")
                            f.write("FILE CONTEXT (Auto-Generated)\n")
                            f.write(f"{'='*80}\n\n")
                            f.write(search_cache[cache_key] + "\n")
                    
                    for i, turn in enumerate(results["turns"], 1):
                        f.write(f"\n{'='*80}\n")
                        f.write(f"TURN {i}\n")
                        f.write(f"{'='*80}\n\n")
                        
                        # Write prompts if available
                        if i <= len(results.get("prompts", [])):
                            turn_prompts = results["prompts"][i-1]
                            if turn_prompts:
                                f.write(f"\n{'~'*80}\n")
                                f.write(f"PROMPTS SENT TO AGENTS (Turn {i})\n")
                                f.write(f"{'~'*80}\n")
                                for agent, prompt in turn_prompts.items():
                                    f.write(f"\n[PROMPT TO {agent.upper()}]:\n")
                                    f.write("-" * 40 + "\n")
                                    f.write(prompt + "\n")
                                    f.write("-" * 40 + "\n")
                        
                        # Write agent responses
                        for agent, response in turn.items():
                            f.write(f"\n[{agent.upper()}]:\n")
                            f.write("-" * 80 + "\n")
                            f.write(response + "\n")
                            f.write("-" * 80 + "\n")
                        
                        # Write evidence gathered if available
                        if i <= len(results.get("evidence_gathered", [])):
                            turn_evidence = results["evidence_gathered"][i-1]
                            if turn_evidence:
                                f.write(f"\n{'~'*80}\n")
                                f.write(f"EVIDENCE RETRIEVED BY ASSISTANTS (Turn {i})\n")
                                f.write(f"{'~'*80}\n")
                                for agent, evidence_data in turn_evidence.items():
                                    f.write(f"\n[EVIDENCE FOR {agent.upper()}]:\n")
                                    f.write("-" * 40 + "\n")
                                    if evidence_data.get('needs_search'):
                                        f.write(f"Query: {evidence_data.get('query', 'N/A')}\n")
                                        f.write(f"Evidence found: {len(evidence_data.get('evidence', []))} items\n\n")
                                        if evidence_data.get('summary'):
                                            f.write(f"Summary:\n{evidence_data['summary']}\n\n")
                                        # Detailed evidence is already in summary, but show structure if needed
                                        if evidence_data.get('evidence'):
                                            f.write(f"Detailed Evidence:\n\n")
                                            for idx, ev in enumerate(evidence_data['evidence'], 1):
                                                f.write(f"  Evidence {idx}:\n")
                                                f.write(f"    Type: {ev.get('type', 'N/A')}\n")
                                                # Get the actual code content
                                                content = ev.get('code') or ev.get('context') or ev.get('content', '')
                                                if content:
                                                    f.write(f"    Content:\n{content}\n\n")
                                    else:
                                        f.write(f"No search needed (assistant determined existing context sufficient)\n")
                                    f.write("-" * 40 + "\n")
                    
                    f.write(f"\n{'='*80}\n")
                    f.write("FINAL DECISION\n")
                    f.write(f"{'='*80}\n\n")
                    
                    # Write Review Board prompt if available
                    if results.get("review_board_prompt"):
                        f.write(f"[PROMPT TO REVIEW BOARD]:\n")
                        f.write("-" * 80 + "\n")
                        f.write(results["review_board_prompt"] + "\n")
                        f.write("-" * 80 + "\n\n")
                    
                    f.write(f"[FINAL DECISION FROM REVIEW BOARD]:\n")
                    f.write("-" * 80 + "\n")
                    f.write(results["final_decision"] + "\n")
                    f.write("-" * 80 + "\n")
            
            print(f"✅ Detailed log: {detailed_path}")
        
        print("\n" + "="*80)
        print("Analysis complete!")
        print("="*80 + "\n")
        
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

