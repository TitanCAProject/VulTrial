#!/usr/bin/env python3
"""
VulTrial CLI - Compatibility Wrapper

This file provides backward compatibility for code that imports from cli_ui.
All actual UI logic has been moved to app/ui/ for better organization.

**DEPRECATED:** This file will be removed in a future version.
Please import from app.ui instead:
    from app.ui import VulTrialUI, main

To use the new modular UI: Run ./vultrial-ui
"""

# Re-export everything from the new modular UI
from .ui import (
    # Components
    Colors, colored, print_header, print_success, print_error,
    print_info, print_warning, print_divider, print_banner,
    format_file_size, format_duration,
    
    # Core classes
    VulTrialUI,
    KeyboardHandler,
    HistoryManager,
    HelpSystem,
    FileSelector,
    SettingsMenu,
    AnalysisRunner,
    AnalysisPreview,
    ResultsDisplay,
    
    # Main function
    main
)

# Backward compatibility: Allow old import style
VulTrialCLI = VulTrialUI  # Alias for backward compatibility


# Main function for backward compatibility
if __name__ == "__main__":
    main()

