"""
History Manager

Tracks recent analyses for quick re-run
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .constants import UIConstants


class HistoryManager:
    """Manage analysis history for quick access"""
    
    def __init__(self, max_history: int = None):
        """
        Initialize history manager
        
        Args:
            max_history: Maximum number of history entries to keep (default from UIConstants)
        """
        if max_history is None:
            max_history = UIConstants.MAX_HISTORY_ENTRIES
        self.max_history = max_history
        self.history_file = Path(".vultrial") / "history.json"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """Load history from disk"""
        if not self.history_file.exists():
            return []
        
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Warning: History file is corrupted ({e}), starting fresh")
            return []
        except Exception as e:
            print(f"Warning: Could not load history ({e}), starting fresh")
            return []
    
    def _save_history(self):
        """Save history to disk"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save history: {e}")
    
    def add_analysis(
        self,
        file_path: str,
        codebase_path: Optional[str],
        mode: str,
        analysis_mode: str,
        result_summary: str
    ):
        """
        Add an analysis to history
        
        Args:
            file_path: Path to analyzed file
            codebase_path: Path to codebase (if any)
            mode: Analysis mode (function/file/all)
            analysis_mode: detailed or consensus
            result_summary: Brief summary of results
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'file_path': file_path,
            'file_name': Path(file_path).name,
            'codebase_path': codebase_path,
            'codebase_name': Path(codebase_path).name if codebase_path else None,
            'mode': mode,
            'analysis_mode': analysis_mode,
            'summary': result_summary
        }
        
        # Add to beginning of list
        self.history.insert(0, entry)
        
        # Trim to max size
        self.history = self.history[:self.max_history]
        
        # Save
        self._save_history()
    
    def get_recent(self, count: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent analyses
        
        Args:
            count: Number of recent entries to return
        
        Returns:
            List of recent analysis entries
        """
        return self.history[:count]
    
    def get_by_index(self, index: int) -> Optional[Dict[str, Any]]:
        """Get history entry by index"""
        if 0 <= index < len(self.history):
            return self.history[index]
        return None
    
    def clear(self):
        """Clear all history"""
        self.history = []
        self._save_history()
    
    def format_entry(self, entry: Dict[str, Any]) -> str:
        """
        Format history entry for display
        
        Args:
            entry: History entry dictionary
        
        Returns:
            Formatted string
        """
        timestamp = datetime.fromisoformat(entry['timestamp'])
        time_ago = self._time_ago(timestamp)
        
        file_name = entry.get('file_name', 'Unknown')
        summary = entry.get('summary', 'No summary')
        
        return f"{file_name} • {time_ago} • {summary}"
    
    def _time_ago(self, timestamp: datetime) -> str:
        """
        Get human-readable time ago string
        
        Args:
            timestamp: Datetime object
        
        Returns:
            String like "2 hours ago", "yesterday", etc.
        """
        now = datetime.now()
        diff = now - timestamp
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins}min ago" if mins == 1 else f"{mins}mins ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}hr ago" if hours == 1 else f"{hours}hrs ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days}day ago" if days == 1 else f"{days}days ago"
        else:
            return timestamp.strftime("%Y-%m-%d")


