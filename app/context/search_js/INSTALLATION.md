# Installation Guide for JavaScript/TypeScript Support

This guide will help you set up the JavaScript/TypeScript search backend for VulTrial.

## Quick Install

### Option 1: With ts-morph (Recommended)

For best results with accurate AST parsing:

```bash
# 1. Install Node.js (if not already installed)
# On macOS:
brew install node

# On Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y nodejs npm

# On Windows:
# Download from https://nodejs.org/

# 2. Install ts-morph
cd app/context/search_js/
npm install

# 3. Verify installation
node --version  # Should show v14.0.0 or higher
npm --version
```

### Option 2: Regex-Only (No Dependencies)

If you prefer not to install Node.js, the backend will automatically use regex-based parsing:

- ✅ **No installation required**
- ✅ Works for most common JavaScript/TypeScript code
- ⚠️ May miss complex syntax or edge cases
- ⚠️ No type information for TypeScript files

## Verification

Test the installation:

```bash
# Run the test suite
cd /path/to/VulTrial
python3 test/test_search_js.py

# Expected output:
# Building JS/TS index with ts-morph...
# Indexed X files, Y classes, Z functions...
# All tests completed!
```

## What Gets Installed

### With ts-morph (Option 1)

```
app/context/search_js/
├── node_modules/          # npm packages (auto-created)
│   └── ts-morph/         # TypeScript compiler wrapper
├── package.json          # npm configuration
├── package-lock.json     # npm lock file (auto-created)
└── tsmorph_bridge.js     # Node.js bridge script
```

**Dependencies:**
- `ts-morph` (v21.0.0+): ~30MB installed size
- Requires Node.js 14+ and npm

### Regex-Only (Option 2)

No additional files or dependencies are created. The backend uses:
- Python standard library only
- Built-in regex patterns for parsing
- No external tools

## Usage After Installation

### In Python Code

```python
from app.context.search_js import JSSearchBackend

# Initialize (works with or without ts-morph)
backend = JSSearchBackend("path/to/js/project")

# Search for vulnerabilities
message, results, success = backend.search_method("eval")
for result in results:
    print(f"Found in {result.file_path}:{result.line_number}")
```

### With VulTrial Pipeline

The backend integrates automatically with VulTrial's language detection:

```bash
# Analyze JavaScript/TypeScript codebase
python -m app.main --codebase path/to/js/project \
                   --file vulnerable.js \
                   --function handleUserInput \
                   --model-type claude \
                   --model-id claude-3-5-sonnet-20241022
```

VulTrial will:
1. Auto-detect JavaScript/TypeScript files
2. Use ts-morph if available, otherwise regex
3. Index all `.js`, `.jsx`, `.ts`, `.tsx` files
4. Enable full search capabilities for agents

## Troubleshooting

### "ts-morph not installed" Warning

This is normal if you chose Option 2 (regex-only). To enable ts-morph:

```bash
cd app/context/search_js/
npm install
```

### "node: command not found"

Install Node.js:
- macOS: `brew install node`
- Ubuntu: `sudo apt-get install nodejs npm`
- Windows: Download from https://nodejs.org/

### "Cannot find module 'ts-morph'"

Reinstall dependencies:

```bash
cd app/context/search_js/
rm -rf node_modules package-lock.json
npm install
```

### Parsing Errors

If files fail to parse:
- Check for syntax errors in source files
- Ensure file encoding is UTF-8
- Backend will automatically fall back to regex parsing

### Performance Issues

For very large codebases (1000+ files):
- Consider filtering files before indexing
- Use specific search queries instead of broad patterns
- Increase system memory if needed

## Uninstallation

To remove ts-morph support:

```bash
cd app/context/search_js/
rm -rf node_modules package-lock.json
```

The backend will automatically fall back to regex parsing.

To completely remove JavaScript/TypeScript support:

```bash
rm -rf app/context/search_js/
```

## Advanced Configuration

### Custom Node.js Path

If Node.js is installed in a non-standard location, you can set the path:

```python
import os
os.environ['NODE_PATH'] = '/custom/path/to/node'

from app.context.search_js import JSSearchBackend
backend = JSSearchBackend("project/")
```

### Disable ts-morph Temporarily

To force regex parsing even when ts-morph is installed:

```python
from app.context.search_js import search_utils

# Temporarily disable ts-morph check
original_check = search_utils.check_tsmorph_available
search_utils.check_tsmorph_available = lambda: False

# Now backend will use regex
backend = JSSearchBackend("project/")

# Restore
search_utils.check_tsmorph_available = original_check
```

## Next Steps

After installation:

1. **Run Tests**: `python3 test/test_search_js.py`
2. **Read Documentation**: `app/context/search_js/README.md`
3. **Try Examples**: Analyze the demo files in `test/demo_code/`
4. **Integrate**: Use with VulTrial's main pipeline

