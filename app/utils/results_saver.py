"""
Results Saver

Centralized logic for saving analysis results to JSON and text formats
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


class ResultsSaver:
    """Save analysis results in various formats"""
    
    @staticmethod
    def generate_output_filename(
        file_path: Optional[str] = None,
        codebase_path: Optional[str] = None,
        output_dir: str = "output",
        extension: str = "json"
    ) -> Path:
        """
        Generate timestamped output filename
        
        Args:
            file_path: Path to analyzed file
            codebase_path: Path to codebase
            output_dir: Output directory
            extension: File extension (json or txt)
        
        Returns:
            Path object for output file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if file_path:
            file_name = Path(file_path).stem
        elif codebase_path:
            file_name = f"codebase_{Path(codebase_path).name}"
        else:
            file_name = "analysis"
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        return output_path / f"{file_name}_{timestamp}.{extension}"
    
    @staticmethod
    def prepare_json_data(
        results: Dict[str, Any],
        file_path: Optional[str] = None,
        codebase_path: Optional[str] = None,
        model_type: Optional[str] = None,
        model_id: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        elapsed_time: float = 0,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Prepare comprehensive JSON data structure
        
        Args:
            results: Analysis results from pipeline
            file_path: Path to analyzed file
            codebase_path: Path to codebase
            model_type: Model type (claude, openai, etc.)
            model_id: Specific model ID
            token_usage: Token usage statistics
            elapsed_time: Analysis duration in seconds
            additional_metadata: Any additional metadata to include
        
        Returns:
            Complete data structure ready for JSON serialization
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "file_analyzed": str(file_path) if file_path else None,
            "codebase": str(codebase_path) if codebase_path else None,
            "model": f"{model_type} ({model_id})" if model_type and model_id else "unknown",
            "analysis_results": results,
            "token_usage": token_usage,
            "elapsed_time": elapsed_time
        }
        
        # Add any additional metadata
        if additional_metadata:
            data.update(additional_metadata)
        
        return data
    
    @staticmethod
    def save_json(
        data: Dict[str, Any],
        output_file: Path
    ) -> bool:
        """
        Save data as JSON
        
        Args:
            data: Data to save
            output_file: Path to output file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        
        except Exception as e:
            print(f"Error saving JSON: {e}")
            return False
    
    @staticmethod
    def save_text_summary(
        data: Dict[str, Any],
        output_file: Path
    ) -> bool:
        """
        Save human-readable text summary
        
        Args:
            data: Analysis data (same structure as JSON)
            output_file: Path to output file
        
        Returns:
            True if successful, False otherwise
        """
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("VulTrial Analysis Summary\n")
                f.write("=" * 70 + "\n\n")
                
                f.write(f"Timestamp: {data.get('timestamp', 'N/A')}\n")
                f.write(f"File: {data.get('file_analyzed', 'N/A')}\n")
                f.write(f"Codebase: {data.get('codebase', 'N/A')}\n")
                f.write(f"Model: {data.get('model', 'N/A')}\n\n")
                
                f.write("-" * 70 + "\n")
                f.write("Results:\n")
                f.write("-" * 70 + "\n\n")
                
                # Write results based on analysis type
                results = data.get('analysis_results', {})
                
                if 'file_analyses' in results:
                    # Codebase analysis
                    f.write(f"Analysis Type: Codebase\n")
                    f.write(f"Files Analyzed: {results.get('total_files', 0)}\n")
                    f.write(f"Total Functions: {results.get('total_functions', 0)}\n")
                    f.write(f"Vulnerable Files: {results.get('vulnerable_files', 0)}\n")
                    f.write(f"Vulnerable Functions: {results.get('vulnerable_functions', 0)}\n\n")
                    f.write(str(results.get('summary', 'N/A')))
                
                elif 'function_analyses' in results:
                    # Multi-function file analysis
                    f.write(f"Analysis Type: Multi-Function File\n")
                    f.write(f"Functions Analyzed: {len(results.get('function_analyses', []))}\n\n")
                    f.write(str(results.get('overall_assessment', 'N/A')))
                
                elif 'final_decision' in results:
                    # Single function analysis
                    f.write(f"Analysis Type: Single Function\n\n")
                    f.write(str(results.get('final_decision', 'N/A')))
                
                f.write("\n\n")
                
                # Token usage
                if data.get('token_usage'):
                    usage = data['token_usage']
                    f.write("-" * 70 + "\n")
                    f.write("Token Usage:\n")
                    f.write("-" * 70 + "\n")
                    f.write(f"Input:  {usage.get('input_tokens', 0):,}\n")
                    f.write(f"Output: {usage.get('output_tokens', 0):,}\n")
                    f.write(f"Total:  {usage.get('total_tokens', 0):,}\n")
            
            return True
        
        except Exception as e:
            print(f"Error saving text summary: {e}")
            return False
    
    @staticmethod
    def save_analysis_results(
        results: Dict[str, Any],
        file_path: Optional[str] = None,
        codebase_path: Optional[str] = None,
        model_type: Optional[str] = None,
        model_id: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None,
        elapsed_time: float = 0,
        output_dir: str = "output",
        auto_filename: bool = True,
        output_file: Optional[str] = None,
        also_save_text: bool = False
    ) -> Optional[str]:
        """
        Save analysis results (convenience method)
        
        Args:
            results: Analysis results from pipeline
            file_path: Path to analyzed file
            codebase_path: Path to codebase
            model_type: Model type
            model_id: Model ID
            token_usage: Token usage stats
            elapsed_time: Analysis duration
            output_dir: Output directory
            auto_filename: Generate timestamped filename automatically
            output_file: Specific output file path (overrides auto_filename)
            also_save_text: Also save text summary
        
        Returns:
            Path to saved file, or None if failed
        """
        # Generate filename
        if output_file:
            json_file = Path(output_file)
        elif auto_filename:
            json_file = ResultsSaver.generate_output_filename(
                file_path, codebase_path, output_dir, "json"
            )
        else:
            return None
        
        # Prepare data
        data = ResultsSaver.prepare_json_data(
            results=results,
            file_path=file_path,
            codebase_path=codebase_path,
            model_type=model_type,
            model_id=model_id,
            token_usage=token_usage,
            elapsed_time=elapsed_time
        )
        
        # Save JSON
        if ResultsSaver.save_json(data, json_file):
            # Also save text summary if requested
            if also_save_text:
                text_file = json_file.with_suffix('.txt')
                ResultsSaver.save_text_summary(data, text_file)
            
            return str(json_file)
        
        return None

