"""Knowledge retriever - on-demand CWE/CAPEC search"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional


class KnowledgeRetriever:
    """Retrieves CWE/CAPEC knowledge on-demand via keyword search"""
    
    def __init__(self, knowledge_dir: str = None):
        """
        Initialize knowledge retriever
        
        Args:
            knowledge_dir: Directory containing CWE/CAPEC XML files
        """
        if knowledge_dir is None:
            # Try common locations
            possible_dirs = [
                Path("app/knowledge/raw"),
                Path("knowledge/data/original")
            ]
            for dir_path in possible_dirs:
                if dir_path.exists():
                    knowledge_dir = str(dir_path)
                    break
        
        self.knowledge_dir = Path(knowledge_dir) if knowledge_dir else None
        self.cwe_file = self.knowledge_dir / "cwec_v4.18.xml" if self.knowledge_dir else None
        self.capec_file = self.knowledge_dir / "capec_v3.9.xml" if self.knowledge_dir else None
    
    def search_cwe_by_keywords(self, keywords: List[str], max_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search CWE database by keywords
        
        Args:
            keywords: List of keywords to search (e.g., ["sql", "injection"])
            max_results: Maximum number of CWEs to return
            
        Returns:
            List of matching CWE entries with id, name, description, mitigation
        """
        if not self.cwe_file or not self.cwe_file.exists():
            return []
        
        try:
            # Parse XML
            tree = ET.parse(str(self.cwe_file))
            root = tree.getroot()
            ns = {'cwe': 'http://cwe.mitre.org/cwe-7'}
            
            # Find all weaknesses
            weaknesses = root.findall('.//cwe:Weakness', ns)
            
            matches = []
            keywords_lower = [k.lower() for k in keywords]
            
            for weakness in weaknesses:
                cwe_id = weakness.get('ID', '')
                name = weakness.get('Name', '')
                
                if not cwe_id or not name:
                    continue
                
                # Calculate relevance score
                name_lower = name.lower()
                
                desc_elem = weakness.find('cwe:Description', ns)
                description = desc_elem.text if desc_elem is not None and desc_elem.text else ""
                desc_lower = description.lower()
                
                # Score based on how many keywords match and where
                score = 0
                keyword_matches_in_name = sum(1 for kw in keywords_lower if kw in name_lower)
                keyword_matches_in_desc = sum(1 for kw in keywords_lower if kw in desc_lower)
                
                # Name matches are worth more
                score = keyword_matches_in_name * 10 + keyword_matches_in_desc
                
                # Bonus for matching ALL keywords
                if all(kw in name_lower or kw in desc_lower for kw in keywords_lower):
                    score += 20
                
                if score > 0:
                    # Get extended description
                    ext_desc_elem = weakness.find('cwe:Extended_Description', ns)
                    extended_desc = ext_desc_elem.text if ext_desc_elem is not None and ext_desc_elem.text else ""
                    
                    # Get mitigation
                    mitigation = ""
                    mit_elem = weakness.find('.//cwe:Mitigation/cwe:Description', ns)
                    if mit_elem is not None and mit_elem.text:
                        mitigation = mit_elem.text
                    
                    matches.append({
                        'id': cwe_id,
                        'name': name,
                        'description': description[:600],
                        'extended_description': extended_desc[:400],
                        'mitigation': mitigation[:400],
                        'score': score
                    })
            
            # Sort by score (highest first) and return top results
            matches.sort(key=lambda x: x['score'], reverse=True)
            return matches[:max_results]
            
        except Exception as e:
            print(f"Warning: CWE search failed: {e}")
            return []
    
    def get_cwe_by_id(self, cwe_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific CWE by ID
        
        Args:
            cwe_id: CWE ID (e.g., "89", "79")
            
        Returns:
            CWE entry dict or None
        """
        if not self.cwe_file or not self.cwe_file.exists():
            return None
        
        try:
            tree = ET.parse(str(self.cwe_file))
            root = tree.getroot()
            ns = {'cwe': 'http://cwe.mitre.org/cwe-7'}
            
            # Find specific weakness by ID
            weakness = root.find(f'.//cwe:Weakness[@ID="{cwe_id}"]', ns)
            
            if weakness is None:
                return None
            
            name = weakness.get('Name', '')
            
            desc_elem = weakness.find('cwe:Description', ns)
            description = desc_elem.text if desc_elem is not None and desc_elem.text else ""
            
            ext_desc_elem = weakness.find('cwe:Extended_Description', ns)
            extended_desc = ext_desc_elem.text if ext_desc_elem is not None and ext_desc_elem.text else ""
            
            mitigation = ""
            mit_elem = weakness.find('.//cwe:Mitigation/cwe:Description', ns)
            if mit_elem is not None and mit_elem.text:
                mitigation = mit_elem.text
            
            return {
                'id': cwe_id,
                'name': name,
                'description': description[:600],
                'extended_description': extended_desc[:400],
                'mitigation': mitigation[:400]
            }
            
        except Exception as e:
            print(f"Warning: CWE lookup failed: {e}")
            return None
    
    def format_cwe_for_agent(self, cwe_entries: List[Dict[str, Any]]) -> str:
        """Format CWE entries for agent consumption"""
        if not cwe_entries:
            return ""
        
        formatted = "[CWE KNOWLEDGE BASE]:\n\n"
        
        for i, cwe in enumerate(cwe_entries, 1):
            formatted += f"CWE-{cwe['id']}: {cwe['name']}\n"
            formatted += f"{'─' * 60}\n"
            
            if cwe.get('description'):
                formatted += f"Description:\n{cwe['description']}\n\n"
            
            if cwe.get('extended_description'):
                formatted += f"Details:\n{cwe['extended_description']}\n\n"
            
            if cwe.get('mitigation'):
                formatted += f"Mitigation:\n{cwe['mitigation']}\n\n"
            
            if i < len(cwe_entries):
                formatted += "\n"
        
        return formatted

