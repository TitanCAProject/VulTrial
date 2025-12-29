"""Path utility helpers for UI modules."""

from pathlib import Path
from typing import Optional
import os

from .components import colored, Colors, print_error, print_info


def normalize_path(path: str, *, show_feedback: bool = True) -> str:
    """Normalize user-provided paths (handles drag-and-drop, quotes, etc.)."""
    if path is None:
        return ""

    original_path = path
    path = path.strip()

    if not path:
        return path

    was_quoted = False
    had_escaped_spaces = False
    had_tilde = False
    had_env_vars = False

    if (path.startswith('"') and path.endswith('"')) or (
        path.startswith("'") and path.endswith("'")
    ):
        path = path[1:-1]
        was_quoted = True

    if path.startswith('~'):
        path = os.path.expanduser(path)
        had_tilde = True

    expanded = os.path.expandvars(path)
    if expanded != path:
        path = expanded
        had_env_vars = True

    if '\\ ' in path:
        path = path.replace('\\ ', ' ')
        had_escaped_spaces = True

    if path.endswith('/') and len(path) > 1:
        path = path.rstrip('/')

    if show_feedback and (
        was_quoted or had_escaped_spaces or had_tilde or had_env_vars or path != original_path
    ):
        print(f"  {colored('✓', Colors.BRIGHT_GREEN)} Normalized: {colored(path, Colors.BRIGHT_CYAN)}")

    return path


def resolve_directory(
    path: str,
    *,
    must_exist: bool = True,
    create: bool = False,
    show_feedback: bool = True
) -> Optional[Path]:
    """Resolve a directory path with optional creation and validation."""

    if not path:
        return None

    normalized = normalize_path(path, show_feedback=show_feedback)
    if not normalized:
        return None

    path_obj = Path(normalized).expanduser()

    existed_before = path_obj.exists()

    if create:
        try:
            path_obj.mkdir(parents=True, exist_ok=True)
            if show_feedback:
                status = "Created" if not existed_before else "Directory ready"
                print(f"  {colored('✓', Colors.BRIGHT_GREEN)} {status}: {colored(str(path_obj), Colors.BRIGHT_CYAN)}")
        except Exception as exc:
            if show_feedback:
                print(f"  {colored('✗', Colors.BRIGHT_RED)} Failed to create directory: {colored(str(exc), Colors.BRIGHT_RED)}")
            return None

    if must_exist and not path_obj.exists():
        if show_feedback:
            print_error("Path does not exist!")
            print_info("Please check the path and try again")
        return None

    if path_obj.exists() and not path_obj.is_dir():
        if show_feedback:
            print_error("Path is not a directory!")
            print_info("Please provide a directory path")
        return None

    try:
        resolved = path_obj.resolve()
    except Exception:
        resolved = path_obj.absolute()

    if show_feedback:
        print_info(f"Resolved path: {colored(str(resolved), Colors.BRIGHT_CYAN)}")

    return resolved


