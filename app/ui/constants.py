"""
UI Constants

Centralized constants for consistent UI behavior
"""


class UIConstants:
    """UI-wide constants"""
    
    # Display dimensions
    DIVIDER_WIDTH = 70
    HEADER_WIDTH = 76
    
    # Pagination
    DEFAULT_PAGE_SIZE = 20
    MIN_PAGE_SIZE = 5
    MAX_PAGE_SIZE = 50
    
    # Path display
    MAX_PATH_DISPLAY = 50
    
    # Timeouts
    DEFAULT_TIMEOUT = 30
    FILE_OPERATION_TIMEOUT = 10
    
    # File browsing
    SUPPORTED_EXTENSIONS = {'.py', '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.java'}
    
    # Progress display
    SPINNER_FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    
    # Analysis defaults
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 32000
    DEFAULT_MAX_TURNS = 4
    
    # Evidence management defaults
    MAX_EVIDENCE_ITEMS = 5
    MAX_EVIDENCE_TOKENS_PER_ITEM = 1000
    MAX_EVIDENCE_LINES_PER_ITEM = 100
    EVIDENCE_TOTAL_TOKEN_BUDGET = 4000
    
    # History compression
    MAX_HISTORY_ENTRIES = 10
    HISTORY_COMPRESSION_START_TURN = 3
    
    # Auto-save
    RESULTS_DIR = "output"
    LOG_DIR = "output/logs"
    
    # Version
    VERSION = "0.4.1"


class ModelDefaults:
    """Default model IDs for each provider"""
    
    DEFAULT_MODEL_IDS = {
        'claude': 'claude-3-5-sonnet-20241022',
        'openai': 'gpt-4o',
        'grok': 'grok-2-1212',
        'gemini': 'gemini-1.5-pro',
    }
    
    # For backward compatibility with CLI
    CLI_DEFAULT_MODEL_IDS = {
        'openai': 'gpt-4',
        'claude': 'claude-3-5-sonnet-20241022',
        'gemini': 'gemini-1.5-pro',
        'grok': 'grok-beta',
    }
    
    @classmethod
    def get_default_model_id(cls, model_type: str, for_cli: bool = False) -> str:
        """Get default model ID for a provider"""
        if for_cli:
            return cls.CLI_DEFAULT_MODEL_IDS.get(model_type, cls.DEFAULT_MODEL_IDS.get(model_type, ''))
        return cls.DEFAULT_MODEL_IDS.get(model_type, '')


class FileIcons:
    """File type icons for display"""
    
    PYTHON = "🐍"
    C_CPP = "⚙️ "
    JAVA = "☕"
    HEADER = "📃"
    DEFAULT = "📄"
    FOLDER = "📁"
    
    @classmethod
    def get_icon(cls, filename: str) -> str:
        """Get icon for file type"""
        if filename.endswith('.py'):
            return cls.PYTHON
        elif filename.endswith(('.c', '.cpp', '.cc', '.cxx')):
            return cls.C_CPP
        elif filename.endswith(('.h', '.hpp')):
            return cls.HEADER
        elif filename.endswith('.java'):
            return cls.JAVA
        else:
            return cls.DEFAULT


class NavigationKeys:
    """Standard navigation keys"""
    
    NEXT = 'n'
    PREVIOUS = 'p'
    BACK = 'b'
    QUIT = 'q'
    HELP = '?'
    CONFIRM = 'y'
    CANCEL = 'n'

