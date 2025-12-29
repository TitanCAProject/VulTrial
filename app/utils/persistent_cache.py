"""Persistent cache for file summaries across sessions"""

import json
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any


class PersistentCache:
    """Disk-based cache with hash-based invalidation"""
    
    def __init__(self, cache_name: str = "file_summaries"):
        """
        Initialize persistent cache
        
        Args:
            cache_name: Name of the cache (creates separate file)
        """
        self.cache_dir = Path(".vultrial") / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_file = self.cache_dir / f"{cache_name}.json"
        self.cache_data = self._load_cache()
    
    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from disk"""
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            # Corrupted cache, start fresh
            return {}
    
    def _save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, indent=2)
        except Exception as e:
            # Don't fail if can't save cache
            print(f"Warning: Could not save cache: {e}")
    
    def _hash_file_content(self, file_path: str) -> Optional[str]:
        """
        Generate hash of file content for cache invalidation
        
        Args:
            file_path: Path to file
            
        Returns:
            MD5 hash of file content, or None if file can't be read
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.md5(content).hexdigest()
        except Exception:
            return None
    
    def get(self, file_path: str) -> Optional[str]:
        """
        Get cached summary for a file
        
        Args:
            file_path: Path to file
            
        Returns:
            Cached summary if valid, None otherwise
        """
        # Get current file hash
        current_hash = self._hash_file_content(file_path)
        if not current_hash:
            return None
        
        # Check if we have a cache entry
        cache_key = str(Path(file_path).absolute())
        if cache_key not in self.cache_data:
            return None
        
        entry = self.cache_data[cache_key]
        
        # Validate hash (cache invalidation)
        if entry.get('hash') != current_hash:
            # File changed, cache invalid
            return None
        
        # Return cached summary
        return entry.get('summary')
    
    def set(self, file_path: str, summary: str):
        """
        Cache a file summary
        
        Args:
            file_path: Path to file
            summary: Summary to cache
        """
        # Get file hash
        file_hash = self._hash_file_content(file_path)
        if not file_hash:
            return
        
        # Store in cache
        cache_key = str(Path(file_path).absolute())
        self.cache_data[cache_key] = {
            'hash': file_hash,
            'summary': summary,
            'file_name': Path(file_path).name
        }
        
        # Save to disk
        self._save_cache()
    
    def clear(self):
        """Clear all cache"""
        self.cache_data = {}
        self._save_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'total_entries': len(self.cache_data),
            'cache_file': str(self.cache_file),
            'cache_size_kb': self.cache_file.stat().st_size / 1024 if self.cache_file.exists() else 0
        }


