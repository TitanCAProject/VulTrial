"""Search utilities adapted from reference implementation"""

from .search_utils import (
    find_python_files,
    parse_python_file,
    get_code_snippets,
    get_class_signature,
    get_code_region_around_line,
    get_code_region_containing_code,
)
from .search_backend import SearchBackend
from .data_structures import SearchResult, CallChainResult, TaintPath
from .call_graph import CallGraph
from .taint_analysis import TaintTracker, InterProceduralTaintTracker
from .control_flow import ControlFlowGraph, find_guards_for_call, has_validation_before
from .analysis_utils import (
    extract_variables,
    extract_function_calls,
    build_def_use_chains,
    is_dangerous_sink,
    is_taint_source,
    get_function_parameters,
    find_return_statements,
)

__all__ = [
    'SearchBackend',
    'SearchResult',
    'CallChainResult',
    'TaintPath',
    'CallGraph',
    'TaintTracker',
    'InterProceduralTaintTracker',
    'ControlFlowGraph',
    'find_guards_for_call',
    'has_validation_before',
    'find_python_files',
    'parse_python_file',
    'get_code_snippets',
    'get_class_signature',
    'get_code_region_around_line',
    'get_code_region_containing_code',
    'extract_variables',
    'extract_function_calls',
    'build_def_use_chains',
    'is_dangerous_sink',
    'is_taint_source',
    'get_function_parameters',
    'find_return_statements',
]

