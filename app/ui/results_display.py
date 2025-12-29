"""Results Display - Enhanced results with inline details"""

import json
from typing import Dict, Any, List
from .components import colored, Colors, print_divider, print_header, print_info


class ResultsDisplay:
    """Display analysis results"""
    
    @staticmethod
    def show_results(results: Dict[str, Any], logger):
        """
        Display results with token usage
        
        Args:
            results: Results from pipeline
            logger: Logger with token tracking
        """
        # Show results
        if "file_analyses" in results:
            # Codebase analysis
            ResultsDisplay._show_codebase_results(results)
        elif "function_analyses" in results:
            # Multi-function file analysis
            ResultsDisplay._show_multi_function_results(results)
        else:
            # Single function analysis
            ResultsDisplay._show_single_function_results(results)
        
        # Show token usage
        ResultsDisplay._show_token_usage(logger)
    
    @staticmethod
    def _show_codebase_results(results):
        """Display codebase analysis results"""
        print()
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print(colored("  📊 Codebase Analysis Results", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print()
        
        total_files = results.get('total_files', 0)
        total_functions = results.get('total_functions', 0)
        vulnerable_files = results.get('vulnerable_files', 0)
        vulnerable_functions = results.get('vulnerable_functions', 0)
        safe_files = results.get('safe_files', 0)
        
        print_info(f"Files analyzed: {colored(str(total_files), Colors.BRIGHT_CYAN)}")
        print_info(f"Total functions: {colored(str(total_functions), Colors.BRIGHT_CYAN)}")
        print()
        
        # Show vulnerable files
        if vulnerable_files > 0:
            print(colored("  ⚠️  Vulnerable Files:", Colors.BRIGHT_RED, bold=True))
            print()
            
            for file_analysis in results.get('file_analyses', []):
                if file_analysis.get('vulnerable_functions', 0) > 0:
                    rel_path = file_analysis['relative_path']
                    vuln_count = file_analysis['vulnerable_functions']
                    total_funcs = file_analysis['total_functions']
                    
                    print(f"  {colored('⚠️ ', Colors.BRIGHT_RED)}  {colored(rel_path, Colors.BRIGHT_WHITE)}")
                    print(f"      {colored(f'{vuln_count}/{total_funcs} functions vulnerable', Colors.BRIGHT_YELLOW)}")
                    print()
        else:
            print(colored("  ✓ No vulnerabilities found in codebase!", Colors.BRIGHT_GREEN, bold=True))
            print()
        
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print(f"  Summary: {colored(f'{vulnerable_files}', Colors.BRIGHT_RED)} vulnerable files, " +
              f"{colored(f'{safe_files}', Colors.BRIGHT_GREEN)} safe files")
        print(f"           {colored(f'{vulnerable_functions}', Colors.BRIGHT_RED)} vulnerable functions, " +
              f"{colored(f'{total_functions - vulnerable_functions}', Colors.BRIGHT_GREEN)} safe functions")
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print()
    
    @staticmethod
    def _show_multi_function_results(results):
        """Display multi-function results with inline details"""
        print()
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print(colored("  📊 Analysis Results", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print()
        
        print_info(f"Functions: {colored(str(len(results['function_analyses'])), Colors.BRIGHT_CYAN)}")
        print()
        
        vulnerable_count = 0
        safe_count = 0
        
        for func_analysis in results["function_analyses"]:
            func_name = func_analysis["function_name"]
            decision = func_analysis["analysis_results"].get("final_decision", "")
            
            # Parse verdicts
            verdicts = ResultsDisplay._parse_verdicts(decision)
            
            if len(verdicts) == 0:
                print(f"  {colored('✓', Colors.BRIGHT_GREEN)}  {colored(func_name, Colors.BRIGHT_WHITE):40s} {colored('SAFE', Colors.BRIGHT_GREEN)}")
                safe_count += 1
            else:
                # Check for valid vulnerabilities
                valid_vulns = [v for v in verdicts if v.get('decision') == 'valid']
                
                if valid_vulns:
                    print(f"  {colored('⚠️ ', Colors.BRIGHT_RED)}  {colored(func_name, Colors.BRIGHT_WHITE):40s} {colored('VULNERABLE', Colors.BRIGHT_RED, bold=True)}")
                    vulnerable_count += 1
                    
                    # Show details inline
                    for v in valid_vulns:
                        vuln_name = v.get('vulnerability', 'Unknown')
                        severity = v.get('severity', 'unknown').upper()
                        confidence = v.get('confidence', 0.0)
                        
                        severity_color = Colors.BRIGHT_RED if severity == 'HIGH' else Colors.BRIGHT_YELLOW
                        conf_str = f"{int(confidence * 100)}%" if confidence > 0 else "N/A"
                        
                        print(f"     {colored('→', Colors.BRIGHT_BLACK)} {colored(vuln_name, Colors.BRIGHT_WHITE)} " +
                              f"{colored(f'({severity})', severity_color)} • " +
                              f"{colored(f'{conf_str} confident', Colors.BRIGHT_BLACK)}")
                else:
                    print(f"  {colored('✓', Colors.BRIGHT_GREEN)}  {colored(func_name, Colors.BRIGHT_WHITE):40s} {colored('SAFE', Colors.BRIGHT_GREEN)}")
                    safe_count += 1
        
        print()
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print(f"  Summary: {colored(f'{vulnerable_count}', Colors.BRIGHT_RED)} vulnerable, " +
              f"{colored(f'{safe_count}', Colors.BRIGHT_GREEN)} safe")
        print_divider("─", 70, Colors.BRIGHT_BLACK)
        print()
    
    @staticmethod
    def _show_single_function_results(results):
        """Display single function results"""
        print()
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print(colored("  📊 Analysis Results", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print()
        
        decision = results.get("final_decision", "")
        verdicts = ResultsDisplay._parse_verdicts(decision)
        
        # Filter to only show valid vulnerabilities
        valid_vulns = [v for v in verdicts if v.get('decision') == 'valid']
        
        if len(valid_vulns) == 0:
            print(f"  {colored('✓ No vulnerabilities found', Colors.BRIGHT_GREEN, bold=True)}")
        else:
            for v in valid_vulns:
                vuln_name = v.get('vulnerability', 'Unknown')
                severity = v.get('severity', 'none')
                confidence = v.get('confidence', 0.0)
                
                print(f"  {colored('⚠️ ', Colors.BRIGHT_RED)}  {colored(vuln_name, Colors.BRIGHT_WHITE, bold=True)}")
                print(f"      Decision: {colored('VALID', Colors.BRIGHT_RED, bold=True)}")
                if severity != 'none':
                    print(f"      Severity: {colored(severity.upper(), Colors.BRIGHT_RED)}")
                if confidence > 0:
                    print(f"      Confidence: {colored(f'{int(confidence*100)}%', Colors.BRIGHT_GREEN)}")
                print()
        
        print_divider("═", 70, Colors.BRIGHT_MAGENTA)
        print()
    
    @staticmethod
    def _show_token_usage(logger):
        """Display token usage and cost"""
        if not logger:
            return
        
        usage = logger.get_token_usage()
        
        print_divider("═", 70, Colors.BRIGHT_CYAN)
        print(colored("  📊 Token Usage & Cost", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", 70, Colors.BRIGHT_CYAN)
        print()
        
        input_tokens_str = f"{usage['input_tokens']:,}"
        output_tokens_str = f"{usage['output_tokens']:,}"
        total_tokens_str = f"{usage['total_tokens']:,}"
        
        print(f"  {colored('Input tokens:', Colors.BRIGHT_WHITE):18s}  {colored(input_tokens_str, Colors.BRIGHT_CYAN)}")
        print(f"  {colored('Output tokens:', Colors.BRIGHT_WHITE):18s}  {colored(output_tokens_str, Colors.BRIGHT_CYAN)}")
        print(f"  {colored('Total tokens:', Colors.BRIGHT_WHITE):18s}  {colored(total_tokens_str, Colors.BRIGHT_YELLOW, bold=True)}")
        
        print()
        print_divider("═", 70, Colors.BRIGHT_CYAN)
        print()
    
    @staticmethod
    def _parse_verdicts(decision_text: str) -> List[Dict[str, Any]]:
        """Parse JSON verdicts from decision text"""
        try:
            if '```json' in decision_text:
                decision_text = decision_text.split('```json')[1].split('```')[0]
            elif '```' in decision_text:
                decision_text = decision_text.split('```')[1].split('```')[0]
            
            verdicts = json.loads(decision_text)
            
            # Handle both list and single dict
            if isinstance(verdicts, list):
                return verdicts
            elif isinstance(verdicts, dict):
                # Single verdict - wrap in list
                return [verdicts]
            else:
                return []
        except:
            return []

