"""Generates overall assessments for files and codebases"""

import json
from typing import Dict, Any
from ...models.base import BaseLLMModel
from ...prompts import FILE_ASSESSMENT_PROMPT, CODEBASE_ASSESSMENT_PROMPT


class AssessmentGenerator:
    """Generates overall assessments for files and codebases"""
    
    def __init__(self, model: BaseLLMModel, verbose: bool = False):
        """
        Initialize assessment generator
        
        Args:
            model: LLM model to use for generating assessments
            verbose: Whether to print verbose output
        """
        self.model = model
        self.verbose = verbose
    
    def generate_file_assessment(self, combined_results: Dict[str, Any]) -> str:
        """
        Generate an overall assessment from all function analyses in a file
        
        Args:
            combined_results: Results from analyzing all functions in a file
            
        Returns:
            Overall assessment string
        """
        try:
            # Collect all vulnerabilities found
            all_vulnerabilities = []
            
            for func_analysis in combined_results.get("function_analyses", []):
                func_name = func_analysis["function_name"]
                final_decision = func_analysis["analysis_results"].get("final_decision", "")
                
                all_vulnerabilities.append({
                    "function": func_name,
                    "decision": final_decision
                })
            
            # Build function summaries
            function_summaries = ""
            for i, vuln in enumerate(all_vulnerabilities, 1):
                function_summaries += f"\n{i}. Function '{vuln['function']}':\n{vuln['decision'][:500]}...\n"
            
            # Use prompt template
            prompt = FILE_ASSESSMENT_PROMPT.format(
                num_functions=len(all_vulnerabilities),
                file_path=combined_results.get('input_metadata', {}).get('file_path', 'unknown'),
                function_summaries=function_summaries
            )
            
            messages = [{"role": "user", "content": prompt}]
            response = self.model.generate(messages, temperature=0.4)
            
            return response
        
        except Exception as e:
            if self.verbose:
                print(f"Error generating overall assessment: {e}")
            return "Overall assessment generation failed"
    
    def generate_codebase_assessment(self, codebase_results: Dict[str, Any]) -> str:
        """
        Generate high-level codebase security summary
        
        Args:
            codebase_results: Results from analyzing entire codebase
            
        Returns:
            Codebase assessment string
        """
        try:
            # Collect vulnerable files
            vulnerable_files = []
            for file_analysis in codebase_results.get('file_analyses', []):
                if file_analysis.get('vulnerable_functions', 0) > 0:
                    vulnerable_files.append({
                        'file': file_analysis.get('relative_path', 'unknown'),
                        'vulns': file_analysis['vulnerable_functions'],
                        'total': file_analysis.get('total_functions', 0)
                    })
            
            # Build vulnerable files list
            vulnerable_files_list = ""
            for vf in vulnerable_files[:20]:  # Show top 20
                vulnerable_files_list += f"- {vf['file']}: {vf['vulns']}/{vf['total']} functions vulnerable\n"
            
            # Use prompt template
            prompt = CODEBASE_ASSESSMENT_PROMPT.format(
                codebase_path=codebase_results.get('codebase_path', 'unknown'),
                total_files=codebase_results.get('total_files', 0),
                total_functions=codebase_results.get('total_functions', 0),
                vulnerable_functions=codebase_results.get('vulnerable_functions', 0),
                vulnerable_files=codebase_results.get('vulnerable_files', 0),
                vulnerable_files_list=vulnerable_files_list
            )
            
            messages = [{"role": "user", "content": prompt}]
            response = self.model.generate(messages, temperature=0.4)
            
            return response
            
        except Exception as e:
            if self.verbose:
                print(f"Error generating codebase summary: {e}")
            return "Codebase summary generation failed"

