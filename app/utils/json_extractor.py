"""Utility to extract and clean JSON from model responses"""

import json
import re
from typing import Any, Optional


def extract_json(text: str) -> Optional[str]:
    """
    Extract JSON from text that may contain thinking tags, markdown, or extra text
    
    Args:
        text: Raw text from model that should contain JSON
        
    Returns:
        Cleaned JSON string, or None if no valid JSON found
    """
    if not text:
        return None
    
    # Remove <think>...</think> tags and their content
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # Try to extract JSON from markdown code blocks
    if '```json' in text:
        # Extract content between ```json and ```
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    if '```' in text:
        # Extract content between ``` and ``` (no language specified)
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # Try to find JSON array or object in the text
    # Look for [ ... ] or { ... }
    
    # Try to find JSON array
    array_match = re.search(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
    if array_match:
        return array_match.group(0)
    
    # Try to find empty array
    if '[]' in text:
        return '[]'
    
    # Try to find JSON object
    object_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if object_match:
        return object_match.group(0)
    
    # Last resort: return the text as-is
    return text.strip()


def parse_json_safe(text: str) -> Any:
    """
    Safely parse JSON from text, with extraction and cleaning
    
    Args:
        text: Raw text that should contain JSON
        
    Returns:
        Parsed JSON object (dict, list, etc.)
        
    Raises:
        ValueError: If JSON cannot be extracted or parsed
    """
    # Extract JSON from the text
    json_str = extract_json(text)
    
    if json_str is None:
        raise ValueError("No JSON found in response")
    
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def clean_agent_response(response: str, expected_type: str = "array") -> str:
    """
    Clean agent response to extract only the JSON part
    
    Args:
        response: Raw response from agent
        expected_type: 'array' or 'object'
        
    Returns:
        Clean JSON string
    """
    try:
        json_str = extract_json(response)
        
        # Validate it's valid JSON
        parsed = json.loads(json_str)
        
        # Validate expected type
        if expected_type == "array" and not isinstance(parsed, list):
            # Try to wrap in array if it's a single object
            if isinstance(parsed, dict):
                parsed = [parsed]
        elif expected_type == "object" and not isinstance(parsed, dict):
            raise ValueError(f"Expected JSON object but got {type(parsed)}")
        
        # Return cleaned JSON string
        return json.dumps(parsed, ensure_ascii=False)
        
    except Exception as e:
        # If all parsing fails, return empty array or object
        if expected_type == "array":
            return "[]"
        else:
            return "{}"
