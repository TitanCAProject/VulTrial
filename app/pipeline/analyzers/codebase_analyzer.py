"""Codebase analyzer - analyzes entire codebase file-by-file"""

from pathlib import Path
from typing import Dict, Any
from ...utils.input_handler import InputHandler
from ...utils.logger import VulTrialLogger
from .multi_function_analyzer import MultiFunctionAnalyzer
from ..managers.assessment_generator import AssessmentGenerator


class CodebaseAnalyzer:
    """Analyzes an entire codebase file-by-file"""
    
    def __init__(
        self,
        multi_function_analyzer: MultiFunctionAnalyzer,
        assessment_generator: AssessmentGenerator,
        verbose: bool = True,
        logger: VulTrialLogger = None
    ):
        """
        Initialize codebase analyzer
        
        Args:
            multi_function_analyzer: Multi-function analyzer for each file
            assessment_generator: Generator for codebase assessment
            verbose: Whether to print verbose output
            logger: Optional logger
        """
        self.multi_function_analyzer = multi_function_analyzer
        self.assessment_generator = assessment_generator
        self.verbose = verbose
        self.logger = logger
    
    def analyze(self, input_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze entire codebase - all files with all functions
        
        Args:
            input_metadata: Metadata about the codebase
            
        Returns:
            Combined results from analyzing all files
        """
        codebase_path = input_metadata['codebase_path']
        
        if self.verbose:
            print("\n" + "="*80)
            print("VulTrial Codebase Analysis Mode")
            print("="*80)
            print(f"Codebase: {codebase_path}")
            print("Strategy: Analyze all source files function-by-function")
            print("="*80)
        
        # Step 1: Find all source files
        source_files = self._find_source_files(codebase_path)
        
        if not source_files:
            from ...ui.components import print_error
            print()
            print_error("No source files found in codebase")
            return {
                'code': '',
                'input_metadata': input_metadata,
                'error': 'No source files found'
            }
        
        self._display_file_list(codebase_path, source_files)
        
        # Step 2: Analyze each file
        codebase_results = self._initialize_results(codebase_path, input_metadata, source_files)
        
        for file_idx, file_path in enumerate(source_files, 1):
            rel_path = file_path.relative_to(Path(codebase_path))
            
            self._analyze_file(file_path, rel_path, file_idx, len(source_files), codebase_path, codebase_results)
        
        # Step 3: Generate overall codebase summary
        codebase_results['summary'] = self.assessment_generator.generate_codebase_assessment(codebase_results)
        
        if self.verbose:
            print("\n" + "="*80)
            print("Codebase Analysis Completed")
            print("="*80 + "\n")
        
        return codebase_results
    
    def _find_source_files(self, codebase_path: str) -> list:
        """Find all source files in codebase"""
        from ...ui.constants import UIConstants
        from ...ui.components import print_success
        
        print()
        print(f"  Scanning codebase for source files...", end='', flush=True)
        
        codebase = Path(codebase_path)
        all_files = []
        
        for ext in UIConstants.SUPPORTED_EXTENSIONS:
            all_files.extend(codebase.rglob(f'*{ext}'))
        
        # Filter out test files and __pycache__
        source_files = []
        for f in all_files:
            rel_path = str(f.relative_to(codebase))
            if 'test' not in rel_path.lower() and '__pycache__' not in rel_path:
                source_files.append(f)
        
        source_files.sort()
        
        print("\r" + " "*70 + "\r", end='')
        
        if source_files and self.verbose:
            print()
            print_success(f"Found {str(len(source_files))} source files")
            print()
        
        return source_files
    
    def _display_file_list(self, codebase_path: str, source_files: list):
        """Display list of files to analyze"""
        from ...ui.constants import FileIcons
        
        if self.verbose:
            print("  Files to analyze:")
            codebase = Path(codebase_path)
            for i, file_path in enumerate(source_files[:10], 1):
                rel_path = file_path.relative_to(codebase)
                icon = FileIcons.get_icon(str(rel_path))
                print(f"    {i}. {icon} {str(rel_path)}")
            if len(source_files) > 10:
                print(f"    ... and {len(source_files) - 10} more files")
            print()
    
    def _initialize_results(self, codebase_path: str, input_metadata: Dict[str, Any], source_files: list) -> Dict[str, Any]:
        """Initialize results structure"""
        return {
            'codebase_path': codebase_path,
            'input_metadata': input_metadata,
            'file_analyses': [],
            'summary': None,
            'total_files': len(source_files),
            'vulnerable_files': 0,
            'safe_files': 0,
            'total_functions': 0,
            'vulnerable_functions': 0
        }
    
    def _analyze_file(
        self,
        file_path: Path,
        rel_path: Path,
        file_idx: int,
        total_files: int,
        codebase_path: str,
        codebase_results: Dict[str, Any]
    ):
        """Analyze a single file"""
        from ...ui.constants import UIConstants, Colors
        from ...ui.components import colored, print_success, print_warning, print_error, print_divider
        
        if self.logger:
            self.logger.log_phase(f"Analyzing File {file_idx}/{total_files}: {rel_path}")
        
        print()
        print_divider("═", UIConstants.DIVIDER_WIDTH, Colors.BRIGHT_CYAN)
        print(colored(f"  📄 File {file_idx}/{total_files}: {rel_path}", Colors.BRIGHT_WHITE, bold=True))
        print_divider("═", UIConstants.DIVIDER_WIDTH, Colors.BRIGHT_CYAN)
        print()
        
        try:
            # Load file
            file_code = InputHandler.load_and_preprocess(str(file_path))
            
            # Create metadata for this file
            file_metadata = {
                'input_type': 'file',
                'file_path': str(file_path),
                'codebase_path': codebase_path,
                'analysis_scope': f"File '{rel_path}' in codebase"
            }
            
            # Run multi-function analysis on this file
            file_results = self.multi_function_analyzer.analyze(file_code, file_metadata)
            
            # Count vulnerabilities in this file
            file_vuln_count = self._count_file_vulnerabilities(file_results)
            
            # Update statistics
            if 'function_analyses' in file_results:
                codebase_results['total_functions'] += len(file_results['function_analyses'])
                codebase_results['vulnerable_functions'] += file_vuln_count
            
            # Add to results
            codebase_results['file_analyses'].append({
                'file_path': str(file_path),
                'relative_path': str(rel_path),
                'file_results': file_results,
                'vulnerable_functions': file_vuln_count,
                'total_functions': len(file_results.get('function_analyses', []))
            })
            
            # Display results
            if file_vuln_count > 0:
                codebase_results['vulnerable_files'] += 1
                print()
                print_warning(f"{file_vuln_count} vulnerable function(s) found in {rel_path}")
            else:
                codebase_results['safe_files'] += 1
                print()
                print_success(f"No vulnerabilities found in {rel_path}")
        
        except Exception as e:
            print()
            print_error(f"Failed to analyze {rel_path}: {e}")
            codebase_results['file_analyses'].append({
                'file_path': str(file_path),
                'relative_path': str(rel_path),
                'error': str(e)
            })
    
    def _count_file_vulnerabilities(self, file_results: Dict[str, Any]) -> int:
        """Count vulnerabilities in file results"""
        import json
        
        file_vuln_count = 0
        if 'function_analyses' in file_results:
            for func_analysis in file_results['function_analyses']:
                decision = func_analysis['analysis_results'].get('final_decision', '[]')
                # Check if vulnerabilities found
                try:
                    if '```json' in decision:
                        decision = decision.split('```json')[1].split('```')[0]
                    elif '```' in decision:
                        decision = decision.split('```')[1].split('```')[0]
                    verdicts = json.loads(decision)
                    valid_vulns = [v for v in verdicts if isinstance(v, dict) and v.get('decision') == 'valid']
                    if valid_vulns:
                        file_vuln_count += 1
                except:
                    pass
        
        return file_vuln_count

