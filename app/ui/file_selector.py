"""File Selector

Handles file browsing, codebase scanning, and file selection.
"""

from pathlib import Path
from typing import Optional, List, Tuple

from .components import colored, Colors, print_header, print_success, print_error, print_info, print_divider
from .keyboard_handler import KeyboardHandler
from .constants import UIConstants, FileIcons
from .path_utils import normalize_path, resolve_directory


class FileSelector:
    """File browsing and selection with search capability"""
    
    @staticmethod
    def select_codebase() -> Optional[str]:
        """
        Prompt user to select a codebase
        
        Returns:
            Path to codebase, or None if cancelled
        """
        print_header("Set Codebase", Colors.BRIGHT_CYAN)
        print()
        print(colored("  💡 Tip: You can drag & drop a folder here!", Colors.BRIGHT_GREEN))
        print()
        print(colored("  Examples:", Colors.BRIGHT_BLACK))
        print(colored("    • data/demo-py", Colors.DIM))
        print(colored("    • ~/projects/mycode", Colors.DIM))
        print()
        
        path_input = input(colored("  Enter path or drag folder: ", Colors.BRIGHT_WHITE)).strip()
        if not path_input:
            return None
        
        path_obj = resolve_directory(path_input, must_exist=True, create=False, show_feedback=True)
        if not path_obj:
            print_info("Tip: You can drag & drop folders directly into the terminal")
            return None
        
        # Scan codebase
        print(f"\n  {colored('⟳', Colors.BRIGHT_YELLOW)} Scanning codebase...", end='', flush=True)
        
        py_files = len(list(path_obj.rglob('*.py')))
        c_files = len(list(path_obj.rglob('*.c'))) + len(list(path_obj.rglob('*.cpp')))
        java_files = len(list(path_obj.rglob('*.java')))
        
        print("\r" + " "*50 + "\r", end='')  # Clear line
        
        code_type = "Python" if py_files > max(c_files, java_files) else ("Java" if java_files > c_files else "C/C++")
        
        print_success(f"Codebase: {colored(path_obj.name, Colors.BRIGHT_WHITE)}")
        print_success(f"Detected: {colored(code_type, Colors.BRIGHT_MAGENTA, bold=True)} " +
                     f"({py_files} Python, {c_files} C/C++, {java_files} Java files)")
        
        return str(path_obj)
    
    @staticmethod
    def browse_files(codebase_path: str, page_size: int = None) -> Optional[str]:
        """
        Browse files in codebase with pagination
        
        Args:
            codebase_path: Path to codebase
            page_size: Files per page (default from UIConstants)
        
        Returns:
            Selected file path, or None if cancelled
        """
        if page_size is None:
            page_size = UIConstants.DEFAULT_PAGE_SIZE
            
        codebase = Path(codebase_path)
        
        print()
        print(f"  {colored('⟳', Colors.BRIGHT_YELLOW)} Scanning for source files...", end='', flush=True)
        
        # Find all source files
        file_extensions = UIConstants.SUPPORTED_EXTENSIONS
        all_files = []
        for ext in file_extensions:
            all_files.extend(codebase.rglob(f'*{ext}'))
        
        # Filter and sort
        source_files = []
        for f in all_files:
            rel_path = f.relative_to(codebase)
            path_str = str(rel_path)
            # Skip test files and __pycache__
            if 'test' not in path_str.lower() and '__pycache__' not in path_str:
                source_files.append((path_str, f))
        
        source_files.sort()
        
        print("\r" + " "*50 + "\r", end='')  # Clear line
        
        if not source_files:
            print_error("No source files found in codebase")
            return None
        
        # Pagination
        current_page = 0
        total_pages = (len(source_files) + page_size - 1) // page_size
        
        while True:
            try:
                # Show current page
                start_idx = current_page * page_size
                end_idx = min(start_idx + page_size, len(source_files))
                
                print()
                print(colored(f"  Files in {codebase.name} (Page {current_page + 1}/{total_pages}):", Colors.BRIGHT_WHITE))
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                
                for i, (rel_path, abs_path) in enumerate(source_files[start_idx:end_idx], start=start_idx + 1):
                    # Icon and color by file type
                    icon = FileIcons.get_icon(rel_path)
                    
                    if rel_path.endswith('.py'):
                        color = Colors.BRIGHT_BLUE
                    elif rel_path.endswith(('.c', '.cpp', '.cc', '.h', '.hpp')):
                        color = Colors.BRIGHT_CYAN
                    elif rel_path.endswith('.java'):
                        color = Colors.BRIGHT_YELLOW
                    else:
                        color = Colors.BRIGHT_WHITE
                    
                    print(f"  {colored(f'{i:2d}', Colors.BRIGHT_CYAN)}. {icon} {colored(rel_path, color)}")
                
                print_divider("─", 70, Colors.BRIGHT_BLACK)
                
                # Navigation
                options = []
                if current_page > 0:
                    options.append(f"{colored('P', Colors.BRIGHT_CYAN)}=prev")
                if current_page < total_pages - 1:
                    options.append(f"{colored('N', Colors.BRIGHT_CYAN)}=next")
                options.append(f"{colored('B', Colors.BRIGHT_CYAN)}=back")
                
                nav_hint = " | ".join(options)
                print(f"\n  Enter number to select, or {nav_hint}")
                print(colored("  (Press Ctrl+C to cancel)", Colors.DIM))
                
                selection = input(colored("  > ", Colors.BRIGHT_CYAN)).strip().lower()
            
            except KeyboardInterrupt:
                print("\n")
                print_info("File selection cancelled")
                print()
                return None
            
            if selection in ['b', 'back']:
                return None
            elif selection in ['n', 'next'] and current_page < total_pages - 1:
                current_page += 1
            elif selection in ['p', 'prev'] and current_page > 0:
                current_page -= 1
            else:
                # Try to parse as number
                try:
                    file_num = int(selection)
                    if 1 <= file_num <= len(source_files):
                        selected_rel_path, selected_abs_path = source_files[file_num - 1]
                        print()
                        print_success(f"Selected: {colored(selected_rel_path, Colors.BRIGHT_CYAN)}")
                        return str(selected_abs_path)
                    else:
                        print_error(f"Invalid selection. Please enter a number between 1 and {len(source_files)}")
                        print_info(f"Tip: Use 'N' for next page, 'P' for previous, or 'B' to go back")
                        import time
                        time.sleep(1.5)
                except ValueError:
                    print_error(f"'{selection}' is not a valid option")
                    print_info(f"Enter a file number (1-{len(source_files)}), N (next), P (previous), or B (back)")
                    import time
                    time.sleep(1.5)
    
    @staticmethod
    def select_file(codebase_path: Optional[str] = None) -> Optional[str]:
        """
        Select a file to analyze
        
        Args:
            codebase_path: Optional codebase path (enables browsing)
        
        Returns:
            Path to selected file, or None if cancelled
        """
        print_header("Set File to Analyze", Colors.BRIGHT_CYAN)
        print()
        
        if codebase_path:
            print_info(f"Codebase: {colored(Path(codebase_path).name, Colors.BRIGHT_WHITE)}")
            print()
            print(colored("  Options:", Colors.BRIGHT_WHITE))
            print(f"  {colored('1', Colors.BRIGHT_CYAN)}. Browse files in codebase")
            print(f"  {colored('2', Colors.BRIGHT_CYAN)}. Enter path manually")
            print()
            
            choice = KeyboardHandler.get_input("Select option (1-2)", "1")
            
            if choice == "1":
                return FileSelector.browse_files(codebase_path)
            else:
                file_path = input(colored("  Enter file path: ", Colors.BRIGHT_WHITE)).strip()
                if file_path:
                    normalized_path = normalize_path(file_path)
                    # Validate file exists
                    if normalized_path and Path(normalized_path).exists():
                        print()
                        print_success(f"File found: {colored(Path(normalized_path).name, Colors.BRIGHT_CYAN)}")
                        return normalized_path
                    else:
                        print()
                        print_error("File not found!")
                        print_info("Please provide a valid file path")
                        return None
                return None
        else:
            # No codebase - manual entry
            print(colored("  💡 Tip: Drag & drop a file here!", Colors.BRIGHT_GREEN))
            print()
            file_path = input(colored("  Enter path or drag file: ", Colors.BRIGHT_WHITE)).strip()
            if file_path:
                normalized_path = normalize_path(file_path)
                # Validate file exists
                if normalized_path and Path(normalized_path).exists():
                    print()
                    print_info(f"File: {colored(Path(normalized_path).name, Colors.BRIGHT_CYAN)}")
                    print_info(f"Full path: {colored(normalized_path, Colors.DIM)}")
                    return normalized_path
                else:
                    print()
                    print_error("File not found!")
                    print_info("Please check the path and try again")
                    return None
            return None

