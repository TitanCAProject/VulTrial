"""
VulTrial - Code Snippet Vulnerability Analyzer

Multi-agent debate framework for detecting security vulnerabilities in code.
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

from .models import HuggingFaceModel
from .pipeline import VulTrialPipeline
from .utils import VulTrialLogger


def get_model(model_id: str, quantization: str = "none", **kwargs):
    """
    Get model instance
    
    Args:
        model_id: Model identifier from Hugging Face Hub
        quantization: Quantization mode ('none', '8bit', '4bit')
        **kwargs: Additional model parameters
        
    Returns:
        Model instance
    """
    # Set quantization flags
    load_in_8bit = quantization == "8bit"
    load_in_4bit = quantization == "4bit"
    
    return HuggingFaceModel(
        model_id=model_id,
        load_in_8bit=load_in_8bit,
        load_in_4bit=load_in_4bit,
        **kwargs
    )


def load_snippet(snippet_input: str) -> str:
    """
    Load code snippet from input (either direct code or file path)
    
    Args:
        snippet_input: Either code string or path to file
        
    Returns:
        Code snippet string
    """
    # Strip quotes if present
    if snippet_input.startswith('"') and snippet_input.endswith('"'):
        snippet_input = snippet_input[1:-1]
    elif snippet_input.startswith("'") and snippet_input.endswith("'"):
        snippet_input = snippet_input[1:-1]
    
    # Handle literal \n in input
    if '\\n' in snippet_input and '\n' not in snippet_input:
        snippet_input = snippet_input.replace('\\n', '\n')
    
    # Check if it's a file path
    is_multiline = '\n' in snippet_input
    
    if not is_multiline and len(snippet_input) < 260:
        try:
            potential_path = Path(snippet_input)
            if potential_path.exists() and potential_path.is_file():
                with open(potential_path, 'r', encoding='utf-8', errors='ignore') as f:
                    snippet_input = f.read()
                print(f"Loaded snippet from file: {potential_path}")
        except (OSError, ValueError):
            pass
    
    return snippet_input


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="VulTrial - Code Snippet Vulnerability Analyzer (Open Source Models)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze code snippet with Qwen 7B (default)
  python -m app.main --code-snippet "if (user) { admin_check(); }"

  # Use Qwen 32B with 4-bit quantization (saves memory)
  python -m app.main --code-snippet "code" --model Qwen/Qwen2-32B-Instruct --quantization 4bit

  # Use Llama 3 8B with 8-bit quantization
  python -m app.main --code-snippet "code" --model meta-llama/Meta-Llama-3-8B-Instruct --quantization 8bit

  # Load snippet from file
  python -m app.main --code-snippet /path/to/snippet.c --model Qwen/Qwen2-7B-Instruct

  # Save results to file
  python -m app.main --code-snippet "code" --output results.json

Recommended Models (from Hugging Face Hub):
  - Qwen/Qwen2-32B-Instruct       (best balance of quality and speed)
  - meta-llama/Meta-Llama-3-70B-Instruct  (highest quality, requires more memory)
  - meta-llama/Meta-Llama-3-8B-Instruct   (fast, good quality)
  - codellama/CodeLlama-34b-Instruct-hf   (specialized for code)
  - mistralai/Mistral-7B-Instruct-v0.3    (fast, efficient)

Note: Some models require Hugging Face authentication. Set HF_TOKEN environment variable:
  export HF_TOKEN="your_huggingface_token"
        """
    )
    
    parser.add_argument(
        '--code-snippet',
        type=str,
        required=True,
        help='Code snippet to analyze (direct code or path to file)'
    )
    
    parser.add_argument(
        '--model', '-m',
        type=str,
        default='Qwen/Qwen2-7B-Instruct',
        help='Hugging Face model ID (default: Qwen/Qwen2-7B-Instruct)'
    )
    
    parser.add_argument(
        '--quantization', '-q',
        type=str,
        default='none',
        choices=['none', '8bit', '4bit'],
        help='Quantization mode to save memory (default: none)'
    )
    
    parser.add_argument(
        '--max-turns',
        type=int,
        default=4,
        help='Maximum number of debate turns (default: 4)'
    )
    
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.7,
        help='Model temperature 0-1 (default: 0.7)'
    )
    
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=2048,
        help='Maximum tokens to generate per response (default: 2048)'
    )
    
    parser.add_argument(
        '--device',
        type=str,
        default=None,
        choices=['cuda', 'cpu'],
        help='Device to run on (default: auto-detect)'
    )
    
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress verbose output'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=None,
        help='Output file path for results (JSON format)'
    )
    
    args = parser.parse_args()
    
    # Print header
    print(f"\n{'='*70}")
    print(f"VulTrial - Code Snippet Vulnerability Analyzer")
    print(f"{'='*70}")
    print(f"Model: {args.model}")
    if args.quantization != 'none':
        print(f"Quantization: {args.quantization}")
    print(f"Max turns: {args.max_turns}")
    print(f"{'='*70}\n")
    
    try:
        # Load code snippet
        code = load_snippet(args.code_snippet)
        print(f"Analyzing: {len(code)} characters")
        print(f"Snippet preview: {code[:100]}..." if len(code) > 100 else f"Snippet: {code}")
        print()
        
        # Initialize model
        print(f"Initializing model...")
        model = get_model(
            model_id=args.model,
            quantization=args.quantization,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            device=args.device
        )
        print(f"Model initialized: {model}\n")
        
        # Initialize logger
        logger = VulTrialLogger(verbose=not args.quiet)
        
        # Initialize pipeline
        print("Setting up VulTrial pipeline...")
        pipeline = VulTrialPipeline(
            model=model,
            max_turns=args.max_turns,
            verbose=not args.quiet
        )
        pipeline.set_logger(logger)
        print("Pipeline ready.\n")
        
        # Run analysis
        print("Starting vulnerability analysis...\n")
        results = pipeline.run(code)
        
        # Display token usage
        print("\n" + "="*70)
        print("TOKEN USAGE")
        print("="*70)
        usage = logger.get_token_usage()
        print(f"Input tokens:  {usage['input_tokens']:,}")
        print(f"Output tokens: {usage['output_tokens']:,}")
        print(f"Total tokens:  {usage['total_tokens']:,}")
        print("="*70)
        
        # Print final results
        print("\n" + "="*70)
        print("FINAL DECISION")
        print("="*70)
        print(results["final_decision"])
        print("="*70)
        
        # Save to file if requested
        if args.output:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "model": args.model,
                "quantization": args.quantization,
                "code_snippet": code,
                "max_turns": args.max_turns,
                "token_usage": usage,
                "final_decision": results["final_decision"],
                "turns": results["turns"]
            }
            
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"\n✅ Results saved to: {output_path}")
        
        print("\n" + "="*70)
        print("Analysis complete!")
        print("="*70 + "\n")
        
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
