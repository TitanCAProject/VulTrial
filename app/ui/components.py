"""
Reusable UI Components

Colors, formatting helpers, and common UI elements
"""

from .constants import UIConstants


# ANSI Color Codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Foreground colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright foreground
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Background colors
    BG_BLACK = '\033[40m'
    BG_BLUE = '\033[44m'
    BG_CYAN = '\033[46m'


def colored(text: str, color: str, bold: bool = False) -> str:
    """Return colored text"""
    prefix = Colors.BOLD if bold else ""
    return f"{prefix}{color}{text}{Colors.RESET}"


def print_header(text: str, color: str = Colors.BRIGHT_CYAN):
    """Print a header"""
    print(f"\n{colored('▊', color)} {colored(text, color, bold=True)}")


def print_success(text: str):
    """Print success message"""
    print(f"  {colored('✓', Colors.BRIGHT_GREEN)} {text}")


def print_error(text: str):
    """Print error message"""
    print(f"  {colored('✗', Colors.BRIGHT_RED)} {text}")


def print_info(text: str):
    """Print info message"""
    print(f"  {colored('ℹ', Colors.BRIGHT_BLUE)} {text}")


def print_warning(text: str):
    """Print warning message"""
    print(f"  {colored('⚠', Colors.BRIGHT_YELLOW)} {text}")


def print_divider(char: str = "─", length: int = None, color: str = Colors.BRIGHT_BLACK):
    """Print a divider line"""
    if length is None:
        length = UIConstants.DIVIDER_WIDTH
    print(colored(char * length, color))


def print_banner(version: str = None):
    """Print welcome banner"""
    if version is None:
        version = UIConstants.VERSION
    print("\n")
    banner_width = UIConstants.HEADER_WIDTH
    print(colored("╔" + "═"*banner_width + "╗", Colors.BRIGHT_CYAN, bold=True))
    print(colored("║", Colors.BRIGHT_CYAN, bold=True) + colored(" "*23 + f"VulTrial v{version}" + " "*38, Colors.BRIGHT_WHITE, bold=True) + colored("║", Colors.BRIGHT_CYAN, bold=True))
    print(colored("║", Colors.BRIGHT_CYAN, bold=True) + colored(" "*13 + "AI-Powered Vulnerability Detection Framework" + " "*19, Colors.BRIGHT_BLACK) + colored("║", Colors.BRIGHT_CYAN, bold=True))
    print(colored("╚" + "═"*banner_width + "╝", Colors.BRIGHT_CYAN, bold=True))
    print()


def format_file_size(bytes_size: int) -> str:
    """Format file size in human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins}m {secs}s"
    else:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"


